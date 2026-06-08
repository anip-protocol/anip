"""Approved-send smoke for the Slack fronting showcase.

This test intentionally posts one message to Slack. Use only with a disposable
channel and a generated Python service that includes the Slack custom bundle.

Expected environment:
- SLACK_BOT_TOKEN
- SLACK_CHANNEL_ID
- ANIP_SLACK_ALLOW_SEND=true
"""
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
from slack_governed_fronting_showcase.app import create_service


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


async def main() -> None:
    channel_id = _require_env("SLACK_CHANNEL_ID")
    _require_env("SLACK_BOT_TOKEN")
    if os.getenv("ANIP_SLACK_ALLOW_SEND", "").lower() != "true":
        raise RuntimeError("ANIP_SLACK_ALLOW_SEND=true is required for approved-send smoke")
    os.environ.setdefault("ANIP_SLACK_ALLOWED_CHANNELS", channel_id)

    service = create_service()
    await service.start()
    try:
        capability_id = "slack.message.prepare"
        params = {
            "channel_id": channel_id,
            "text": f"ANIP approved Slack post through generated service at {int(time.time())}",
        }
        token_response = await service.issue_token(
            "human:local-dev",
            {
                "subject": "agent:live-slack-approved-send",
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

        # This smoke runs in-process so it can create the approval request
        # fixture before exercising the public continuation invocation.
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
            raise AssertionError(f"expected approved send to complete, got {sent}")
        print(
            json.dumps(
                {
                    "channel_id": channel_id,
                    "approval_request_id": approval_request_id,
                    "approval_grant_id": grant["grant_id"],
                    "posted_message": result.get("posted_message"),
                },
                indent=2,
            )
        )
    finally:
        await service.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
