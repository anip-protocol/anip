import os

import pytest
from fastapi.testclient import TestClient

from slack_governed_fronting_showcase.app import create_app
from slack_governed_fronting_showcase.runtime_target import GENERATED_CAPABILITY_METADATA


def _slack_env_present() -> bool:
    return all(os.getenv(name) for name in ("SLACK_BOT_TOKEN", "SLACK_CHANNEL_ID"))


def _slack_send_enabled() -> bool:
    return _slack_env_present() and os.getenv("ANIP_SLACK_ALLOW_SEND", "").lower() == "true"


def _issue_token(client: TestClient, capability_id: str, scope: list[str]) -> str:
    response = client.post(
        "/anip/tokens",
        headers={"Authorization": "Bearer dev-admin-key"},
        json={
            "capability": capability_id,
            "scope": scope,
            "subject": "agent:live-slack-test",
            "purpose_parameters": {"actor_id": "test", "source": "pytest"},
        },
    )
    assert response.status_code == 200
    return response.json()["token"]


@pytest.mark.skipif(not _slack_env_present(), reason="Slack env vars are not configured")
def test_live_slack_channel_read_context_is_bounded() -> None:
    client = TestClient(create_app())
    capability = next(item for item in GENERATED_CAPABILITY_METADATA if item["capability_id"] == "slack.channel.read_context")
    token = _issue_token(client, capability["capability_id"], capability["minimum_scope"])
    response = client.post(
        "/anip/invoke/slack.channel.read_context",
        headers={"Authorization": f"Bearer {token}"},
        json={"parameters": {"channel_id": os.environ["SLACK_CHANNEL_ID"], "limit": 5}},
    )
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["execution_status"] == "completed"
    assert result["result"]["channel_id"] == os.environ["SLACK_CHANNEL_ID"]
    assert result["result"]["count"] <= 5


@pytest.mark.skipif(not _slack_env_present(), reason="Slack env vars are not configured")
def test_live_slack_message_prepare_without_send() -> None:
    client = TestClient(create_app())
    capability = next(item for item in GENERATED_CAPABILITY_METADATA if item["capability_id"] == "slack.message.prepare")
    token = _issue_token(client, capability["capability_id"], capability["minimum_scope"])
    response = client.post(
        "/anip/invoke/slack.message.prepare",
        headers={"Authorization": f"Bearer {token}"},
        json={"parameters": {"channel_id": os.environ["SLACK_CHANNEL_ID"], "text": "ANIP governed Slack message preview"}},
    )
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["execution_status"] == "prepared"
    assert result["approval_required"] is True
    assert result["mutation_performed"] is False
    assert result["post_message_request"]["body"]["channel"] == os.environ["SLACK_CHANNEL_ID"]


@pytest.mark.skipif(not _slack_env_present(), reason="Slack env vars are not configured")
def test_live_slack_message_prepare_accepts_approval_grant_without_send(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANIP_SLACK_ALLOW_SEND", raising=False)
    client = TestClient(create_app())
    capability = next(item for item in GENERATED_CAPABILITY_METADATA if item["capability_id"] == "slack.message.prepare")
    token = _issue_token(client, capability["capability_id"], capability["minimum_scope"])
    parameters = {
        "channel_id": os.environ["SLACK_CHANNEL_ID"],
        "text": "ANIP governed Slack message approval preview",
        "request_send_approval": True,
    }
    approval_response = client.post(
        "/anip/invoke/slack.message.prepare",
        headers={"Authorization": f"Bearer {token}"},
        json={"parameters": parameters},
    )
    assert approval_response.status_code == 400
    approval_request_id = approval_response.json()["failure"]["approval_required"]["approval_request_id"]

    approver_token = _issue_token(
        client,
        capability["capability_id"],
        [*capability["minimum_scope"], "approver:slack.message.prepare"],
    )
    grant_response = client.post(
        "/anip/approval_grants",
        headers={"Authorization": f"Bearer {approver_token}"},
        json={"approval_request_id": approval_request_id, "grant_type": "one_time"},
    )
    assert grant_response.status_code == 200, grant_response.text

    continuation = client.post(
        "/anip/invoke/slack.message.prepare",
        headers={"Authorization": f"Bearer {token}"},
        json={"parameters": parameters, "approval_grant": grant_response.json()["grant_id"]},
    )
    assert continuation.status_code == 200
    result = continuation.json()["result"]
    assert result["execution_status"] == "prepared"
    assert result["mutation_performed"] is False
    assert result["approval_grant"]["approval_request_id"] == approval_request_id


@pytest.mark.skipif(not _slack_send_enabled(), reason="Slack send env flag is not enabled")
def test_live_slack_message_send_requires_anip_approval_grant() -> None:
    client = TestClient(create_app())
    capability = next(item for item in GENERATED_CAPABILITY_METADATA if item["capability_id"] == "slack.message.prepare")
    token = _issue_token(client, capability["capability_id"], capability["minimum_scope"])
    parameters = {
        "channel_id": os.environ["SLACK_CHANNEL_ID"],
        "text": "ANIP governed Slack send smoke",
        "request_send_approval": True,
    }
    approval_response = client.post(
        "/anip/invoke/slack.message.prepare",
        headers={"Authorization": f"Bearer {token}"},
        json={"parameters": parameters},
    )
    assert approval_response.status_code == 400
    approval_request_id = approval_response.json()["failure"]["approval_required"]["approval_request_id"]

    approver_token = _issue_token(
        client,
        capability["capability_id"],
        [*capability["minimum_scope"], "approver:slack.message.prepare"],
    )
    grant_response = client.post(
        "/anip/approval_grants",
        headers={"Authorization": f"Bearer {approver_token}"},
        json={"approval_request_id": approval_request_id, "grant_type": "one_time"},
    )
    assert grant_response.status_code == 200, grant_response.text

    response = client.post(
        "/anip/invoke/slack.message.prepare",
        headers={"Authorization": f"Bearer {token}"},
        json={"parameters": parameters, "approval_grant": grant_response.json()["grant_id"]},
    )
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["execution_status"] == "completed"
    assert result["mutation_performed"] is True
    assert result["posted_message"]["ts"]
