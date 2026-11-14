"""Live read/preview smoke for a generated GitLab fronting Python service.

Run from the generated Python service directory.

Expected environment:
- GITLAB_TOKEN
- GITLAB_PROJECT_ID, for example group/project

The smoke never mutates GitLab: it sets ANIP_GITLAB_ALLOW_MUTATION=false. It
authenticates over HTTP through the generated service's ANIP_API_KEYS_JSON,
which it sets itself. Package 0.2.0 declares no policy bindings and no
approval-gated capability, so every authenticated principal may invoke every
capability and write-adjacent capabilities return previews without a grant.
The smoke checks that the package still has no bindings (a package that adds
them needs actor-specific keys here), and that an unknown API key is refused.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from importlib import import_module
from pathlib import Path
from typing import Any


def _generated_roots() -> list[str]:
    cwd = Path.cwd()
    cwd_text = str(cwd)
    if cwd_text.startswith("/private/tmp/"):
        return ["/tmp/" + cwd_text.removeprefix("/private/tmp/")]
    return [str(cwd)]


def _ensure_generated_pythonpath() -> None:
    required = [path for root in _generated_roots() for path in (str(Path(root) / "src"), root)]
    existing = [item for item in os.getenv("PYTHONPATH", "").split(os.pathsep) if item]
    missing = [item for item in required if item not in existing]
    if missing and os.getenv("ANIP_GITLAB_SMOKE_REEXEC") != "1":
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join([*required, *existing])
        env["ANIP_GITLAB_SMOKE_REEXEC"] = "1"
        raise SystemExit(subprocess.run([sys.executable, *sys.argv], env=env, check=False).returncode)
    for root in reversed(_generated_roots()):
        for path in (Path(root), Path(root) / "src"):
            text = str(path)
            if text not in sys.path:
                sys.path.insert(0, text)


_ensure_generated_pythonpath()


def _project_parts(project_id: str) -> tuple[str, str]:
    if "/" not in project_id:
        raise RuntimeError("GITLAB_PROJECT_ID must be a namespace/project path for the governed ANIP inputs")
    namespace, project = project_id.rsplit("/", 1)
    return namespace, project


SMOKE_KEY = "smoke-gitlab-operator"
SMOKE_KEYS = {SMOKE_KEY: "human:live-gitlab-smoke|actor_id=gitlab_operator"}


def _generated_module() -> str:
    return os.getenv("ANIP_GITLAB_GENERATED_MODULE", "").strip() or _discover_generated_module()


def _discover_generated_module() -> str:
    for root in _generated_roots():
        src = Path(root) / "src"
        for candidate in src.glob("*/app.py"):
            if candidate.parent.name.endswith(".egg-info"):
                continue
            return candidate.parent.name
    return "gitlab_governed_fronting_showcase"


def _issue_token(client: Any, key: str, capability_id: str) -> Any:
    return client.post(
        "/anip/tokens",
        headers={"Authorization": f"Bearer {key}"},
        json={"capability": capability_id, "scope": [capability_id], "subject": "agent:live-gitlab-smoke"},
    )


def _invoke(client: Any, capability_id: str, parameters: dict[str, Any]) -> dict[str, Any]:
    token_response = _issue_token(client, SMOKE_KEY, capability_id)
    token_response.raise_for_status()
    response = client.post(
        f"/anip/invoke/{capability_id}",
        headers={"Authorization": f"Bearer {token_response.json()['token']}"},
        json={"parameters": parameters},
    )
    payload = response.json()
    if not payload.get("success"):
        raise RuntimeError(payload)
    return payload["result"]


def main() -> None:
    project_id = os.environ["GITLAB_PROJECT_ID"]
    namespace, project = _project_parts(project_id)
    os.environ.setdefault("ANIP_GITLAB_ALLOWED_PROJECTS", project_id)
    os.environ["ANIP_GITLAB_ALLOW_MUTATION"] = "false"
    os.environ["ANIP_API_KEYS_JSON"] = json.dumps(SMOKE_KEYS)

    cases: dict[str, dict[str, Any]] = {
        "gitlab.project.search_context": {
            "parameters": {"namespace": namespace, "project": project, "query": "issue", "limit": 5},
            "expected_status": "completed",
            "expect_mutation": None,
        },
        "gitlab.issue.prepare": {
            "parameters": {
                "namespace": namespace,
                "project": project,
                "title": "ANIP governed GitLab issue preview",
                "body": "Preview only. This smoke must not create a GitLab issue.",
            },
            "expected_status": "prepared",
            "expect_mutation": False,
        },
        "gitlab.pipeline.trigger.request": {
            "parameters": {"namespace": namespace, "project": project, "pipeline_ref": "preview-only", "ref": "main"},
            "expected_status": "prepared",
            "expect_mutation": False,
        },
        "gitlab.release_notes.prepare": {
            "parameters": {"namespace": namespace, "project": project, "range": "HEAD", "audience": "internal"},
            "expected_status": "completed",
            "expect_mutation": False,
        },
    }

    from fastapi.testclient import TestClient

    module_name = _generated_module()
    bindings = import_module(f"{module_name}.runtime_target").RUNTIME_TARGET.get("policy_bindings") or []
    if bindings:
        raise AssertionError(
            f"{module_name} declares {len(bindings)} runtime policy bindings; give this smoke API keys for the actors they select"
        )
    with TestClient(import_module(f"{module_name}.app").create_app()) as client:
        summary: dict[str, dict[str, Any]] = {}
        for capability_id, case in cases.items():
            result = _invoke(client, capability_id, case["parameters"])
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
                "gitlab_action": result.get("gitlab_action"),
            }
        unknown_key = _issue_token(client, "smoke-unknown-key", "gitlab.project.search_context")
        if unknown_key.status_code != 401:
            raise AssertionError(f"expected an unknown API key to be refused with 401, got {unknown_key.status_code}: {unknown_key.text}")

    print(json.dumps({
        "project_id": project_id,
        "capabilities_tested": len(summary),
        "results": summary,
        "refusals": [{"check": "unknown API key", "status": unknown_key.status_code}],
    }, indent=2))


if __name__ == "__main__":
    main()
