from __future__ import annotations

import asyncio
import os

import pytest

from notion_governed_fronting_showcase import backend_adapter as adapter_module


def _capability(capability_id: str) -> dict:
    return {"capability_id": capability_id}


def _plan() -> dict:
    return {
        "selected_binding": {"backend_kind": "native_api"},
        "semantic_input": {"workspace_scope": "anip"},
        "adapter_input": {},
        "backend_input_contract": {},
        "unresolved_required_backend_inputs": [],
    }


class _Ctx:
    approval_grant = {"grant_id": "grant_1", "approval_request_id": "apr_1", "grant_type": "one_time"}


def test_missing_token_returns_backend_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NOTION_TOKEN", raising=False)
    result = asyncio.run(async_execute(_capability("notion.workspace.search_context"), _plan(), {}))
    assert result["execution_status"] == "backend_error"
    assert result["notion_error"]["error"] == "missing_notion_token"


def test_search_workspace_returns_bounded_results(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NOTION_TOKEN", "token")
    monkeypatch.delenv("ANIP_NOTION_ALLOWED_WORKSPACES", raising=False)
    monkeypatch.setattr(adapter_module, "_notion_request_json", lambda *_args, **_kwargs: _search_payload())
    result = asyncio.run(
        async_execute(
            _capability("notion.workspace.search_context"),
            _plan(),
            {"workspace_scope": "anip", "query": "roadmap", "limit": 5},
        )
    )
    assert result["execution_status"] == "completed"
    assert result["result"]["count"] == 1


def test_prepare_page_creation_stops_without_mutation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NOTION_TOKEN", "token")
    monkeypatch.delenv("ANIP_NOTION_ALLOWED_PARENTS", raising=False)
    monkeypatch.delenv("ANIP_NOTION_ALLOW_MUTATION", raising=False)
    result = asyncio.run(
        async_execute(
            _capability("notion.page.create.prepare"),
            _plan(),
            {"parent_id": "page_1", "title": "Hello", "content_summary": "Body"},
        )
    )
    assert result["execution_status"] == "prepared"
    assert result["approval_required"] is True
    assert result["mutation_performed"] is False
    assert result["notion_request"]["body"]["properties"]["title"]["title"][0]["text"]["content"] == "Hello"


def test_prepare_page_creation_with_grant_and_flag_creates_page(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []

    def fake_request(method: str, path: str, *_args, **_kwargs) -> dict:
        calls.append((method, path))
        return {"object": "page", "id": "page_created", "url": "https://notion.so/page_created", "properties": {}}

    monkeypatch.setenv("NOTION_TOKEN", "token")
    monkeypatch.setenv("ANIP_NOTION_ALLOW_MUTATION", "true")
    monkeypatch.delenv("ANIP_NOTION_ALLOWED_PARENTS", raising=False)
    monkeypatch.setattr(adapter_module, "_notion_request_json", fake_request)
    result = asyncio.run(
        async_execute(
            _capability("notion.page.create.prepare"),
            _plan(),
            {"parent_id": "page_1", "title": "Hello", "content_summary": "Body"},
            _Ctx(),
        )
    )
    assert result["execution_status"] == "completed"
    assert result["mutation_performed"] is True
    assert result["created_page"]["id"] == "page_created"
    assert ("POST", "/pages") in calls


def test_workspace_allowlist_restricts_unlisted_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NOTION_TOKEN", "token")
    monkeypatch.setenv("ANIP_NOTION_ALLOWED_WORKSPACES", "allowed")
    result = asyncio.run(
        async_execute(
            _capability("notion.workspace.search_context"),
            _plan(),
            {"workspace_scope": "anip", "query": "roadmap"},
        )
    )
    assert result["execution_status"] == "restricted"


@pytest.mark.skipif(
    not (os.getenv("NOTION_TOKEN") and os.getenv("NOTION_DATABASE_ID") and os.getenv("NOTION_DATA_SOURCE_ID")),
    reason="Notion live database credentials are not configured",
)
def test_live_database_query_uses_configured_data_source(monkeypatch: pytest.MonkeyPatch) -> None:
    database_id = os.environ["NOTION_DATABASE_ID"]
    data_source_id = os.environ["NOTION_DATA_SOURCE_ID"]
    monkeypatch.setenv("ANIP_NOTION_ALLOWED_DATABASES", database_id)
    monkeypatch.setenv("ANIP_NOTION_ALLOWED_DATA_SOURCES", data_source_id)
    result = asyncio.run(
        async_execute(
            _capability("notion.database.query_context"),
            _plan(),
            {"database_id": database_id, "limit": 5},
        )
    )
    assert result["execution_status"] == "completed"
    assert result["result"]["database_id"] == database_id
    assert result["result"]["data_source_id"] == data_source_id


def _search_payload() -> dict:
    return {
        "results": [
            {
                "object": "page",
                "id": "page_1",
                "url": "https://notion.so/page_1",
                "properties": {"Name": {"type": "title", "title": [{"plain_text": "Roadmap"}]}},
            }
        ]
    }


async def async_execute(capability: dict, plan: dict, params: dict, ctx: object | None = None) -> dict:
    return await adapter_module.backend_adapter.execute(capability, plan, params, ctx)
