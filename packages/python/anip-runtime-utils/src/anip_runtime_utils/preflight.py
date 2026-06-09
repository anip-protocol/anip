"""Reusable preflight helpers for bounded agent runtimes."""

from __future__ import annotations

from typing import Any


def contains_any_phrase(text: str, phrases: list[str]) -> bool:
    lowered = text.lower()
    return any(phrase.lower() in lowered for phrase in phrases)


def build_denied_preflight_result(
    *,
    question: str,
    model: str,
    base_url: str,
    rationale: str,
    user_message: str,
    detail: str,
    resolution_action: str,
    resolution_requires: str,
) -> dict[str, Any]:
    return {
        "runtime": "llm",
        "question": question,
        "loop_counts": {
            "planner_loops": 0,
            "service_invoke_loops": 0,
            "total_loops": 0,
        },
        "planner": {
            "model": model,
            "base_url": base_url,
            "rationale": rationale,
            "user_message": user_message,
        },
        "selected_capability": None,
        "parameters": {},
        "capability_metadata": None,
        "anip_result": {
            "success": False,
            "failure": {
                "type": "denied",
                "detail": detail,
                "resolution": {
                    "action": resolution_action,
                    "requires": resolution_requires,
                },
            },
        },
    }
