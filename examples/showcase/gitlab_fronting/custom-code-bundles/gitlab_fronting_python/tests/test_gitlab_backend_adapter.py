from __future__ import annotations

import asyncio
import os
from importlib import import_module

import pytest


def _adapter_module():
    module_name = os.getenv("ANIP_PYTHON_MODULE_NAME", "{{ANIP_PYTHON_MODULE_NAME}}").strip()
    if module_name.startswith("{{"):
        module_name = "gitlab_governed_fronting_showcase"
    return import_module(f"{module_name}.backend_adapter")


adapter_module = _adapter_module()


def _capability(capability_id: str) -> dict:
    return {"capability_id": capability_id}


def _plan() -> dict:
    return {
        "selected_binding": {"backend_kind": "native_api"},
        "semantic_input": {"namespace": "group", "project": "demo"},
        "adapter_input": {},
        "backend_input_contract": {},
        "unresolved_required_backend_inputs": [],
    }


class _Ctx:
    approval_grant = {"grant_id": "grant_1", "approval_request_id": "apr_1", "grant_type": "one_time"}


def test_missing_token_returns_backend_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITLAB_TOKEN", raising=False)
    result = asyncio.run(async_execute(_capability("gitlab.project.search_context"), _plan(), {}))
    assert result["execution_status"] == "backend_error"
    assert result["gitlab_error"]["error"] == "missing_gitlab_token"


def test_prepare_issue_stops_without_mutation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITLAB_TOKEN", "token")
    monkeypatch.delenv("ANIP_GITLAB_ALLOW_MUTATION", raising=False)
    monkeypatch.setattr(adapter_module, "_gitlab_request_json", lambda *_args, **_kwargs: _project_payload())
    result = asyncio.run(
        async_execute(
            _capability("gitlab.issue.prepare"),
            _plan(),
            {"namespace": "group", "project": "demo", "title": "Hello", "body": "Body"},
        )
    )
    assert result["execution_status"] == "prepared"
    assert result["approval_required"] is True
    assert result["mutation_performed"] is False
    assert result["gitlab_request"]["body"]["title"] == "Hello"


def test_prepare_issue_with_grant_and_flag_creates_issue(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []

    def fake_request(method: str, path: str, *_args, **_kwargs) -> dict:
        calls.append((method, path))
        if method == "POST":
            return {"iid": 42, "web_url": "https://gitlab.test/group/demo/-/issues/42", "state": "opened"}
        return _project_payload()

    monkeypatch.setenv("GITLAB_TOKEN", "token")
    monkeypatch.setenv("ANIP_GITLAB_ALLOW_MUTATION", "true")
    monkeypatch.setattr(adapter_module, "_gitlab_request_json", fake_request)
    result = asyncio.run(
        async_execute(
            _capability("gitlab.issue.prepare"),
            _plan(),
            {"namespace": "group", "project": "demo", "title": "Hello", "body": "Body"},
            _Ctx(),
        )
    )
    assert result["execution_status"] == "completed"
    assert result["mutation_performed"] is True
    assert result["created_issue"]["iid"] == 42
    assert ("POST", "/projects/group%2Fdemo/issues") in calls


def test_project_allowlist_restricts_unlisted_project(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITLAB_TOKEN", "token")
    monkeypatch.setenv("ANIP_GITLAB_ALLOWED_PROJECTS", "group/allowed")
    result = asyncio.run(
        async_execute(
            _capability("gitlab.project.search_context"),
            _plan(),
            {"namespace": "group", "project": "demo", "query": "issue"},
        )
    )
    assert result["execution_status"] == "restricted"


def _project_payload() -> dict:
    return {
        "id": 123,
        "path_with_namespace": "group/demo",
        "default_branch": "main",
        "visibility": "private",
        "web_url": "https://gitlab.test/group/demo",
    }


async def async_execute(capability: dict, plan: dict, params: dict, ctx: object | None = None) -> dict:
    return await adapter_module.backend_adapter.execute(capability, plan, params, ctx)
