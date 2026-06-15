"""Verify the manually maintained GTM benchmark has not drifted accidentally."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_MANIFEST = REPO_ROOT / "examples" / "showcase" / "gtm" / "manual-benchmark-manifest.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST), help="Path to the benchmark manifest.")
    parser.add_argument(
        "--write",
        action="store_true",
        help="Refresh checksums in the manifest for files that currently exist.",
    )
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    manifest = load_manifest(manifest_path)
    failures: list[str] = []

    for entry in manifest.get("files", []):
        relative = str(entry["path"])
        expected = str(entry["sha256"])
        path = REPO_ROOT / relative
        if not path.exists():
            failures.append(f"missing: {relative}")
            continue
        actual = sha256(path)
        if args.write:
            entry["sha256"] = actual
            continue
        if actual != expected:
            failures.append(f"changed: {relative} expected={expected} actual={actual}")

    if args.write:
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        print(f"Manual GTM benchmark manifest refreshed: {len(manifest.get('files', []))} files in {manifest_path}")
        return 0

    if failures:
        print("Manual GTM benchmark verification failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(f"Manual GTM benchmark verified: {len(manifest.get('files', []))} files match {manifest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
