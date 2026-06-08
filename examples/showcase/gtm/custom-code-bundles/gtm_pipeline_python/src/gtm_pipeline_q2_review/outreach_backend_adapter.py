"""MCP adapter for the GTM outreach helper backend."""
from __future__ import annotations

import json
import os
from typing import Any

import anyio
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from anip_service import ANIPError


BACKEND_URL = os.getenv("GTM_OUTREACH_BACKEND_URL", "http://127.0.0.1:9500/mcp").rstrip("/")
BACKEND_AUTH_TOKEN = os.getenv("GTM_OUTREACH_BACKEND_TOKEN", "demo-outreach-backend-token")


def _compact_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in arguments.items() if value is not None}


def _first_text_content(result: Any) -> str:
    content = getattr(result, "content", None)
    if not isinstance(content, list):
        raise ANIPError("temporarily_unavailable", "The outreach backend returned an invalid MCP response.", resolution={"action": "retry_later"})
    for item in content:
        text = getattr(item, "text", None)
        if isinstance(text, str):
            return text
    raise ANIPError("temporarily_unavailable", "The outreach backend returned no readable MCP content.", resolution={"action": "retry_later"})


def _translate_mcp_error(text: str) -> ANIPError:
    lowered = text.lower()
    if "clarification_required" in lowered:
        detail = "The outreach request is not specific enough yet."
        hint = None
        for line in text.splitlines():
            if line.startswith("Detail: "):
                detail = line[len("Detail: ") :].strip()
            elif line.startswith("Hint: "):
                hint = line[len("Hint: ") :].strip()
        resolution = {"action": "provide_missing_parameter"}
        if hint:
            resolution["hint"] = hint
        return ANIPError("clarification_required", detail, resolution=resolution)
    if "authentication_required" in lowered:
        return ANIPError("temporarily_unavailable", "The outreach backend rejected the MCP request.", resolution={"action": "retry_later"})
    return ANIPError("temporarily_unavailable", "The outreach backend returned an MCP tool error.", resolution={"action": "retry_later"})


async def _call_tool_async(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {BACKEND_AUTH_TOKEN}"}
    async with streamablehttp_client(BACKEND_URL, headers=headers, timeout=20) as (read_stream, write_stream, _get_session_id):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments=arguments)
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict) and not getattr(result, "isError", False):
        return structured
    text = _first_text_content(result)
    if getattr(result, "isError", False):
        raise _translate_mcp_error(text)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ANIPError("temporarily_unavailable", "The outreach backend returned malformed MCP tool content.", resolution={"action": "retry_later"}) from exc
    if not isinstance(payload, dict):
        raise ANIPError("temporarily_unavailable", "The outreach backend returned an unexpected payload shape.", resolution={"action": "retry_later"})
    return payload


async def draft_outreach_message_async(*, target_ref: str, objective: str, channel: str | None = None, persona: str | None = None) -> dict[str, Any]:
    return await _call_tool_async("draft_outreach_message", _compact_arguments({"target_ref": target_ref, "objective": objective, "channel": channel, "persona": persona}))


def draft_outreach_message(*, target_ref: str, objective: str, channel: str | None = None, persona: str | None = None) -> dict[str, Any]:
    return anyio.run(lambda: draft_outreach_message_async(target_ref=target_ref, objective=objective, channel=channel, persona=persona))


async def suggest_followup_content_async(*, target_ref: str, variant_count: int | None = None, persona: str | None = None) -> dict[str, Any]:
    return await _call_tool_async("suggest_followup_content", _compact_arguments({"target_ref": target_ref, "variant_count": variant_count, "persona": persona}))


def suggest_followup_content(*, target_ref: str, variant_count: int | None = None, persona: str | None = None) -> dict[str, Any]:
    return anyio.run(lambda: suggest_followup_content_async(target_ref=target_ref, variant_count=variant_count, persona=persona))


async def objection_response_variants_async(*, objection_theme: str, target_ref: str | None = None, persona: str | None = None) -> dict[str, Any]:
    return await _call_tool_async("objection_response_variants", _compact_arguments({"objection_theme": objection_theme, "target_ref": target_ref, "persona": persona}))


def objection_response_variants(*, objection_theme: str, target_ref: str | None = None, persona: str | None = None) -> dict[str, Any]:
    return anyio.run(lambda: objection_response_variants_async(objection_theme=objection_theme, target_ref=target_ref, persona=persona))
