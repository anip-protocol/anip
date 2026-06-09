"""Deterministic MCP backend for GTM outreach showcase flows."""
from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path
from typing import Any

import mcp.types as mcp_types
from fastapi import FastAPI
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.requests import Request
from starlette.routing import Mount


FIXTURES_PATH = Path(__file__).resolve().with_name("fixtures.json")
FIXTURES = json.loads(FIXTURES_PATH.read_text())
BACKEND_TOKEN = os.getenv("GTM_OUTREACH_BACKEND_TOKEN", "demo-outreach-backend-token")


def _require_auth(request: Request | None) -> None:
    if request is None:
        raise ValueError("FAILED: authentication_required\nDetail: Missing request context\nRetryable: yes")
    auth_header = request.headers.get("authorization", "")
    expected = f"Bearer {BACKEND_TOKEN}"
    if auth_header.strip() != expected:
        raise ValueError("FAILED: authentication_required\nDetail: Valid bearer required\nRetryable: yes")


def _target_key(target_ref: str) -> str:
    raw = str(target_ref or "").strip()
    if not raw:
        raise ValueError("FAILED: clarification_required\nDetail: target_ref is required\nRetryable: yes")
    for candidate in FIXTURES["targets"].keys():
        if candidate.lower() == raw.lower():
            return candidate
    raise ValueError(
        "FAILED: clarification_required\n"
        f"Detail: Unknown target_ref '{raw}'\n"
        "Hint: Use Condax, Acme Corporation, or Codehow.\n"
        "Retryable: yes"
    )


def _theme_key(objection_theme: str) -> str:
    raw = str(objection_theme or "").strip().lower()
    if not raw:
        raise ValueError("FAILED: clarification_required\nDetail: objection_theme is required\nRetryable: yes")
    aliases = {
        "pricing": "pricing",
        "price": "pricing",
        "competitor": "competitor",
        "competitor comparison": "competitor",
        "implementation_risk": "implementation_risk",
        "implementation": "implementation_risk",
        "implementation risk": "implementation_risk",
    }
    key = aliases.get(raw)
    if not key:
        raise ValueError(
            "FAILED: clarification_required\n"
            f"Detail: Unsupported objection_theme '{objection_theme}'\n"
            "Hint: Use pricing, competitor, or implementation_risk.\n"
            "Retryable: yes"
        )
    return key


def _bounded_variant_count(value: object | None) -> int:
    try:
        return max(1, min(int(value or 3), 3))
    except (TypeError, ValueError):
        return 3


def _draft_outreach_message(arguments: dict[str, Any]) -> dict[str, Any]:
    target_name = _target_key(str(arguments.get("target_ref") or ""))
    target = FIXTURES["targets"][target_name]
    objective = str(arguments.get("objective") or "").strip() or "first_touch"
    channel = str(arguments.get("channel") or "email").strip() or "email"
    persona = str(arguments.get("persona") or target["persona"]).strip() or target["persona"]
    subject = {
        "first_touch": f"{target_name}: governed GTM follow-up without workflow sprawl",
        "follow_up": f"Following up on {target_name}'s GTM workflow priorities",
        "revive_stalled": f"A practical path to unblock stalled GTM work at {target_name}",
    }.get(objective, f"{target_name}: a bounded next step for {objective}")
    body = (
        f"Hi {persona},\n\n"
        f"I'm reaching out because {target_name} looks like a strong fit for a governed GTM workflow review. "
        f"Teams in {target['industry']} often struggle with {target['pain_point']}. "
        f"We help them get to {target['proof_point']} without giving an agent raw, unconstrained system access.\n\n"
        f"If useful, I can show how that would apply to {target_name}'s current priorities and suggest {target['next_step']}.\n\n"
        "Best,\nANIP GTM Team"
    )
    return {
        "draft_id": f"draft_{target_name.lower().replace(' ', '_')}_{objective}",
        "target_ref": target_name,
        "objective": objective,
        "channel": channel,
        "persona": persona,
        "subject": subject,
        "body": body,
        "tone": "direct and operational",
        "rationale": f"Anchored to {target['priority_context']} and {target['pain_point']}.",
        "target_summary": {
            "industry": target["industry"],
            "region": target["region"],
            "priority_context": target["priority_context"],
        },
    }


def _suggest_followup_content(arguments: dict[str, Any]) -> dict[str, Any]:
    target_name = _target_key(str(arguments.get("target_ref") or ""))
    target = FIXTURES["targets"][target_name]
    variant_count = _bounded_variant_count(arguments.get("variant_count"))
    variants = [
        {
            "variant_id": f"{target_name.lower().replace(' ', '_')}_followup_{idx}",
            "channel": "email",
            "subject": subject,
            "body": body,
            "rationale": rationale,
        }
        for idx, (subject, body, rationale) in enumerate(
            [
                (
                    f"{target_name}: quick follow-up on governed GTM review",
                    f"I wanted to follow up on whether a bounded review of {target_name}'s GTM workflow would be useful. "
                    f"The main gap we typically see in {target['industry']} is {target['pain_point']}.",
                    "Keeps the message short and tied to the concrete pain point.",
                ),
                (
                    f"{target_name}: a focused next step",
                    f"If timing is better next week, I can send a short outline showing how governed scoring, approvals, "
                    f"and follow-up planning could support {target_name}'s current priorities.",
                    "Offers a low-friction next step instead of pushing for a meeting immediately.",
                ),
                (
                    f"{target_name}: one practical GTM workflow idea",
                    f"A good starting point for {target_name} would be {target['next_step']}, anchored to {target['proof_point']}.",
                    "Turns the follow-up into a concrete operational suggestion.",
                ),
            ],
            start=1,
        )
    ]
    return {
        "target_ref": target_name,
        "variants": variants[:variant_count],
    }


def _objection_response_variants(arguments: dict[str, Any]) -> dict[str, Any]:
    theme = _theme_key(str(arguments.get("objection_theme") or ""))
    theme_spec = FIXTURES["objection_themes"][theme]
    target_ref = str(arguments.get("target_ref") or "").strip() or None
    target_name = _target_key(target_ref) if target_ref else None
    variants = []
    for item in theme_spec["variants"]:
        variants.append(
            {
                "pattern_id": item["variant_id"],
                "pattern_type": theme_spec["label"],
                "target_ref": target_name,
                "message": item["message"],
                "rationale": item["rationale"],
            }
        )
    return {
        "objection_theme": theme_spec["label"],
        "target_ref": target_name,
        "variants": variants,
    }


TOOLS = {
    "draft_outreach_message": (
        mcp_types.Tool(
            name="draft_outreach_message",
            description="Draft a bounded outreach message for an explicit GTM target and objective.",
            inputSchema={
                "type": "object",
                "properties": {
                    "target_ref": {"type": "string"},
                    "objective": {"type": "string"},
                    "channel": {"type": "string"},
                    "persona": {"type": "string"},
                },
                "required": ["target_ref", "objective"],
            },
        ),
        _draft_outreach_message,
    ),
    "suggest_followup_content": (
        mcp_types.Tool(
            name="suggest_followup_content",
            description="Return bounded follow-up content variants for an explicit GTM target.",
            inputSchema={
                "type": "object",
                "properties": {
                    "target_ref": {"type": "string"},
                    "variant_count": {"type": "integer"},
                    "persona": {"type": "string"},
                },
                "required": ["target_ref"],
            },
        ),
        _suggest_followup_content,
    ),
    "objection_response_variants": (
        mcp_types.Tool(
            name="objection_response_variants",
            description="Return bounded objection-response variants for a selected theme.",
            inputSchema={
                "type": "object",
                "properties": {
                    "objection_theme": {"type": "string"},
                    "target_ref": {"type": "string"},
                    "persona": {"type": "string"},
                },
                "required": ["objection_theme"],
            },
        ),
        _objection_response_variants,
    ),
}


app = FastAPI(title="GTM Outreach MCP Backend")
mcp_server = Server("gtm-outreach-mcp")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@mcp_server.list_tools()
async def handle_list_tools() -> list[mcp_types.Tool]:
    return [tool for tool, _handler in TOOLS.values()]


@mcp_server.call_tool()
async def handle_call_tool(name: str, arguments: dict[str, Any]) -> list[mcp_types.TextContent]:
    if name not in TOOLS:
        raise ValueError(f"Unknown tool: {name}")
    request: Request | None = None
    try:
        request = getattr(mcp_server.request_context, "request", None)
    except LookupError:
        request = None
    _require_auth(request)
    _tool, handler = TOOLS[name]
    payload = handler(arguments or {})
    return [mcp_types.TextContent(type="text", text=json.dumps(payload))]


session_manager = StreamableHTTPSessionManager(
    app=mcp_server,
    json_response=False,
    stateless=True,
)
existing_lifespan = app.router.lifespan_context


@contextlib.asynccontextmanager
async def combined_lifespan(app_: Any):
    async with existing_lifespan(app_):
        async with session_manager.run():
            yield


app.router.lifespan_context = combined_lifespan
app.routes.append(Mount("/mcp", app=session_manager.handle_request))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "9500")))
