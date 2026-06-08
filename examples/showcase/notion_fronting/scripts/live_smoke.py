"""Live smoke for the Notion fronting showcase.

Expected environment:
- NOTION_TOKEN
- NOTION_WORKSPACE_SCOPE
- NOTION_PARENT_PAGE_ID
- NOTION_DATABASE_ID
"""
from __future__ import annotations

import json
import os

from fastapi.testclient import TestClient

from notion_governed_fronting_showcase.app import create_app


def issue_token(client: TestClient, capability_id: str) -> str:
    response = client.post(
        "/anip/tokens",
        headers={"Authorization": "Bearer dev-admin-key"},
        json={
            "capability": capability_id,
            "scope": [capability_id],
            "subject": "agent:live-notion-smoke",
            "purpose_parameters": {"actor_id": "notion_fronting_consumer", "source": "live-smoke"},
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
    workspace_scope = os.environ["NOTION_WORKSPACE_SCOPE"]
    parent_id = os.environ["NOTION_PARENT_PAGE_ID"]
    database_id = os.environ["NOTION_DATABASE_ID"]
    os.environ.setdefault("ANIP_NOTION_ALLOWED_WORKSPACES", workspace_scope)
    os.environ.setdefault("ANIP_NOTION_ALLOWED_PARENTS", parent_id)
    os.environ.setdefault("ANIP_NOTION_ALLOWED_PAGES", parent_id)
    os.environ.setdefault("ANIP_NOTION_ALLOWED_DATABASES", database_id)
    client = TestClient(create_app())
    cases = {
        "notion.workspace.search_context": {
            "parameters": {"workspace_scope": workspace_scope, "query": "ANIP", "limit": 5},
            "expected_status": "completed",
            "expect_mutation": None,
        },
        "notion.page.create.prepare": {
            "parameters": {
                "parent_id": parent_id,
                "title": "ANIP governed Notion page preview",
                "content_summary": "Preview only. This smoke must not create a Notion page.",
            },
            "expected_status": "prepared",
            "expect_mutation": False,
        },
        "notion.database.query_context": {
            "parameters": {"database_id": database_id, "limit": 5},
            "expected_status": "completed",
            "expect_mutation": None,
        },
        "notion.page.update.prepare": {
            "parameters": {
                "page_id": parent_id,
                "change_summary": "Preview only. This smoke must not update a Notion page.",
                "content_patch": "No update should be applied.",
            },
            "expected_status": "prepared",
            "expect_mutation": False,
        },
        "notion.comment.prepare": {
            "parameters": {
                "page_id": parent_id,
                "comment_purpose": "smoke-test",
                "context": "Preview only. This smoke must not post a Notion comment.",
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
            "notion_action": result.get("notion_action"),
        }

    print(json.dumps({"workspace_scope": workspace_scope, "capabilities_tested": len(summary), "results": summary}, indent=2))


if __name__ == "__main__":
    main()
