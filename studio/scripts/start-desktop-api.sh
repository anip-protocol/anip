#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

export STUDIO_MODE="${STUDIO_MODE:-desktop}"
export STUDIO_DB_BACKEND="${STUDIO_DB_BACKEND:-sqlite}"
export ANIP_STUDIO_DESKTOP_DATA_DIR="${ANIP_STUDIO_DESKTOP_DATA_DIR:-${HOME}/.anip/studio}"
export STUDIO_SQLITE_PATH="${STUDIO_SQLITE_PATH:-${ANIP_STUDIO_DESKTOP_DATA_DIR}/studio.sqlite}"
export STUDIO_SEED_SHOWCASES="${STUDIO_SEED_SHOWCASES:-1}"
export STUDIO_READ_ONLY="${STUDIO_READ_ONLY:-0}"
export STUDIO_RUN_MIGRATIONS="${STUDIO_RUN_MIGRATIONS:-1}"

mkdir -p "$(dirname "${STUDIO_SQLITE_PATH}")"

UVICORN="${REPO_ROOT}/.venv/bin/uvicorn"
if [[ ! -x "${UVICORN}" ]]; then
  echo "Missing executable ${UVICORN}. Create the repository virtualenv before starting the desktop API." >&2
  exit 1
fi

cd "${REPO_ROOT}"
exec "${UVICORN}" studio.server.app:app \
  --host 127.0.0.1 \
  --port "${STUDIO_DESKTOP_API_PORT:-8100}"
