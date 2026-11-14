from __future__ import annotations

import pytest

from github_governed_fronting_showcase import backend_adapter as adapter_module


def _capability() -> dict:
    return {"capability_id": "github.repo.search_context"}


def _plan() -> dict:
    return {
        "selected_binding": {"backend_kind": "native_api"},
        "semantic_input": {"owner": "acme", "repo": "demo"},
        "backend_input_contract": {},
    }


def _search(params: dict) -> dict:
    return adapter_module.DefaultBackendAdapter()._search_repository_context(_capability(), _plan(), params, "token")


@pytest.mark.parametrize(
    "query",
    ["repo:other/private", "bug REPO:other/private", "org:acme-private", "user: someone", "owner :someone", "label:bug -repo:x"],
)
def test_search_refuses_scope_qualifiers_in_query(monkeypatch: pytest.MonkeyPatch, query: str) -> None:
    calls: list[str] = []
    monkeypatch.setattr(adapter_module, "_github_request_json", lambda _method, path, *_a, **_k: calls.append(path) or {"items": []})
    result = _search({"owner": "acme", "repo": "demo", "query": query})
    assert result["execution_status"] == "restricted"
    assert result["repository"] == {"owner": "acme", "repo": "demo"}
    assert calls == []


def test_search_keeps_plain_query_terms(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(adapter_module, "_github_request_json", lambda *_a, **_k: {"items": [], "total_count": 0})
    result = _search({"owner": "acme", "repo": "demo", "query": "label:bug repository crash"})
    assert result["execution_status"] == "completed"
    assert result["github_query"] == "repo:acme/demo label:bug repository crash"


def test_search_drops_items_from_other_repositories(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "total_count": 3,
        "items": [
            {"number": 1, "title": "ours", "state": "open", "repository_url": "https://api.github.com/repos/Acme/Demo"},
            {"number": 2, "title": "theirs", "state": "open", "repository_url": "https://api.github.com/repos/other/private"},
            {"number": 3, "title": "no repository"},
        ],
    }
    monkeypatch.setattr(adapter_module, "_github_request_json", lambda *_a, **_k: payload)
    result = _search({"owner": "acme", "repo": "demo", "query": "crash"})
    assert result["execution_status"] == "completed"
    assert [item["number"] for item in result["result"]["items"]] == [1]
    assert result["result"]["total_count"] is None
