"""Execute GTM question-bank artifacts through the live regression harness."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[5]
QUESTION_BANK_DIR = REPO_ROOT / "docs" / "examples" / "gtm-showcase" / "question-banks"
RUNNER_PATH = Path(__file__).with_name("run_phase1_regression.py")
OUTPUT_DIR = REPO_ROOT / "docs" / "examples" / "gtm-showcase" / "question-bank-runs"
DEFAULT_RUNTIME_URL = "http://127.0.0.1:9304"

ACTOR_PREFIX_RE = re.compile(r"^\[(?P<actor>[a-z0-9_]+)\]\s*(?P<question>.+)$", re.IGNORECASE)
FOLLOWUP_RE = re.compile(r"^Use (?P<followup>.+?) after asking (?P<initial>.+?)[.?!]?$", re.IGNORECASE)


def _parse_actor(question: str) -> tuple[str | None, str]:
    match = ACTOR_PREFIX_RE.match(question.strip())
    if not match:
        return None, question.strip()
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


def _entry_to_case(entry: dict[str, Any], default_actor_id: str = "sales_leader") -> dict[str, Any]:
    actor_id, cleaned_question = _parse_actor(str(entry["question"]))
    actor_id = actor_id or default_actor_id
    expected_outcome = str(entry["expected_outcome"])
    category = str(entry["category"])
    if str(entry["id"]) == "compound-bottleneck-draft-safe-stop":
        expected_outcome = "approval_required"

    case: dict[str, Any] = {
        "id": str(entry["id"]),
        "category": category,
        "actor_id": actor_id,
    }

    if category == "clarification_followup":
        match = FOLLOWUP_RE.match(cleaned_question)
        if not match:
            raise ValueError(f"Could not parse clarification_followup entry: {cleaned_question}")
        followup_text = match.group("followup").strip()
        initial_question = _normalize_initial_followup_question(match.group("initial"))
        if followup_text and followup_text[-1] not in ".?!":
            followup_text = f"{followup_text}."
        case["turns"] = [
            {
                "question": initial_question,
                "expected": {"outcome": "clarification_required"},
            },
            {
                "question": followup_text,
                "expected": {"outcome": expected_outcome},
            },
        ]
        return case

    case["question"] = cleaned_question
    case["expected"] = {"outcome": expected_outcome}
    return case


def _bank_path(phase: int) -> Path:
    return QUESTION_BANK_DIR / f"phase{phase}-question-bank.json"


def _suite_for_phase(phase: int) -> dict[str, Any]:
    payload = json.loads(_bank_path(phase).read_text())
    entries = payload["entries"]
    cases = [_entry_to_case(entry) for entry in entries]
    return {
        "suite": f"gtm_phase{phase}_question_bank",
        "cases": cases,
    }


def _run_suite(suite: dict[str, Any], runtime_url: str, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
        temp_path = Path(handle.name)
        handle.write(json.dumps(suite, indent=2))
        handle.write("\n")
    try:
        command = [
            sys.executable,
            str(RUNNER_PATH),
            "--runtime-url",
            runtime_url,
            "--cases",
            str(temp_path),
            "--output-dir",
            str(output_dir),
        ]
        completed = subprocess.run(command, capture_output=True, text=True)
        stdout = completed.stdout.strip()
        result = json.loads(stdout) if stdout else {}
        result["returncode"] = completed.returncode
        result["stderr"] = completed.stderr.strip()
        return result
    finally:
        temp_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-url", default=DEFAULT_RUNTIME_URL)
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    parser.add_argument("--phase", type=int, action="append", dest="phases")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    if args.all:
        phases = list(range(1, 8))
    elif args.phases:
        phases = args.phases
    else:
        phases = [1]

    results: list[dict[str, Any]] = []
    for phase in phases:
        suite = _suite_for_phase(phase)
        result = _run_suite(suite, runtime_url=args.runtime_url, output_dir=Path(args.output_dir))
        result["phase"] = phase
        result["suite"] = suite["suite"]
        results.append(result)

    print(json.dumps({"runs": results}, indent=2))
    return 0 if all(item.get("returncode") == 0 for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
