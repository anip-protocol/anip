"""Report printer — formats contract test results for the terminal."""

from __future__ import annotations

from itertools import groupby
from operator import attrgetter

from .checks.check_result import CheckResult

_STATUS_ICON = {
    "PASS": "\u2713",
    "FAIL": "\u2717",
    "WARN": "!",
    "SKIP": "-",
}


def print_report(results: list[CheckResult]) -> None:
    """Print a formatted contract test report to stdout."""
    print()
    print("ANIP Contract Test Report")
    print("\u2550" * 55)

    # Group results by capability.
    sorted_results = sorted(results, key=attrgetter("capability"))
    for capability, group in groupby(sorted_results, key=attrgetter("capability")):
        print(f"  {capability}")
        for r in group:
            icon = _STATUS_ICON.get(r.result, "?")
            label = f"{r.check_name} "
            dots = "." * (30 - len(label))
            print(f"    {icon} {label}{dots} {r.result} ({r.confidence})")

    print("\u2550" * 55)

    passed = sum(1 for r in results if r.result == "PASS")
    failed = sum(1 for r in results if r.result == "FAIL")
    warnings = sum(1 for r in results if r.result == "WARN")
    skipped = sum(1 for r in results if r.result == "SKIP")
    print(f"{passed} passed, {failed} failed, {warnings} warnings, {skipped} skipped")
    print()
