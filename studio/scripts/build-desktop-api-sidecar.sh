#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
TARGET_TRIPLE="$(rustc -vV | awk '/^host:/ {print $2}')"
SIDECAR_NAME="anip-studio-api-${TARGET_TRIPLE}"
DIST_DIR="${REPO_ROOT}/studio/src-tauri/bin"
WORK_DIR="${REPO_ROOT}/studio/src-tauri/pyinstaller-work"
SPEC_DIR="${REPO_ROOT}/studio/src-tauri/pyinstaller-spec"

case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*|Windows_NT)
    PYINSTALLER="${PYINSTALLER:-${REPO_ROOT}/.venv/Scripts/pyinstaller.exe}"
    ADD_DATA_SEPARATOR=";"
    NATIVE_PATH_CONVERTER="cygpath -w"
    ;;
  *)
    PYINSTALLER="${PYINSTALLER:-${REPO_ROOT}/.venv/bin/pyinstaller}"
    ADD_DATA_SEPARATOR=":"
    NATIVE_PATH_CONVERTER=""
    ;;
esac

if [[ ! -x "${PYINSTALLER}" ]]; then
  echo "Missing ${PYINSTALLER}. Create .venv and install ${REPO_ROOT}/studio/server/desktop-build-requirements.txt first." >&2
  exit 1
fi

mkdir -p "${DIST_DIR}"

native_path() {
  if [[ -n "${NATIVE_PATH_CONVERTER}" ]]; then
    ${NATIVE_PATH_CONVERTER} "$1"
  else
    printf '%s' "$1"
  fi
}

add_data_arg() {
  printf '%s%s%s' "$(native_path "$1")" "${ADD_DATA_SEPARATOR}" "$2"
}

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
  --add-data "$(add_data_arg "${REPO_ROOT}/tooling/schemas" "tooling/schemas")" \
  --add-data "$(add_data_arg "${REPO_ROOT}/studio/server/migrations" "studio/server/migrations")" \
  --add-data "$(add_data_arg "${REPO_ROOT}/studio/server/seed_data" "studio/server/seed_data")" \
  --add-data "$(add_data_arg "${REPO_ROOT}/studio/server/showcase_snapshots" "studio/server/showcase_snapshots")" \
  --add-data "$(add_data_arg "${REPO_ROOT}/studio/server/vocabulary_defaults.json" "studio/server")" \
  --add-data "$(add_data_arg "${REPO_ROOT}/docs/examples" "docs/examples")" \
  --hidden-import anip_design_validate \
  --hidden-import jwt \
  --hidden-import psycopg_binary \
  "${REPO_ROOT}/studio/server/desktop_entry.py"

chmod +x "${DIST_DIR}/${SIDECAR_NAME}"
echo "Built ${DIST_DIR}/${SIDECAR_NAME}"
