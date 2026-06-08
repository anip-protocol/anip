#!/usr/bin/env bash
set -euo pipefail

generated_root="${ANIP_GITLAB_GENERATED_PYTHON_DIR:-$PWD}"
if [[ "$generated_root" == /private/tmp/* ]]; then
  generated_root="/tmp/${generated_root#/private/tmp/}"
fi

export PYTHONPATH="${generated_root}/src:${generated_root}${PYTHONPATH:+:${PYTHONPATH}}"
export ANIP_GITLAB_SMOKE_REEXEC=1

exec "${PYTHON:-python}" "$(dirname "$0")/approved_issue_smoke.py"
