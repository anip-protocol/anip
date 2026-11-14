"""Approved page-creation smoke for the Notion fronting showcase.

This test intentionally creates one Notion page. Use only with a disposable
parent page and a generated Python service that includes the Notion custom bundle.

Expected environment:
- NOTION_TOKEN
- NOTION_WORKSPACE_SCOPE
- NOTION_PARENT_PAGE_ID
- ANIP_NOTION_ALLOW_MUTATION=true

The smoke follows the approval path a client takes. It invokes
notion.page.create.prepare as governed_notion_requester, whose 0.2.0 binding
requires approval, and expects approval_required. notion_change_approver then
issues a one-time grant through POST /anip/approval_grants, and the requester
invokes again with the same parameters and the top-level approval_grant. The
Notion adapter creates the page only on that granted invocation.
"""
from __future__ import annotations

import json
import os
import time

from fastapi.testclient import TestClient
from notion_governed_fronting_showcase.app import create_app

REQUESTER_KEY = "smoke-requester"
APPROVER_KEY = "smoke-change-approver"
SMOKE_KEYS = {
    REQUESTER_KEY: "human:live-notion-smoke|actor_id=governed_notion_requester",
    APPROVER_KEY: "human:live-notion-approver|actor_id=notion_change_approver",
}
CAPABILITY_ID = "notion.page.create.prepare"


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def _token(client: TestClient, key: str, scope: list[str]) -> str:
    response = client.post(
        "/anip/tokens",
        headers={"Authorization": f"Bearer {key}"},
        json={"capability": CAPABILITY_ID, "scope": scope, "subject": "agent:live-notion-approved-page"},
    )
    response.raise_for_status()
    return response.json()["token"]


def _invoke(client: TestClient, params: dict, approval_grant: str | None = None) -> dict:
    body: dict = {"parameters": params}
    if approval_grant:
        body["approval_grant"] = approval_grant
    token = _token(client, REQUESTER_KEY, [CAPABILITY_ID])
    return client.post(f"/anip/invoke/{CAPABILITY_ID}", headers={"Authorization": f"Bearer {token}"}, json=body).json()


def main() -> None:
    workspace_scope = _require_env("NOTION_WORKSPACE_SCOPE")
    parent_id = _require_env("NOTION_PARENT_PAGE_ID")
    _require_env("NOTION_TOKEN")
    if os.getenv("ANIP_NOTION_ALLOW_MUTATION", "").lower() != "true":
        raise RuntimeError("ANIP_NOTION_ALLOW_MUTATION=true is required for approved page smoke")
    os.environ.setdefault("ANIP_NOTION_ALLOWED_WORKSPACES", workspace_scope)
    os.environ.setdefault("ANIP_NOTION_ALLOWED_PARENTS", parent_id)
    os.environ["ANIP_API_KEYS_JSON"] = json.dumps(SMOKE_KEYS)
    client = TestClient(create_app())

    params = {
        "parent_id": parent_id,
        "title": f"ANIP approved Notion page through generated service at {int(time.time())}",
        "content_summary": "Created by explicit ANIP Notion approved-page smoke.",
    }
    first = _invoke(client, params)
    failure = first.get("failure") or {}
    approval_request_id = (failure.get("approval_required") or {}).get("approval_request_id")
    if first.get("success") is not False or failure.get("type") != "approval_required" or not approval_request_id:
        raise AssertionError(f"expected approval_required with an approval_request_id, got {first}")

    approver_token = _token(client, APPROVER_KEY, [f"approver:{CAPABILITY_ID}"])
    grant = client.post(
        "/anip/approval_grants",
        headers={"Authorization": f"Bearer {approver_token}"},
        json={"approval_request_id": approval_request_id, "grant_type": "one_time"},
    ).json()
    if not grant.get("grant_id"):
        raise AssertionError(f"approval grant was not issued: {grant}")

    sent = _invoke(client, params, approval_grant=grant["grant_id"])
    result = sent.get("result") or {}
    if not sent.get("success") or result.get("execution_status") != "completed" or result.get("mutation_performed") is not True:
        raise AssertionError(f"expected approved page creation to complete, got {sent}")
    print(
        json.dumps(
            {
                "workspace_scope": workspace_scope,
                "approval_request_id": approval_request_id,
                "approval_grant_id": grant["grant_id"],
                "created_page": result.get("created_page"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
