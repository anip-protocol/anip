"""Live smoke for the Linear fronting showcase.

Expected environment:
- LINEAR_API_KEY
- LINEAR_TEAM_KEY
"""
from __future__ import annotations

import json
import os

from fastapi.testclient import TestClient

from linear_governed_fronting_showcase.app import create_app


def issue_token(client: TestClient, capability_id: str) -> str:
    response = client.post(
        "/anip/tokens",
        headers={"Authorization": "Bearer dev-admin-key"},
        json={
            "capability": capability_id,
            "scope": [capability_id],
            "subject": "agent:live-linear-smoke",
            "purpose_parameters": {"actor_id": "linear_fronting_consumer", "source": "live-smoke"},
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
    team_key = os.environ["LINEAR_TEAM_KEY"]
    os.environ.setdefault("ANIP_LINEAR_ALLOWED_TEAMS", team_key)
    client = TestClient(create_app())
    search_result = invoke(client, "linear.issue.search_context", {"team_key": team_key, "query": "ANIP", "limit": 5})
    items = ((search_result.get("result") or {}).get("items") or [])
    issue_id = (items[0] or {}).get("id") if items else None
    if not issue_id:
        raise AssertionError("linear.issue.search_context did not return an ANIP issue to use for preview-only follow-up smokes")
    cases = {
        "linear.issue.search_context": {
            "parameters": {"team_key": team_key, "query": "ANIP", "limit": 5},
            "expected_status": "completed",
            "expect_mutation": None,
        },
        "linear.issue.prepare": {
            "parameters": {
                "team_key": team_key,
                "title": "ANIP governed Linear issue preview",
                "description": "Preview only. This smoke must not create a Linear issue.",
            },
            "expected_status": "prepared",
            "expect_mutation": False,
        },
        "linear.comment.prepare": {
            "parameters": {
                "issue_id": issue_id,
                "comment_purpose": "smoke-test",
                "context": "Preview only. This smoke must not post a Linear comment.",
            },
            "expected_status": "prepared",
            "expect_mutation": False,
        },
        "linear.status_transition.request": {
            "parameters": {
                "issue_id": issue_id,
                "target_status": "Backlog",
                "reason": "Preview only. This smoke must not transition a Linear issue.",
            },
            "expected_status": "prepared",
            "expect_mutation": False,
        },
        "linear.cycle_move.request": {
            "parameters": {
                "issue_id": issue_id,
                "target_cycle": "next",
                "reason": "Preview only. This smoke must not move a Linear issue.",
            },
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
            "linear_action": result.get("linear_action"),
        }

    print(json.dumps({"team_key": team_key, "capabilities_tested": len(summary), "results": summary}, indent=2))


if __name__ == "__main__":
    main()
