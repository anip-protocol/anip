#!/usr/bin/env python3
"""Hardened ANIP Execution Scenario Validation runner.

This file remains the stable CLI and import compatibility surface, while the
evaluator logic itself now lives in the adjacent ``anip_evaluator`` package.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml
from anip_evaluator import (
    CATEGORY_EVALUATORS,
    SCHEMA_DIR,
    evaluate,
    evaluate_cross_service,
    evaluate_generic,
    evaluate_observability,
    evaluate_orchestration,
    evaluate_recovery,
    evaluate_safety,
    load_json,
    load_yaml,
    to_markdown,
    validate_payload,
)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run ANIP Execution Scenario Validation.")
    parser.add_argument("--requirements", required=True, type=Path)
    parser.add_argument("--proposal", required=True, type=Path)
    parser.add_argument("--scenario", required=True, type=Path)
    parser.add_argument("--evaluation-out", type=Path, help="Write structured evaluation YAML here.")
    parser.add_argument("--markdown-out", type=Path, help="Write markdown report here.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    requirements_doc = load_yaml(args.requirements)
    proposal_doc = load_yaml(args.proposal)
    scenario_doc = load_yaml(args.scenario)

    validate_payload(requirements_doc, SCHEMA_DIR / "requirements.schema.json")
    validate_payload(proposal_doc, SCHEMA_DIR / "proposal.schema.json")
    validate_payload(scenario_doc, SCHEMA_DIR / "scenario.schema.json")

    evaluation_doc = evaluate(requirements_doc, proposal_doc, scenario_doc)
    validate_payload(evaluation_doc, SCHEMA_DIR / "evaluation.schema.json")

    markdown = to_markdown(evaluation_doc)

    if args.evaluation_out:
        args.evaluation_out.parent.mkdir(parents=True, exist_ok=True)
        with args.evaluation_out.open("w", encoding="utf-8") as fh:
            yaml.safe_dump(evaluation_doc, fh, sort_keys=False)

    if args.markdown_out:
        args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_out.write_text(markdown, encoding="utf-8")

    print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
