"""Live smoke for the Superset fronting showcase.

Expected environment:
- SUPERSET_BASE_URL
- SUPERSET_USERNAME and SUPERSET_PASSWORD, or SUPERSET_ACCESS_TOKEN
- SUPERSET_WORKSPACE_SCOPE
"""
from __future__ import annotations

import json
import os

from fastapi.testclient import TestClient

from superset_governed_fronting_showcase.app import create_app


def issue_token(client: TestClient, capability_id: str) -> str:
    response = client.post(
        "/anip/tokens",
        headers={"Authorization": "Bearer dev-admin-key"},
        json={
            "capability": capability_id,
            "scope": [capability_id],
            "subject": "agent:live-superset-smoke",
            "purpose_parameters": {"actor_id": "superset_fronting_consumer", "source": "live-smoke"},
        },
    )
    response.raise_for_status()
    return response.json()["token"]


def invoke(client: TestClient, capability_id: str, parameters: dict) -> dict:
    token = issue_token(client, capability_id)
    response = client.post(
        f"/anip/invoke/{capability_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"parameters": parameters},
    )
    if response.status_code >= 400:
        raise RuntimeError(response.text)
    payload = response.json()
    if not payload.get("success"):
        raise RuntimeError(payload)
    return payload["result"]


def main() -> None:
    workspace_scope = os.getenv("SUPERSET_WORKSPACE_SCOPE", "local")
    os.environ.setdefault("ANIP_SUPERSET_ALLOWED_WORKSPACES", workspace_scope)
    client = TestClient(create_app())
    cases = {
        "superset.analytics.discover_context": {
            "parameters": {"workspace_scope": workspace_scope, "query": "birth", "limit": 5},
            "expected_status": "completed",
            "expect_mutation": None,
        },
        "superset.chart.preview.create": {
            "parameters": {"dataset_ref": "1", "metric": "count", "visualization_type": "bar", "title": "ANIP preview chart"},
            "expected_status": "prepared",
            "expect_mutation": False,
        },
        "superset.dataset.draft.prepare": {
            "parameters": {"database_ref": "1", "dataset_purpose": "ANIP smoke", "query_intent": "Count records by category"},
            "expected_status": "prepared",
            "expect_mutation": False,
        },
    }

    summary: dict[str, dict] = {}
    for capability_id, case in cases.items():
        result = invoke(client, capability_id, case["parameters"])
        execution_status = result.get("execution_status")
        expected_status = case["expected_status"]
        if execution_status != expected_status:
            raise AssertionError(f"{capability_id}: expected {expected_status}, got {execution_status}: {result}")
        expected_mutation = case["expect_mutation"]
        if expected_mutation is not None and result.get("mutation_performed") is not expected_mutation:
            raise AssertionError(f"{capability_id}: unexpected mutation posture: {result}")
        summary[capability_id] = {
            "execution_status": execution_status,
            "mutation_performed": result.get("mutation_performed"),
            "approval_required": result.get("approval_required"),
            "superset_action": result.get("superset_action"),
        }

    print(json.dumps({"workspace_scope": workspace_scope, "capabilities_tested": len(summary), "results": summary}, indent=2))


if __name__ == "__main__":
    main()
