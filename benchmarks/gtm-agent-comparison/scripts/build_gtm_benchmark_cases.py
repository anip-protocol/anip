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


def _load_variation_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for path in sorted(VARIATION_BANK_DIR.glob("phase*-variation-bank-20.json")):
        payload = _read_json(path)
        for case in payload.get("cases") or []:
            cases.append(dict(case))
    return cases


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=["question-bank", "variation-bank", "all"], default="all")
    parser.add_argument("--output", required=True)
    parser.add_argument("--default-actor-id", default="sales_leader")
    args = parser.parse_args()

    cases: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    sources: list[str] = []
    if args.suite in {"question-bank", "all"}:
        question_cases, skipped = _load_question_bank_cases(args.default_actor_id)
        cases.extend(question_cases)
        sources.append(str(QUESTION_BANK_DIR))
    if args.suite in {"variation-bank", "all"}:
        cases.extend(_load_variation_cases())
        sources.append(str(VARIATION_BANK_DIR))

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
