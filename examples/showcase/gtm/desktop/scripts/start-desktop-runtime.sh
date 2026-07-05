#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${APP_DIR}/../../../.." && pwd)"

export PYTHONPATH="${REPO_ROOT}:${REPO_ROOT}/packages/python/anip-core/src:${REPO_ROOT}/packages/python/anip-crypto/src:${REPO_ROOT}/packages/python/anip-server/src:${REPO_ROOT}/packages/python/anip-service/src:${REPO_ROOT}/packages/python/anip-fastapi/src:${REPO_ROOT}/packages/python/anip-runtime-utils/src:${REPO_ROOT}/examples/showcase/gtm/agents/llm_runtime:${REPO_ROOT}/examples/showcase/gtm/generated/language-parity/python/src:${PYTHONPATH:-}"
exec python3 "${APP_DIR}/sidecar/gtm_desktop_entry.py"
