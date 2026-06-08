#!/usr/bin/env python3
"""Export a restoreable Studio project snapshot from the configured database."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from studio.server.db import close_pool, get_pool  # noqa: E402
from studio.server.project_snapshots import export_project_snapshot  # noqa: E402


def _package_metadata(values: list[str]) -> list[dict[str, str]]:
    packages: list[dict[str, str]] = []
    for value in values:
        package_id, sep, version = value.partition("@")
        if not sep or not package_id or not version:
            raise SystemExit(f"Package metadata must use package-id@version, got: {value}")
        packages.append({"package_id": package_id, "package_version": version})
    return packages


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--source", default="studio-db")
    parser.add_argument(
        "--published-package",
        action="append",
        default=[],
        help="Package lineage marker in package-id@version form. Can be repeated.",
    )
    args = parser.parse_args()

    with get_pool().connection() as conn:
        snapshot = export_project_snapshot(
            conn,
            args.project_id,
            published_packages=_package_metadata(args.published_package) or None,
            source=args.source,
        )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Wrote Studio project snapshot: {output}")
    close_pool()


if __name__ == "__main__":
    main()
