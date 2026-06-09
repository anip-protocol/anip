"""Approved page-creation smoke for the Notion fronting showcase."""
from __future__ import annotations

import asyncio
import json
import os
import time

from anip_service.v023 import (
    new_approval_request_id,
    sha256_digest,
    utc_in_iso,
    utc_now_iso,
)
from notion_governed_fronting_showcase.app import create_service


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


async def main() -> None:
    workspace_scope = _require_env("NOTION_WORKSPACE_SCOPE")
    parent_id = _require_env("NOTION_PARENT_PAGE_ID")
    _require_env("NOTION_TOKEN")
    if os.getenv("ANIP_NOTION_ALLOW_MUTATION", "").lower() != "true":
        raise RuntimeError("ANIP_NOTION_ALLOW_MUTATION=true is required for approved page smoke")
    os.environ.setdefault("ANIP_NOTION_ALLOWED_WORKSPACES", workspace_scope)
    os.environ.setdefault("ANIP_NOTION_ALLOWED_PARENTS", parent_id)

    service = create_service()
    await service.start()
    try:
        capability_id = "notion.page.create.prepare"
        params = {
            "parent_id": parent_id,
            "title": f"ANIP approved Notion page through generated service at {int(time.time())}",
            "content_summary": "Created by explicit ANIP Notion approved-page smoke.",
        }
        token_response = await service.issue_token(
            "human:local-dev",
            {
                "subject": "agent:live-notion-approved-page",
                "scope": [capability_id],
                "capability": capability_id,
                "ttl_hours": 1,
            },
        )
        token = await service.resolve_bearer_token(token_response["token"])
        preview = await service.invoke(capability_id, token, params)
        preview_result = preview.get("result") or {}
        if preview_result.get("execution_status") != "prepared" or preview_result.get("mutation_performed") is not False:
            raise AssertionError(f"expected preview-only prepared result, got {preview}")

        capability = service._capabilities[capability_id]
        grant_policy = capability.declaration.grant_policy.model_dump()
        approval_request_id = new_approval_request_id()
        approval_request = {
            "approval_request_id": approval_request_id,
            "capability": capability_id,
            "scope": list(capability.declaration.minimum_scope),
            "requester": {"subject": token.subject, "root_principal": token.root_principal},
            "parent_invocation_id": preview.get("invocation_id"),
            "preview": preview_result,
            "preview_digest": sha256_digest(preview_result),
            "requested_parameters": params,
            "requested_parameters_digest": sha256_digest(params),
            "grant_policy": grant_policy,
            "status": "pending",
            "approver": None,
            "decided_at": None,
            "created_at": utc_now_iso(),
            "expires_at": utc_in_iso(grant_policy["expires_in_seconds"]),
        }
        await service._storage.store_approval_request(approval_request)
        grant = await service.issue_approval_grant(
            approval_request_id,
            "one_time",
            {"subject": "human:local-dev", "root_principal": "human:local-dev"},
        )
        sent = await service.invoke(capability_id, token, params, approval_grant=grant["grant_id"])
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
    finally:
        await service.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
