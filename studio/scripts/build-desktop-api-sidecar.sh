#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
TARGET_TRIPLE="$(rustc -vV | awk '/^host:/ {print $2}')"
SIDECAR_NAME="anip-studio-api-${TARGET_TRIPLE}"
DIST_DIR="${REPO_ROOT}/studio/src-tauri/bin"
WORK_DIR="${REPO_ROOT}/studio/src-tauri/pyinstaller-work"
SPEC_DIR="${REPO_ROOT}/studio/src-tauri/pyinstaller-spec"
PYINSTALLER="${PYINSTALLER:-${REPO_ROOT}/.venv/bin/pyinstaller}"

if [[ ! -x "${PYINSTALLER}" ]]; then
  echo "Missing ${PYINSTALLER}. Run: ${REPO_ROOT}/.venv/bin/python -m pip install -r ${REPO_ROOT}/studio/server/desktop-build-requirements.txt" >&2
  exit 1
fi

mkdir -p "${DIST_DIR}"

"${PYINSTALLER}" \
  --noconfirm \
  --clean \
  --onefile \
  --name "${SIDECAR_NAME}" \
  --distpath "${DIST_DIR}" \
  --workpath "${WORK_DIR}" \
  --specpath "${SPEC_DIR}" \
  --paths "${REPO_ROOT}" \
  --paths "${REPO_ROOT}/tooling/bin" \
  --paths "${REPO_ROOT}/packages/python/anip-core/src" \
  --paths "${REPO_ROOT}/packages/python/anip-crypto/src" \
  --paths "${REPO_ROOT}/packages/python/anip-server/src" \
  --paths "${REPO_ROOT}/packages/python/anip-service/src" \
  --paths "${REPO_ROOT}/packages/python/anip-fastapi/src" \
  --add-data "${REPO_ROOT}/tooling/schemas:tooling/schemas" \
  --add-data "${REPO_ROOT}/studio/server/migrations:studio/server/migrations" \
  --add-data "${REPO_ROOT}/studio/server/seed_data:studio/server/seed_data" \
  --add-data "${REPO_ROOT}/studio/server/showcase_snapshots:studio/server/showcase_snapshots" \
  --add-data "${REPO_ROOT}/studio/server/vocabulary_defaults.json:studio/server" \
  --add-data "${REPO_ROOT}/docs/examples:docs/examples" \
  --hidden-import anip_design_validate \
  --hidden-import psycopg_binary \
  "${REPO_ROOT}/studio/server/desktop_entry.py"

chmod +x "${DIST_DIR}/${SIDECAR_NAME}"
echo "Built ${DIST_DIR}/${SIDECAR_NAME}"
