"""Round-trip and validation tests for v0.23 composition + approval grant models."""

import pytest
from pydantic import ValidationError

from anip_core import (
    ANIPFailure,
    ApprovalGrant,
    ApprovalRequest,
    ApprovalRequiredMetadata,
    AuditPolicy,
    CapabilityDeclaration,
    CapabilityInput,
    CapabilityOutput,
    Composition,
    CompositionStep,
    FailurePolicy,
    GrantPolicy,
    InvokeRequest,
    IssueApprovalGrantRequest,
    IssueApprovalGrantResponse,
    Resolution,
    SideEffect,
    SideEffectType,
)


# --- Capability Composition ---


def _composed_decl() -> CapabilityDeclaration:
    return CapabilityDeclaration(
        name="at_risk_account_enrichment_summary",
        description="Composed GTM example",
        inputs=[CapabilityInput(name="quarter", type="string", required=True)],
        output=CapabilityOutput(type="enriched_accounts", fields=["account_count", "accounts"]),
        side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
        minimum_scope=["gtm.read"],
        kind="composed",
        composition=Composition(
            authority_boundary="same_service",
            steps=[
                CompositionStep(id="select", capability="select_at_risk", empty_result_source=True),
                CompositionStep(id="enrich", capability="enrich_accounts"),
            ],
            input_mapping={
                "select": {"quarter": "$.input.quarter"},
                "enrich": {"accounts": "$.steps.select.output.accounts"},
            },
            output_mapping={
                "account_count": "$.steps.enrich.output.account_count",
                "accounts": "$.steps.enrich.output.accounts",
            },
            empty_result_policy="return_success_no_results",
            empty_result_output={"account_count": 0, "accounts": []},
            failure_policy=FailurePolicy(),
            audit_policy=AuditPolicy(record_child_invocations=True, parent_task_lineage=True),
        ),
    )


class TestCapabilityKind:
    def test_atomic_default(self):
        d = CapabilityDeclaration(
            name="cap",
            description="d",
            inputs=[],
            output=CapabilityOutput(type="x", fields=[]),
            side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
            minimum_scope=["s"],
        )
        assert d.kind == "atomic"
        assert d.composition is None

    def test_atomic_explicit_round_trip(self):
        d = CapabilityDeclaration(
            name="cap",
            description="d",
            inputs=[],
            output=CapabilityOutput(type="x", fields=[]),
            side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
            minimum_scope=["s"],
            kind="atomic",
        )
        data = d.model_dump()
        d2 = CapabilityDeclaration.model_validate(data)
        assert d2.kind == "atomic"

    def test_composed_round_trip(self):
        d = _composed_decl()
        data = d.model_dump()
        d2 = CapabilityDeclaration.model_validate(data)
        assert d2.kind == "composed"
        assert d2.composition is not None
        assert d2.composition.authority_boundary == "same_service"
        assert d2.composition.steps[0].empty_result_source is True
        assert d2.composition.steps[1].empty_result_source is False
        assert d2.composition.empty_result_policy == "return_success_no_results"
        assert d2.composition.empty_result_output == {"account_count": 0, "accounts": []}
        assert d2.composition.failure_policy.child_clarification == "propagate"
        assert d2.composition.failure_policy.child_error == "fail_parent"

    def test_step_default_empty_result_source(self):
        s = CompositionStep(id="s1", capability="c1")
        assert s.empty_result_source is False
        assert s.empty_result_path is None

    def test_step_with_explicit_empty_result_path(self):
        s = CompositionStep(
            id="s1",
            capability="c1",
            empty_result_source=True,
            empty_result_path="$.results",
        )
        s2 = CompositionStep.model_validate(s.model_dump())
        assert s2.empty_result_source is True
        assert s2.empty_result_path == "$.results"


# --- Approval Grant Models ---


def _grant_policy() -> GrantPolicy:
    return GrantPolicy(
        allowed_grant_types=["one_time", "session_bound"],
        default_grant_type="one_time",
        expires_in_seconds=900,
        max_uses=1,
    )


def _approval_request(status: str = "pending") -> ApprovalRequest:
    approver: dict | None = None
    decided_at: str | None = None
    if status in ("approved", "denied"):
        approver = {"principal": "manager_456"}
        decided_at = "2026-01-01T00:01:00Z"
    elif status == "expired":
        decided_at = "2026-01-01T00:15:01Z"
    return ApprovalRequest(
        approval_request_id="apr_test",
        capability="finance.transfer_funds",
        scope=["finance.write"],
        requester={"principal": "user_123"},
        preview={"amount": 50000, "currency": "USD"},
        preview_digest="sha256:preview",
        requested_parameters={"to": "acct-2", "amount": 50000},
        requested_parameters_digest="sha256:params",
        grant_policy=_grant_policy(),
        status=status,  # type: ignore[arg-type]
        approver=approver,
        decided_at=decided_at,
        created_at="2026-01-01T00:00:00Z",
        expires_at="2026-01-01T00:15:00Z",
    )


def _grant() -> ApprovalGrant:
    return ApprovalGrant(
        grant_id="grant_test",
        approval_request_id="apr_test",
        grant_type="one_time",
        capability="finance.transfer_funds",
        scope=["finance.write"],
        approved_parameters_digest="sha256:params",
        preview_digest="sha256:preview",
        requester={"principal": "user_123"},
        approver={"principal": "manager_456"},
        issued_at="2026-01-01T00:01:00Z",
        expires_at="2026-01-01T00:16:00Z",
        max_uses=1,
        use_count=0,
        session_id=None,
        signature="sig_test",
    )


class TestApprovalRequest:
    def test_pending_round_trip(self):
        r = _approval_request("pending")
        data = r.model_dump()
        r2 = ApprovalRequest.model_validate(data)
        assert r2.status == "pending"
        assert r2.approver is None
        assert r2.decided_at is None

    def test_approved_round_trip(self):
        r = _approval_request("approved")
        r2 = ApprovalRequest.model_validate(r.model_dump())
        assert r2.status == "approved"
        assert r2.approver == {"principal": "manager_456"}
        assert r2.decided_at is not None

    def test_expired_round_trip(self):
        r = _approval_request("expired")
        r2 = ApprovalRequest.model_validate(r.model_dump())
        assert r2.status == "expired"
        assert r2.approver is None
        assert r2.decided_at is not None


class TestApprovalGrant:
    def test_one_time_round_trip(self):
        g = _grant()
        g2 = ApprovalGrant.model_validate(g.model_dump())
        assert g2.grant_id == "grant_test"
        assert g2.approval_request_id == "apr_test"
        assert g2.grant_type == "one_time"
        assert g2.session_id is None
        assert g2.use_count == 0

    def test_session_bound_round_trip(self):
        g = _grant().model_copy(
            update={"grant_type": "session_bound", "session_id": "sess_1", "max_uses": 5}
        )
        g2 = ApprovalGrant.model_validate(g.model_dump())
        assert g2.grant_type == "session_bound"
        assert g2.session_id == "sess_1"
        assert g2.max_uses == 5

    def test_grant_required_fields(self):
        with pytest.raises(ValidationError):
            ApprovalGrant(grant_id="g1")  # type: ignore[call-arg]


class TestApprovalRequiredFailure:
    def test_failure_with_metadata_round_trip(self):
        f = ANIPFailure(
            type="approval_required",
            detail="approval needed",
            resolution=Resolution(action="contact_service_owner", recovery_class="terminal"),
            retry=False,
            approval_required=ApprovalRequiredMetadata(
                approval_request_id="apr_test",
                preview_digest="sha256:preview",
                requested_parameters_digest="sha256:params",
                grant_policy=_grant_policy(),
            ),
        )
        f2 = ANIPFailure.model_validate(f.model_dump())
        assert f2.approval_required is not None
        assert f2.approval_required.approval_request_id == "apr_test"
        assert f2.approval_required.grant_policy.expires_in_seconds == 900

    def test_non_approval_failure_has_no_metadata(self):
        f = ANIPFailure(
            type="budget_exceeded",
            detail="too expensive",
            resolution=Resolution(action="request_budget_increase", recovery_class="redelegation_then_retry"),
        )
        assert f.approval_required is None


class TestInvokeRequest:
    def test_invoke_with_approval_grant(self):
        ir = InvokeRequest(token="jwt", approval_grant="grant_test")
        ir2 = InvokeRequest.model_validate(ir.model_dump())
        assert ir2.approval_grant == "grant_test"

    def test_invoke_without_approval_grant_default_none(self):
        ir = InvokeRequest(token="jwt")
        assert ir.approval_grant is None


class TestIssueApprovalGrant:
    def test_request_round_trip(self):
        req = IssueApprovalGrantRequest(
            approval_request_id="apr_test",
            grant_type="one_time",
            expires_in_seconds=600,
            max_uses=1,
        )
        req2 = IssueApprovalGrantRequest.model_validate(req.model_dump())
        assert req2.grant_type == "one_time"
        assert req2.expires_in_seconds == 600

    def test_response_round_trip(self):
        resp = IssueApprovalGrantResponse(grant=_grant())
        resp2 = IssueApprovalGrantResponse.model_validate(resp.model_dump())
        assert resp2.grant.grant_id == "grant_test"

    def test_session_bound_request_requires_session_id(self):
        with pytest.raises(ValidationError):
            IssueApprovalGrantRequest(
                approval_request_id="apr_test",
                grant_type="session_bound",
            )

    def test_one_time_request_rejects_session_id(self):
        with pytest.raises(ValidationError):
            IssueApprovalGrantRequest(
                approval_request_id="apr_test",
                grant_type="one_time",
                session_id="sess_1",
            )

    def test_one_time_request_rejects_max_uses_other_than_one(self):
        with pytest.raises(ValidationError):
            IssueApprovalGrantRequest(
                approval_request_id="apr_test",
                grant_type="one_time",
                max_uses=5,
            )


# --- Negative validators (security invariants) ---


class TestApprovalGrantInvariants:
    def _base_kwargs(self) -> dict:
        return dict(
            grant_id="g1",
            approval_request_id="apr_1",
            capability="cap",
            scope=["s"],
            approved_parameters_digest="d1",
            preview_digest="d2",
            requester={"principal": "u1"},
            approver={"principal": "u2"},
            issued_at="2026-01-01T00:00:00Z",
            expires_at="2026-01-01T00:15:00Z",
            signature="sig",
        )

    def test_one_time_rejects_max_uses_above_one(self):
        with pytest.raises(ValidationError):
            ApprovalGrant(grant_type="one_time", max_uses=5, **self._base_kwargs())

    def test_one_time_rejects_session_id(self):
        with pytest.raises(ValidationError):
            ApprovalGrant(
                grant_type="one_time",
                max_uses=1,
                session_id="sess_1",
                **self._base_kwargs(),
            )

    def test_session_bound_requires_session_id(self):
        with pytest.raises(ValidationError):
            ApprovalGrant(
                grant_type="session_bound",
                max_uses=5,
                session_id=None,
                **self._base_kwargs(),
            )

    def test_session_bound_with_session_id_succeeds(self):
        g = ApprovalGrant(
            grant_type="session_bound",
            max_uses=5,
            session_id="sess_1",
            **self._base_kwargs(),
        )
        assert g.session_id == "sess_1"


class TestApprovalRequestInvariants:
    def _base_kwargs(self) -> dict:
        return dict(
            approval_request_id="apr_1",
            capability="cap",
            scope=["s"],
            requester={"principal": "u1"},
            preview={"k": "v"},
            preview_digest="d2",
            requested_parameters={"k": "v"},
            requested_parameters_digest="d1",
            grant_policy=_grant_policy(),
            created_at="2026-01-01T00:00:00Z",
            expires_at="2026-01-01T00:15:00Z",
        )

    def test_pending_with_approver_rejected(self):
        with pytest.raises(ValidationError):
            ApprovalRequest(
                status="pending",
                approver={"principal": "u2"},
                **self._base_kwargs(),
            )

    def test_pending_with_decided_at_rejected(self):
        with pytest.raises(ValidationError):
            ApprovalRequest(
                status="pending",
                decided_at="2026-01-01T00:01:00Z",
                **self._base_kwargs(),
            )

    def test_approved_without_approver_rejected(self):
        with pytest.raises(ValidationError):
            ApprovalRequest(
                status="approved",
                decided_at="2026-01-01T00:01:00Z",
                **self._base_kwargs(),
            )

    def test_expired_with_approver_rejected(self):
        with pytest.raises(ValidationError):
            ApprovalRequest(
                status="expired",
                approver={"principal": "u2"},
                decided_at="2026-01-01T00:15:01Z",
                **self._base_kwargs(),
            )

    def test_expired_without_decided_at_rejected(self):
        with pytest.raises(ValidationError):
            ApprovalRequest(status="expired", **self._base_kwargs())


class TestANIPFailureApprovalInvariants:
    def _base_resolution(self) -> Resolution:
        return Resolution(action="contact_service_owner", recovery_class="terminal")

    def test_approval_required_without_metadata_rejected(self):
        with pytest.raises(ValidationError):
            ANIPFailure(
                type="approval_required",
                detail="needs approval",
                resolution=self._base_resolution(),
            )

    def test_non_approval_with_metadata_rejected(self):
        with pytest.raises(ValidationError):
            ANIPFailure(
                type="budget_exceeded",
                detail="too expensive",
                resolution=self._base_resolution(),
                approval_required=ApprovalRequiredMetadata(
                    approval_request_id="apr_1",
                    preview_digest="d2",
                    requested_parameters_digest="d1",
                    grant_policy=_grant_policy(),
                ),
            )


class TestCapabilityDeclarationKindInvariants:
    def _base_kwargs(self) -> dict:
        return dict(
            name="cap",
            description="d",
            inputs=[],
            output=CapabilityOutput(type="x", fields=[]),
            side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
            minimum_scope=["s"],
        )

    def test_composed_without_composition_rejected(self):
        with pytest.raises(ValidationError):
            CapabilityDeclaration(kind="composed", **self._base_kwargs())

    def test_atomic_with_composition_rejected(self):
        comp = _composed_decl().composition
        with pytest.raises(ValidationError):
            CapabilityDeclaration(kind="atomic", composition=comp, **self._base_kwargs())

    def test_omitted_kind_with_composition_rejected(self):
        # Kind defaults to "atomic"; composition non-null must therefore be rejected.
        comp = _composed_decl().composition
        with pytest.raises(ValidationError):
            CapabilityDeclaration(composition=comp, **self._base_kwargs())
