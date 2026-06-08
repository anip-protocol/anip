"""Tests for governed integration-fronting foundation endpoints."""

import os

os.environ.setdefault("DATABASE_URL", "postgresql://anip:anip@localhost:5432/anip_studio")


def test_create_governed_service_project_with_integration_profile(client):
    client.post("/api/workspaces", json={"id": "ws-fronting", "name": "Fronting"})
    response = client.post(
        "/api/projects",
        json={
            "id": "proj-fronting",
            "workspace_id": "ws-fronting",
            "name": "Jira Governance",
            "project_type": "governed_service_project",
            "integration_profile": {
                "kind": "native_api",
                "systems": [
                    {
                        "system_id": "jira",
                        "display_name": "Jira",
                        "backend_kind": "native_api",
                        "auth_mode": "service_delegated",
                        "connection_ref": "conn-jira-prod",
                    }
                ],
            },
        },
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["project_type"] == "governed_service_project"
    assert data["integration_profile"]["kind"] == "native_api"
    assert data["integration_profile"]["systems"][0]["system_id"] == "jira"


def test_workspace_connection_and_discovery_records_are_deterministic_metadata(client):
    client.post("/api/workspaces", json={"id": "ws-jira", "name": "Jira Workspace"})
    client.post(
        "/api/projects",
        json={
            "id": "proj-jira",
            "workspace_id": "ws-jira",
            "name": "Jira Governance",
            "project_type": "governed_service_project",
        },
    )
    connection = client.post(
        "/api/workspaces/ws-jira/connections",
        json={
            "id": "conn-jira-prod",
            "display_name": "Jira Production",
            "backend_kind": "native_api",
            "system_kind": "jira",
            "endpoint_ref": "jira-prod-base-url",
            "auth_mode": "service_delegated",
            "identity_provider_ref": "corp-sso",
            "secret_ref": "vault://anip/jira/service-account",
            "allowed_project_refs": ["proj-jira"],
        },
    )
    assert connection.status_code == 201, connection.text
    connection_data = connection.json()
    assert connection_data["secret_ref"] == "vault://anip/jira/service-account"
    assert connection_data["allowed_project_refs"] == ["proj-jira"]

    record = client.post(
        "/api/projects/proj-jira/integration-discovery-records",
        json={
            "id": "disc-create-issue",
            "connection_id": "conn-jira-prod",
            "operation_id": "jira.create_issue",
            "backend_kind": "native_api",
            "method": "POST",
            "path_template": "/rest/api/3/issue",
            "side_effect_level": "write",
            "input_schema_summary": {
                "required": ["project_key", "issue_type", "summary"],
                "optional": ["description", "priority", "labels", "assignee"],
            },
            "risk_notes": [
                "Creates a durable Jira issue.",
                "Must not be exposed directly as an agent-facing operation.",
            ],
        },
    )
    assert record.status_code == 201, record.text
    record_data = record.json()
    assert record_data["operation_id"] == "jira.create_issue"
    assert record_data["content_hash"]

    listed = client.get("/api/projects/proj-jira/integration-discovery-records")
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == "disc-create-issue"


def test_discovery_record_rejects_connection_outside_allowed_projects(client):
    client.post("/api/workspaces", json={"id": "ws-restricted", "name": "Restricted"})
    client.post("/api/projects", json={"id": "proj-allowed", "workspace_id": "ws-restricted", "name": "Allowed"})
    client.post("/api/projects", json={"id": "proj-denied", "workspace_id": "ws-restricted", "name": "Denied"})
    client.post(
        "/api/workspaces/ws-restricted/connections",
        json={
            "id": "conn-restricted",
            "display_name": "Restricted Jira",
            "backend_kind": "native_api",
            "auth_mode": "service_delegated",
            "allowed_project_refs": ["proj-allowed"],
        },
    )

    response = client.post(
        "/api/projects/proj-denied/integration-discovery-records",
        json={
            "id": "disc-denied",
            "connection_id": "conn-restricted",
            "operation_id": "jira.create_issue",
            "backend_kind": "native_api",
        },
    )
    assert response.status_code == 400
    assert "not allowed" in response.json()["detail"]


def test_seeded_issue_tracker_fronting_showcase_has_full_fronting_context(client):
    response = client.post("/api/seed")
    assert response.status_code == 200, response.text

    project = client.get("/api/projects/project-issue-tracker-fronting-showcase")
    assert project.status_code == 200
    project_data = project.json()
    assert project_data["project_type"] == "governed_service_project"
    assert project_data["integration_profile"]["kind"] == "hybrid"

    documents = client.get("/api/projects/project-issue-tracker-fronting-showcase/documents")
    assert documents.status_code == 200
    document_kinds = {item["kind"] for item in documents.json()}
    assert {"business_intent", "api_docs", "mcp_schema", "policy_source"}.issubset(document_kinds)

    connections = client.get("/api/workspaces/ws-issue-tracker-fronting/connections")
    assert connections.status_code == 200
    connection_ids = {item["id"] for item in connections.json()}
    assert {"conn-issue-tracker-native-api", "conn-issue-tracker-mcp"}.issubset(connection_ids)

    discovery = client.get("/api/projects/project-issue-tracker-fronting-showcase/integration-discovery-records")
    assert discovery.status_code == 200
    operation_ids = {item["operation_id"] for item in discovery.json()}
    assert {"issue_rest.create_issue", "issue_mcp.create_issue"}.issubset(operation_ids)

    pm_artifacts = client.get("/api/projects/project-issue-tracker-fronting-showcase/pm-artifacts")
    assert pm_artifacts.status_code == 200
    mappings = [
        item
        for item in pm_artifacts.json()
        if item["data"].get("artifact_type") == "integration_fronting_capability_mapping"
    ]
    assert len(mappings) == 4
    prepare_ticket = next(item for item in mappings if item["data"]["capability_id"] == "issue_tracker.prepare_ticket")
    assert [binding["backend_kind"] for binding in prepare_ticket["data"]["backend_bindings"]] == ["native_api", "mcp"]


def test_seeded_fronting_starter_projects_load_source_specs(client):
    response = client.post("/api/seed")
    assert response.status_code == 200, response.text

    projects = client.get("/api/projects", params={"workspace_id": "ws-anip-showcases"})
    assert projects.status_code == 200
    project_ids = {item["id"] for item in projects.json()}
    assert {
        "jira-fronting-starter",
        "github-fronting-starter",
        "slack-fronting-starter",
        "notion-fronting-starter",
        "linear-fronting-starter",
        "gitlab-fronting-starter",
        "superset-fronting-starter",
    }.issubset(project_ids)

    jira = client.get("/api/projects/jira-fronting-starter")
    assert jira.status_code == 200
    jira_data = jira.json()
    assert jira_data["project_type"] == "governed_service_project"
    assert jira_data["integration_profile"]["kind"] == "hybrid"
    assert [system["backend_kind"] for system in jira_data["integration_profile"]["systems"]] == [
        "native_api",
        "mcp",
    ]

    docs = client.get("/api/projects/jira-fronting-starter/documents")
    assert docs.status_code == 200
    doc_rows = docs.json()
    assert any(item["id"] == "doc-jira-fronting-source-spec" for item in doc_rows)
    assert any(item["id"] == "doc-jira-developer-evidence" for item in doc_rows)
    assert any(item["kind"] == "business_intent" for item in doc_rows)
    assert any(item.get("filename") == "jira-developer-evidence.template.md" for item in doc_rows)

    connections = client.get("/api/workspaces/ws-anip-showcases/connections")
    assert connections.status_code == 200
    connection_ids = {item["id"] for item in connections.json()}
    assert {"conn-jira-native", "conn-jira-mcp", "conn-github-native", "conn-slack-native", "conn-superset-native"}.issubset(
        connection_ids
    )
