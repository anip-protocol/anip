import os

import pytest
from fastapi.testclient import TestClient

from github_governed_fronting_showcase.app import create_app
from github_governed_fronting_showcase.runtime_target import GENERATED_CAPABILITY_METADATA


def _github_env_present() -> bool:
    return all(os.getenv(name) for name in ("GITHUB_TOKEN", "GITHUB_OWNER", "GITHUB_REPO"))


def _github_mutation_enabled() -> bool:
    return _github_env_present() and os.getenv("ANIP_GITHUB_ALLOW_MUTATION", "").lower() == "true"


def _repo_params() -> dict[str, str]:
    return {"owner": os.getenv("GITHUB_OWNER", ""), "repo": os.getenv("GITHUB_REPO", "")}


def _issue_token(client: TestClient, capability_id: str, scope: list[str]) -> str:
    response = client.post(
        "/anip/tokens",
        headers={"Authorization": "Bearer dev-admin-key"},
        json={
            "capability": capability_id,
            "scope": scope,
            "subject": "agent:live-github-test",
            "purpose_parameters": {"actor_id": "test", "source": "pytest"},
        },
    )
    assert response.status_code == 200
    return response.json()["token"]


@pytest.mark.skipif(not _github_env_present(), reason="GitHub env vars are not configured")
def test_live_github_repo_search_uses_bounded_repo_query() -> None:
    client = TestClient(create_app())
    capability = next(item for item in GENERATED_CAPABILITY_METADATA if item["capability_id"] == "github.repo.search_context")
    token = _issue_token(client, capability["capability_id"], capability["minimum_scope"])
    response = client.post(
        "/anip/invoke/github.repo.search_context",
        headers={"Authorization": f"Bearer {token}"},
        json={"parameters": {**_repo_params(), "query": "is:issue", "limit": 5}},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    result = payload["result"]
    assert result["execution_status"] == "completed"
    assert result["github_query"].startswith(f"repo:{os.environ['GITHUB_OWNER']}/{os.environ['GITHUB_REPO']}")
    assert result["result"]["count"] <= 5


@pytest.mark.skipif(not _github_env_present(), reason="GitHub env vars are not configured")
def test_live_github_issue_prepare_uses_metadata_without_mutation() -> None:
    client = TestClient(create_app())
    capability = next(item for item in GENERATED_CAPABILITY_METADATA if item["capability_id"] == "github.issue.prepare")
    token = _issue_token(client, capability["capability_id"], capability["minimum_scope"])
    response = client.post(
        "/anip/invoke/github.issue.prepare",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "parameters": {
                **_repo_params(),
                "title": "ANIP governed GitHub issue preview",
                "body": "This is a live metadata-backed preview and must not create a GitHub issue.",
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
    assert result["github_metadata"]["owner"] == os.environ["GITHUB_OWNER"]
    assert result["github_metadata"]["repo"] == os.environ["GITHUB_REPO"]
    request = result["create_issue_request"]
    assert request["method"] == "POST"
    assert request["path"] == f"/repos/{os.environ['GITHUB_OWNER']}/{os.environ['GITHUB_REPO']}/issues"
    assert request["body"]["title"] == "ANIP governed GitHub issue preview"


@pytest.mark.skipif(not _github_env_present(), reason="GitHub env vars are not configured")
def test_live_github_issue_prepare_accepts_approval_grant_without_mutation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANIP_GITHUB_ALLOW_MUTATION", raising=False)
    client = TestClient(create_app())
    capability = next(item for item in GENERATED_CAPABILITY_METADATA if item["capability_id"] == "github.issue.prepare")
    token = _issue_token(client, capability["capability_id"], capability["minimum_scope"])
    parameters = {
        **_repo_params(),
        "title": "ANIP governed GitHub issue approval preview",
        "body": "This validates the approval grant path without creating a GitHub issue.",
        "labels": ["anip", "fronting-demo"],
        "request_execution_approval": True,
    }
    approval_response = client.post(
        "/anip/invoke/github.issue.prepare",
        headers={"Authorization": f"Bearer {token}"},
        json={"parameters": parameters},
    )
    assert approval_response.status_code == 400
    approval_request_id = approval_response.json()["failure"]["approval_required"]["approval_request_id"]

    approver_token = _issue_token(
        client,
        capability["capability_id"],
        [*capability["minimum_scope"], "approver:github.issue.prepare"],
    )
    grant_response = client.post(
        "/anip/approval_grants",
        headers={"Authorization": f"Bearer {approver_token}"},
        json={"approval_request_id": approval_request_id, "grant_type": "one_time"},
    )
    assert grant_response.status_code == 200, grant_response.text

    continuation = client.post(
        "/anip/invoke/github.issue.prepare",
        headers={"Authorization": f"Bearer {token}"},
        json={"parameters": parameters, "approval_grant": grant_response.json()["grant_id"]},
    )
    assert continuation.status_code == 200
    result = continuation.json()["result"]
    assert result["execution_status"] == "prepared"
    assert result["mutation_performed"] is False
    assert result["approval_grant"]["approval_request_id"] == approval_request_id


@pytest.mark.skipif(not _github_mutation_enabled(), reason="GitHub mutation env flag is not enabled")
def test_live_github_issue_create_requires_anip_approval_grant() -> None:
    client = TestClient(create_app())
    capability = next(item for item in GENERATED_CAPABILITY_METADATA if item["capability_id"] == "github.issue.prepare")
    token = _issue_token(client, capability["capability_id"], capability["minimum_scope"])
    parameters = {
        **_repo_params(),
        "title": "ANIP governed GitHub issue create smoke",
        "body": "Created by explicit ANIP GitHub mutation smoke test.",
        "labels": ["anip", "fronting-demo", "mutation-smoke"],
        "request_execution_approval": True,
    }
    approval_response = client.post(
        "/anip/invoke/github.issue.prepare",
        headers={"Authorization": f"Bearer {token}"},
        json={"parameters": parameters},
    )
    assert approval_response.status_code == 400
    approval_request_id = approval_response.json()["failure"]["approval_required"]["approval_request_id"]

    approver_token = _issue_token(
        client,
        capability["capability_id"],
        [*capability["minimum_scope"], "approver:github.issue.prepare"],
    )
    grant_response = client.post(
        "/anip/approval_grants",
        headers={"Authorization": f"Bearer {approver_token}"},
        json={"approval_request_id": approval_request_id, "grant_type": "one_time"},
    )
    assert grant_response.status_code == 200, grant_response.text

    response = client.post(
        "/anip/invoke/github.issue.prepare",
        headers={"Authorization": f"Bearer {token}"},
        json={"parameters": parameters, "approval_grant": grant_response.json()["grant_id"]},
    )
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["execution_status"] == "completed"
    assert result["mutation_performed"] is True
    assert result["created_issue"]["number"]
