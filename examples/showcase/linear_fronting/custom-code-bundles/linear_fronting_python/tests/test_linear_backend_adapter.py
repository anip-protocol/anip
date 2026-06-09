from __future__ import annotations

import asyncio

import pytest

from linear_governed_fronting_showcase import backend_adapter as adapter_module


def _capability(capability_id: str) -> dict:
    return {"capability_id": capability_id}


def _plan() -> dict:
    return {
        "selected_binding": {"backend_kind": "native_api"},
        "semantic_input": {"team_key": "ANIP"},
        "adapter_input": {},
        "backend_input_contract": {},
        "unresolved_required_backend_inputs": [],
    }


class _Ctx:
    approval_grant = {"grant_id": "grant_1", "approval_request_id": "apr_1", "grant_type": "one_time"}


def test_missing_token_returns_backend_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LINEAR_API_KEY", raising=False)
    result = asyncio.run(async_execute(_capability("linear.issue.search_context"), _plan(), {}))
    assert result["execution_status"] == "backend_error"
    assert result["linear_error"]["error"] == "missing_linear_api_key"


def test_prepare_issue_stops_without_mutation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LINEAR_API_KEY", "token")
    monkeypatch.delenv("ANIP_LINEAR_ALLOW_MUTATION", raising=False)
    monkeypatch.setattr(adapter_module, "_linear_graphql", lambda *_args, **_kwargs: _team_payload())
    result = asyncio.run(
        async_execute(
            _capability("linear.issue.prepare"),
            _plan(),
            {"team_key": "ANIP", "title": "Hello", "description": "Body"},
        )
    )
    assert result["execution_status"] == "prepared"
    assert result["approval_required"] is True
    assert result["mutation_performed"] is False
    assert result["linear_request"]["input"]["title"] == "Hello"


def test_prepare_issue_with_grant_and_flag_creates_issue(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_graphql(_token: str, query: str, _variables: dict | None = None) -> dict:
        calls.append(query)
        if "mutation CreateIssue" in query:
            return {"data": {"issueCreate": {"success": True, "issue": {"id": "i1", "identifier": "ANIP-1", "url": "https://linear.app/anip/issue/ANIP-1", "state": {"name": "Todo"}}}}}
        return _team_payload()

    monkeypatch.setenv("LINEAR_API_KEY", "token")
    monkeypatch.setenv("ANIP_LINEAR_ALLOW_MUTATION", "true")
    monkeypatch.setattr(adapter_module, "_linear_graphql", fake_graphql)
    result = asyncio.run(
        async_execute(
            _capability("linear.issue.prepare"),
            _plan(),
            {"team_key": "ANIP", "title": "Hello", "description": "Body"},
            _Ctx(),
        )
    )
    assert result["execution_status"] == "completed"
    assert result["mutation_performed"] is True
    assert result["created_issue"]["identifier"] == "ANIP-1"
    assert any("mutation CreateIssue" in query for query in calls)


def test_team_allowlist_restricts_unlisted_team(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LINEAR_API_KEY", "token")
    monkeypatch.setenv("ANIP_LINEAR_ALLOWED_TEAMS", "ENG")
    result = asyncio.run(
        async_execute(
            _capability("linear.issue.search_context"),
            _plan(),
            {"team_key": "ANIP", "query": "issue"},
        )
    )
    assert result["execution_status"] == "restricted"


def _team_payload() -> dict:
    return {"data": {"teams": {"nodes": [{"id": "team_1", "key": "ANIP", "name": "ANIP"}]}}}


async def async_execute(capability: dict, plan: dict, params: dict, ctx: object | None = None) -> dict:
    return await adapter_module.backend_adapter.execute(capability, plan, params, ctx)
