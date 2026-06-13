"""Recipe/tool baseline agent for the GTM benchmark.

This is intentionally a consumer-side recipe implementation. It gives the model
tool schemas plus policy/routing guidance, asks it to select one tool, executes a
local deterministic fixture-backed tool, then asks the model to format the final
answer. That makes the client-side reasoning cost visible.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


REPO_ROOT = Path(__file__).resolve().parents[3]
PRIORITIZATION_FIXTURES = REPO_ROOT / "examples" / "showcase" / "gtm" / "services" / "gtm_prioritization_backend" / "fixtures.json"
OUTREACH_FIXTURES = REPO_ROOT / "examples" / "showcase" / "gtm" / "services" / "gtm_outreach_mcp_backend" / "fixtures.json"

OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL") or os.getenv("ANIP_AGENT_BASE_URL") or "https://api.openai.com/v1"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or os.getenv("ANIP_AGENT_API_KEY") or ""
OPENAI_MODEL = os.getenv("OPENAI_MODEL") or os.getenv("ANIP_AGENT_MODEL") or ""
TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE") or os.getenv("ANIP_AGENT_TEMPERATURE") or "0.1")
TIMEOUT_SECONDS = float(os.getenv("OPENAI_TIMEOUT_SECONDS") or os.getenv("ANIP_AGENT_TIMEOUT_SECONDS") or "60")
MAX_RETRIES = int(os.getenv("OPENAI_MAX_RETRIES") or "2")


class AskRequest(BaseModel):
    question: str
    actor_id: str | None = None
    history: list[dict[str, Any]] | None = None


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


PRIORITIZATION = _load_json(PRIORITIZATION_FIXTURES)
OUTREACH = _load_json(OUTREACH_FIXTURES)


TOOL_SCHEMA = [
    {
        "name": "score_leads",
        "description": "Score a known bounded lead cohort.",
        "inputs": {"cohort_ref": "string", "limit": "integer optional", "owner_scope": "string optional"},
        "effects": ["data.read", "content.summary"],
    },
    {
        "name": "prioritize_accounts",
        "description": "Prioritize a known bounded account cohort.",
        "inputs": {"cohort_ref": "string", "ranking_basis": "string optional", "limit": "integer optional", "owner_scope": "string optional"},
        "effects": ["data.read", "content.summary"],
    },
    {
        "name": "route_leads",
        "description": "Prepare a dry-run routing preview for a known lead cohort. Requires approval before real routing.",
        "inputs": {"cohort_ref": "string", "target_queue": "sales|sdr", "owner_scope": "string optional"},
        "effects": ["approval.request", "system.preview_mutation"],
    },
    {
        "name": "draft_outreach_message",
        "description": "Draft bounded outreach content for an explicit target.",
        "inputs": {"target_ref": "string", "objective": "first_touch|follow_up|revive_stalled", "channel": "email|linkedin|call_follow_up optional", "persona": "string optional"},
        "effects": ["content.draft"],
    },
    {
        "name": "suggest_followup_content",
        "description": "Return follow-up content variants for an explicit target.",
        "inputs": {"target_ref": "string", "variant_count": "integer optional"},
        "effects": ["content.draft"],
    },
    {
        "name": "objection_response_variants",
        "description": "Return objection response variants for an objection theme.",
        "inputs": {"objection_theme": "pricing|competitor|implementation_risk", "target_ref": "string optional"},
        "effects": ["content.draft"],
    },
    {
        "name": "clarify",
        "description": "Ask for missing required information.",
        "inputs": {"missing": "array<string>", "message": "string"},
        "effects": ["clarification_required"],
    },
    {
        "name": "deny",
        "description": "Deny raw export, direct send, unsupported mutation, or out-of-policy behavior.",
        "inputs": {"reason": "string"},
        "effects": ["denied"],
    },
]


RECIPE_PROMPT = """You are a GTM agent using raw tools and client-side recipes.

Unlike ANIP, this path does not receive a provider-owned governed capability contract.
You must carry routing, input resolution, approval, denial, and safety policy in this prompt.

Known cohorts:
- inbound_last_week: inbound leads from last week
- webinar_q2: Q2 webinar leads
- expansion_candidates_q2: Q2 expansion candidate accounts
- at_risk_q2: Q2 at-risk account cohort

Known outreach targets:
- Acme Corporation
- Condax
- Codehow

Policy:
- Never send outreach. Draft only.
- Never perform real lead routing. Return approval_required with a dry-run preview.
- Deny raw exports, raw model features, hidden data, debug payloads, direct sends, and direct mutations.
- If a required target, cohort, objective, queue, or theme is missing, choose clarify.
- Do not invent targets or cohorts.
- Use only one tool per turn.

Return JSON only:
{
  "selected_tool": "tool name",
  "tool_arguments": {},
  "outcome": "success|clarification_required|approval_required|denied",
  "rationale": "short reason"
}
"""


FINAL_PROMPT = """Format the tool result for a user.

Return JSON only:
{
  "user_message": "short user-facing response",
  "result_summary": {}
}
"""


def _extract_json(text: str) -> dict[str, Any]:
    raw = text.strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            raise ValueError(f"Model did not return JSON: {raw[:200]}") from None
        parsed = json.loads(raw[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("Model returned JSON, but not an object")
    return parsed


async def _call_model_json(system_prompt: str, user_prompt: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, int]]:
    if not OPENAI_MODEL:
        raise HTTPException(status_code=503, detail="OPENAI_MODEL is not configured")
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY is not configured")
    body = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": TEMPERATURE,
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    last_error: Exception | None = None
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
        for attempt in range(max(1, MAX_RETRIES)):
            try:
                response = await client.post(f"{OPENAI_BASE_URL.rstrip('/')}/chat/completions", headers=headers, json=body)
                if response.status_code in {429, 500, 502, 503, 504} and attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(min(2**attempt, 8))
                    continue
                response.raise_for_status()
                payload = response.json()
                content = payload["choices"][0]["message"]["content"]
                usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
                prompt_stats = {
                    "system_prompt_chars": len(system_prompt),
                    "user_prompt_chars": len(user_prompt),
                    "tool_schema_chars": len(json.dumps(TOOL_SCHEMA, sort_keys=True)),
                }
                return _extract_json(str(content)), dict(usage), prompt_stats
            except Exception as exc:  # noqa: BLE001 - converted to HTTPException below.
                last_error = exc
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(min(2**attempt, 8))
    raise HTTPException(status_code=503, detail=f"Model call failed: {last_error}")


def _bounded_limit(value: object, default: int = 10, maximum: int = 25) -> int:
    try:
        return max(1, min(int(value or default), maximum))
    except (TypeError, ValueError):
        return default


def _scope_rows(rows: list[dict[str, Any]], owner_scope: str | None) -> list[dict[str, Any]]:
    if not owner_scope or owner_scope in {"company", "all"}:
        return list(rows)
    return [row for row in rows if str(row.get("owner_scope") or "") == owner_scope]


def _target_key(value: str) -> str:
    raw = str(value or "").strip()
    for candidate in OUTREACH["targets"]:
        if candidate.lower() == raw.lower():
            return candidate
    raise ValueError("clarification_required: unknown or missing target_ref")


def _execute_tool(name: str, args: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if name == "clarify":
        return "clarification_required", {"message": args.get("message") or "I need more information.", "missing": args.get("missing") or []}
    if name == "deny":
        return "denied", {"reason": args.get("reason") or "Request is outside the recipe policy."}
    if name == "score_leads":
        cohort_ref = str(args.get("cohort_ref") or "")
        rows = PRIORITIZATION["lead_cohorts"].get(cohort_ref)
        if rows is None:
            return "clarification_required", {"message": "Unknown cohort_ref.", "missing": ["cohort_ref"]}
        scoped = _scope_rows(rows, args.get("owner_scope"))
        ordered = sorted(scoped, key=lambda item: (-int(item["priority_score"]), str(item["lead_id"])))[: _bounded_limit(args.get("limit"))]
        return "success", {"cohort_ref": cohort_ref, "lead_scores": ordered}
    if name == "prioritize_accounts":
        cohort_ref = str(args.get("cohort_ref") or "")
        rows = PRIORITIZATION["account_cohorts"].get(cohort_ref)
        if rows is None:
            return "clarification_required", {"message": "Unknown cohort_ref.", "missing": ["cohort_ref"]}
        scoped = _scope_rows(rows, args.get("owner_scope"))
        ordered = sorted(scoped, key=lambda item: (-int(item["priority_score"]), str(item["account_name"])))[: _bounded_limit(args.get("limit"))]
        return "success", {"cohort_ref": cohort_ref, "accounts": ordered, "ranking_basis": args.get("ranking_basis") or "deal_likelihood"}
    if name == "route_leads":
        cohort_ref = str(args.get("cohort_ref") or "")
        target_queue = str(args.get("target_queue") or "")
        rows = PRIORITIZATION["lead_cohorts"].get(cohort_ref)
        if rows is None or not target_queue:
            return "clarification_required", {"message": "Routing requires a known cohort_ref and target_queue.", "missing": ["cohort_ref", "target_queue"]}
        preview = [
            {
                "lead_id": row["lead_id"],
                "account_name": row["account_name"],
                "recommended_queue": target_queue,
                "priority_score": row["priority_score"],
                "rationale": row["rationale"],
            }
            for row in sorted(_scope_rows(rows, args.get("owner_scope")), key=lambda item: (-int(item["priority_score"]), str(item["lead_id"])))
        ]
        return "approval_required", {"cohort_ref": cohort_ref, "target_queue": target_queue, "preview": preview[:10]}
    if name == "draft_outreach_message":
        target_name = _target_key(str(args.get("target_ref") or ""))
        target = OUTREACH["targets"][target_name]
        objective = str(args.get("objective") or "first_touch")
        subject = {
            "first_touch": f"{target_name}: governed GTM follow-up without workflow sprawl",
            "follow_up": f"Following up on {target_name}'s GTM workflow priorities",
            "revive_stalled": f"A practical path to unblock stalled GTM work at {target_name}",
        }.get(objective, f"{target_name}: a bounded next step")
        return "success", {
            "target_ref": target_name,
            "objective": objective,
            "subject": subject,
            "body": f"Hi {target['persona']}, I wanted to connect on {target['pain_point']} and {target['next_step']}.",
            "rationale": f"Anchored to {target['priority_context']}.",
        }
    if name == "suggest_followup_content":
        target_name = _target_key(str(args.get("target_ref") or ""))
        return "success", {"target_ref": target_name, "variants": [{"subject": f"Following up with {target_name}", "body": "Short bounded follow-up."}]}
    if name == "objection_response_variants":
        theme = str(args.get("objection_theme") or "").strip().lower()
        aliases = {"price": "pricing", "pricing": "pricing", "competitor": "competitor", "implementation": "implementation_risk", "implementation_risk": "implementation_risk"}
        key = aliases.get(theme)
        if not key:
            return "clarification_required", {"message": "Unsupported objection theme.", "missing": ["objection_theme"]}
        return "success", {"objection_theme": key, "variants": OUTREACH["objection_themes"][key]["variants"]}
    return "denied", {"reason": f"Unknown tool: {name}"}


app = FastAPI(title="GTM Recipe/Tool Baseline Agent")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/ask")
async def ask(req: AskRequest) -> dict[str, Any]:
    plan_prompt = (
        f"Tools:\n{json.dumps(TOOL_SCHEMA, indent=2)}\n\n"
        f"Actor: {req.actor_id or 'sales_leader'}\n"
        f"History: {json.dumps(req.history or [])}\n"
        f"Question: {req.question}\n"
    )
    started = time.perf_counter()
    plan, plan_usage, plan_stats = await _call_model_json(RECIPE_PROMPT, plan_prompt)
    selected_tool = str(plan.get("selected_tool") or "").strip()
    tool_arguments = plan.get("tool_arguments") if isinstance(plan.get("tool_arguments"), dict) else {}
    outcome, tool_result = _execute_tool(selected_tool, tool_arguments)
    final_prompt = (
        f"Question: {req.question}\n"
        f"Selected tool: {selected_tool}\n"
        f"Outcome: {outcome}\n"
        f"Tool result: {json.dumps(tool_result, indent=2)}\n"
    )
    final, final_usage, final_stats = await _call_model_json(FINAL_PROMPT, final_prompt)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    usage = {
        "prompt_tokens": int(plan_usage.get("prompt_tokens") or 0) + int(final_usage.get("prompt_tokens") or 0),
        "completion_tokens": int(plan_usage.get("completion_tokens") or 0) + int(final_usage.get("completion_tokens") or 0),
        "total_tokens": int(plan_usage.get("total_tokens") or 0) + int(final_usage.get("total_tokens") or 0),
        "plan_usage": plan_usage,
        "final_usage": final_usage,
    }
    prompt_stats = {
        "system_prompt_chars": plan_stats["system_prompt_chars"] + final_stats["system_prompt_chars"],
        "user_prompt_chars": plan_stats["user_prompt_chars"] + final_stats["user_prompt_chars"],
        "tool_schema_chars": plan_stats["tool_schema_chars"],
    }
    return {
        "runtime": "gtm-recipe-tool-baseline",
        "model": OPENAI_MODEL,
        "question": req.question,
        "actor_id": req.actor_id or "sales_leader",
        "outcome": outcome,
        "selected_tool": selected_tool,
        "tool_arguments": tool_arguments,
        "tool_result": tool_result,
        "planner": {
            "mode": "consumer_side_recipe_tool_selection",
            "rationale": plan.get("rationale"),
            "prompt_stats": prompt_stats,
            "usage": usage,
        },
        "usage": usage,
        "prompt_stats": prompt_stats,
        "loop_counts": {
            "planner_loops": 2,
            "tool_invoke_loops": 1,
            "total_loops": 3,
        },
        "elapsed_ms": elapsed_ms,
        "user_message": final.get("user_message"),
        "result_summary": final.get("result_summary"),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "9313")))
