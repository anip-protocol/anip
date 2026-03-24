"""CLI entry point for the contract test harness."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from .report import print_report
from .runner import ContractTestRunner


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="anip-contract-tests",
        description="ANIP side-effect contract testing harness",
    )
    parser.add_argument("--base-url", required=True, help="Base URL of the ANIP service")
    parser.add_argument("--test-pack", required=True, help="Path to test pack JSON file")
    parser.add_argument("--storage-dsn", default=None, help="SQLite DSN for storage probe")
    args = parser.parse_args()

    with open(args.test_pack) as f:
        test_pack = json.load(f)

    runner = ContractTestRunner(
        base_url=args.base_url,
        test_pack=test_pack,
        storage_dsn=args.storage_dsn,
    )
    results = asyncio.run(runner.run_all())
    print_report(results)

    # Exit with non-zero if any failures.
    if any(r.result == "FAIL" for r in results):
        sys.exit(1)
