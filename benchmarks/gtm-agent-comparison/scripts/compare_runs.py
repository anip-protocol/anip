"""Compare two GTM benchmark run JSON files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _summary(run: dict[str, Any]) -> dict[str, Any]:
    return dict(run.get("summary") or {})


def _by_id(run: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item["id"]): item for item in run.get("results", []) if isinstance(item, dict) and item.get("id")}


def _delta(left: float | int | None, right: float | int | None) -> float | None:
    if left is None or right is None:
        return None
    return round(float(right) - float(left), 6)


def _markdown_table(rows: list[list[Any]]) -> str:
    if not rows:
        return ""
    header = rows[0]
    widths = [len(str(cell)) for cell in header]
    for row in rows[1:]:
        widths = [max(width, len(str(cell))) for width, cell in zip(widths, row, strict=True)]
    lines = []
    lines.append("| " + " | ".join(str(cell).ljust(width) for cell, width in zip(header, widths, strict=True)) + " |")
    lines.append("| " + " | ".join("-" * width for width in widths) + " |")
    for row in rows[1:]:
        lines.append("| " + " | ".join(str(cell).ljust(width) for cell, width in zip(row, widths, strict=True)) + " |")
    return "\n".join(lines)


def _cost(summary: dict[str, Any]) -> str:
    value = summary.get("estimated_cost")
    if not isinstance(value, dict):
        return "n/a"
    currency = value.get("currency") or "USD"
    total = value.get("total_cost")
    return "n/a" if total is None else f"{currency} {total}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--left", required=True, help="Baseline run JSON.")
    parser.add_argument("--right", required=True, help="Comparison run JSON.")
    parser.add_argument("--left-label", default="left")
    parser.add_argument("--right-label", default="right")
    parser.add_argument("--output", help="Optional markdown output path.")
    args = parser.parse_args()

    left = _read_json(Path(args.left))
    right = _read_json(Path(args.right))
    left_summary = _summary(left)
    right_summary = _summary(right)
    summary_rows = [
        ["Metric", args.left_label, args.right_label, "Delta right-left"],
        ["Cases", left_summary.get("case_count"), right_summary.get("case_count"), _delta(left_summary.get("case_count"), right_summary.get("case_count"))],
        ["Passed", left_summary.get("passed"), right_summary.get("passed"), _delta(left_summary.get("passed"), right_summary.get("passed"))],
        ["Pass rate", left_summary.get("pass_rate"), right_summary.get("pass_rate"), _delta(left_summary.get("pass_rate"), right_summary.get("pass_rate"))],
        ["Total loops", left_summary.get("total_loops"), right_summary.get("total_loops"), _delta(left_summary.get("total_loops"), right_summary.get("total_loops"))],
        ["Avg loops", left_summary.get("average_loops"), right_summary.get("average_loops"), _delta(left_summary.get("average_loops"), right_summary.get("average_loops"))],
        ["Est. prompt tokens", left_summary.get("estimated_prompt_tokens"), right_summary.get("estimated_prompt_tokens"), _delta(left_summary.get("estimated_prompt_tokens"), right_summary.get("estimated_prompt_tokens"))],
        ["Est. cost", _cost(left_summary), _cost(right_summary), "n/a"],
    ]

    left_cases = _by_id(left)
    right_cases = _by_id(right)
    case_rows = [["Case", args.left_label, args.right_label, "Expected"]]
    for case_id in sorted(set(left_cases) | set(right_cases)):
        left_case = left_cases.get(case_id, {})
        right_case = right_cases.get(case_id, {})
        case_rows.append([
            case_id,
            left_case.get("observed_outcome", "missing"),
            right_case.get("observed_outcome", "missing"),
            left_case.get("expected_outcome") or right_case.get("expected_outcome") or "",
        ])

    markdown = "\n\n".join(
        [
            "# GTM Agent Benchmark Comparison",
            "## Summary",
            _markdown_table(summary_rows),
            "## Case Outcomes",
            _markdown_table(case_rows),
        ]
    )
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(markdown + "\n", encoding="utf-8")
    print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
