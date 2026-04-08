#!/bin/sh
set -eu

# Keep deployed Studio clean by default. Dogfood-only protocol pressure is
# available only when the image is explicitly opted into it.
if [ "${STUDIO_ALLOW_DOGFOOD:-0}" != "1" ]; then
  unset STUDIO_DOGFOOD_PROFILE || true
fi

exec "$@"
