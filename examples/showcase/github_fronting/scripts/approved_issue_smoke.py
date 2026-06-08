"""Approved issue-creation smoke for the GitHub fronting showcase.

This test intentionally creates one GitHub issue. Use only with a disposable
repository and a generated Python service that includes the GitHub custom bundle.

Expected environment:
- GITHUB_TOKEN
- GITHUB_OWNER
- GITHUB_REPO
- ANIP_GITHUB_ALLOW_MUTATION=true
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
from github_governed_fronting_showcase.app import create_service


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


async def main() -> None:
    owner = _require_env("GITHUB_OWNER")
    repo = _require_env("GITHUB_REPO")
    _require_env("GITHUB_TOKEN")
    if os.getenv("ANIP_GITHUB_ALLOW_MUTATION", "").lower() != "true":
        raise RuntimeError("ANIP_GITHUB_ALLOW_MUTATION=true is required for approved issue smoke")
    os.environ.setdefault("ANIP_GITHUB_ALLOWED_REPOS", f"{owner}/{repo}")

    service = create_service()
    await service.start()
    try:
        capability_id = "github.issue.prepare"
        params = {
            "owner": owner,
            "repo": repo,
            "title": f"ANIP approved GitHub issue through generated service at {int(time.time())}",
            "body": "Created by explicit ANIP GitHub approved-issue smoke.",
        }
        token_response = await service.issue_token(
            "human:local-dev",
            {
                "subject": "agent:live-github-approved-issue",
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
            raise AssertionError(f"expected approved issue creation to complete, got {sent}")
        print(
            json.dumps(
                {
                    "repository": f"{owner}/{repo}",
                    "approval_request_id": approval_request_id,
                    "approval_grant_id": grant["grant_id"],
                    "created_issue": result.get("created_issue"),
                },
                indent=2,
            )
        )
    finally:
        await service.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
