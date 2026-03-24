#!/bin/bash
# Sync built Studio assets to the Python adapter package
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEST="$SCRIPT_DIR/../packages/python/anip-studio/src/anip_studio/static"

rm -rf "$DEST"
mkdir -p "$DEST"
cp -r "$SCRIPT_DIR/dist/"* "$DEST/"

echo "Synced studio/dist/ → packages/python/anip-studio/src/anip_studio/static/"
