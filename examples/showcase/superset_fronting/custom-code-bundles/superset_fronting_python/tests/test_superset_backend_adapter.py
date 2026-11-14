from __future__ import annotations

import asyncio

import pytest

from {{ANIP_PYTHON_MODULE_NAME}} import backend_adapter as adapter_module


def _capability(capability_id: str) -> dict:
    return {"capability_id": capability_id}


def _plan() -> dict:
    return {
        "selected_binding": {"backend_kind": "native_api"},
        "semantic_input": {"workspace_scope": "local"},
        "adapter_input": {},
        "backend_input_contract": {},
        "unresolved_required_backend_inputs": [],
    }


def test_missing_credentials_returns_backend_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SUPERSET_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("SUPERSET_USERNAME", raising=False)
    monkeypatch.delenv("SUPERSET_PASSWORD", raising=False)
    result = asyncio.run(async_execute(_capability("superset.analytics.discover_context"), _plan(), {}))
    assert result["execution_status"] == "backend_error"
    assert result["superset_error"]["error"] == "missing_superset_credentials"


def test_discover_context_reads_bounded_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPERSET_ACCESS_TOKEN", "token")

    def fake_request(_method: str, path: str, *_args, **_kwargs) -> dict:
        if "/dataset/" in path:
            return {"result": {"data": [{"id": 1, "table_name": "birth_names"}]}}
        return {"result": {"data": []}}

    monkeypatch.setattr(adapter_module, "_request_json", fake_request)
    result = asyncio.run(
        async_execute(
            _capability("superset.analytics.discover_context"),
            _plan(),
            {"workspace_scope": "local", "query": "birth", "limit": 5},
        )
    )
    assert result["execution_status"] == "completed"
    assert result["result"]["count"] == 1


def test_discover_context_reads_every_catalog_for_asset_type_all(monkeypatch: pytest.MonkeyPatch) -> None:
    # "all" is asset_type's declared default, so it is what a call without
    # asset_type carries; it must not filter out every endpoint.
    monkeypatch.setenv("SUPERSET_ACCESS_TOKEN", "token")
    paths: list[str] = []

    def fake_request(_method: str, path: str, *_args, **_kwargs) -> dict:
        paths.append(path)
        kind = path.split("/")[3]
        return {"result": {"data": [{"id": 1, "table_name" if kind == "dataset" else "slice_name" if kind == "chart" else "dashboard_title": f"{kind} one"}]}}

    monkeypatch.setattr(adapter_module, "_request_json", fake_request)
    result = asyncio.run(
        async_execute(
            _capability("superset.analytics.discover_context"),
            _plan(),
            {"workspace_scope": "local", "asset_type": "all", "limit": 5},
        )
    )
    assert result["execution_status"] == "completed"
    assert [item["asset_type"] for item in result["result"]["items"]] == ["dataset", "chart", "dashboard"]
    assert [path.split("?")[0] for path in paths] == ["/api/v1/dataset/", "/api/v1/chart/", "/api/v1/dashboard/"]


def test_discovery_endpoints_per_asset_type() -> None:
    every = ["dataset", "chart", "dashboard"]
    assert [kind for kind, _ in adapter_module.discovery_endpoints("all")] == every
    assert [kind for kind, _ in adapter_module.discovery_endpoints("")] == every
    assert [kind for kind, _ in adapter_module.discovery_endpoints("chart")] == ["chart"]
    # metric and dimension are declared values without a Superset list endpoint.
    assert adapter_module.discovery_endpoints("metric") == []


def test_chart_preview_never_saves_chart(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPERSET_ACCESS_TOKEN", "token")
    result = asyncio.run(
        async_execute(
            _capability("superset.chart.preview.create"),
            _plan(),
            {"dataset_ref": "1", "metric": "count", "visualization_type": "bar"},
        )
    )
    assert result["execution_status"] == "prepared"
    assert result["approval_required"] is True
    assert result["mutation_performed"] is False
    assert result["superset_request"]["body"]["save_chart"] is False


def test_dataset_allowlist_restricts_unlisted_dataset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPERSET_ACCESS_TOKEN", "token")
    monkeypatch.setenv("ANIP_SUPERSET_ALLOWED_DATASETS", "allowed")
    result = asyncio.run(
        async_execute(
            _capability("superset.analytics.answer_question"),
            _plan(),
            {"question": "What changed?", "dataset_ref": "blocked"},
        )
    )
    assert result["execution_status"] == "restricted"


async def async_execute(capability: dict, plan: dict, params: dict, ctx: object | None = None) -> dict:
    return await adapter_module.backend_adapter.execute(capability, plan, params, ctx)
