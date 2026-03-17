import pytest
from anip_service import ANIPService, Capability, InvocationContext, ANIPError
from anip_core import CapabilityDeclaration, CapabilityInput, CapabilityOutput, SideEffect, SideEffectType


def _test_cap(name: str = "greet", scope: list[str] | None = None) -> Capability:
    return Capability(
        declaration=CapabilityDeclaration(
            name=name,
            description="Say hello",
            contract_version="1.0",
            inputs=[CapabilityInput(name="name", type="string", required=True, description="Who to greet")],
            output=CapabilityOutput(type="object", fields=["message"]),
            side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
            minimum_scope=scope or ["greet"],
        ),
        handler=lambda ctx, params: {"message": f"Hello, {params['name']}!"},
    )


class TestANIPServiceInit:
    def test_minimal_construction(self):
        service = ANIPService(
            service_id="test-service",
            capabilities=[_test_cap()],
            storage=":memory:",
        )
        assert service._service_id == "test-service"
        assert "greet" in service._capabilities

    def test_manifest_built_from_capabilities(self):
        service = ANIPService(
            service_id="test-service",
            capabilities=[_test_cap()],
            storage=":memory:",
        )
        manifest = service.get_manifest()
        assert "greet" in manifest.capabilities

    def test_discovery_document(self):
        service = ANIPService(
            service_id="test-service",
            capabilities=[_test_cap()],
            storage=":memory:",
        )
        disc = service.get_discovery(base_url="https://test.example.com")
        ad = disc["anip_discovery"]

        # Required fields per SPEC.md §6.1
        assert ad["protocol"] == "anip/0.8"
        assert ad["compliance"] == "anip-compliant"
        assert ad["base_url"] == "https://test.example.com"
        assert ad["profile"]["core"] == "1.0"
        assert ad["auth"]["delegation_token_required"] is True
        assert ad["auth"]["minimum_scope_for_discovery"] == "none"

        # Capability summary shape
        greet = ad["capabilities"]["greet"]
        assert greet["description"] == "Say hello"
        assert greet["side_effect"] == "read"
        assert greet["minimum_scope"] == ["greet"]
        assert greet["financial"] is False
        assert greet["contract"] == "1.0"
        assert "contract_version" not in greet

        # Trust and endpoints — only actually implemented endpoints
        assert ad["trust_level"] == "signed"
        assert ad["endpoints"]["manifest"] == "/anip/manifest"
        assert ad["endpoints"]["permissions"] == "/anip/permissions"
        assert ad["endpoints"]["invoke"] == "/anip/invoke/{capability}"
        assert ad["endpoints"]["tokens"] == "/anip/tokens"
        assert ad["endpoints"]["audit"] == "/anip/audit"
        assert ad["endpoints"]["checkpoints"] == "/anip/checkpoints"
        assert "handshake" not in ad["endpoints"]  # not implemented

    def test_discovery_omits_base_url_when_not_passed(self):
        service = ANIPService(
            service_id="test-service",
            capabilities=[_test_cap()],
            storage=":memory:",
        )
        disc = service.get_discovery()
        assert "base_url" not in disc["anip_discovery"]

    def test_jwks_available(self):
        service = ANIPService(
            service_id="test-service",
            capabilities=[_test_cap()],
            storage=":memory:",
        )
        jwks = service.get_jwks()
        assert "keys" in jwks

    def test_attested_trust_rejected(self):
        with pytest.raises(ValueError, match="not yet supported"):
            ANIPService(
                service_id="test-service",
                capabilities=[_test_cap()],
                storage=":memory:",
                trust="attested",
            )

    def test_sqlite_storage_string(self, tmp_path):
        db = tmp_path / "test.db"
        service = ANIPService(
            service_id="test-service",
            capabilities=[_test_cap()],
            storage=f"sqlite:///{db}",
        )
        assert service._storage is not None

    def test_discovery_includes_posture(self):
        service = ANIPService(
            service_id="test-service",
            capabilities=[_test_cap()],
            storage=":memory:",
        )
        disc = service.get_discovery()
        posture = disc["anip_discovery"]["posture"]
        assert posture["audit"]["enabled"] is True
        assert posture["audit"]["signed"] is True
        assert posture["audit"]["queryable"] is True
        assert posture["lineage"]["invocation_id"] is True
        assert posture["lineage"]["client_reference_id"]["supported"] is True
        assert posture["lineage"]["client_reference_id"]["max_length"] == 256
        assert posture["metadata_policy"]["bounded_lineage"] is True
        assert posture["metadata_policy"]["freeform_context"] is False
        assert posture["failure_disclosure"]["detail_level"] == "redacted"
        assert posture["anchoring"]["enabled"] is False
        assert posture["anchoring"]["proofs_available"] is False

    def test_discovery_posture_anchored_with_policy(self):
        from anip_server import LocalFileSink, CheckpointPolicy
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            service = ANIPService(
                service_id="test-service",
                capabilities=[_test_cap()],
                storage=":memory:",
                trust={
                    "level": "anchored",
                    "anchoring": {
                        "cadence": "PT30S",
                        "max_lag": 120,
                        "sinks": [LocalFileSink(directory=tmpdir)],
                    },
                },
                checkpoint_policy=CheckpointPolicy(entry_count=100),
            )
            disc = service.get_discovery()
            posture = disc["anip_discovery"]["posture"]
            assert posture["anchoring"]["enabled"] is True
            assert posture["anchoring"]["cadence"] == "PT30S"
            assert posture["anchoring"]["max_lag"] == 120
            assert posture["anchoring"]["proofs_available"] is True

    def test_discovery_posture_anchored_without_policy(self):
        """Anchored trust without checkpoint policy — proofs NOT available."""
        service = ANIPService(
            service_id="test-service",
            capabilities=[_test_cap()],
            storage=":memory:",
            trust={"level": "anchored", "anchoring": {"cadence": "PT30S", "max_lag": 120}},
        )
        disc = service.get_discovery()
        posture = disc["anip_discovery"]["posture"]
        assert posture["anchoring"]["enabled"] is True
        assert posture["anchoring"]["proofs_available"] is False


class TestANIPServiceInvoke:
    def _make_service(self, caps=None):
        return ANIPService(
            service_id="test-service",
            capabilities=caps or [_test_cap()],
            storage=":memory:",
        )

    async def _issue_test_token(self, service, scope=None, capability=None):
        """Helper to issue a root token for testing."""
        cap = capability or "greet"
        result = await service._engine.issue_root_token(
            authenticated_principal="human:test@example.com",
            subject="human:test@example.com",
            scope=scope or ["greet"],
            capability=cap,
            purpose_parameters={"task_id": "test"},
            ttl_hours=1,
        )
        token, token_id = result
        return token

    async def test_invoke_unknown_capability(self):
        service = self._make_service()
        token = await self._issue_test_token(service)
        result = await service.invoke("nonexistent", token, {})
        assert result["success"] is False
        assert result["failure"]["type"] == "unknown_capability"

    async def test_invoke_success(self):
        service = self._make_service()
        token = await self._issue_test_token(service)
        result = await service.invoke("greet", token, {"name": "World"})
        assert result["success"] is True
        assert result["result"]["message"] == "Hello, World!"

    async def test_invoke_with_async_handler(self):
        """Test that async handlers are properly awaited."""
        async def async_handler(ctx, params):
            return {"message": f"Async hello, {params['name']}!"}

        cap = Capability(
            declaration=CapabilityDeclaration(
                name="async_greet",
                description="Say hello asynchronously",
                contract_version="1.0",
                inputs=[CapabilityInput(name="name", type="string", required=True, description="Who to greet")],
                output=CapabilityOutput(type="object", fields=["message"]),
                side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
                minimum_scope=["greet"],
            ),
            handler=async_handler,
        )
        service = self._make_service(caps=[cap])
        token = await self._issue_test_token(service, scope=["greet"], capability="async_greet")
        result = await service.invoke("async_greet", token, {"name": "World"})
        assert result["success"] is True
        assert result["result"]["message"] == "Async hello, World!"

    async def test_invoke_handler_anip_error(self):
        def failing_handler(ctx, params):
            raise ANIPError("not_found", "Thing not found")

        cap = Capability(
            declaration=CapabilityDeclaration(
                name="fail_cap",
                description="Always fails",
                contract_version="1.0",
                inputs=[],
                output=CapabilityOutput(type="object", fields=[]),
                side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
                minimum_scope=["test"],
            ),
            handler=failing_handler,
        )
        service = self._make_service(caps=[cap])
        token = await self._issue_test_token(service, scope=["test"], capability="fail_cap")
        result = await service.invoke("fail_cap", token, {})
        assert result["success"] is False
        assert result["failure"]["type"] == "not_found"

    async def test_invoke_handler_unexpected_error(self):
        def crashing_handler(ctx, params):
            raise RuntimeError("boom")

        cap = Capability(
            declaration=CapabilityDeclaration(
                name="crash_cap",
                description="Crashes",
                contract_version="1.0",
                inputs=[],
                output=CapabilityOutput(type="object", fields=[]),
                side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
                minimum_scope=["test"],
            ),
            handler=crashing_handler,
        )
        service = self._make_service(caps=[cap])
        token = await self._issue_test_token(service, scope=["test"], capability="crash_cap")
        result = await service.invoke("crash_cap", token, {})
        assert result["success"] is False
        assert result["failure"]["type"] == "internal_error"
        # Detail should NOT leak the actual exception
        assert "boom" not in result["failure"]["detail"]

    async def test_invoke_cost_tracking(self):
        def handler_with_cost(ctx, params):
            ctx.set_cost_actual({"financial": {"amount": 450.0, "currency": "USD"}})
            return {"booked": True}

        cap = Capability(
            declaration=CapabilityDeclaration(
                name="cost_cap",
                description="Tracks cost",
                contract_version="1.0",
                inputs=[],
                output=CapabilityOutput(type="object", fields=[]),
                side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
                minimum_scope=["test"],
            ),
            handler=handler_with_cost,
        )
        service = self._make_service(caps=[cap])
        token = await self._issue_test_token(service, scope=["test"], capability="cost_cap")
        result = await service.invoke("cost_cap", token, {})
        assert result["success"] is True
        assert result["cost_actual"]["financial"]["amount"] == 450.0

    async def test_invoke_response_includes_invocation_id(self):
        service = self._make_service()
        token = await self._issue_test_token(service)
        result = await service.invoke("greet", token, {"name": "World"})
        assert result["success"] is True
        assert "invocation_id" in result
        assert result["invocation_id"].startswith("inv-")
        assert len(result["invocation_id"]) == 16  # "inv-" + 12 hex

    async def test_invoke_response_echoes_client_reference_id(self):
        service = self._make_service()
        token = await self._issue_test_token(service)
        result = await service.invoke(
            "greet", token, {"name": "World"},
            client_reference_id="task:42",
        )
        assert result["client_reference_id"] == "task:42"

    async def test_invoke_response_client_reference_id_null_when_absent(self):
        service = self._make_service()
        token = await self._issue_test_token(service)
        result = await service.invoke("greet", token, {"name": "World"})
        assert result["client_reference_id"] is None

    async def test_invoke_failure_still_has_invocation_id(self):
        service = self._make_service()
        token = await self._issue_test_token(service)
        result = await service.invoke("nonexistent", token, {})
        assert result["success"] is False
        assert "invocation_id" in result
        assert result["invocation_id"].startswith("inv-")

    async def test_invocation_context_has_lineage(self):
        """Handler should see invocation_id and client_reference_id in context."""
        captured_ctx = {}

        def capturing_handler(ctx, params):
            captured_ctx["invocation_id"] = ctx.invocation_id
            captured_ctx["client_reference_id"] = ctx.client_reference_id
            return {"ok": True}

        from anip_core import CapabilityDeclaration, CapabilityOutput, SideEffect, SideEffectType
        from anip_service import Capability
        cap = Capability(
            declaration=CapabilityDeclaration(
                name="ctx_cap",
                description="Captures context",
                contract_version="1.0",
                inputs=[],
                output=CapabilityOutput(type="object", fields=[]),
                side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
                minimum_scope=["test"],
            ),
            handler=capturing_handler,
        )
        service = self._make_service(caps=[cap])
        token = await self._issue_test_token(service, scope=["test"], capability="ctx_cap")
        result = await service.invoke("ctx_cap", token, {}, client_reference_id="ref-abc")
        assert captured_ctx["invocation_id"].startswith("inv-")
        assert captured_ctx["client_reference_id"] == "ref-abc"


class TestANIPServiceClassification:
    """Verify that invoke() stores event_class, retention_tier, and expires_at in audit."""

    def _make_service(self, caps=None):
        return ANIPService(
            service_id="test-service",
            capabilities=caps or [_test_cap()],
            storage=":memory:",
        )

    async def _issue_test_token(self, service, scope=None, capability=None):
        cap = capability or "greet"
        result = await service._engine.issue_root_token(
            authenticated_principal="human:test@example.com",
            subject="human:test@example.com",
            scope=scope or ["greet"],
            capability=cap,
            purpose_parameters={"task_id": "test"},
            ttl_hours=1,
        )
        token, token_id = result
        return token

    async def test_successful_read_stores_low_risk_success(self):
        service = self._make_service()
        token = await self._issue_test_token(service)
        result = await service.invoke("greet", token, {"name": "World"})
        assert result["success"] is True

        audit_result = await service.query_audit(token)
        entries = audit_result["entries"]
        assert len(entries) >= 1
        entry = entries[0]
        assert entry["event_class"] == "low_risk_success"
        assert entry["retention_tier"] == "short"
        assert entry["expires_at"] is not None

    async def test_failed_invocation_stores_event_class(self):
        def failing_handler(ctx, params):
            raise ANIPError("not_found", "Thing not found")

        cap = Capability(
            declaration=CapabilityDeclaration(
                name="fail_cap",
                description="Always fails",
                contract_version="1.0",
                inputs=[],
                output=CapabilityOutput(type="object", fields=[]),
                side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
                minimum_scope=["test"],
            ),
            handler=failing_handler,
        )
        service = self._make_service(caps=[cap])
        token = await self._issue_test_token(service, scope=["test"], capability="fail_cap")
        result = await service.invoke("fail_cap", token, {})
        assert result["success"] is False

        audit_result = await service.query_audit(token)
        entries = audit_result["entries"]
        assert len(entries) >= 1
        entry = entries[0]
        # "not_found" is not in MALFORMED_FAILURE_TYPES, so it's high_risk_denial
        assert entry["event_class"] == "high_risk_denial"
        assert entry["retention_tier"] == "medium"
        assert entry["expires_at"] is not None

    async def test_internal_error_stores_malformed_or_spam(self):
        def crashing_handler(ctx, params):
            raise RuntimeError("boom")

        cap = Capability(
            declaration=CapabilityDeclaration(
                name="crash_cap",
                description="Crashes",
                contract_version="1.0",
                inputs=[],
                output=CapabilityOutput(type="object", fields=[]),
                side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
                minimum_scope=["test"],
            ),
            handler=crashing_handler,
        )
        service = self._make_service(caps=[cap])
        token = await self._issue_test_token(service, scope=["test"], capability="crash_cap")
        result = await service.invoke("crash_cap", token, {})
        assert result["success"] is False

        audit_result = await service.query_audit(token)
        entries = audit_result["entries"]
        assert len(entries) >= 1
        entry = entries[0]
        # "internal_error" IS in MALFORMED_FAILURE_TYPES
        assert entry["event_class"] == "malformed_or_spam"
        assert entry["retention_tier"] == "short"
        assert entry["expires_at"] is not None

    async def test_write_capability_success_stores_high_risk(self):
        cap = Capability(
            declaration=CapabilityDeclaration(
                name="write_cap",
                description="A write capability",
                contract_version="1.0",
                inputs=[],
                output=CapabilityOutput(type="object", fields=[]),
                side_effect=SideEffect(type=SideEffectType.WRITE, rollback_window="PT1H"),
                minimum_scope=["write"],
            ),
            handler=lambda ctx, params: {"written": True},
        )
        service = self._make_service(caps=[cap])
        token = await self._issue_test_token(service, scope=["write"], capability="write_cap")
        result = await service.invoke("write_cap", token, {})
        assert result["success"] is True

        audit_result = await service.query_audit(token)
        entries = audit_result["entries"]
        assert len(entries) >= 1
        entry = entries[0]
        assert entry["event_class"] == "high_risk_success"
        assert entry["retention_tier"] == "long"
        assert entry["expires_at"] is not None

    async def test_query_audit_event_class_filter(self):
        """Verify event_class filter works through query_audit."""
        cap = Capability(
            declaration=CapabilityDeclaration(
                name="multi_cap",
                description="Multi-use cap",
                contract_version="1.0",
                inputs=[CapabilityInput(name="name", type="string", required=True, description="name")],
                output=CapabilityOutput(type="object", fields=["message"]),
                side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
                minimum_scope=["test"],
            ),
            handler=lambda ctx, params: {"message": f"Hello, {params['name']}!"},
        )
        service = self._make_service(caps=[cap])
        token = await self._issue_test_token(service, scope=["test"], capability="multi_cap")

        # Successful invocation -> low_risk_success
        await service.invoke("multi_cap", token, {"name": "World"})

        # Query with event_class filter
        result_filtered = await service.query_audit(token, {"event_class": "low_risk_success"})
        assert result_filtered["count"] >= 1

        result_filtered_empty = await service.query_audit(token, {"event_class": "high_risk_success"})
        assert result_filtered_empty["count"] == 0


class TestANIPServiceTokenLifecycle:
    def _make_service(self):
        return ANIPService(
            service_id="test-service",
            capabilities=[_test_cap()],
            storage=":memory:",
            authenticate=lambda bearer: {"test-key": "human:test@example.com"}.get(bearer),
        )

    async def test_issue_and_resolve_round_trip(self):
        service = self._make_service()
        issued = await service.issue_token("human:test@example.com", {
            "subject": "human:test@example.com",
            "scope": ["greet"],
            "capability": "greet",
            "purpose_parameters": {"task_id": "test"},
        })
        assert issued["issued"] is True
        assert "token" in issued

        # Round-trip: resolve the JWT we just issued
        resolved = await service.resolve_bearer_token(issued["token"])
        assert resolved.subject == "human:test@example.com"

    async def test_authenticate_bearer_with_api_key(self):
        service = self._make_service()
        principal = await service.authenticate_bearer("test-key")
        assert principal == "human:test@example.com"

    async def test_authenticate_bearer_unknown(self):
        service = self._make_service()
        principal = await service.authenticate_bearer("unknown-key")
        assert principal is None

    async def test_sub_delegation_guardrail(self):
        service = self._make_service()
        issued = await service.issue_token("human:test@example.com", {
            "subject": "agent:bot-1",
            "scope": ["greet"],
            "capability": "greet",
            "purpose_parameters": {"task_id": "test"},
        })
        # The wrong principal tries to sub-delegate
        with pytest.raises(ANIPError, match="insufficient_authority"):
            await service.issue_token("human:wrong@example.com", {
                "parent_token": issued["token_id"],
                "subject": "agent:bot-2",
                "scope": ["greet"],
                "capability": "greet",
            })
