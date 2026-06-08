"""Live smoke for the Slack fronting showcase.

Expected environment:
- SLACK_BOT_TOKEN
- SLACK_CHANNEL_ID

Run after generating the Python service with the Slack custom bundle:

PYTHONPATH="<repo python packages>:<generated src>" python examples/showcase/slack_fronting/scripts/live_smoke.py
"""
from __future__ import annotations

import json
import os
import urllib.request

from fastapi.testclient import TestClient

from slack_governed_fronting_showcase.app import create_app


def slack_post(path: str, body: dict) -> dict:
    token = os.environ["SLACK_BOT_TOKEN"]
    request = urllib.request.Request(
        f"https://slack.com/api/{path}",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode())


def issue_token(client: TestClient, capability_id: str) -> str:
    response = client.post(
        "/anip/tokens",
        headers={"Authorization": "Bearer dev-admin-key"},
        json={
            "capability": capability_id,
            "scope": [capability_id],
            "subject": "agent:live-slack-smoke",
            "purpose_parameters": {"actor_id": "slack_fronting_consumer", "source": "live-smoke"},
        },
    )
    response.raise_for_status()
    return response.json()["token"]


def invoke(client: TestClient, capability_id: str, parameters: dict) -> dict:
    token = issue_token(client, capability_id)
    response = client.post(
        f"/anip/invoke/{capability_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"parameters": parameters},
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("success"):
        raise RuntimeError(payload)
    return payload["result"]


def main() -> None:
    channel_id = os.environ["SLACK_CHANNEL_ID"]
    os.environ.setdefault("ANIP_SLACK_ALLOWED_CHANNELS", channel_id)
    history = slack_post("conversations.history", {"channel": channel_id, "limit": 1})
    if not history.get("ok"):
        raise RuntimeError(history)
    messages = history.get("messages", [])
    thread_ts = (messages[0] or {}).get("thread_ts") or (messages[0] or {}).get("ts") if messages else None
    client = TestClient(create_app())

    cases = {
        "slack.channel.read_context": {
            "parameters": {"channel_id": channel_id, "limit": 5},
            "expected_status": "completed",
            "expect_mutation": None,
        },
        "slack.message.prepare": {
            "parameters": {"channel_id": channel_id, "text": "ANIP Slack fronting smoke preview"},
            "expected_status": "prepared",
            "expect_mutation": False,
        },
        "slack.incident_update.prepare": {
            "parameters": {
                "channel_id": channel_id,
                "incident_id": "INC-123",
                "status": "monitoring",
                "summary": "Preview an incident update without sending it.",
                "next_update_time": "in 30 minutes",
            },
            "expected_status": "prepared",
            "expect_mutation": False,
        },
        "slack.announcement.request": {
            "parameters": {
                "channel_id": channel_id,
                "announcement": "Preview a governed announcement without sending it.",
                "audience": "internal",
            },
            "expected_status": "prepared",
            "expect_mutation": False,
        },
    }
    if thread_ts:
        cases["slack.thread.summarize"] = {
            "parameters": {"channel_id": channel_id, "thread_ts": thread_ts, "focus": "smoke test", "limit": 10},
            "expected_status": "completed",
            "expect_mutation": None,
        }

    summary: dict[str, dict] = {}
    for capability_id, case in cases.items():
        result = invoke(client, capability_id, case["parameters"])
        execution_status = result.get("execution_status")
        expected_status = case["expected_status"]
        if execution_status != expected_status:
            raise AssertionError(f"{capability_id}: expected {expected_status}, got {execution_status}: {result}")
        expected_mutation = case["expect_mutation"]
        if expected_mutation is not None and result.get("mutation_performed") is not expected_mutation:
            raise AssertionError(f"{capability_id}: unexpected mutation posture: {result}")
        summary[capability_id] = {
            "execution_status": execution_status,
            "mutation_performed": result.get("mutation_performed"),
            "approval_required": result.get("approval_required"),
            "slack_action": result.get("slack_action"),
        }
        if capability_id in {"slack.channel.read_context", "slack.thread.summarize"}:
            summary[capability_id]["message_count"] = (result.get("result") or {}).get("count")

    print(json.dumps({"channel_id": channel_id, "capabilities_tested": len(summary), "results": summary}, indent=2))


if __name__ == "__main__":
    main()
