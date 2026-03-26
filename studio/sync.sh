#!/bin/bash
# Build Studio for embedded mode and sync assets to the Python adapter package
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEST="$SCRIPT_DIR/../packages/python/anip-studio/src/anip_studio/static"

# Build with embedded base path
echo "Building Studio with VITE_BASE_PATH=/studio/ ..."
cd "$SCRIPT_DIR"
VITE_BASE_PATH=/studio/ npx vite build

# Sync to Python adapter
rm -rf "$DEST"
mkdir -p "$DEST"
cp -r "$SCRIPT_DIR/dist/"* "$DEST/"

echo "Synced studio/dist/ → packages/python/anip-studio/src/anip_studio/static/"
