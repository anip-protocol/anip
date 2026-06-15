"""Build GTM benchmark case suites from showcase question banks."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
QUESTION_BANK_DIR = REPO_ROOT / "docs" / "examples" / "gtm-showcase" / "question-banks"
VARIATION_BANK_DIR = REPO_ROOT / "docs" / "examples" / "gtm-showcase" / "variation-question-banks-v3"

ACTOR_PREFIX_RE = re.compile(r"^\[(?P<actor>[a-z0-9_]+)\]\s*(?P<question>.+)$", re.IGNORECASE)
FOLLOWUP_RE = re.compile(r"^Use (?P<followup>.+?) after asking (?P<initial>.+?)[.?!]?$", re.IGNORECASE)

MULTITURN_EXTENSION_SPECS = [
    {
        "id_prefix": "pipeline-risk-quarter",
        "actor_id": "sales_leader",
        "initials": [
            "Which deals are at risk, and why?",
            "Show me the risky pipeline accounts.",
            "Summarize pipeline risk for leadership.",
            "Which pipeline accounts need attention?",
            "Give me a bounded risk review.",
        ],
        "followups": ["Use 2017-Q1.", "Use 2017-Q2.", "Use 2017-Q3.", "Use 2017-Q4.", "Use the East region for 2017-Q2."],
        "final_outcome": "success",
        "category": "benchmark_multiturn_pipeline",
    },
    {
        "id_prefix": "pipeline-stalled-quarter",
        "actor_id": "sales_leader",
        "initials": [
            "Show stalled opportunities.",
            "Which opportunities have been open too long?",
            "Find the stalled deals.",
            "Show me aging open opportunities.",
            "Where is pipeline motion stuck?",
        ],
        "followups": ["Use 2017-Q1.", "Use 2017-Q2.", "Use 2017-Q3.", "Use 2017-Q4.", "Use 2017-Q2 and more than 30 days."],
        "final_outcome": "success",
        "category": "benchmark_multiturn_pipeline",
    },
    {
        "id_prefix": "enrichment-accounts",
        "actor_id": "sales_leader",
        "initials": [
            "Summarize firmographic context for important accounts.",
            "Show enrichment context for the accounts we should review.",
            "Give me account enrichment for the target accounts.",
            "Summarize account context for leadership.",
            "Show firmographic evidence for selected accounts.",
        ],
        "followups": [
            "Use Acme Corporation.",
            "Use Condax.",
            "Use Codehow.",
            "Use Acme Corporation and Codehow.",
            "Use Acme Corporation, Codehow, and Condax.",
        ],
        "final_outcome": "success",
        "category": "benchmark_multiturn_enrichment",
    },
    {
        "id_prefix": "lookalike-reference",
        "actor_id": "sales_leader",
        "initials": [
            "Find lookalike accounts.",
            "Show similar accounts to our best customer.",
            "Find accounts that resemble a known customer.",
            "Find accounts similar to a specific account.",
            "Find similar target accounts.",
        ],
        "followups": ["Use Condax.", "Use Acme Corporation.", "Use Codehow.", "Use Condax with a top five limit.", "Use Acme Corporation with a top three limit."],
        "final_outcome": "success",
        "category": "benchmark_multiturn_enrichment",
    },
    {
        "id_prefix": "outreach-target",
        "actor_id": "sales_leader",
        "initials": [
            "Draft outreach for the account.",
            "Prepare a follow-up message.",
            "Write a first-touch email.",
            "Draft a LinkedIn outreach note.",
            "Suggest follow-up content.",
        ],
        "followups": [
            "Use Acme Corporation.",
            "Use Condax.",
            "Use Codehow.",
            "Use Acme Corporation with a follow-up objective.",
            "Use Condax with a first-touch objective.",
        ],
        "final_outcome": "success",
        "category": "benchmark_multiturn_outreach",
    },
    {
        "id_prefix": "prioritization-cohort",
        "actor_id": "sales_leader",
        "initials": [
            "Score the leads.",
            "Prioritize the account cohort.",
            "Rank the highest-priority targets.",
            "Show the best accounts to work.",
            "Score a named lead cohort.",
        ],
        "followups": [
            "Use inbound_last_week.",
            "Use at_risk_q2.",
            "Use expansion_candidates_q2.",
            "Use at_risk_q2.",
            "Use inbound_last_week with a top five limit.",
        ],
        "final_outcome": "success",
        "category": "benchmark_multiturn_prioritization",
    },
    {
        "id_prefix": "routing-cohort",
        "actor_id": "rev_ops_manager",
        "initials": [
            "Route the leads to sales.",
            "Prepare lead routing.",
            "Prepare routing for the selected lead cohort.",
            "Create a routing preview.",
            "Route the latest cohort.",
        ],
        "followups": [
            "Use inbound_last_week.",
            "Use webinar_q2.",
            "Use inbound_last_week and target sales.",
            "Use webinar_q2 and target sales.",
            "Use inbound_last_week and stop at approval preview.",
        ],
        "final_outcome": "approval_required",
        "category": "benchmark_multiturn_approval",
    },
    {
        "id_prefix": "forecast-quarter",
        "actor_id": "sales_leader",
        "initials": [
            "Show the forecast.",
            "Summarize likely pipeline outlook.",
            "Give me the forecast view.",
            "Show the risk-adjusted forecast.",
            "Summarize forecast totals.",
        ],
        "followups": ["Use 2017-Q1.", "Use 2017-Q2.", "Use 2017-Q3.", "Use 2017-Q4.", "Use 2017-Q2 for East."],
        "final_outcome": "success",
        "category": "benchmark_multiturn_forecast",
    },
    {
        "id_prefix": "bottleneck-quarter",
        "actor_id": "sales_leader",
        "initials": [
            "Where are we bottlenecked?",
            "Show stage bottlenecks.",
            "Find the biggest pipeline bottlenecks.",
            "Show bottleneck evidence.",
            "Summarize stalled stage concentration.",
        ],
        "followups": ["Use 2017-Q1.", "Use 2017-Q2.", "Use 2017-Q3.", "Use 2017-Q4.", "Use East in 2017-Q2."],
        "final_outcome": "success",
        "category": "benchmark_multiturn_bottleneck",
    },
    {
        "id_prefix": "reassignment-quarter",
        "actor_id": "rev_ops_manager",
        "initials": [
            "Prepare a reassignment plan.",
            "Preview manager reassignment.",
            "Create an overload reassignment preview.",
            "Prepare territory reassignment.",
            "Show reassignment options.",
        ],
        "followups": ["Use 2017-Q1.", "Use 2017-Q2.", "Use 2017-Q3.", "Use 2017-Q4.", "Use East in 2017-Q2."],
        "final_outcome": "approval_required",
        "category": "benchmark_multiturn_approval",
    },
]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _parse_actor(question: str, default_actor_id: str) -> tuple[str, str]:
    match = ACTOR_PREFIX_RE.match(question.strip())
    if not match:
        return default_actor_id, question.strip()
    return match.group("actor"), match.group("question").strip()


def _normalize_initial_followup_question(raw: str) -> str:
    question = raw.strip()
    if question.lower().startswith("for lookalike accounts"):
        question = f"Find {question}"
    elif question.lower().startswith("for firmographic context"):
        question = f"Summarize {question}"
    elif question and question[0].islower():
        question = question[0].upper() + question[1:]
    if question and question[-1] not in ".?!":
        question = f"{question}?"
    return question


def _question_bank_followup_to_case(entry: dict[str, Any], default_actor_id: str) -> dict[str, Any] | None:
    actor_id, question = _parse_actor(str(entry["question"]), default_actor_id)
    match = FOLLOWUP_RE.match(question)
    if not match:
        return None
    followup_text = match.group("followup").strip()
    if followup_text and followup_text[-1] not in ".?!":
        followup_text = f"{followup_text}."
    return {
        "id": str(entry["id"]),
        "category": str(entry.get("category") or "clarification_followup"),
        "actor_id": actor_id,
        "turns": [
            {
                "question": _normalize_initial_followup_question(match.group("initial")),
                "expected": {"outcome": "clarification_required"},
            },
            {
                "question": followup_text,
                "expected": {"outcome": str(entry["expected_outcome"])},
            },
        ],
    }


def _question_bank_entry_to_case(entry: dict[str, Any], default_actor_id: str) -> dict[str, Any] | None:
    category = str(entry.get("category") or "")
    if category == "clarification_followup":
        return None
    actor_id, question = _parse_actor(str(entry["question"]), default_actor_id)
    expected_outcome = str(entry["expected_outcome"])
    if str(entry["id"]) == "compound-bottleneck-draft-safe-stop":
        expected_outcome = "approval_required"
    return {
        "id": str(entry["id"]),
        "category": category,
        "actor_id": actor_id,
        "question": question,
        "expected": {"outcome": expected_outcome},
    }


def _load_question_bank_cases(default_actor_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cases: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for path in sorted(QUESTION_BANK_DIR.glob("phase*-question-bank.json")):
        payload = _read_json(path)
        for entry in payload.get("entries") or []:
            case = _question_bank_entry_to_case(entry, default_actor_id)
            if case is None:
                skipped.append({"path": str(path), "id": entry.get("id"), "category": entry.get("category")})
            else:
                cases.append(case)
    return cases, skipped


def _load_question_bank_multiturn_cases(default_actor_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cases: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for path in sorted(QUESTION_BANK_DIR.glob("phase*-question-bank.json")):
        payload = _read_json(path)
        for entry in payload.get("entries") or []:
            if str(entry.get("category") or "") != "clarification_followup":
                continue
            case = _question_bank_followup_to_case(entry, default_actor_id)
            if case is None:
                skipped.append({"path": str(path), "id": entry.get("id"), "category": entry.get("category")})
            else:
                cases.append(case)
    return cases, skipped


def _load_variation_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for path in sorted(VARIATION_BANK_DIR.glob("phase*-variation-bank-20.json")):
        payload = _read_json(path)
        for case in payload.get("cases") or []:
            cases.append(dict(case))
    return cases


def _generated_multiturn_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for spec in MULTITURN_EXTENSION_SPECS:
        for index, (initial, followup) in enumerate(zip(spec["initials"], spec["followups"], strict=True), start=1):
            cases.append(
                {
                    "id": f"{spec['id_prefix']}-{index:02d}",
                    "category": spec["category"],
                    "actor_id": spec["actor_id"],
                    "turns": [
                        {"question": initial, "expected": {"outcome": "clarification_required"}},
                        {"question": followup, "expected": {"outcome": spec["final_outcome"]}},
                    ],
                }
            )
    return cases


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=["question-bank", "variation-bank", "multiturn", "all"], default="all")
    parser.add_argument("--output", required=True)
    parser.add_argument("--default-actor-id", default="sales_leader")
    args = parser.parse_args()

    cases: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    sources: list[str] = []
    if args.suite in {"question-bank", "all"}:
        question_cases, question_skipped = _load_question_bank_cases(args.default_actor_id)
        cases.extend(question_cases)
        if args.suite == "question-bank":
            skipped.extend(question_skipped)
        sources.append(str(QUESTION_BANK_DIR))
    if args.suite in {"variation-bank", "all"}:
        cases.extend(_load_variation_cases())
        sources.append(str(VARIATION_BANK_DIR))
    if args.suite in {"multiturn", "all"}:
        followup_cases, followup_skipped = _load_question_bank_multiturn_cases(args.default_actor_id)
        cases.extend(followup_cases)
        cases.extend(_generated_multiturn_cases())
        skipped.extend(followup_skipped)
        sources.append(str(QUESTION_BANK_DIR))
        sources.append("generated:benchmarks/gtm-agent-comparison/scripts/build_gtm_benchmark_cases.py#MULTITURN_EXTENSION_SPECS")

    payload = {
        "suite": f"gtm_{args.suite}_benchmark",
        "case_count": len(cases),
        "skipped_count": len(skipped),
        "skipped": skipped,
        "sources": sources,
        "cases": cases,
    }
    _write_json(Path(args.output), payload)
    print(json.dumps({"output": args.output, "case_count": len(cases), "skipped_count": len(skipped)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
