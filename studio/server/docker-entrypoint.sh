#!/bin/sh
set -eu

if [ "${STUDIO_MIGRATE_ONLY:-0}" = "1" ] || [ "${STUDIO_MIGRATE_ONLY:-}" = "true" ]; then
  python -m studio.server.migrate
  exit 0
fi

exec "$@"
