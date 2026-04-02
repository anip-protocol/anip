#!/bin/bash
# Build Studio for embedded mode and sync assets to ALL runtime adapter packages.
# Only Inspect-only builds are allowed to be synced into runtime packages.
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$SCRIPT_DIR/.."

# Build Inspect-only with embedded base path
echo "Building Studio (Inspect-only) with VITE_BASE_PATH=/studio/ ..."
cd "$SCRIPT_DIR"
VITE_INSPECT_ONLY=true VITE_BASE_PATH=/studio/ npx vite build

# The build above sets VITE_INSPECT_ONLY=true, which excludes Design routes at runtime.
# Design view chunks may still exist as dead code in the bundle (Vite doesn't fully tree-shake
# conditional arrays), but Design routes are not registered and the mode switcher is hidden.
# This is acceptable for embedded packaging — Design views are unreachable without routes.

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
