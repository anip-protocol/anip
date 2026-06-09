#!/usr/bin/env python3
"""Audit source-controlled release artifacts against a registry inventory.

This script is intentionally read-only. It checks that packages/templates already
published to an ANIP Registry also exist in the repository, and that published
showcase packages have restorable Studio snapshots.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path
from typing import Any


SHOWCASE_PACKAGE_DIRS = [
    "gtm",
    "jira_fronting",
    "github_fronting",
    "gitlab_fronting",
    "slack_fronting",
    "linear_fronting",
    "notion_fronting",
    "superset_fronting",
    "devops",
    "finance",
    "travel",
]


def load_json(source: str) -> dict[str, Any]:
    if source.startswith(("http://", "https://")):
        request = urllib.request.Request(source, headers={"User-Agent": "anip-release-audit/1.0"})
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    return json.loads(Path(source).read_text(encoding="utf-8"))


def registry_endpoint(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def package_paths(package_id: str, version: str) -> list[Path]:
    filename = f"{package_id}-{version}.anip-package.json"
    return [
        Path("examples/showcase") / showcase_dir / "registry-packages" / filename
        for showcase_dir in SHOWCASE_PACKAGE_DIRS
    ]


def template_path(template_id: str, version: str) -> Path:
    return (
        Path("examples/showcase/templates/registry-templates")
        / f"{template_id}-{version}.anip-template.json"
    )


def snapshot_path(package_id: str, version: str) -> Path:
    return (
        Path("studio/server/showcase_snapshots")
        / f"{package_id}-{version}.studio-project-snapshot.json"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--registry-url",
        default="https://registry.anip.dev/registry-api/v1",
        help="Registry API base URL.",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root to audit.",
    )
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    publications = load_json(registry_endpoint(args.registry_url, "publications")).get("items", [])
    templates = load_json(registry_endpoint(args.registry_url, "templates")).get("items", [])

    failures: list[str] = []

    for item in publications:
        package_id = item.get("package_id")
        version = item.get("package_version")
        if not package_id or not version:
            failures.append(f"Malformed publication item: {item!r}")
            continue
        candidates = package_paths(package_id, version)
        if not any((root / path).is_file() for path in candidates):
            failures.append(f"Missing package artifact for {package_id}@{version}")

        if package_id == "gtm-pipeline-q2-review" or str(package_id).endswith("-fronting-showcase"):
            path = snapshot_path(package_id, version)
            if not (root / path).is_file():
                failures.append(f"Missing Studio snapshot for {package_id}@{version}: {path}")

    for item in templates:
        template_id = item.get("template_id")
        version = item.get("template_version")
        if not template_id or not version:
            failures.append(f"Malformed template item: {item!r}")
            continue
        path = template_path(template_id, version)
        if not (root / path).is_file():
            failures.append(f"Missing template artifact for {template_id}@{version}: {path}")

    if failures:
        print("Release artifact audit failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print(
        f"Release artifact audit passed: {len(publications)} packages, "
        f"{len(templates)} templates."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
