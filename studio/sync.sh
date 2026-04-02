#!/bin/bash
# WARNING: This syncs the full Studio build (including Design mode routes) into
# runtime adapter packages. Design mode is intended as standalone-only and will
# show empty/placeholder content when embedded. A proper Inspect-only build
# split is planned but not yet implemented.
#
# Build Studio for embedded mode and sync assets to ALL runtime adapter packages
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$SCRIPT_DIR/.."

# Build with embedded base path
echo "Building Studio with VITE_BASE_PATH=/studio/ ..."
cd "$SCRIPT_DIR"
VITE_BASE_PATH=/studio/ npx vite build

# Sync to Python adapter
DEST_PY="$ROOT/packages/python/anip-studio/src/anip_studio/static"
rm -rf "$DEST_PY"
mkdir -p "$DEST_PY"
cp -r "$SCRIPT_DIR/dist/"* "$DEST_PY/"
echo "  → Python: packages/python/anip-studio/src/anip_studio/static/"

# Sync to TypeScript adapter
DEST_TS="$ROOT/packages/typescript/studio/static"
rm -rf "$DEST_TS"
mkdir -p "$DEST_TS"
cp -r "$SCRIPT_DIR/dist/"* "$DEST_TS/"
echo "  → TypeScript: packages/typescript/studio/static/"

# Sync to Go adapter (for go:embed)
DEST_GO="$ROOT/packages/go/studioapi/static"
rm -rf "$DEST_GO"
mkdir -p "$DEST_GO"
cp -r "$SCRIPT_DIR/dist/"* "$DEST_GO/"
echo "  → Go: packages/go/studioapi/static/"

# Sync to Java adapter (classpath resources)
DEST_JAVA="$ROOT/packages/java/anip-studio/src/main/resources/studio"
rm -rf "$DEST_JAVA"
mkdir -p "$DEST_JAVA"
cp -r "$SCRIPT_DIR/dist/"* "$DEST_JAVA/"
echo "  → Java: packages/java/anip-studio/src/main/resources/studio/"

# Sync to C# adapter (embedded resources)
DEST_CS="$ROOT/packages/csharp/src/Anip.Studio/static"
rm -rf "$DEST_CS"
mkdir -p "$DEST_CS"
cp -r "$SCRIPT_DIR/dist/"* "$DEST_CS/"
echo "  → C#: packages/csharp/src/Anip.Studio/static/"

echo "Synced studio/dist/ → all 5 runtime adapters"
