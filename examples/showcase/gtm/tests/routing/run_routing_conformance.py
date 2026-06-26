#!/usr/bin/env python3
"""Run deterministic GTM routing cases against an agent app profile."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from anip_runtime_utils.agent_consumption import (
    capability_match_score,
    missing_required_input_names,
    select_consumable_capability,
)


@dataclass(frozen=True)
class RouteResult:
    case_id: str
    ok: bool
    expected_decision: str
    observed_decision: str
    expected_capability: str | None
    observed_capability: str | None
    detail: str


def _load_profile(path: Path) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError("agent profile must be a JSON object")
    metadata = data.get("capability_metadata")
    if not isinstance(metadata, dict) or not metadata:
        raise ValueError("agent profile is missing capability_metadata")
    selection_hints = data.get("selection_hints")
    if not isinstance(selection_hints, list):
        selection_hints = []
    return (
        {str(capability_id): value for capability_id, value in metadata.items() if isinstance(value, dict)},
        [item for item in selection_hints if isinstance(item, dict)],
    )


def _capability_effects(capability: dict[str, Any], field: str) -> set[str]:
    effects = capability.get("business_effects")
    if not isinstance(effects, dict):
        return set()
    values = effects.get(field)
    if not isinstance(values, list):
        return set()
    return {str(value).strip() for value in values if str(value or "").strip()}


def _requested_effects(case: dict[str, Any]) -> set[str]:
    values = case.get("requested_effects")
    if not isinstance(values, list):
        return set()
    return {str(value).strip() for value in values if str(value or "").strip()}


def _best_scored_capability(utterance: str, metadata: dict[str, dict[str, Any]]) -> tuple[str | None, float]:
    best_capability: str | None = None
    best_score = 0.0
    for capability_id, capability_metadata in metadata.items():
        score = capability_match_score(utterance, capability_id, capability_metadata)
        if score > best_score:
            best_capability = capability_id
            best_score = score
    return best_capability, best_score


def _route_case(case: dict[str, Any], metadata: dict[str, dict[str, Any]], selection_hints: list[dict[str, Any]]) -> tuple[str, str | None, str]:
    utterance = str(case.get("utterance") or "")
    requested = _requested_effects(case)
    if requested:
        producing = [
            capability_id
            for capability_id, capability_metadata in metadata.items()
            if requested <= _capability_effects(capability_metadata, "produces")
        ]
        if not producing:
            return "deny", None, f"no capability declares requested effects {sorted(requested)}"

    selected, score = _best_scored_capability(utterance, metadata)
    if selected is None or score <= 0:
        return "clarify", None, "no scored capability"

    selected = select_consumable_capability(utterance, selected, metadata, selection_hints)
    capability_metadata = metadata[selected]
    forbidden = _capability_effects(capability_metadata, "does_not_produce")
    blocked = sorted(requested & forbidden)
    if blocked:
        return "deny", selected, f"selected capability forbids requested effects {blocked}"

    missing = missing_required_input_names(utterance, capability_metadata)
    if missing:
        return "clarify", selected, f"missing required inputs {sorted(missing)}"
    return "invoke", selected, f"score={score:.3f}"


def _run_case(case: dict[str, Any], metadata: dict[str, dict[str, Any]], selection_hints: list[dict[str, Any]]) -> RouteResult:
    case_id = str(case.get("id") or "unnamed")
    expected_decision = str(case["expected_decision"])
    expected_capability = case.get("expected_capability")
    expected_capability = str(expected_capability) if expected_capability is not None else None
    observed_decision, observed_capability, detail = _route_case(case, metadata, selection_hints)
    ok = observed_decision == expected_decision and observed_capability == expected_capability
    return RouteResult(
        case_id=case_id,
        ok=ok,
        expected_decision=expected_decision,
        observed_decision=observed_decision,
        expected_capability=expected_capability,
        observed_capability=observed_capability,
        detail=detail,
    )


def _load_cases(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text())
    if not isinstance(data, list):
        raise ValueError("cases file must contain a JSON array")
    return [item for item in data if isinstance(item, dict)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True, type=Path, help="Path to agent-consumption/agent-app-profile.json")
    parser.add_argument("--cases", required=True, type=Path, help="Path to routing cases JSON")
    args = parser.parse_args()

    metadata, selection_hints = _load_profile(args.profile)
    results = [_run_case(case, metadata, selection_hints) for case in _load_cases(args.cases)]
    failures = [result for result in results if not result.ok]
    for result in results:
        status = "PASS" if result.ok else "FAIL"
        print(
            f"{status} {result.case_id}: "
            f"decision expected={result.expected_decision} observed={result.observed_decision}; "
            f"capability expected={result.expected_capability} observed={result.observed_capability}; "
            f"{result.detail}"
        )
    print(f"\n{len(results) - len(failures)}/{len(results)} routing conformance cases passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
