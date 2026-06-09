import importlib

import pytest
from fastapi.testclient import TestClient

from gtm_pipeline_q2_review.app import app


SECONDARY_SERVICES = [
    (
        "gtm_pipeline_q2_review.services.gtm_enrichment_service.app",
        {
            "gtm.account_enrichment_summary",
            "gtm.at_risk_account_enrichment_summary",
            "gtm.lookalike_accounts",
        },
    ),
    (
        "gtm_pipeline_q2_review.services.gtm_prioritization_service.app",
        {
            "gtm.score_leads",
            "gtm.prioritize_accounts",
            "gtm.route_leads",
        },
    ),
    (
        "gtm_pipeline_q2_review.services.gtm_outreach_service.app",
        {
            "gtm.bottleneck_account_outreach_draft",
            "gtm.draft_outreach_message",
            "gtm.prioritized_outreach_draft",
            "gtm.suggest_followup_content",
            "gtm.objection_response_variants",
        },
    ),
]


def _discovery_capability_names(payload: dict) -> set[str]:
    discovered = payload.get("capabilities")
    if discovered is None:
        discovered = payload.get("anip_discovery", {}).get("capabilities", [])
    if isinstance(discovered, dict):
        return set(discovered.keys())
    return {capability["name"] for capability in discovered}


def _issue_token(client: TestClient, capability_id: str, scope: list[str]) -> str:
    response = client.post(
        "/anip/tokens",
        headers={"Authorization": "Bearer demo-sales-leader-key"},
        json={
            "capability": capability_id,
            "scope": scope,
            "subject": "agent:test",
            "purpose_parameters": {"actor_id": "sales_leader", "source": "pytest"},
        },
    )
    assert response.status_code == 200
    return response.json()["token"]


def _minimum_scope(client: TestClient, capability_id: str) -> list[str]:
    manifest = client.get("/anip/manifest")
    assert manifest.status_code == 200
    capabilities = manifest.json().get("capabilities", {})
    if isinstance(capabilities, list):
        capabilities = {item["name"]: item for item in capabilities}
    capability = capabilities[capability_id]
    return capability.get("minimum_scope") or []


def test_custom_gtm_service_discovery_and_approval_preview() -> None:
    client = TestClient(app)
    discovery = client.get("/.well-known/anip")
    assert discovery.status_code == 200
    capabilities = _discovery_capability_names(discovery.json())
    assert "gtm.prepare_followup_tasks" in capabilities
    assert "gtm.lookalike_accounts" not in capabilities

    token = _issue_token(client, "gtm.prepare_followup_tasks", _minimum_scope(client, "gtm.prepare_followup_tasks"))
    invoke = client.post(
        "/anip/invoke/gtm.prepare_followup_tasks",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "parameters": {
                "quarter": "2017-Q2",
                "ranking_basis": "risk_score",
                "limit": 2,
            }
        },
    )
    assert invoke.status_code == 400
    payload = invoke.json()
    assert payload["success"] is False
    assert payload["failure"]["type"] == "approval_required"
    assert payload["failure"]["resolution"]["preview"]["tasks"]


def test_pipeline_service_applies_declared_default_ranking_basis() -> None:
    client = TestClient(app)
    token = _issue_token(client, "gtm.account_risk_summary", _minimum_scope(client, "gtm.account_risk_summary"))
    invoke = client.post(
        "/anip/invoke/gtm.account_risk_summary",
        headers={"Authorization": f"Bearer {token}"},
        json={"parameters": {"quarter": "2017-Q2", "limit": 2}},
    )
    assert invoke.status_code == 200
    payload = invoke.json()
    assert payload["success"] is True
    assert payload["result"]["ranking_basis"] == "risk_score"
    assert payload["result"]["accounts"]


def test_pipeline_service_requires_explicit_quarter_label() -> None:
    client = TestClient(app)
    token = _issue_token(client, "gtm.account_risk_summary", _minimum_scope(client, "gtm.account_risk_summary"))
    invoke = client.post(
        "/anip/invoke/gtm.account_risk_summary",
        headers={"Authorization": f"Bearer {token}"},
        json={"parameters": {"quarter": "this quarter"}},
    )
    assert invoke.status_code == 400
    payload = invoke.json()
    assert payload["success"] is False
    assert payload["failure"]["type"] == "clarification_required"
    assert payload["failure"]["resolution"]["requires"] == "quarter"


def test_enrichment_service_clarifies_vague_account_scope() -> None:
    module = importlib.import_module("gtm_pipeline_q2_review.services.gtm_enrichment_service.app")
    client = TestClient(module.app)
    token = _issue_token(client, "gtm.account_enrichment_summary", ["gtm.enrichment.read"])
    invoke = client.post(
        "/anip/invoke/gtm.account_enrichment_summary",
        headers={"Authorization": f"Bearer {token}"},
        json={"parameters": {"account_names": "the accounts we should review next"}},
    )
    assert invoke.status_code == 400
    payload = invoke.json()
    assert payload["failure"]["type"] == "clarification_required"
    assert payload["failure"]["resolution"]["requires"] == "account_names"


def test_enrichment_service_accepts_and_joined_explicit_account_names() -> None:
    module = importlib.import_module("gtm_pipeline_q2_review.services.gtm_enrichment_service.app")
    client = TestClient(module.app)
    token = _issue_token(client, "gtm.account_enrichment_summary", ["gtm.enrichment.read"])
    invoke = client.post(
        "/anip/invoke/gtm.account_enrichment_summary",
        headers={"Authorization": f"Bearer {token}"},
        json={"parameters": {"account_names": "Acme Corporation and Codehow"}},
    )
    assert invoke.status_code == 200
    payload = invoke.json()
    assert payload["success"] is True
    account_names = [item["account_name"] for item in payload["result"]["result"]["accounts"]]
    assert account_names == ["Acme Corporation", "Codehow"]


def test_enrichment_service_clarifies_vague_lookalike_reference() -> None:
    module = importlib.import_module("gtm_pipeline_q2_review.services.gtm_enrichment_service.app")
    client = TestClient(module.app)
    token = _issue_token(client, "gtm.lookalike_accounts", ["gtm.enrichment.read"])
    invoke = client.post(
        "/anip/invoke/gtm.lookalike_accounts",
        headers={"Authorization": f"Bearer {token}"},
        json={"parameters": {"reference_account": "our best customer"}},
    )
    assert invoke.status_code == 400
    payload = invoke.json()
    assert payload["failure"]["type"] == "clarification_required"
    assert payload["failure"]["resolution"]["requires"] == "reference_account"


def test_outreach_service_applies_declared_default_objective(monkeypatch: pytest.MonkeyPatch) -> None:
    module = importlib.import_module("gtm_pipeline_q2_review.services.gtm_outreach_service.app")

    async def fake_draft_outreach_message_async(**kwargs):
        return kwargs

    monkeypatch.setattr(module, "draft_outreach_message_async", fake_draft_outreach_message_async)
    client = TestClient(module.app)
    token = _issue_token(client, "gtm.draft_outreach_message", ["gtm.outreach.read"])
    invoke = client.post(
        "/anip/invoke/gtm.draft_outreach_message",
        headers={"Authorization": f"Bearer {token}"},
        json={"parameters": {"target_ref": "Acme Corporation", "channel": "email"}},
    )
    assert invoke.status_code == 200
    payload = invoke.json()
    assert payload["success"] is True
    assert payload["result"]["result"]["objective"] == "first_touch"


@pytest.mark.parametrize(("module_name", "expected_capabilities"), SECONDARY_SERVICES)
def test_generated_secondary_services_are_scoped(module_name: str, expected_capabilities: set[str]) -> None:
    module = importlib.import_module(module_name)
    client = TestClient(module.app)
    discovery = client.get("/.well-known/anip")
    assert discovery.status_code == 200
    capabilities = _discovery_capability_names(discovery.json())
    assert capabilities == expected_capabilities
