from __future__ import annotations

import asyncio

import pytest

from {{ANIP_PYTHON_MODULE_NAME}} import backend_adapter as adapter_module


def _capability(capability_id: str) -> dict:
    return {"capability_id": capability_id}


def _plan() -> dict:
    return {
        "selected_binding": {"backend_kind": "native_api"},
        "semantic_input": {"owner": "acme", "repo": "demo"},
        "adapter_input": {},
        "backend_input_contract": {},
        "unresolved_required_backend_inputs": [],
    }


class _Ctx:
    approval_grant = {"grant_id": "grant_1", "approval_request_id": "apr_1", "grant_type": "one_time"}


def test_missing_token_returns_backend_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    result = asyncio.run(async_execute(_capability("github.repo.search_context"), _plan(), {}))
    assert result["execution_status"] == "backend_error"
    assert result["github_error"]["error"] == "missing_github_token"


def test_prepare_issue_stops_without_mutation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.delenv("ANIP_GITHUB_ALLOW_MUTATION", raising=False)
    monkeypatch.setattr(adapter_module, "_github_request_json", lambda *_args, **_kwargs: _repo_payload())
    result = asyncio.run(
        async_execute(
            _capability("github.issue.prepare"),
            _plan(),
            {"owner": "acme", "repo": "demo", "title": "Hello", "body": "Body"},
        )
    )
    assert result["execution_status"] == "prepared"
    assert result["approval_required"] is True
    assert result["mutation_performed"] is False
    assert result["github_request"]["body"]["title"] == "Hello"


def test_prepare_issue_with_grant_and_flag_creates_issue(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []

    def fake_request(method: str, path: str, *_args, **_kwargs) -> dict:
        calls.append((method, path))
        if method == "POST":
            return {"number": 42, "html_url": "https://github.test/acme/demo/issues/42", "state": "open"}
        return _repo_payload()

    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.setenv("ANIP_GITHUB_ALLOW_MUTATION", "true")
    monkeypatch.setattr(adapter_module, "_github_request_json", fake_request)
    result = asyncio.run(
        async_execute(
            _capability("github.issue.prepare"),
            _plan(),
            {"owner": "acme", "repo": "demo", "title": "Hello", "body": "Body"},
            _Ctx(),
        )
    )
    assert result["execution_status"] == "completed"
    assert result["mutation_performed"] is True
    assert result["created_issue"]["number"] == 42
    assert ("POST", "/repos/acme/demo/issues") in calls


def test_repo_allowlist_restricts_unlisted_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.setenv("ANIP_GITHUB_ALLOWED_REPOS", "acme/allowed")
    result = asyncio.run(
        async_execute(
            _capability("github.repo.search_context"),
            _plan(),
            {"owner": "acme", "repo": "demo", "query": "is:issue"},
        )
    )
    assert result["execution_status"] == "restricted"


def _repo_payload() -> dict:
    return {
        "name": "demo",
        "default_branch": "main",
        "private": False,
        "html_url": "https://github.test/acme/demo",
        "owner": {"login": "acme"},
    }


async def async_execute(capability: dict, plan: dict, params: dict, ctx: object | None = None) -> dict:
    return await adapter_module.backend_adapter.execute(capability, plan, params, ctx)
