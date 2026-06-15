#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
GTM_DIR="$ROOT_DIR/examples/showcase/gtm"
CATALOG="$GTM_DIR/custom-code-bundles/bundle-catalog.json"
OUTPUT_ROOT="${OUTPUT_ROOT:-/tmp/anip-gtm-custom-bundle-smoke}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

case "$OUTPUT_ROOT" in
  ""|"/"|"/tmp"|"/private/tmp")
    echo "unsafe OUTPUT_ROOT: $OUTPUT_ROOT" >&2
    exit 2
    ;;
esac
rm -rf "$OUTPUT_ROOT"
mkdir -p "$OUTPUT_ROOT"

"$PYTHON_BIN" - "$CATALOG" <<'PY' | while IFS=$'\t' read -r package_bundle language target path digest; do
import json
import sys
from pathlib import Path

catalog_path = Path(sys.argv[1]).resolve()
with catalog_path.open(encoding="utf-8") as handle:
    catalog = json.load(handle)
package_bundle = (catalog_path.parent / catalog["package"]["bundle_path"]).resolve()
for bundle in catalog["bundles"]:
    print(
        package_bundle,
        bundle["language"],
        bundle["target"],
        bundle["path"],
        bundle["bundle_tree_sha256"],
        sep="\t",
    )
PY
  echo "==> verify custom bundle ${language}"
  (
    cd "$ROOT_DIR/packages/go"
    GOCACHE="${GOCACHE:-/private/tmp/anip-go-cache}" go run ./cmd/anip generate \
      --package-bundle "$package_bundle" \
      --target "$target" \
      --dependency-source local \
      --custom-code-bundle "$GTM_DIR/custom-code-bundles/$path" \
      --verify-custom-code-bundle-digest "$digest" \
      --output "$OUTPUT_ROOT/$language" \
      --force >/dev/null
  )
  test -f "$OUTPUT_ROOT/$language/custom-code-bundle-report.json"
  echo "ok ${language}"
done

echo "custom bundle smoke output: $OUTPUT_ROOT"
