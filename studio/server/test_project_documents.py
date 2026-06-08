"""Tests for project document storage and runtime status."""

import base64
from urllib.error import URLError


def test_runtime_status_reports_deterministic_by_default(client):
    resp = client.get("/api/runtime-status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["studio_api_reachable"] is True
    assert data["assistant_provider"] == "deterministic"
    assert data["llm_enabled"] is False
    assert data["llm_ready"] is False
    assert data["read_only_mode"] is False


def test_settings_reports_default_registry_policy(client):
    resp = client.get("/api/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert data["assistant"]["assistant_provider"] == "deterministic"
    simulator = data["simulator"]
    assert simulator["simulator_provider"] == "openai"
    assert simulator["simulator_model"] == "gpt-5.4-mini"
    assert simulator["provider_source"] == "default"
    assert simulator["model_source"] == "default"
    assert simulator["api_key_configured"] is False
    assert simulator["api_key_source"] == "none"
    registry = data["registry"]
    assert registry["registry_url"] == "http://127.0.0.1:8200"
    assert registry["registry_url_source"] == "default"
    assert registry["required_registry_mode"] is None
    assert registry["required_registry_mode_source"] == "unset"
    assert registry["trusted_registry_key_id"] is None
    assert registry["trusted_registry_key_id_source"] == "unset"
    assert registry["publish_token_configured"] is False
    assert registry["publish_token_source"] == "none"
    assert registry["allows_development_registry"] is True
    assert registry["key_pinned"] is False
    assert "Development Registry mode is allowed" in registry["warning"]


def test_settings_reports_production_registry_policy_from_env(client, monkeypatch):
    monkeypatch.setenv("STUDIO_REGISTRY_URL", "https://registry.example.com/")
    monkeypatch.setenv("STUDIO_REGISTRY_REQUIRED_MODE", "production")
    monkeypatch.setenv("STUDIO_REGISTRY_TRUSTED_KEY_ID", "registry-prod-2026-04")
    monkeypatch.setenv("STUDIO_REGISTRY_PUBLISH_TOKEN", "env-publish-token")

    resp = client.get("/api/settings")
    assert resp.status_code == 200
    registry = resp.json()["registry"]
    assert registry["registry_url"] == "https://registry.example.com"
    assert registry["registry_url_source"] == "env"
    assert registry["required_registry_mode"] == "production"
    assert registry["required_registry_mode_source"] == "env"
    assert registry["trusted_registry_key_id"] == "registry-prod-2026-04"
    assert registry["trusted_registry_key_id_source"] == "env"
    assert registry["publish_token_configured"] is True
    assert registry["publish_token_source"] == "env"
    assert registry["allows_development_registry"] is False
    assert registry["key_pinned"] is True
    assert registry["warning"] is None


def test_settings_persists_local_registry_policy(client):
    updated = client.put(
        "/api/settings",
        json={
            "registry": {
                "registry_url": "http://127.0.0.1:8300/",
                "required_registry_mode": "production",
                "trusted_registry_key_id": "registry-prod-local",
                "registry_publish_token": "stored-publish-token",
            },
        },
    )
    assert updated.status_code == 200, updated.text
    registry = updated.json()["registry"]
    assert registry["registry_url"] == "http://127.0.0.1:8300"
    assert registry["registry_url_source"] == "stored"
    assert registry["required_registry_mode"] == "production"
    assert registry["required_registry_mode_source"] == "stored"
    assert registry["trusted_registry_key_id"] == "registry-prod-local"
    assert registry["trusted_registry_key_id_source"] == "stored"
    assert registry["publish_token_configured"] is True
    assert registry["publish_token_source"] == "stored"
    assert registry["allows_development_registry"] is False
    assert registry["key_pinned"] is True
    assert registry["warning"] is None

    fetched = client.get("/api/settings")
    assert fetched.status_code == 200
    assert fetched.json()["registry"]["trusted_registry_key_id"] == "registry-prod-local"

    cleared = client.put(
        "/api/settings",
        json={"registry": {"clear_registry_publish_token": True}},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["registry"]["publish_token_configured"] is False


def test_settings_rejects_invalid_registry_mode(client):
    updated = client.put(
        "/api/settings",
        json={"registry": {"required_registry_mode": "staging"}},
    )
    assert updated.status_code == 422


def test_registry_publish_proxy_requires_studio_publish_token(client):
    resp = client.post(
        "/api/registry/publications",
        json={
            "package_id": "work-item-fronting",
            "package_version": "0.2.0",
        },
    )
    assert resp.status_code == 400
    assert "publish token" in resp.json()["detail"]


def test_registry_publish_proxy_sends_bearer_token(client, monkeypatch):
    from studio.server import app as studio_app

    captured = {}

    class FakeResponse:
        status = 201

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return b'{"ok": true}'

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["authorization"] = request.get_header("Authorization")
        captured["body"] = request.data
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(studio_app, "urlopen", fake_urlopen)
    configured = client.put(
        "/api/settings",
        json={
            "registry": {
                "registry_url": "http://registry.test:8200",
                "registry_publish_token": "stored-publish-token",
            },
        },
    )
    assert configured.status_code == 200, configured.text

    project = client.post(
        "/api/projects",
        json={"id": "work-item-fronting", "name": "Work Item Fronting"},
    )
    assert project.status_code == 201, project.text
    saved_revision = {
        "revision_number": 5,
        "revision_artifact_id": "developer-r5",
        "previous_revision_artifact_id": None,
        "saved_at": "2026-05-10T00:00:00Z",
    }
    current_definition = {
        "artifact_type": "developer_definition",
        "compiled_contract_identity": {"signature": "sha256:contract"},
        "saved_revision": saved_revision,
        "source_inputs": {"product_revision_artifact_id": "product-r3", "product_revision_number": 3},
    }
    revision = client.post(
        "/api/projects/work-item-fronting/pm-artifacts",
        json={
            "id": "developer-r5",
            "title": "Developer Definition Revision 5",
            "data": {**current_definition, "artifact_type": "developer_definition_revision"},
        },
    )
    assert revision.status_code == 201, revision.text
    current = client.post(
        "/api/projects/work-item-fronting/pm-artifacts",
        json={
            "id": "work-item-fronting-developer-definition",
            "title": "Developer Definition",
            "data": current_definition,
        },
    )
    assert current.status_code == 201, current.text
    payload = {
        "package_id": "work-item-fronting",
        "package_version": "0.2.0",
        "project_ref": "work-item-fronting",
        "product_revision_ref": "product-r3",
        "developer_revision_ref": "developer-r5",
        "contract_signature": "sha256:contract",
        "lineage": {
            "project_ref": "work-item-fronting",
            "product_revision": {"ref": "product-r3", "artifact_id": "product-r3", "revision_number": 3},
            "developer_revision": {
                "ref": "developer-r5",
                "artifact_id": "developer-r5",
                "revision_number": 5,
                "contract_signature": "sha256:contract",
            },
        },
        "manifest": {"name": "Work Item Fronting", "anip_spec_version": "anip/0.24"},
        "service_definition": {
            "artifact_type": "developer_definition",
            "compiled_contract_identity": {"signature": "sha256:contract"},
        },
        "recommended_lock": {},
    }

    resp = client.post(
        "/api/registry/publications",
        json=payload,
    )
    assert resp.status_code == 201, resp.text
    assert captured["url"] == "http://registry.test:8200/registry-api/v1/publications"
    assert captured["authorization"] == "Bearer stored-publish-token"
    assert b"work-item-fronting" in captured["body"]


def test_registry_template_publish_proxy_sends_bearer_token(client, monkeypatch):
    from studio.server import app as studio_app

    captured = {}

    class FakeResponse:
        status = 201

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return b'{"ok": true}'

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["authorization"] = request.get_header("Authorization")
        captured["body"] = request.data
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(studio_app, "urlopen", fake_urlopen)
    configured = client.put(
        "/api/settings",
        json={
            "registry": {
                "registry_url": "http://registry.test:8200",
                "registry_publish_token": "stored-publish-token",
            },
        },
    )
    assert configured.status_code == 200, configured.text

    resp = client.post(
        "/api/registry/templates",
        json={
            "template_id": "notion-fronting-starter",
            "template_version": "0.1.0",
        },
    )
    assert resp.status_code == 201, resp.text
    assert captured["url"] == "http://registry.test:8200/registry-api/v1/templates"
    assert captured["authorization"] == "Bearer stored-publish-token"
    assert b"notion-fronting-starter" in captured["body"]


def test_registry_template_read_proxy_does_not_require_publish_token(client, monkeypatch):
    from studio.server import app as studio_app

    captured = {}

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return b'{"items": [{"template_id": "notion-fronting-starter"}]}'

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["authorization"] = request.get_header("Authorization")
        captured["method"] = request.get_method()
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(studio_app, "urlopen", fake_urlopen)
    configured = client.put(
        "/api/settings",
        json={
            "registry": {
                "registry_url": "http://registry.test:8200",
                "clear_registry_publish_token": True,
            },
        },
    )
    assert configured.status_code == 200, configured.text

    resp = client.get("/api/registry/templates?domain=notion")
    assert resp.status_code == 200, resp.text
    assert captured["url"] == "http://registry.test:8200/registry-api/v1/templates?domain=notion"
    assert captured["authorization"] is None
    assert captured["method"] == "GET"
    assert resp.json()["items"][0]["template_id"] == "notion-fronting-starter"


def test_registry_template_list_degrades_when_registry_unavailable(client, monkeypatch):
    from studio.server import app as studio_app

    def fake_urlopen(request, timeout):
        raise URLError("connection refused")

    monkeypatch.setattr(studio_app, "urlopen", fake_urlopen)

    resp = client.get("/api/registry/templates")

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["items"] == []
    assert "Registry templates are unavailable" in data["warning"]


def test_registry_template_download_proxy_quotes_path_parts(client, monkeypatch):
    from studio.server import app as studio_app

    captured = {}

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return b'{"schema": "anip-starter-template-package/v0"}'

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        return FakeResponse()

    monkeypatch.setattr(studio_app, "urlopen", fake_urlopen)
    configured = client.put(
        "/api/settings",
        json={"registry": {"registry_url": "http://registry.test:8200"}},
    )
    assert configured.status_code == 200, configured.text

    resp = client.get("/api/registry/templates/notion template/0.1.0/download")
    assert resp.status_code == 200, resp.text
    assert captured["url"] == "http://registry.test:8200/registry-api/v1/templates/notion%20template/0.1.0/download"


def test_settings_infers_production_registry_policy_without_key_pin(client, monkeypatch):
    reset = client.put(
        "/api/settings",
        json={"registry": {"registry_url": None, "required_registry_mode": None, "trusted_registry_key_id": None, "clear_registry_publish_token": True}},
    )
    assert reset.status_code == 200, reset.text
    monkeypatch.setenv("STUDIO_MODE", "production")

    resp = client.get("/api/settings")
    assert resp.status_code == 200
    registry = resp.json()["registry"]
    assert registry["required_registry_mode"] == "production"
    assert registry["required_registry_mode_source"] == "production-default"
    assert registry["production_mode_detected"] is True
    assert registry["allows_development_registry"] is False
    assert registry["key_pinned"] is False
    assert "key is not pinned" in registry["warning"]


def test_runtime_status_reports_env_managed_provider_and_read_only(client, monkeypatch):
    monkeypatch.setenv("STUDIO_ASSISTANT_PROVIDER", "openai")
    monkeypatch.setenv("STUDIO_ASSISTANT_MODEL", "gpt-5.4-mini")
    monkeypatch.setenv("OPENAI_API_KEY", "env-secret")
    monkeypatch.setenv("STUDIO_READ_ONLY", "true")
    monkeypatch.setenv("STUDIO_READ_ONLY_REASON", "Hosted demo mode.")

    resp = client.get("/api/runtime-status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["assistant_provider"] == "openai"
    assert data["assistant_model"] == "gpt-5.4-mini"
    assert data["api_key_configured"] is True
    assert data["api_key_source"] == "env"
    assert data["provider_source"] == "env"
    assert data["model_source"] == "env"
    assert data["read_only_mode"] is True
    assert data["read_only_reason"] == "Hosted demo mode."


def test_runtime_config_persists_local_settings_without_echoing_api_key(client):
    updated = client.put(
        "/api/runtime-config",
        json={
            "assistant_provider": "openai",
            "assistant_model": "gpt-5.4",
            "assistant_api_key": "stored-secret",
            "temperature": 0.4,
            "timeout_seconds": 45,
            "strict": True,
        },
    )
    assert updated.status_code == 200, updated.text
    updated_data = updated.json()
    assert updated_data["assistant_provider"] == "openai"
    assert updated_data["assistant_model"] == "gpt-5.4"
    assert updated_data["assistant_base_url"] is None
    assert updated_data["api_key_configured"] is True
    assert updated_data["stored_api_key_configured"] is True
    assert updated_data["provider_source"] == "stored"
    assert updated_data["model_source"] == "stored"
    assert updated_data["base_url_source"] == "default"
    assert updated_data["api_key_source"] == "stored"
    assert "assistant_api_key" not in updated_data

    fetched = client.get("/api/runtime-config")
    assert fetched.status_code == 200
    fetched_data = fetched.json()
    assert fetched_data["api_key_configured"] is True
    assert fetched_data["stored_api_key_configured"] is True
    assert "assistant_api_key" not in fetched_data

    timeout_only = client.put("/api/runtime-config", json={"timeout_seconds": 90})
    assert timeout_only.status_code == 200, timeout_only.text
    timeout_data = timeout_only.json()
    assert timeout_data["assistant_provider"] == "openai"
    assert timeout_data["assistant_model"] == "gpt-5.4"
    assert timeout_data["assistant_base_url"] is None
    assert timeout_data["timeout_seconds"] == 90
    assert timeout_data["api_key_configured"] is True
    assert timeout_data["stored_api_key_configured"] is True


def test_simulator_config_persists_local_settings_without_echoing_api_key(client):
    updated = client.put(
        "/api/simulator-config",
        json={
            "simulator_provider": "openai",
            "simulator_model": "gpt-5.4-mini",
            "simulator_api_key": "stored-simulator-secret",
            "temperature": 0,
            "timeout_seconds": 30,
        },
    )
    assert updated.status_code == 200, updated.text
    updated_data = updated.json()
    assert updated_data["simulator_provider"] == "openai"
    assert updated_data["simulator_model"] == "gpt-5.4-mini"
    assert updated_data["simulator_base_url"] is None
    assert updated_data["api_key_configured"] is True
    assert updated_data["stored_api_key_configured"] is True
    assert updated_data["provider_source"] == "stored"
    assert updated_data["model_source"] == "stored"
    assert updated_data["base_url_source"] == "default"
    assert updated_data["api_key_source"] == "stored"
    assert "simulator_api_key" not in updated_data

    fetched = client.get("/api/settings")
    assert fetched.status_code == 200
    simulator = fetched.json()["simulator"]
    assert simulator["api_key_configured"] is True
    assert simulator["stored_api_key_configured"] is True
    assert "simulator_api_key" not in simulator

    cleared = client.put("/api/settings", json={"simulator": {"clear_simulator_api_key": True}})
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["simulator"]["api_key_configured"] is False


def test_simulator_config_reports_env_managed_provider(client, monkeypatch):
    monkeypatch.setenv("STUDIO_SIMULATOR_PROVIDER", "openai")
    monkeypatch.setenv("STUDIO_SIMULATOR_MODEL", "gpt-5.4-mini")
    monkeypatch.setenv("STUDIO_SIMULATOR_API_KEY", "env-simulator-secret")

    resp = client.get("/api/settings")
    assert resp.status_code == 200
    simulator = resp.json()["simulator"]
    assert simulator["simulator_provider"] == "openai"
    assert simulator["simulator_model"] == "gpt-5.4-mini"
    assert simulator["api_key_configured"] is True
    assert simulator["api_key_source"] == "env"
    assert simulator["provider_source"] == "env"
    assert simulator["model_source"] == "env"


def test_agent_consumption_simulator_endpoint_returns_model_output(client, monkeypatch):
    from studio.server import app as studio_app

    captured = {}

    async def fake_run(payload):
        captured["payload"] = payload
        return {
            "artifact_type": "agent_consumption_simulation_model_output",
            "schema_version": "anip-agent-consumption-simulator/v0",
            "simulator_runtime": {
                "provider": "openai",
                "model": "gpt-5.4-mini",
            },
            "cases": [
                {
                    "probe_id": "probe-1",
                    "selected_capability_id": "demo.capability",
                    "actual_outcome": "clarification_required",
                    "parameter_plan": {},
                    "used_consumability_hints": ["required_context"],
                    "rationale": "Missing account context should clarify.",
                    "confidence": 0.82,
                },
            ],
            "summary": {"notes": "ok"},
        }

    monkeypatch.setattr(studio_app, "run_agent_consumption_simulation", fake_run)

    resp = client.post(
        "/api/agent-consumption-simulator/run",
        json={
            "project": {"id": "proj", "name": "Project"},
            "developer_definition": {},
            "readiness": {},
            "agent_consumability": {},
            "probes": [{"id": "probe-1"}],
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["simulator_runtime"]["model"] == "gpt-5.4-mini"
    assert data["cases"][0]["probe_id"] == "probe-1"
    assert captured["payload"]["probes"][0]["id"] == "probe-1"


def test_read_only_mode_blocks_mutating_api_routes(client, monkeypatch):
    from studio.server import app as studio_app

    monkeypatch.setenv("STUDIO_READ_ONLY", "true")

    async def fake_run(payload):
        return {
            "artifact_type": "agent_consumption_simulation_model_output",
            "schema_version": "anip-agent-consumption-simulator/v0",
            "simulator_runtime": {"provider": "openai", "model": "gpt-5.4-mini"},
            "cases": [],
            "summary": {},
        }

    monkeypatch.setattr(studio_app, "run_agent_consumption_simulation", fake_run)

    create_workspace = client.post(
        "/api/workspaces",
        json={"id": "ws-readonly", "name": "Blocked"},
    )
    assert create_workspace.status_code == 403

    update_config = client.put(
        "/api/runtime-config",
        json={"assistant_provider": "openai"},
    )
    assert update_config.status_code == 403

    update_simulator_config = client.put(
        "/api/simulator-config",
        json={"simulator_provider": "openai"},
    )
    assert update_simulator_config.status_code == 403

    simulator_run = client.post(
        "/api/agent-consumption-simulator/run",
        json={
            "developer_definition": {},
            "readiness": {},
            "agent_consumability": {},
            "probes": [],
        },
    )
    assert simulator_run.status_code == 403

    assistant_invoke = client.post(
        "/studio-assistant/anip/invoke/assistant.propose",
        json={"parameters": {}},
    )
    assert assistant_invoke.status_code == 403

    workbench_invoke = client.post(
        "/studio-workbench/anip/invoke/workbench.inspect",
        json={"parameters": {}},
    )
    assert workbench_invoke.status_code == 403

    validate_shape = client.post(
        "/api/validate-shape",
        json={"requirements": {}, "shape": {}, "scenario": {}},
    )
    assert validate_shape.status_code != 403

    validate_contract = client.post(
        "/api/validate",
        json={"requirements": {}, "proposal": {}, "scenario": {}},
    )
    assert validate_contract.status_code != 403

    arbitrary_patch = client.patch("/api/workspaces/ws-readonly", json={"name": "Still blocked"})
    assert arbitrary_patch.status_code == 403

    arbitrary_delete = client.delete("/api/workspaces/ws-readonly")
    assert arbitrary_delete.status_code == 403

    get_config = client.get("/api/runtime-config")
    assert get_config.status_code == 200
    assert get_config.json()["read_only_mode"] is True

    get_simulator_config = client.get("/api/simulator-config")
    assert get_simulator_config.status_code == 200
    assert get_simulator_config.json()["read_only_mode"] is True


def test_read_only_database_url_only_applies_in_read_only_mode(monkeypatch):
    from studio.server import app as studio_app

    monkeypatch.setenv("STUDIO_READ_ONLY_DATABASE_URL", "postgresql://readonly@db/anip")

    monkeypatch.setenv("STUDIO_READ_ONLY", "false")
    assert studio_app._read_only_database_url() == ""

    monkeypatch.setenv("STUDIO_READ_ONLY", "true")
    assert studio_app._read_only_database_url() == "postgresql://readonly@db/anip"


def test_project_document_roundtrip(client):
    client.post("/api/projects", json={"id": "proj-docs", "name": "Docs Project"})

    payload = {
        "id": "doc-1",
        "title": "Canonical business spec",
        "kind": "business_spec",
        "filename": "business-spec.md",
        "media_type": "text/markdown",
        "source_path": "docs/examples/gtm-showcase/business-spec.md",
        "content_base64": base64.b64encode(b"# Title\n\nA bounded business spec.\n").decode("ascii"),
    }
    created = client.post("/api/projects/proj-docs/documents", json=payload)
    assert created.status_code == 201, created.text
    row = created.json()
    assert row["id"] == "doc-1"
    assert row["kind"] == "business_spec"

    listed = client.get("/api/projects/proj-docs/documents")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == ["doc-1"]

    preview = client.get("/api/projects/proj-docs/documents/doc-1/preview")
    assert preview.status_code == 200
    assert "# Title" in preview.json()["content"]

    download = client.get("/api/projects/proj-docs/documents/doc-1/download")
    assert download.status_code == 200
    assert download.headers["content-type"].startswith("text/markdown")
    assert b"A bounded business spec." in download.content

    detail = client.get("/api/projects/proj-docs")
    assert detail.status_code == 200
    assert detail.json()["documents_count"] == 1
