import os

import pytest
from fastapi.testclient import TestClient

from jira_governed_fronting_showcase.app import create_app
from jira_governed_fronting_showcase.runtime_target import GENERATED_CAPABILITY_METADATA


def _jira_env_present() -> bool:
    return all(os.getenv(name) for name in ("JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN"))


def _jira_mutation_enabled() -> bool:
    return _jira_env_present() and os.getenv("ANIP_JIRA_ALLOW_MUTATION", "").lower() == "true"


def _issue_token(client: TestClient, capability_id: str, scope: list[str]) -> str:
    response = client.post(
        "/anip/tokens",
        headers={"Authorization": "Bearer dev-admin-key"},
        json={
            "capability": capability_id,
            "scope": scope,
            "subject": "agent:live-jira-test",
            "purpose_parameters": {"actor_id": "test", "source": "pytest"},
        },
    )
    assert response.status_code == 200
    return response.json()["token"]


@pytest.mark.skipif(not _jira_env_present(), reason="Jira env vars are not configured")
def test_live_jira_backlog_search_uses_bounded_project_query() -> None:
    client = TestClient(create_app())
    capability = next(item for item in GENERATED_CAPABILITY_METADATA if item["capability_id"] == "jira.backlog.search")
    token = _issue_token(client, capability["capability_id"], capability["minimum_scope"])
    response = client.post(
        "/anip/invoke/jira.backlog.search",
        headers={"Authorization": f"Bearer {token}"},
        json={"parameters": {"project_key": "SCRUM", "query": "Task", "limit": 10}},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    result = payload["result"]
    assert result["execution_status"] == "completed"
    assert result["jql"].startswith('project = "SCRUM"')
    assert "ORDER BY created DESC" in result["jql"]
    assert result["result"]["count"] >= 1
    assert all(issue["project_key"] == "SCRUM" for issue in result["result"]["issues"])


@pytest.mark.skipif(not _jira_env_present(), reason="Jira env vars are not configured")
def test_live_jira_bug_prepare_uses_metadata_without_mutation() -> None:
    client = TestClient(create_app())
    capability = next(item for item in GENERATED_CAPABILITY_METADATA if item["capability_id"] == "jira.bug.prepare")
    token = _issue_token(client, capability["capability_id"], capability["minimum_scope"])
    response = client.post(
        "/anip/invoke/jira.bug.prepare",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "parameters": {
                "project_key": "SCRUM",
                "summary": "ANIP governed bug preview",
                "description": "This is a live metadata-backed preview and must not create a Jira issue.",
                "severity": "sev3",
                "labels": ["anip", "fronting-demo"],
            }
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    result = payload["result"]
    assert result["execution_status"] == "prepared"
    assert result["approval_required"] is True
    assert result["mutation_performed"] is False
    assert result["jira_metadata"]["selected_issue_type"]["name"] == "Bug"
    request = result["create_issue_request"]
    assert request["method"] == "POST"
    assert request["path"] == "/rest/api/3/issue"
    fields = request["body"]["fields"]
    assert fields["project"]["key"] == "SCRUM"
    assert fields["issuetype"]["id"] == result["jira_metadata"]["selected_issue_type"]["id"]
    assert fields["summary"] == "ANIP governed bug preview"
    assert fields["labels"] == ["anip", "fronting-demo"]


@pytest.mark.skipif(not _jira_env_present(), reason="Jira env vars are not configured")
def test_live_jira_bug_prepare_accepts_approval_grant_without_mutation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANIP_JIRA_ALLOW_MUTATION", raising=False)
    client = TestClient(create_app())
    capability = next(item for item in GENERATED_CAPABILITY_METADATA if item["capability_id"] == "jira.bug.prepare")
    token = _issue_token(client, capability["capability_id"], capability["minimum_scope"])
    parameters = {
        "project_key": "SCRUM",
        "summary": "ANIP governed bug approval preview",
        "description": "This validates the approval grant path without creating a Jira issue.",
        "severity": "sev3",
        "labels": ["anip", "fronting-demo"],
        "request_execution_approval": True,
    }
    approval_response = client.post(
        "/anip/invoke/jira.bug.prepare",
        headers={"Authorization": f"Bearer {token}"},
        json={"parameters": parameters},
    )
    assert approval_response.status_code == 400
    approval_request_id = approval_response.json()["failure"]["approval_required"]["approval_request_id"]

    approver_token = _issue_token(
        client,
        capability["capability_id"],
        [*capability["minimum_scope"], "approver:jira.bug.prepare"],
    )
    grant_response = client.post(
        "/anip/approval_grants",
        headers={"Authorization": f"Bearer {approver_token}"},
        json={"approval_request_id": approval_request_id, "grant_type": "one_time"},
    )
    assert grant_response.status_code == 200, grant_response.text

    continuation = client.post(
        "/anip/invoke/jira.bug.prepare",
        headers={"Authorization": f"Bearer {token}"},
        json={"parameters": parameters, "approval_grant": grant_response.json()["grant_id"]},
    )
    assert continuation.status_code == 200
    result = continuation.json()["result"]
    assert result["execution_status"] == "prepared"
    assert result["mutation_performed"] is False
    assert result["approval_grant"]["approval_request_id"] == approval_request_id


@pytest.mark.skipif(not _jira_mutation_enabled(), reason="Jira mutation env flag is not enabled")
def test_live_jira_bug_create_requires_anip_approval_grant() -> None:
    client = TestClient(create_app())
    capability = next(item for item in GENERATED_CAPABILITY_METADATA if item["capability_id"] == "jira.bug.prepare")
    token = _issue_token(client, capability["capability_id"], capability["minimum_scope"])
    parameters = {
        "project_key": "SCRUM",
        "summary": "ANIP governed bug create smoke",
        "description": "Created by explicit ANIP Jira mutation smoke test.",
        "severity": "sev4",
        "labels": ["anip", "fronting-demo", "mutation-smoke"],
        "request_execution_approval": True,
    }
    approval_response = client.post(
        "/anip/invoke/jira.bug.prepare",
        headers={"Authorization": f"Bearer {token}"},
        json={"parameters": parameters},
    )
    assert approval_response.status_code == 400
    approval_payload = approval_response.json()
    assert approval_payload["success"] is False
    approval_request_id = approval_payload["failure"]["approval_required"]["approval_request_id"]

    approver_token = _issue_token(
        client,
        capability["capability_id"],
        [*capability["minimum_scope"], "approver:jira.bug.prepare"],
    )
    grant_response = client.post(
        "/anip/approval_grants",
        headers={"Authorization": f"Bearer {approver_token}"},
        json={"approval_request_id": approval_request_id, "grant_type": "one_time"},
    )
    assert grant_response.status_code == 200, grant_response.text
    approval_grant = grant_response.json()["grant_id"]

    response = client.post(
        "/anip/invoke/jira.bug.prepare",
        headers={"Authorization": f"Bearer {token}"},
        json={"parameters": parameters, "approval_grant": approval_grant},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    result = payload["result"]
    assert result["execution_status"] == "completed"
    assert result["mutation_performed"] is True
    assert result["created_issue"]["key"].startswith("SCRUM-")
