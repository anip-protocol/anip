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


@pytest.mark.parametrize(
    "query",
    ["repo:other/private", "bug REPO:other/private", "org:acme-private", "user: someone", "owner :someone", "label:bug -repo:x"],
)
def test_search_refuses_scope_qualifiers_in_query(monkeypatch: pytest.MonkeyPatch, query: str) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    calls: list[str] = []
    monkeypatch.setattr(adapter_module, "_github_request_json", lambda _method, path, *_a, **_k: calls.append(path) or {"items": []})
    result = asyncio.run(
        async_execute(_capability("github.repo.search_context"), _plan(), {"owner": "acme", "repo": "demo", "query": query})
    )
    assert result["execution_status"] == "restricted"
    assert result["repository"] == {"owner": "acme", "repo": "demo"}
    assert calls == []


def test_search_keeps_plain_query_terms(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    paths: list[str] = []
    monkeypatch.setattr(adapter_module, "_github_request_json", lambda _method, path, *_a, **_k: paths.append(path) or {"items": [], "total_count": 0})
    result = asyncio.run(
        async_execute(_capability("github.repo.search_context"), _plan(), {"owner": "acme", "repo": "demo", "query": "label:bug repository crash"})
    )
    assert result["execution_status"] == "completed"
    assert result["github_query"] == "repo:acme/demo label:bug repository crash"


def test_search_drops_items_from_other_repositories(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    payload = {
        "total_count": 3,
        "items": [
            {"number": 1, "title": "ours", "state": "open", "repository_url": "https://api.github.com/repos/Acme/Demo"},
            {"number": 2, "title": "theirs", "state": "open", "repository_url": "https://api.github.com/repos/other/private"},
            {"number": 3, "title": "no repository"},
        ],
    }
    monkeypatch.setattr(adapter_module, "_github_request_json", lambda *_a, **_k: payload)
    result = asyncio.run(
        async_execute(_capability("github.repo.search_context"), _plan(), {"owner": "acme", "repo": "demo", "query": "crash"})
    )
    assert result["execution_status"] == "completed"
    assert [item["number"] for item in result["result"]["items"]] == [1]
    assert result["result"]["total_count"] is None


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
