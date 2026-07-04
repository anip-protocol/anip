#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${APP_DIR}/../../../.." && pwd)"
TARGET_TRIPLE="$(rustc -vV | awk '/^host:/ {print $2}')"
SIDECAR_NAME="gtm-agent-desktop-runtime-${TARGET_TRIPLE}"
SIDECAR_FILE="${SIDECAR_NAME}"
DIST_DIR="${APP_DIR}/src-tauri/bin"
WORK_DIR="${APP_DIR}/src-tauri/pyinstaller-work"
SPEC_DIR="${APP_DIR}/src-tauri/pyinstaller-spec"

case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*|Windows_NT)
    PYINSTALLER="${PYINSTALLER:-${REPO_ROOT}/.venv/Scripts/pyinstaller.exe}"
    SIDECAR_FILE="${SIDECAR_NAME}.exe"
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
  echo "Missing ${PYINSTALLER}. Create .venv and install ${APP_DIR}/sidecar/desktop-build-requirements.txt first." >&2
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
  --paths "${REPO_ROOT}/packages/python/anip-core/src" \
  --paths "${REPO_ROOT}/packages/python/anip-crypto/src" \
  --paths "${REPO_ROOT}/packages/python/anip-service/src" \
  --paths "${REPO_ROOT}/packages/python/anip-fastapi/src" \
  --paths "${REPO_ROOT}/packages/python/anip-runtime-utils/src" \
  --paths "${REPO_ROOT}/examples/showcase/gtm/agents/llm_runtime" \
  --paths "${REPO_ROOT}/examples/showcase/gtm/generated/language-parity/python/src" \
  --add-data "$(add_data_arg "${REPO_ROOT}/examples/showcase/gtm/agents/llm_runtime" "examples/showcase/gtm/agents/llm_runtime")" \
  --add-data "$(add_data_arg "${REPO_ROOT}/examples/showcase/gtm/generated/language-parity/python/src" "examples/showcase/gtm/generated/language-parity/python/src")" \
  --add-data "$(add_data_arg "${REPO_ROOT}/examples/showcase/gtm/generated/language-parity/python/agent-consumption" "examples/showcase/gtm/generated/language-parity/python/agent-consumption")" \
  --hidden-import app \
  --hidden-import gtm_agent_app \
  --hidden-import gtm_pipeline_q2_review.app \
  --hidden-import gtm_pipeline_q2_review.services.gtm_enrichment_service.app \
  --hidden-import gtm_pipeline_q2_review.services.gtm_prioritization_service.app \
  --hidden-import gtm_pipeline_q2_review.services.gtm_outreach_service.app \
  --hidden-import psycopg_binary \
  "${APP_DIR}/sidecar/gtm_desktop_entry.py"

chmod +x "${DIST_DIR}/${SIDECAR_FILE}"
echo "Built ${DIST_DIR}/${SIDECAR_FILE}"
