"""Approved issue-creation smoke for the GitLab fronting showcase.

This test intentionally creates one GitLab issue. Use only with a disposable
project and a generated Python service that includes the GitLab custom bundle.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
from importlib import import_module
from pathlib import Path


def _generated_roots() -> list[str]:
    cwd = Path.cwd()
    cwd_text = str(cwd)
    if cwd_text.startswith("/private/tmp/"):
        return ["/tmp/" + cwd_text.removeprefix("/private/tmp/")]
    return [str(cwd)]


def ensure_generated_pythonpath() -> None:
    roots = _generated_roots()
    required = [path for root in roots for path in (str(Path(root) / "src"), root)]
    existing = [item for item in os.getenv("PYTHONPATH", "").split(os.pathsep) if item]
    missing = [item for item in required if item not in existing]
    if missing and os.getenv("ANIP_GITLAB_SMOKE_REEXEC") != "1":
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join([*required, *existing])
        env["ANIP_GITLAB_SMOKE_REEXEC"] = "1"
        raise SystemExit(subprocess.run([sys.executable, *sys.argv], env=env, check=False).returncode)


ensure_generated_pythonpath()


def ensure_generated_project_on_path() -> None:
    roots = _generated_roots()
    for root in reversed(roots):
        for path in (Path(root), Path(root) / "src"):
            text = str(path)
            if text not in sys.path:
                sys.path.insert(0, text)


ensure_generated_project_on_path()

from anip_service.v023 import (
    new_approval_request_id,
    sha256_digest,
    utc_in_iso,
    utc_now_iso,
)


def create_generated_service():
    module_name = os.getenv("ANIP_GITLAB_GENERATED_MODULE", "").strip() or _discover_generated_module()
    app_module = import_module(f"{module_name}.app")
    time.sleep(float(os.getenv("ANIP_GITLAB_SMOKE_READY_DELAY_SECONDS", "2")))
    return app_module.create_service()


def _discover_generated_module() -> str:
    for root in _generated_roots():
        src = Path(root) / "src"
        for candidate in src.glob("*/app.py"):
            if candidate.parent.name.endswith(".egg-info"):
                continue
            return candidate.parent.name
    return "gitlab_governed_fronting_showcase"


def _project_parts(project_id: str) -> tuple[str, str]:
    if "/" not in project_id:
        raise RuntimeError("GITLAB_PROJECT_ID must be a namespace/project path for the governed ANIP inputs")
    namespace, project = project_id.rsplit("/", 1)
    return namespace, project


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


async def main() -> None:
    project_id = _require_env("GITLAB_PROJECT_ID")
    namespace, project = _project_parts(project_id)
    _require_env("GITLAB_TOKEN")
    if os.getenv("ANIP_GITLAB_ALLOW_MUTATION", "").lower() != "true":
        raise RuntimeError("ANIP_GITLAB_ALLOW_MUTATION=true is required for approved issue smoke")
    os.environ.setdefault("ANIP_GITLAB_ALLOWED_PROJECTS", project_id)

    service = create_generated_service()
    await service.start()
    await asyncio.sleep(float(os.getenv("ANIP_GITLAB_SMOKE_READY_DELAY_SECONDS", "2")))
    try:
        capability_id = "gitlab.issue.prepare"
        params = {
            "namespace": namespace,
            "project": project,
            "title": f"ANIP approved GitLab issue through generated service at {int(time.time())}",
            "body": "Created by explicit ANIP GitLab approved-issue smoke.",
        }
        token_response = await service.issue_token(
            "human:local-dev",
            {
                "subject": "agent:live-gitlab-approved-issue",
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

        # In-process fixture creation lets the smoke exercise continuation with
        # a real stored approval request and reserved one-time grant.
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
                    "project_id": project_id,
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
