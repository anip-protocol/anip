"""Run a benchmark case file against an HTTP agent endpoint."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _post_json(url: str, payload: dict[str, Any], timeout_seconds: float) -> tuple[int, dict[str, Any]]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            return exc.code, {"error": body}


def _failure_type(payload: dict[str, Any]) -> str | None:
    if isinstance(payload.get("failure"), dict):
        return str(payload["failure"].get("type") or "") or None
    anip_result = payload.get("anip_result")
    if isinstance(anip_result, dict) and isinstance(anip_result.get("failure"), dict):
        return str(anip_result["failure"].get("type") or "") or None
    return None


def _observed_outcome(payload: dict[str, Any]) -> str:
    if payload.get("outcome"):
        return str(payload["outcome"])
    anip_result = payload.get("anip_result")
    if isinstance(anip_result, dict):
        if anip_result.get("success") is True:
            return "success"
        failure = anip_result.get("failure")
        if isinstance(failure, dict):
            return str(failure.get("type") or "unknown")
    failure = _failure_type(payload)
    if failure:
        return failure
    if payload.get("success") is True:
        return "success"
    return "unknown"


def _loop_counts(payload: dict[str, Any]) -> dict[str, int]:
    raw = payload.get("loop_counts")
    if isinstance(raw, dict):
        return {
            "planner_loops": int(raw.get("planner_loops") or 0),
            "service_invoke_loops": int(raw.get("service_invoke_loops") or 0),
            "tool_invoke_loops": int(raw.get("tool_invoke_loops") or raw.get("service_invoke_loops") or 0),
            "total_loops": int(raw.get("total_loops") or 0),
        }
    return {"planner_loops": 0, "service_invoke_loops": 0, "tool_invoke_loops": 0, "total_loops": 0}


def _usage(payload: dict[str, Any]) -> dict[str, Any]:
    for key in ("usage", "model_usage"):
        if isinstance(payload.get(key), dict):
            return dict(payload[key])
    planner = payload.get("planner")
    if isinstance(planner, dict) and isinstance(planner.get("usage"), dict):
        return dict(planner["usage"])
    return {}


def _planner(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("planner")
    return dict(value) if isinstance(value, dict) else {}


def _planner_fallback(payload: dict[str, Any]) -> dict[str, Any]:
    planner = _planner(payload)
    value = planner.get("fallback")
    return dict(value) if isinstance(value, dict) else {}


def _planner_usage(payload: dict[str, Any], key: str) -> dict[str, Any]:
    planner = _planner(payload)
    value = planner.get(key)
    return dict(value) if isinstance(value, dict) else {}


def _prompt_stats(payload: dict[str, Any]) -> dict[str, Any]:
    planner = payload.get("planner")
    if isinstance(planner, dict) and isinstance(planner.get("prompt_stats"), dict):
        return dict(planner["prompt_stats"])
    stats = payload.get("prompt_stats")
    if isinstance(stats, dict):
        return dict(stats)
    return {}


def _estimated_tokens_from_prompt_stats(stats: dict[str, Any]) -> int | None:
    chars = 0
    for key, value in stats.items():
        if key.endswith("_chars") and isinstance(value, int):
            chars += value
    if chars <= 0:
        return None
    return math.ceil(chars / 4)


def _pricing_for_model(pricing: dict[str, Any] | None, model: str | None) -> dict[str, Any] | None:
    if not pricing or not model:
        return None
    models = pricing.get("models")
    if not isinstance(models, dict):
        return None
    candidate = models.get(model)
    return dict(candidate) if isinstance(candidate, dict) else None


def _estimate_cost(usage: dict[str, Any], pricing: dict[str, Any] | None, model: str | None) -> dict[str, Any] | None:
    model_pricing = _pricing_for_model(pricing, model)
    if not model_pricing:
        return None
    input_rate = model_pricing.get("input_per_million_tokens")
    output_rate = model_pricing.get("output_per_million_tokens")
    if input_rate is None or output_rate is None:
        return None
    prompt_tokens = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
    completion_tokens = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
    if prompt_tokens <= 0 and completion_tokens <= 0:
        return None
    input_cost = prompt_tokens * float(input_rate) / 1_000_000
    output_cost = completion_tokens * float(output_rate) / 1_000_000
    return {
        "currency": pricing.get("currency") or "USD",
        "input_cost": round(input_cost, 8),
        "output_cost": round(output_cost, 8),
        "total_cost": round(input_cost + output_cost, 8),
        "pricing_model": model,
    }


def _estimate_response_cost(payload: dict[str, Any], pricing: dict[str, Any] | None, model: str | None) -> dict[str, Any] | None:
    fallback = _planner_fallback(payload)
    primary_usage = _planner_usage(payload, "primary_usage")
    fallback_usage = _planner_usage(payload, "fallback_usage")
    if fallback and (primary_usage or fallback_usage):
        currency = pricing.get("currency") if isinstance(pricing, dict) else "USD"
        parts: list[dict[str, Any]] = []
        primary_model = str(fallback.get("primary_model") or model or "")
        fallback_model = str(fallback.get("fallback_model") or "")
        for label, usage, usage_model in (
            ("primary", primary_usage, primary_model),
            ("fallback", fallback_usage, fallback_model),
        ):
            if not usage or not usage_model:
                continue
            cost = _estimate_cost(usage, pricing, usage_model)
            if cost:
                parts.append({"tier": label, **cost})
        if parts:
            return {
                "currency": currency or "USD",
                "total_cost": round(sum(float(part["total_cost"]) for part in parts), 8),
                "parts": parts,
            }
    return _estimate_cost(_usage(payload), pricing, model)


def _sum_estimated_costs(costs: list[dict[str, Any] | None]) -> dict[str, Any] | None:
    valid = [cost for cost in costs if isinstance(cost, dict) and cost.get("total_cost") is not None]
    if not valid:
        return None
    currency = next((str(cost.get("currency")) for cost in valid if cost.get("currency")), "USD")
    return {
        "currency": currency,
        "total_cost": round(sum(float(cost["total_cost"]) for cost in valid), 8),
        "parts": valid,
    }


def _usage_token_totals(usage: dict[str, Any]) -> dict[str, int]:
    prompt_details = usage.get("prompt_tokens_details")
    completion_details = usage.get("completion_tokens_details")
    return {
        "prompt_tokens": int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0),
        "completion_tokens": int(usage.get("completion_tokens") or usage.get("output_tokens") or 0),
        "total_tokens": int(usage.get("total_tokens") or 0),
        "cached_tokens": int(prompt_details.get("cached_tokens") or 0) if isinstance(prompt_details, dict) else 0,
        "reasoning_tokens": int(completion_details.get("reasoning_tokens") or 0) if isinstance(completion_details, dict) else 0,
    }


def _sum_usage(usages: list[dict[str, Any]]) -> dict[str, int]:
    totals = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "cached_tokens": 0,
        "reasoning_tokens": 0,
    }
    for usage in usages:
        if not isinstance(usage, dict):
            continue
        item = _usage_token_totals(usage)
        for key in totals:
            totals[key] += item[key]
    return totals


def _model(payload: dict[str, Any]) -> str | None:
    planner = payload.get("planner")
    if isinstance(planner, dict) and planner.get("model"):
        return str(planner["model"])
    if payload.get("model"):
        return str(payload["model"])
    return None


def _selected(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "capability": payload.get("selected_capability") or payload.get("planned_capability"),
        "service": payload.get("selected_service"),
        "tool": payload.get("selected_tool"),
        "parameters": payload.get("parameters") or payload.get("tool_arguments"),
    }


def _result_fallback_summary(response: dict[str, Any]) -> dict[str, Any]:
    fallback = _planner_fallback(response)
    return {
        "enabled": bool(fallback.get("enabled")),
        "used": bool(fallback.get("used")),
        "reason": fallback.get("reason"),
        "primary_model": fallback.get("primary_model"),
        "fallback_model": fallback.get("fallback_model"),
        "primary_usage": _planner_usage(response, "primary_usage"),
        "fallback_usage": _planner_usage(response, "fallback_usage"),
    }


def _run_case(
    agent: str,
    agent_url: str,
    case: dict[str, Any],
    timeout_seconds: float,
    pricing: dict[str, Any] | None,
) -> dict[str, Any]:
    if isinstance(case.get("turns"), list):
        return _run_multi_turn_case(agent, agent_url, case, timeout_seconds, pricing)
    request_payload = {
        "question": case["question"],
        "actor_id": case.get("actor_id") or "sales_leader",
        "history": case.get("history") or [],
    }
    started = time.perf_counter()
    status, response = _post_json(agent_url, request_payload, timeout_seconds)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    observed = _observed_outcome(response)
    expected = str((case.get("expected") or {}).get("outcome") or "")
    prompt_stats = _prompt_stats(response)
    usage = _usage(response)
    model = _model(response)
    estimated_cost = _estimate_response_cost(response, pricing, model)
    return {
        "id": case["id"],
        "category": case.get("category"),
        "agent": agent,
        "actor_id": request_payload["actor_id"],
        "question": case["question"],
        "http_status": status,
        "elapsed_ms": elapsed_ms,
        "expected_outcome": expected,
        "observed_outcome": observed,
        "passed": observed == expected,
        "model": model,
        "loop_counts": _loop_counts(response),
        "selected": _selected(response),
        "failure_type": _failure_type(response),
        "usage": usage,
        "estimated_cost": estimated_cost,
        "fallback": _result_fallback_summary(response),
        "prompt_stats": prompt_stats,
        "estimated_prompt_tokens": _estimated_tokens_from_prompt_stats(prompt_stats),
        "raw_response": response,
    }


def _history_assistant_content(response: dict[str, Any]) -> str:
    if response.get("user_message"):
        return str(response["user_message"])
    planner = response.get("planner")
    if isinstance(planner, dict) and planner.get("user_message"):
        return str(planner["user_message"])
    failure = _failure_type(response)
    if failure:
        return failure
    return _observed_outcome(response)


def _run_multi_turn_case(
    agent: str,
    agent_url: str,
    case: dict[str, Any],
    timeout_seconds: float,
    pricing: dict[str, Any] | None,
) -> dict[str, Any]:
    actor_id = case.get("actor_id") or "sales_leader"
    history = list(case.get("history") or [])
    turn_results: list[dict[str, Any]] = []
    started = time.perf_counter()
    for index, turn in enumerate(case["turns"], start=1):
        question = str(turn["question"])
        request_payload = {
            "question": question,
            "actor_id": actor_id,
            "history": history,
        }
        turn_started = time.perf_counter()
        status, response = _post_json(agent_url, request_payload, timeout_seconds)
        elapsed_ms = round((time.perf_counter() - turn_started) * 1000, 2)
        observed = _observed_outcome(response)
        expected = str((turn.get("expected") or {}).get("outcome") or "")
        prompt_stats = _prompt_stats(response)
        usage = _usage(response)
        model = _model(response)
        estimated_cost = _estimate_response_cost(response, pricing, model)
        turn_result = {
            "turn": index,
            "question": question,
            "http_status": status,
            "elapsed_ms": elapsed_ms,
            "expected_outcome": expected,
            "observed_outcome": observed,
            "passed": observed == expected,
            "model": model,
            "loop_counts": _loop_counts(response),
            "selected": _selected(response),
            "failure_type": _failure_type(response),
            "usage": usage,
            "estimated_cost": estimated_cost,
            "fallback": _result_fallback_summary(response),
            "prompt_stats": prompt_stats,
            "estimated_prompt_tokens": _estimated_tokens_from_prompt_stats(prompt_stats),
            "raw_response": response,
        }
        turn_results.append(turn_result)
        history.append({"role": "user", "content": question})
        assistant_entry: dict[str, Any] = {"role": "assistant", "content": _history_assistant_content(response)}
        continuation = response.get("continuation")
        if isinstance(continuation, dict):
            assistant_entry["continuation"] = continuation
        history.append(assistant_entry)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    final_turn = turn_results[-1] if turn_results else {}
    loop_counts = {
        "planner_loops": sum(int(item["loop_counts"].get("planner_loops") or 0) for item in turn_results),
        "service_invoke_loops": sum(int(item["loop_counts"].get("service_invoke_loops") or 0) for item in turn_results),
        "tool_invoke_loops": sum(int(item["loop_counts"].get("tool_invoke_loops") or 0) for item in turn_results),
        "total_loops": sum(int(item["loop_counts"].get("total_loops") or 0) for item in turn_results),
    }
    estimated_prompt_tokens = sum(int(item.get("estimated_prompt_tokens") or 0) for item in turn_results)
    usage = _sum_usage([dict(item.get("usage") or {}) for item in turn_results])
    model = final_turn.get("model")
    primary_usage = _sum_usage([dict((item.get("fallback") or {}).get("primary_usage") or {}) for item in turn_results])
    fallback_usage = _sum_usage([dict((item.get("fallback") or {}).get("fallback_usage") or {}) for item in turn_results])
    fallback_turns = [item for item in turn_results if (item.get("fallback") or {}).get("used")]
    return {
        "id": case["id"],
        "category": case.get("category"),
        "agent": agent,
        "actor_id": actor_id,
        "question": str(case.get("question") or final_turn.get("question") or ""),
        "turn_count": len(turn_results),
        "http_status": final_turn.get("http_status"),
        "elapsed_ms": elapsed_ms,
        "expected_outcome": final_turn.get("expected_outcome"),
        "observed_outcome": final_turn.get("observed_outcome"),
        "passed": all(item["passed"] for item in turn_results),
        "model": model,
        "loop_counts": loop_counts,
        "selected": final_turn.get("selected"),
        "failure_type": final_turn.get("failure_type"),
        "usage": usage,
        "estimated_cost": _sum_estimated_costs([item.get("estimated_cost") for item in turn_results]),
        "fallback": {
            "enabled": any(bool((item.get("fallback") or {}).get("enabled")) for item in turn_results),
            "used": bool(fallback_turns),
            "turns": len(fallback_turns),
            "reasons": [
                str((item.get("fallback") or {}).get("reason"))
                for item in fallback_turns
                if (item.get("fallback") or {}).get("reason")
            ],
            "primary_usage": primary_usage,
            "fallback_usage": fallback_usage,
        },
        "prompt_stats": {},
        "estimated_prompt_tokens": estimated_prompt_tokens or None,
        "turn_results": turn_results,
    }


def _summarize(agent: str, suite: str, cases: list[dict[str, Any]], results: list[dict[str, Any]]) -> dict[str, Any]:
    passed = sum(1 for item in results if item["passed"])
    loop_total = sum(int(item["loop_counts"].get("total_loops") or 0) for item in results)
    elapsed_total = sum(float(item["elapsed_ms"]) for item in results)
    estimated_prompt_tokens = sum(int(item.get("estimated_prompt_tokens") or 0) for item in results)
    usage_totals = _sum_usage([dict(item.get("usage") or {}) for item in results])
    primary_usage_totals = _sum_usage([dict((item.get("fallback") or {}).get("primary_usage") or {}) for item in results])
    fallback_usage_totals = _sum_usage([dict((item.get("fallback") or {}).get("fallback_usage") or {}) for item in results])
    has_usage = any(value > 0 for value in usage_totals.values())
    fallback_items = [item for item in results if (item.get("fallback") or {}).get("used")]
    fallback_reasons: dict[str, int] = {}
    for item in fallback_items:
        fallback = item.get("fallback") if isinstance(item.get("fallback"), dict) else {}
        reasons = fallback.get("reasons") if isinstance(fallback.get("reasons"), list) else [fallback.get("reason")]
        for reason in reasons:
            if not reason:
                continue
            reason_text = str(reason)
            fallback_reasons[reason_text] = fallback_reasons.get(reason_text, 0) + 1
    total_cost = 0.0
    has_cost = False
    currency = None
    for item in results:
        estimated_cost = item.get("estimated_cost")
        if isinstance(estimated_cost, dict) and estimated_cost.get("total_cost") is not None:
            has_cost = True
            total_cost += float(estimated_cost["total_cost"])
            currency = estimated_cost.get("currency") or currency
    return {
        "agent": agent,
        "suite": suite,
        "case_count": len(cases),
        "passed": passed,
        "failed": len(cases) - passed,
        "pass_rate": round(passed / len(cases), 4) if cases else 0.0,
        "total_loops": loop_total,
        "average_loops": round(loop_total / len(cases), 2) if cases else 0.0,
        "total_elapsed_ms": round(elapsed_total, 2),
        "average_elapsed_ms": round(elapsed_total / len(cases), 2) if cases else 0.0,
        "estimated_prompt_tokens": estimated_prompt_tokens or None,
        "fallback": {
            "count": len(fallback_items),
            "rate": round(len(fallback_items) / len(cases), 4) if cases else 0.0,
            "reasons": fallback_reasons,
            "primary_usage": (
                {
                    **primary_usage_totals,
                    "average_total_tokens": round(primary_usage_totals["total_tokens"] / len(cases), 2) if cases else 0.0,
                    "cached_token_ratio": (
                        round(primary_usage_totals["cached_tokens"] / primary_usage_totals["prompt_tokens"], 4)
                        if primary_usage_totals["prompt_tokens"] > 0
                        else 0.0
                    ),
                }
                if any(value > 0 for value in primary_usage_totals.values())
                else None
            ),
            "fallback_usage": (
                {
                    **fallback_usage_totals,
                    "average_total_tokens": round(fallback_usage_totals["total_tokens"] / len(cases), 2) if cases else 0.0,
                    "cached_token_ratio": (
                        round(fallback_usage_totals["cached_tokens"] / fallback_usage_totals["prompt_tokens"], 4)
                        if fallback_usage_totals["prompt_tokens"] > 0
                        else 0.0
                    ),
                }
                if any(value > 0 for value in fallback_usage_totals.values())
                else None
            ),
        },
        "usage": (
            {
                **usage_totals,
                "average_total_tokens": round(usage_totals["total_tokens"] / len(cases), 2) if cases else 0.0,
                "cached_token_ratio": (
                    round(usage_totals["cached_tokens"] / usage_totals["prompt_tokens"], 4)
                    if usage_totals["prompt_tokens"] > 0
                    else 0.0
                ),
            }
            if has_usage
            else None
        ),
        "estimated_cost": (
            {
                "currency": currency or "USD",
                "total_cost": round(total_cost, 8),
                "average_cost": round(total_cost / len(cases), 8) if cases else 0.0,
            }
            if has_cost
            else None
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", required=True)
    parser.add_argument("--agent-url", required=True)
    parser.add_argument("--cases", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--pricing", help="Optional pricing JSON used to estimate costs from reported token usage.")
    parser.add_argument("--timeout-seconds", type=float, default=90.0)
    args = parser.parse_args()

    cases_path = Path(args.cases)
    suite = _read_json(cases_path)
    pricing = _read_json(Path(args.pricing)) if args.pricing else None
    cases = list(suite.get("cases") or [])
    run_id = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")
    results = [_run_case(args.agent, args.agent_url, case, args.timeout_seconds, pricing) for case in cases]
    output = {
        "schema_version": "anip-agent-benchmark-run.v1",
        "run_id": run_id,
        "created_at": dt.datetime.now(dt.UTC).isoformat(),
        "agent": args.agent,
        "agent_url": args.agent_url,
        "cases_path": str(cases_path),
        "summary": _summarize(args.agent, str(suite.get("suite") or cases_path.stem), cases, results),
        "results": results,
    }
    output_path = Path(args.output_dir) / f"{args.agent}-{run_id}.json"
    latest_path = Path(args.output_dir) / f"{args.agent}-latest.json"
    _write_json(output_path, output)
    _write_json(latest_path, output)
    print(json.dumps({"summary": output["summary"], "output_path": str(output_path)}, indent=2, sort_keys=True))
    return 0 if output["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
