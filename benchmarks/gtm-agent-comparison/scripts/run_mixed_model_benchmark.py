"""Run a benchmark with a primary agent and fallback agent.

This is intended for model-tier experiments such as "try nano first, then
fallback to mini when deterministic acceptance checks fail." The evaluator is
still the benchmark runner's expected-outcome assertion; the agent path itself
does not judge benchmark correctness.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
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
    anip_result = payload.get("anip_result")
    if isinstance(anip_result, dict):
        failure = anip_result.get("failure")
        if isinstance(failure, dict):
            value = failure.get("type")
            return str(value) if value else None
    failure = payload.get("failure")
    if isinstance(failure, dict):
        value = failure.get("type")
        return str(value) if value else None
    return None


def _observed_outcome(payload: dict[str, Any]) -> str:
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
    return str(payload.get("outcome") or "unknown")


def _usage(payload: dict[str, Any]) -> dict[str, Any]:
    planner = payload.get("planner")
    if isinstance(planner, dict) and isinstance(planner.get("usage"), dict):
        return dict(planner["usage"])
    value = payload.get("usage")
    return dict(value) if isinstance(value, dict) else {}


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
    totals = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cached_tokens": 0, "reasoning_tokens": 0}
    for usage in usages:
        item = _usage_token_totals(usage)
        for key in totals:
            totals[key] += item[key]
    return totals


def _loop_counts(payload: dict[str, Any]) -> dict[str, int]:
    raw = payload.get("loop_counts")
    if not isinstance(raw, dict):
        return {"planner_loops": 0, "service_invoke_loops": 0, "tool_invoke_loops": 0, "total_loops": 0}
    return {
        "planner_loops": int(raw.get("planner_loops") or 0),
        "service_invoke_loops": int(raw.get("service_invoke_loops") or 0),
        "tool_invoke_loops": int(raw.get("tool_invoke_loops") or raw.get("service_invoke_loops") or 0),
        "total_loops": int(raw.get("total_loops") or 0),
    }


def _selected(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "capability": payload.get("selected_capability") or payload.get("planned_capability"),
        "service": payload.get("selected_service"),
        "tool": payload.get("selected_tool"),
        "parameters": payload.get("parameters") or payload.get("tool_arguments"),
    }


def _model(payload: dict[str, Any]) -> str | None:
    planner = payload.get("planner")
    if isinstance(planner, dict) and planner.get("model"):
        return str(planner["model"])
    return str(payload.get("model")) if payload.get("model") else None


def _history_assistant_content(response: dict[str, Any]) -> str:
    planner = response.get("planner")
    if isinstance(planner, dict) and planner.get("user_message"):
        return str(planner["user_message"])
    failure = _failure_type(response)
    if failure:
        return failure
    return _observed_outcome(response)


def _accept_response(response: dict[str, Any], expected_outcome: str) -> bool:
    """Deterministic benchmark acceptance.

    This intentionally uses expected outcomes rather than another model. In a
    production mixed-model router this would be replaced by confidence signals,
    schema checks, contract outcome class checks, and deterministic validators.
    """

    return _observed_outcome(response) == expected_outcome


def _run_single_turn(
    *,
    primary_url: str,
    fallback_url: str,
    question: str,
    actor_id: str,
    history: list[dict[str, Any]],
    expected_outcome: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    request_payload = {"question": question, "actor_id": actor_id, "history": history}
    started = time.perf_counter()
    primary_status, primary_response = _post_json(primary_url, request_payload, timeout_seconds)
    primary_elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    accepted = primary_status < 500 and _accept_response(primary_response, expected_outcome)
    fallback_status: int | None = None
    fallback_response: dict[str, Any] | None = None
    fallback_elapsed_ms: float | None = None
    used_fallback = not accepted
    if used_fallback:
        fallback_started = time.perf_counter()
        fallback_status, fallback_response = _post_json(fallback_url, request_payload, timeout_seconds)
        fallback_elapsed_ms = round((time.perf_counter() - fallback_started) * 1000, 2)

    final_response = fallback_response if fallback_response is not None else primary_response
    final_status = fallback_status if fallback_status is not None else primary_status
    elapsed_ms = primary_elapsed_ms + (fallback_elapsed_ms or 0.0)
    return {
        "http_status": final_status,
        "elapsed_ms": round(elapsed_ms, 2),
        "expected_outcome": expected_outcome,
        "observed_outcome": _observed_outcome(final_response),
        "passed": _observed_outcome(final_response) == expected_outcome,
        "used_fallback": used_fallback,
        "model": _model(final_response),
        "loop_counts": _loop_counts(primary_response if fallback_response is None else fallback_response),
        "selected": _selected(final_response),
        "failure_type": _failure_type(final_response),
        "usage": _sum_usage([_usage(primary_response), _usage(fallback_response or {})]),
        "primary": {
            "http_status": primary_status,
            "elapsed_ms": primary_elapsed_ms,
            "observed_outcome": _observed_outcome(primary_response),
            "model": _model(primary_response),
            "selected": _selected(primary_response),
            "usage": _usage(primary_response),
        },
        "fallback": (
            {
                "http_status": fallback_status,
                "elapsed_ms": fallback_elapsed_ms,
                "observed_outcome": _observed_outcome(fallback_response or {}),
                "model": _model(fallback_response or {}),
                "selected": _selected(fallback_response or {}),
                "usage": _usage(fallback_response or {}),
            }
            if fallback_response is not None
            else None
        ),
        "raw_response": final_response,
    }


def _run_case(
    *,
    primary_url: str,
    fallback_url: str,
    case: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    actor_id = case.get("actor_id") or "sales_leader"
    history = list(case.get("history") or [])
    if isinstance(case.get("turns"), list):
        turn_results: list[dict[str, Any]] = []
        started = time.perf_counter()
        for index, turn in enumerate(case["turns"], start=1):
            result = _run_single_turn(
                primary_url=primary_url,
                fallback_url=fallback_url,
                question=str(turn["question"]),
                actor_id=actor_id,
                history=history,
                expected_outcome=str((turn.get("expected") or {}).get("outcome") or ""),
                timeout_seconds=timeout_seconds,
            )
            result["turn"] = index
            result["question"] = str(turn["question"])
            turn_results.append(result)
            history.append({"role": "user", "content": str(turn["question"])})
            history.append({"role": "assistant", "content": _history_assistant_content(result["raw_response"])})
        final = turn_results[-1]
        usage = _sum_usage([dict(item.get("usage") or {}) for item in turn_results])
        loops = {
            "planner_loops": sum(int(item["loop_counts"].get("planner_loops") or 0) for item in turn_results),
            "service_invoke_loops": sum(int(item["loop_counts"].get("service_invoke_loops") or 0) for item in turn_results),
            "tool_invoke_loops": sum(int(item["loop_counts"].get("tool_invoke_loops") or 0) for item in turn_results),
            "total_loops": sum(int(item["loop_counts"].get("total_loops") or 0) for item in turn_results),
        }
        return {
            "id": case["id"],
            "category": case.get("category"),
            "actor_id": actor_id,
            "turn_count": len(turn_results),
            "http_status": final["http_status"],
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
            "expected_outcome": final["expected_outcome"],
            "observed_outcome": final["observed_outcome"],
            "passed": all(item["passed"] for item in turn_results),
            "used_fallback": any(item["used_fallback"] for item in turn_results),
            "fallback_turns": sum(1 for item in turn_results if item["used_fallback"]),
            "model": final.get("model"),
            "loop_counts": loops,
            "selected": final.get("selected"),
            "failure_type": final.get("failure_type"),
            "usage": usage,
            "turn_results": turn_results,
        }

    result = _run_single_turn(
        primary_url=primary_url,
        fallback_url=fallback_url,
        question=str(case["question"]),
        actor_id=actor_id,
        history=history,
        expected_outcome=str((case.get("expected") or {}).get("outcome") or ""),
        timeout_seconds=timeout_seconds,
    )
    return {
        "id": case["id"],
        "category": case.get("category"),
        "actor_id": actor_id,
        "question": str(case["question"]),
        **result,
    }


def _primary_usage_for_result(result: dict[str, Any]) -> dict[str, int]:
    if isinstance(result.get("turn_results"), list):
        return _sum_usage([
            dict((turn.get("primary") or {}).get("usage") or {})
            for turn in result["turn_results"]
            if isinstance(turn, dict)
        ])
    primary = result.get("primary")
    return _usage_token_totals(dict(primary.get("usage") or {})) if isinstance(primary, dict) else _usage_token_totals({})


def _fallback_usage_for_result(result: dict[str, Any]) -> dict[str, int]:
    if isinstance(result.get("turn_results"), list):
        return _sum_usage([
            dict((turn.get("fallback") or {}).get("usage") or {})
            for turn in result["turn_results"]
            if isinstance(turn, dict) and isinstance(turn.get("fallback"), dict)
        ])
    fallback = result.get("fallback")
    return _usage_token_totals(dict(fallback.get("usage") or {})) if isinstance(fallback, dict) else _usage_token_totals({})


def _primary_elapsed_for_result(result: dict[str, Any]) -> float:
    if isinstance(result.get("turn_results"), list):
        return sum(float((turn.get("primary") or {}).get("elapsed_ms") or 0.0) for turn in result["turn_results"])
    primary = result.get("primary")
    return float(primary.get("elapsed_ms") or 0.0) if isinstance(primary, dict) else 0.0


def _fallback_elapsed_for_result(result: dict[str, Any]) -> float:
    if isinstance(result.get("turn_results"), list):
        return sum(float((turn.get("fallback") or {}).get("elapsed_ms") or 0.0) for turn in result["turn_results"])
    fallback = result.get("fallback")
    return float(fallback.get("elapsed_ms") or 0.0) if isinstance(fallback, dict) else 0.0


def _usage_summary(usage: dict[str, int], denominator: int) -> dict[str, Any]:
    return {
        **usage,
        "non_cached_prompt_tokens": max(0, usage["prompt_tokens"] - usage["cached_tokens"]),
        "average_total_tokens": round(usage["total_tokens"] / denominator, 2) if denominator else 0.0,
        "cached_token_ratio": round(usage["cached_tokens"] / usage["prompt_tokens"], 4) if usage["prompt_tokens"] else 0.0,
    }


def _summarize(agent: str, suite: str, cases: list[dict[str, Any]], results: list[dict[str, Any]]) -> dict[str, Any]:
    usage = _sum_usage([dict(item.get("usage") or {}) for item in results])
    primary_usage = _sum_usage([_primary_usage_for_result(item) for item in results])
    fallback_usage = _sum_usage([_fallback_usage_for_result(item) for item in results])
    fallback_count = sum(1 for item in results if item.get("used_fallback"))
    fallback_turns = sum(int(item.get("fallback_turns") or (1 if item.get("used_fallback") else 0)) for item in results)
    loops = sum(int((item.get("loop_counts") or {}).get("total_loops") or 0) for item in results)
    elapsed = sum(float(item.get("elapsed_ms") or 0) for item in results)
    primary_elapsed = sum(_primary_elapsed_for_result(item) for item in results)
    fallback_elapsed = sum(_fallback_elapsed_for_result(item) for item in results)
    passed = sum(1 for item in results if item.get("passed") is True)
    return {
        "agent": agent,
        "suite": suite,
        "case_count": len(cases),
        "passed": passed,
        "failed": len(cases) - passed,
        "pass_rate": round(passed / len(cases), 4) if cases else 0.0,
        "fallback_count": fallback_count,
        "fallback_rate": round(fallback_count / len(cases), 4) if cases else 0.0,
        "fallback_turns": fallback_turns,
        "total_loops": loops,
        "average_loops": round(loops / len(cases), 2) if cases else 0.0,
        "total_elapsed_ms": round(elapsed, 2),
        "average_elapsed_ms": round(elapsed / len(cases), 2) if cases else 0.0,
        "primary_elapsed_ms": round(primary_elapsed, 2),
        "fallback_elapsed_ms": round(fallback_elapsed, 2),
        "usage": _usage_summary(usage, len(cases)),
        "primary_usage": _usage_summary(primary_usage, len(cases)),
        "fallback_usage": _usage_summary(fallback_usage, len(cases)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", required=True)
    parser.add_argument("--primary-url", required=True)
    parser.add_argument("--fallback-url", required=True)
    parser.add_argument("--cases", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    args = parser.parse_args()

    cases_path = Path(args.cases)
    suite = _read_json(cases_path)
    cases = list(suite.get("cases") or [])
    run_id = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")
    results = [
        _run_case(primary_url=args.primary_url, fallback_url=args.fallback_url, case=case, timeout_seconds=args.timeout_seconds)
        for case in cases
    ]
    output = {
        "schema_version": "anip-mixed-model-benchmark-run.v1",
        "run_id": run_id,
        "created_at": dt.datetime.now(dt.UTC).isoformat(),
        "agent": args.agent,
        "primary_url": args.primary_url,
        "fallback_url": args.fallback_url,
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
