"""Backend execution seam for generated capabilities."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

BackendInvocationPlan = dict[str, Any]
GeneratedCapability = dict[str, Any]


def _slack_env() -> str | None:
    return os.getenv("SLACK_BOT_TOKEN", "").strip() or None


def _bounded_limit(value: Any) -> int:
    try:
        limit = int(value)
    except (TypeError, ValueError):
        limit = 20
    return max(1, min(limit, 50))


def _slack_post_json(path: str, token: str, body: dict[str, Any]) -> dict[str, Any]:
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
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return {"ok": False, "error": "slack_http_error", "status": exc.code, "detail": detail}


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
    if os.getenv("ANIP_SLACK_ALLOW_SEND", "").lower() != "true":
        return False
    return _approval_grant_from_context(ctx) is not None


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
        token = _slack_env()
        if capability["capability_id"] == "slack.channel.read_context" and token is not None:
            return self._read_channel_context(capability, plan, _params, token)
        if capability["capability_id"] == "slack.thread.summarize" and token is not None:
            return self._read_thread_context(capability, plan, _params, token)
        if capability["capability_id"] in {"slack.message.prepare", "slack.incident_update.prepare", "slack.announcement.request"} and token is not None:
            return self._prepare_or_send_message(capability, plan, _params, token, ctx)
        return {
            "execution_status": "backend_execution_stub",
            "capability_id": capability["capability_id"],
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
        limit = _bounded_limit(params.get("limit"))
        query = str(params.get("query") or "").strip().lower()
        payload = _slack_post_json("conversations.history", token, {"channel": channel_id, "limit": limit})
        if not payload.get("ok"):
            return {
                "execution_status": "backend_error",
                "capability_id": capability["capability_id"],
                "selected_backend": plan["selected_binding"],
                "semantic_input": plan["semantic_input"],
                "slack_error": payload,
            }
        messages = [_message_summary(message) for message in payload.get("messages", [])]
        if query:
            messages = [message for message in messages if query in str(message.get("text") or "").lower()]
        return {
            "execution_status": "completed",
            "capability_id": capability["capability_id"],
            "selected_backend": plan["selected_binding"],
            "semantic_input": plan["semantic_input"],
            "result": {"messages": messages[:limit], "count": len(messages[:limit]), "channel_id": channel_id},
        }

    def _read_thread_context(
        self,
        capability: GeneratedCapability,
        plan: BackendInvocationPlan,
        params: dict[str, Any],
        token: str,
    ) -> dict[str, Any]:
        channel_id = str(params.get("channel_id") or "").strip()
        thread_ts = str(params.get("thread_ts") or "").strip()
        payload = _slack_post_json("conversations.replies", token, {"channel": channel_id, "ts": thread_ts, "limit": 50})
        if not payload.get("ok"):
            return {
                "execution_status": "backend_error",
                "capability_id": capability["capability_id"],
                "selected_backend": plan["selected_binding"],
                "semantic_input": plan["semantic_input"],
                "slack_error": payload,
            }
        replies = [_message_summary(message) for message in payload.get("messages", [])]
        return {
            "execution_status": "completed",
            "capability_id": capability["capability_id"],
            "selected_backend": plan["selected_binding"],
            "semantic_input": plan["semantic_input"],
            "result": {"messages": replies, "count": len(replies), "channel_id": channel_id, "thread_ts": thread_ts},
        }

    def _message_text(self, capability: GeneratedCapability, params: dict[str, Any]) -> str:
        if capability["capability_id"] == "slack.incident_update.prepare":
            parts = [
                f"Incident {params.get('incident_id')}: {params.get('status')}",
                str(params.get("summary") or "").strip(),
            ]
            if params.get("next_update_time"):
                parts.append(f"Next update: {params.get('next_update_time')}")
            return "\n".join(part for part in parts if part)
        if capability["capability_id"] == "slack.announcement.request":
            audience = str(params.get("audience") or "").strip()
            prefix = f"[{audience}] " if audience else ""
            return prefix + str(params.get("announcement") or "").strip()
        return str(params.get("text") or "").strip()

    def _prepare_or_send_message(
        self,
        capability: GeneratedCapability,
        plan: BackendInvocationPlan,
        params: dict[str, Any],
        token: str,
        ctx: Any,
    ) -> dict[str, Any]:
        channel_id = str(params.get("channel_id") or "").strip()
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
        posted = _slack_post_json("chat.postMessage", token, body)
        if not posted.get("ok"):
            preview["execution_status"] = "backend_error"
            preview["slack_error"] = posted
            return preview
        return {
            **preview,
            "execution_status": "completed",
            "approval_required": False,
            "mutation_performed": True,
            "posted_message": {"channel": posted.get("channel"), "ts": posted.get("ts")},
            "note": "Sent Slack message after the ANIP runtime validated and reserved an approval grant.",
        }

backend_adapter = DefaultBackendAdapter()
