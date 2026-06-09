"""Slack Web API backend seam for the governed fronting showcase."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

BackendInvocationPlan = dict[str, Any]
GeneratedCapability = dict[str, Any]


def _slack_token() -> str | None:
    return os.getenv("SLACK_BOT_TOKEN", "").strip() or None


def _csv_env(name: str) -> set[str]:
    return {item.strip() for item in os.getenv(name, "").split(",") if item.strip()}


def _bounded_limit(value: Any, *, default: int = 20, maximum: int = 50) -> int:
    try:
        limit = int(value)
    except (TypeError, ValueError):
        limit = default
    return max(1, min(limit, maximum))


def _slack_post_json(path: str, token: str, body: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        f"https://slack.com/api/{path}",
        data=urllib.parse.urlencode({key: str(value) for key, value in body.items() if value is not None}).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return {
            "ok": False,
            "error": "slack_http_error",
            "status": exc.code,
            "detail": exc.read().decode("utf-8", errors="replace"),
        }


def _message_summary(message: dict[str, Any]) -> dict[str, Any]:
    return {
        "ts": message.get("ts"),
        "user": message.get("user") or message.get("bot_id"),
        "text": message.get("text"),
        "thread_ts": message.get("thread_ts"),
    }


def _approval_grant_from_context(ctx: Any) -> dict[str, Any] | None:
    grant = getattr(ctx, "approval_grant", None)
    if isinstance(grant, dict) and grant.get("grant_id") and grant.get("approval_request_id"):
        return grant
    return None


def _mutation_enabled(ctx: Any) -> bool:
    return os.getenv("ANIP_SLACK_ALLOW_SEND", "").lower() == "true" and _approval_grant_from_context(ctx) is not None


def _channel_allowed(channel_id: str) -> bool:
    blocked = _csv_env("ANIP_SLACK_BLOCKED_CHANNELS")
    allowed = _csv_env("ANIP_SLACK_ALLOWED_CHANNELS")
    if channel_id in blocked:
        return False
    return not allowed or channel_id in allowed


def _restricted_channel_response(capability: GeneratedCapability, plan: BackendInvocationPlan, channel_id: str) -> dict[str, Any]:
    return {
        "execution_status": "restricted",
        "capability_id": capability["capability_id"],
        "selected_backend": plan["selected_binding"],
        "semantic_input": plan["semantic_input"],
        "channel_id": channel_id,
        "reason": "Slack channel is outside the configured ANIP channel policy.",
    }


class DefaultBackendAdapter:
    async def execute(
        self,
        capability: GeneratedCapability,
        plan: BackendInvocationPlan,
        _params: dict[str, Any],
        ctx: Any = None,
    ) -> dict[str, Any]:
        if plan["unresolved_required_backend_inputs"]:
            return {
                "execution_status": "backend_input_incomplete",
                "capability_id": capability["capability_id"],
                "backend_input_contract": plan["backend_input_contract"],
                "unresolved_required_backend_inputs": plan["unresolved_required_backend_inputs"],
                "note": "Generated host is runnable, but backend-only inputs still require extension completion.",
            }
        token = _slack_token()
        capability_id = capability["capability_id"]
        if capability_id == "slack.channel.read_context" and token is not None:
            return self._read_channel_context(capability, plan, _params, token)
        if capability_id == "slack.thread.summarize" and token is not None:
            return self._read_thread_context(capability, plan, _params, token)
        if capability_id in {"slack.message.prepare", "slack.incident_update.prepare", "slack.announcement.request"}:
            return self._prepare_or_send_message(capability, plan, _params, token, ctx)
        return {
            "execution_status": "backend_execution_stub",
            "capability_id": capability_id,
            "selected_backend": plan["selected_binding"],
            "semantic_input": plan["semantic_input"],
            "backend_input_contract": plan["backend_input_contract"],
            "note": "Replace DefaultBackendAdapter.execute() with provider-specific backend execution.",
        }

    def _read_channel_context(
        self,
        capability: GeneratedCapability,
        plan: BackendInvocationPlan,
        params: dict[str, Any],
        token: str,
    ) -> dict[str, Any]:
        channel_id = str(params.get("channel_id") or "").strip()
        if not _channel_allowed(channel_id):
            return _restricted_channel_response(capability, plan, channel_id)
        limit = _bounded_limit(params.get("limit"))
        query = str(params.get("query") or "").strip().lower()
        payload = _slack_post_json("conversations.history", token, {"channel": channel_id, "limit": limit})
        if not payload.get("ok"):
            return self._backend_error(capability, plan, payload)
        messages = [_message_summary(message) for message in payload.get("messages", [])]
        if query:
            messages = [message for message in messages if query in str(message.get("text") or "").lower()]
        messages = messages[:limit]
        return {
            "execution_status": "completed",
            "capability_id": capability["capability_id"],
            "selected_backend": plan["selected_binding"],
            "semantic_input": plan["semantic_input"],
            "result": {"messages": messages, "count": len(messages), "channel_id": channel_id},
        }

    def _read_thread_context(
        self,
        capability: GeneratedCapability,
        plan: BackendInvocationPlan,
        params: dict[str, Any],
        token: str,
    ) -> dict[str, Any]:
        channel_id = str(params.get("channel_id") or "").strip()
        if not _channel_allowed(channel_id):
            return _restricted_channel_response(capability, plan, channel_id)
        thread_ts = str(params.get("thread_ts") or "").strip()
        limit = _bounded_limit(params.get("limit"), default=50, maximum=100)
        payload = _slack_post_json("conversations.replies", token, {"channel": channel_id, "ts": thread_ts, "limit": limit})
        if not payload.get("ok"):
            return self._backend_error(capability, plan, payload)
        replies = [_message_summary(message) for message in payload.get("messages", [])]
        return {
            "execution_status": "completed",
            "capability_id": capability["capability_id"],
            "selected_backend": plan["selected_binding"],
            "semantic_input": plan["semantic_input"],
            "result": {"messages": replies, "count": len(replies), "channel_id": channel_id, "thread_ts": thread_ts},
        }

    def _message_text(self, capability: GeneratedCapability, params: dict[str, Any]) -> str:
        capability_id = capability["capability_id"]
        if capability_id == "slack.incident_update.prepare":
            parts = [
                f"Incident {params.get('incident_id')}: {params.get('status')}",
                str(params.get("summary") or "").strip(),
            ]
            if params.get("next_update_time"):
                parts.append(f"Next update: {params.get('next_update_time')}")
            return "\n".join(part for part in parts if part)
        if capability_id == "slack.announcement.request":
            audience = str(params.get("audience") or "").strip()
            prefix = f"[{audience}] " if audience else ""
            return prefix + str(params.get("announcement") or "").strip()
        return str(params.get("text") or "").strip()

    def _prepare_or_send_message(
        self,
        capability: GeneratedCapability,
        plan: BackendInvocationPlan,
        params: dict[str, Any],
        token: str | None,
        ctx: Any,
    ) -> dict[str, Any]:
        channel_id = str(params.get("channel_id") or "").strip()
        if not _channel_allowed(channel_id):
            return _restricted_channel_response(capability, plan, channel_id)
        body: dict[str, Any] = {"channel": channel_id, "text": self._message_text(capability, params)}
        if params.get("thread_ts"):
            body["thread_ts"] = str(params.get("thread_ts"))
        preview = {
            "execution_status": "prepared",
            "capability_id": capability["capability_id"],
            "selected_backend": plan["selected_binding"],
            "semantic_input": plan["semantic_input"],
            "approval_required": True,
            "mutation_performed": False,
            "slack_action": "chat.postMessage",
            "post_message_request": {"method": "POST", "path": "/api/chat.postMessage", "body": body},
            "note": "Prepared a Slack message payload. No Slack message was sent.",
        }
        approval_grant = _approval_grant_from_context(ctx)
        if approval_grant is not None:
            preview["approval_grant"] = {
                "grant_id": approval_grant.get("grant_id"),
                "approval_request_id": approval_grant.get("approval_request_id"),
                "grant_type": approval_grant.get("grant_type"),
            }
        if not _mutation_enabled(ctx):
            return preview
        if token is None:
            preview["execution_status"] = "backend_error"
            preview["slack_error"] = {"ok": False, "error": "missing_slack_token"}
            return preview
        posted = _slack_post_json("chat.postMessage", token, body)
        if not posted.get("ok"):
            return {**preview, "execution_status": "backend_error", "slack_error": posted}
        return {
            **preview,
            "execution_status": "completed",
            "approval_required": False,
            "mutation_performed": True,
            "posted_message": {"channel": posted.get("channel"), "ts": posted.get("ts")},
            "note": "Sent Slack message after the ANIP runtime validated and reserved an approval grant.",
        }

    def _backend_error(self, capability: GeneratedCapability, plan: BackendInvocationPlan, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "execution_status": "backend_error",
            "capability_id": capability["capability_id"],
            "selected_backend": plan["selected_binding"],
            "semantic_input": plan["semantic_input"],
            "slack_error": payload,
        }


backend_adapter = DefaultBackendAdapter()
