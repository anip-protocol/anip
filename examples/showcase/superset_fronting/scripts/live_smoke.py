"""Live smoke for the Superset fronting showcase.

The Python bundle never mutates Superset: write-adjacent capabilities return
governed previews. The smoke sets ANIP_SUPERSET_ALLOW_MUTATION=false, so granted
calls return previews too.

Expected environment:
- SUPERSET_BASE_URL
- SUPERSET_USERNAME and SUPERSET_PASSWORD, or SUPERSET_ACCESS_TOKEN
- SUPERSET_WORKSPACE_SCOPE

Optional:
- ANIP_SUPERSET_GENERATED_APP_MODULE (default superset_governed_fronting_showcase.app)

The smoke authenticates through the generated service's ANIP_API_KEYS_JSON, which
it sets itself: one API key per actor that the 0.2.0 policy bindings select, an
approver, and principals no binding selects. It checks that:

- each capability succeeds for an actor whose binding allows it;
- approval-gated capabilities return approval_required, and complete after an
  approver issues a grant through POST /anip/approval_grants;
- a principal without an actor claim, an actor no binding names, an actor the
  capability's bindings do not name, deny bindings and a clarify binding are
  refused.

Run after generating the Python service with the Superset custom bundle:

PYTHONPATH="<repo python packages>:<generated src>" python examples/showcase/superset_fronting/scripts/live_smoke.py
"""
from __future__ import annotations

import importlib
import json
import os
from typing import Any

from fastapi.testclient import TestClient

DEFAULT_APP_MODULE = "superset_governed_fronting_showcase.app"

# API key -> ANIP principal. The actor_id claims are the actors the 0.2.0
# runtime policy bindings select.
SMOKE_KEYS = {
    "smoke-analytics-consumer": "human:live-superset-smoke|actor_id=analytics_consumer",
    "smoke-analytics-creator": "human:live-superset-smoke|actor_id=analytics_creator",
    "smoke-analytics-owner": "human:live-superset-smoke|actor_id=analytics_owner",
    "smoke-bi-admin": "human:live-superset-smoke|actor_id=BI_admin",
    "smoke-dataset-draft-requester": "human:live-superset-smoke|actor_id=dataset_draft_requester",
    "smoke-approver": "human:live-superset-approver",
    "smoke-no-actor": "human:live-superset-smoke",
    "smoke-unknown-actor": "human:live-superset-smoke|actor_id=superset_unknown_actor",
}
APPROVER_KEY = "smoke-approver"
NO_BINDING_DETAIL = "No runtime policy binding matches the current actor for this capability."


def generated_app_module() -> str:
    return os.getenv("ANIP_SUPERSET_GENERATED_APP_MODULE", "").strip() or DEFAULT_APP_MODULE


def create_generated_client() -> tuple[TestClient, dict[str, list[str]]]:
    """Return a client and the minimum scope for every generated capability."""
    app_module = generated_app_module()
    package_name = app_module.rsplit(".", 1)[0]
    runtime_target = importlib.import_module(f"{package_name}.runtime_target")
    scopes = {
        str(capability["capability_id"]): list(capability.get("minimum_scope") or [capability["capability_id"]])
        for capability in getattr(runtime_target, "GENERATED_CAPABILITY_METADATA", [])
        if capability.get("capability_id")
    }
    return TestClient(importlib.import_module(app_module).create_app()), scopes


class Smoke:
    def __init__(self, client: TestClient, scopes: dict[str, list[str]]) -> None:
        self.client = client
        self.scopes = scopes

    def token(self, key: str, capability_id: str, scope: list[str] | None = None) -> str:
        response = self.client.post(
            "/anip/tokens",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "capability": capability_id,
                "scope": scope or self.scopes.get(capability_id, [capability_id]),
                "subject": "agent:live-superset-smoke",
                "purpose_parameters": {"source": "live-smoke"},
            },
        )
        response.raise_for_status()
        return response.json()["token"]

    def invoke(self, key: str, capability_id: str, parameters: dict, approval_grant: str | None = None) -> dict:
        body: dict[str, Any] = {"parameters": parameters}
        if approval_grant:
            body["approval_grant"] = approval_grant
        response = self.client.post(
            f"/anip/invoke/{capability_id}",
            headers={"Authorization": f"Bearer {self.token(key, capability_id)}"},
            json=body,
        )
        return response.json()

    def grant(self, key: str, capability_id: str, approval_request_id: str, scope: list[str] | None = None) -> dict:
        token = self.token(key, capability_id, scope=scope or [f"approver:{capability_id}"])
        response = self.client.post(
            "/anip/approval_grants",
            headers={"Authorization": f"Bearer {token}"},
            json={"approval_request_id": approval_request_id, "grant_type": "one_time"},
        )
        return response.json()


def expect_result(capability_id: str, payload: dict, status: str, mutation: bool | None) -> dict:
    if not payload.get("success"):
        raise AssertionError(f"{capability_id}: expected {status}, got failure: {payload}")
    result = payload["result"]
    if result.get("execution_status") != status:
        raise AssertionError(f"{capability_id}: expected {status}, got {result.get('execution_status')}: {result}")
    if mutation is not None and result.get("mutation_performed") is not mutation:
        raise AssertionError(f"{capability_id}: unexpected mutation posture: {result}")
    return result


def expect_failure(capability_id: str, payload: dict, failure_type: str, detail: str | None = None) -> dict:
    failure = payload.get("failure") or {}
    if payload.get("success") is not False or failure.get("type") != failure_type:
        raise AssertionError(f"{capability_id}: expected failure {failure_type}, got {payload}")
    if detail is not None and failure.get("detail") != detail:
        raise AssertionError(f"{capability_id}: expected detail {detail!r}, got {failure.get('detail')!r}")
    return failure


def run_with_approval(smoke: Smoke, key: str, capability_id: str, parameters: dict, check_approver_scope: bool) -> tuple[dict, dict]:
    failure = expect_failure(capability_id, smoke.invoke(key, capability_id, parameters), "approval_required")
    approval_request_id = (failure.get("approval_required") or {}).get("approval_request_id")
    if not approval_request_id:
        raise AssertionError(f"{capability_id}: approval_required carried no approval_request_id: {failure}")
    if check_approver_scope:
        # A token without approver:<capability> scope cannot issue the grant.
        refused = smoke.grant(key, capability_id, approval_request_id, scope=smoke.scopes.get(capability_id))
        expect_failure(capability_id, refused, "approver_not_authorized")
    grant = smoke.grant(APPROVER_KEY, capability_id, approval_request_id)
    grant_id = grant.get("grant_id")
    if not grant_id:
        raise AssertionError(f"{capability_id}: approval grant was not issued: {grant}")
    result = expect_result(capability_id, smoke.invoke(key, capability_id, parameters, approval_grant=grant_id), "prepared", False)
    return result, {"approval_request_id": approval_request_id, "grant_id": grant_id}


def main() -> None:
    os.environ["ANIP_API_KEYS_JSON"] = json.dumps(SMOKE_KEYS)
    # The granted calls must return previews: keep the bundle's approved path off.
    os.environ["ANIP_SUPERSET_ALLOW_MUTATION"] = "false"
    workspace_scope = os.getenv("SUPERSET_WORKSPACE_SCOPE", "local")
    os.environ.setdefault("ANIP_SUPERSET_ALLOWED_WORKSPACES", workspace_scope)
    smoke = Smoke(*create_generated_client())

    discover = {"workspace_scope": workspace_scope, "query": "birth", "limit": 5}
    chart_preview = {"dataset_ref": "1", "metric": "count", "visualization_type": "bar", "title": "ANIP preview chart"}
    # (capability, API key, parameters, expected execution_status, expected mutation_performed)
    allowed: list[tuple[str, str, dict[str, Any], str, bool | None]] = [
        ("superset.analytics.discover_context", "smoke-analytics-consumer", discover, "completed", None),
        ("superset.chart.preview.create", "smoke-analytics-creator", chart_preview, "prepared", False),
        ("superset.dashboard.draft.prepare", "smoke-analytics-owner", {
            "dashboard_scope": workspace_scope,
            "objective": "Review ANIP smoke analytics",
            "chart_refs": ["1"],
        }, "prepared", False),
    ]
    publish = {"chart_preview_ref": "preview-1", "dashboard_scope": workspace_scope, "reason": "Validate the governed publish request without mutating Superset."}
    dataset_draft = {"database_ref": "1", "dataset_purpose": "ANIP smoke", "query_intent": "Count records by category"}
    # Approval-gated capabilities: (capability, requester API key, parameters).
    gated: list[tuple[str, str, dict[str, Any]]] = [
        ("superset.chart.publish.request", "smoke-analytics-creator", publish),
        ("superset.dataset.draft.prepare", "smoke-dataset-draft-requester", dataset_draft),
    ]
    question = {"question": "How many records per category?", "dataset_ref": "1"}
    # (label, capability, API key, parameters, expected failure type, expected detail)
    refused: list[tuple[str, str, str, dict[str, Any], str, str | None]] = [
        ("principal without an actor claim", "superset.analytics.discover_context", "smoke-no-actor", discover, "denied", NO_BINDING_DETAIL),
        ("actor no binding names", "superset.analytics.discover_context", "smoke-unknown-actor", discover, "denied", NO_BINDING_DETAIL),
        ("actor the capability's bindings do not name", "superset.dashboard.draft.prepare", "smoke-dataset-draft-requester", allowed[2][2], "denied", NO_BINDING_DETAIL),
        ("deny binding", "superset.analytics.answer_question", "smoke-analytics-consumer", question, "denied", None),
        ("deny binding", "superset.analytics.discover_context", "smoke-analytics-owner", discover, "denied", None),
        ("deny binding", "superset.dataset.draft.prepare", "smoke-analytics-creator", dataset_draft, "denied", None),
        ("clarify binding", "superset.chart.publish.request", "smoke-analytics-consumer", publish, "clarification_required", None),
    ]

    summary: dict[str, dict] = {}
    for capability_id, key, parameters, status, mutation in allowed:
        result = expect_result(capability_id, smoke.invoke(key, capability_id, parameters), status, mutation)
        summary[capability_id] = {
            "actor": SMOKE_KEYS[key],
            "execution_status": result.get("execution_status"),
            "mutation_performed": result.get("mutation_performed"),
            "superset_action": result.get("superset_action"),
        }
        if capability_id == "superset.analytics.discover_context":
            summary[capability_id]["item_count"] = (result.get("result") or {}).get("count")
    for index, (capability_id, key, parameters) in enumerate(gated):
        result, approval = run_with_approval(smoke, key, capability_id, parameters, check_approver_scope=index == 0)
        summary[capability_id] = {
            "actor": SMOKE_KEYS[key],
            "first_attempt": "approval_required",
            **approval,
            "execution_status": result.get("execution_status"),
            "mutation_performed": result.get("mutation_performed"),
            "superset_action": result.get("superset_action"),
        }
    refusals = []
    for label, capability_id, key, parameters, failure_type, detail in refused:
        expect_failure(capability_id, smoke.invoke(key, capability_id, parameters), failure_type, detail)
        refusals.append({"check": label, "capability_id": capability_id, "actor": SMOKE_KEYS[key], "failure": failure_type})

    print(json.dumps({
        "workspace_scope": workspace_scope,
        "capabilities_tested": len(summary),
        "results": summary,
        "refusals": refusals,
    }, indent=2))


if __name__ == "__main__":
    main()
