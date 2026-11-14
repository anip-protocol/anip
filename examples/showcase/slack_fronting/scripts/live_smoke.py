"""Read-only live smoke for the Slack fronting showcase.

Expected environment:
- SLACK_BOT_TOKEN
- SLACK_CHANNEL_ID

The smoke never sends a Slack message: it sets ANIP_SLACK_ALLOW_SEND=false. It
authenticates through the generated service's ANIP_API_KEYS_JSON, which it sets
itself. Package 0.2.1 binds every capability to the collaborator actor and has
no binding or capability that requires approval, so the collaborator gets
reads and previews without a grant, and a principal without the collaborator
actor claim is refused. approved_send_smoke.py covers the granted send.

Run after generating the Python service with the Slack custom bundle:

PYTHONPATH="<repo python packages>:<generated src>" python examples/showcase/slack_fronting/scripts/live_smoke.py
"""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Any

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


# Package 0.2.1 binds every capability to the collaborator actor; a principal
# without that actor claim is refused.
LIVE_SMOKE_KEY = "live-slack-smoke-key"
SMOKE_KEYS = {
    LIVE_SMOKE_KEY: "human:live-slack-smoke|actor_id=collaborator",
    "smoke-no-actor": "human:live-slack-smoke",
    "smoke-unknown-actor": "human:live-slack-smoke|actor_id=slack_unknown_actor",
}
NO_BINDING_DETAIL = "No runtime policy binding matches the current actor for this capability."


def issue_token(client: TestClient, capability_id: str, key: str = LIVE_SMOKE_KEY) -> str:
    response = client.post(
        "/anip/tokens",
        headers={"Authorization": f"Bearer {key}"},
        json={
            "capability": capability_id,
            "scope": [capability_id],
            "subject": "agent:live-slack-smoke",
            "purpose_parameters": {"source": "live-smoke"},
        },
    )
    response.raise_for_status()
    return response.json()["token"]


def invoke_payload(client: TestClient, capability_id: str, parameters: dict, key: str = LIVE_SMOKE_KEY) -> dict:
    token = issue_token(client, capability_id, key)
    response = client.post(
        f"/anip/invoke/{capability_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"parameters": parameters},
    )
    return response.json()


def invoke(client: TestClient, capability_id: str, parameters: dict) -> dict:
    payload = invoke_payload(client, capability_id, parameters)
    if not payload.get("success"):
        raise RuntimeError(payload)
    return payload["result"]


def expect_refused(client: TestClient, capability_id: str, parameters: dict, key: str) -> dict:
    payload = invoke_payload(client, capability_id, parameters, key)
    failure = payload.get("failure") or {}
    if payload.get("success") is not False or failure.get("type") != "denied" or failure.get("detail") != NO_BINDING_DETAIL:
        raise AssertionError(f"{capability_id}: expected {SMOKE_KEYS[key]} to be denied, got {payload}")
    return {"capability_id": capability_id, "actor": SMOKE_KEYS[key], "failure": "denied"}


def main() -> None:
    channel_id = os.environ["SLACK_CHANNEL_ID"]
    os.environ.setdefault("ANIP_SLACK_ALLOWED_CHANNELS", channel_id)
    os.environ["ANIP_SLACK_ALLOW_SEND"] = "false"
    os.environ["ANIP_API_KEYS_JSON"] = json.dumps(SMOKE_KEYS)
    history = slack_post("conversations.history", {"channel": channel_id, "limit": 1})
    if not history.get("ok"):
        raise RuntimeError(history)
    messages = history.get("messages", [])
    thread_ts = (messages[0] or {}).get("thread_ts") or (messages[0] or {}).get("ts") if messages else None
    client = TestClient(create_app())

    cases: dict[str, dict[str, Any]] = {
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

    read = cases["slack.channel.read_context"]["parameters"]
    refusals = [
        {"check": "principal without an actor claim", **expect_refused(client, "slack.channel.read_context", read, "smoke-no-actor")},
        {"check": "actor no binding names", **expect_refused(client, "slack.channel.read_context", read, "smoke-unknown-actor")},
    ]

    print(json.dumps({"channel_id": channel_id, "capabilities_tested": len(summary), "results": summary, "refusals": refusals}, indent=2))


if __name__ == "__main__":
    main()
