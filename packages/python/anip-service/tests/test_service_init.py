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
        disc = service.get_discovery()
        assert "anip_discovery" in disc
        assert "greet" in disc["anip_discovery"]["capabilities"]
        assert disc["anip_discovery"]["trust_level"] == "signed"

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


class TestANIPServiceInvoke:
    def _make_service(self, caps=None):
        return ANIPService(
            service_id="test-service",
            capabilities=caps or [_test_cap()],
            storage=":memory:",
        )

    def test_invoke_unknown_capability(self):
        service = self._make_service()
        token = self._issue_test_token(service)
        result = service.invoke("nonexistent", token, {})
        assert result["success"] is False
        assert result["failure"]["type"] == "unknown_capability"

    def test_invoke_success(self):
        service = self._make_service()
        token = self._issue_test_token(service)
        result = service.invoke("greet", token, {"name": "World"})
        assert result["success"] is True
        assert result["result"]["message"] == "Hello, World!"

    def test_invoke_handler_anip_error(self):
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
        token = self._issue_test_token(service, scope=["test"], capability="fail_cap")
        result = service.invoke("fail_cap", token, {})
        assert result["success"] is False
        assert result["failure"]["type"] == "not_found"

    def test_invoke_handler_unexpected_error(self):
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
        token = self._issue_test_token(service, scope=["test"], capability="crash_cap")
        result = service.invoke("crash_cap", token, {})
        assert result["success"] is False
        assert result["failure"]["type"] == "internal_error"
        # Detail should NOT leak the actual exception
        assert "boom" not in result["failure"]["detail"]

    def test_invoke_cost_tracking(self):
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
        token = self._issue_test_token(service, scope=["test"], capability="cost_cap")
        result = service.invoke("cost_cap", token, {})
        assert result["success"] is True
        assert result["cost_actual"]["financial"]["amount"] == 450.0

    def _issue_test_token(self, service, scope=None, capability=None):
        """Helper to issue a root token for testing."""
        cap = capability or "greet"
        result = service._engine.issue_root_token(
            authenticated_principal="human:test@example.com",
            subject="human:test@example.com",
            scope=scope or ["greet"],
            capability=cap,
            purpose_parameters={"task_id": "test"},
            ttl_hours=1,
        )
        token, token_id = result
        return token


class TestANIPServiceTokenLifecycle:
    def _make_service(self):
        return ANIPService(
            service_id="test-service",
            capabilities=[_test_cap()],
            storage=":memory:",
            authenticate=lambda bearer: {"test-key": "human:test@example.com"}.get(bearer),
        )

    def test_issue_and_resolve_round_trip(self):
        service = self._make_service()
        issued = service.issue_token("human:test@example.com", {
            "subject": "human:test@example.com",
            "scope": ["greet"],
            "capability": "greet",
            "purpose_parameters": {"task_id": "test"},
        })
        assert issued["issued"] is True
        assert "token" in issued

        # Round-trip: resolve the JWT we just issued
        resolved = service.resolve_bearer_token(issued["token"])
        assert resolved.subject == "human:test@example.com"

    def test_authenticate_bearer_with_api_key(self):
        service = self._make_service()
        principal = service.authenticate_bearer("test-key")
        assert principal == "human:test@example.com"

    def test_authenticate_bearer_unknown(self):
        service = self._make_service()
        principal = service.authenticate_bearer("unknown-key")
        assert principal is None

    def test_sub_delegation_guardrail(self):
        service = self._make_service()
        issued = service.issue_token("human:test@example.com", {
            "subject": "agent:bot-1",
            "scope": ["greet"],
            "capability": "greet",
            "purpose_parameters": {"task_id": "test"},
        })
        # The wrong principal tries to sub-delegate
        with pytest.raises(ANIPError, match="insufficient_authority"):
            service.issue_token("human:wrong@example.com", {
                "parent_token": issued["token_id"],
                "subject": "agent:bot-2",
                "scope": ["greet"],
                "capability": "greet",
            })
