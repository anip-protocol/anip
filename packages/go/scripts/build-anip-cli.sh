#!/usr/bin/env bash
set -euo pipefail

VERSION="${1:-dev}"
if [[ ! "$VERSION" =~ ^[0-9A-Za-z][0-9A-Za-z._-]*$ ]]; then
  echo "invalid version: $VERSION" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DIST_DIR="${DIST_DIR:-$GO_DIR/dist}"
STAGING_ROOT="$DIST_DIR/staging"
CHECKSUMS_FILE="$DIST_DIR/anip_${VERSION}_checksums.txt"
TARGETS="${ANIP_CLI_TARGETS:-darwin/amd64 darwin/arm64 linux/amd64 linux/arm64 windows/amd64 windows/arm64}"
CACHE_ROOT="${ANIP_CLI_BUILD_CACHE:-$GO_DIR/.build-cache}"
export GOCACHE="${GOCACHE:-$CACHE_ROOT/go-build-cache}"

rm -rf "$STAGING_ROOT"
mkdir -p "$DIST_DIR" "$STAGING_ROOT" "$GOCACHE"
rm -f "$DIST_DIR"/anip_"$VERSION"_*.tar.gz "$DIST_DIR"/anip_"$VERSION"_*.zip "$CHECKSUMS_FILE"

build_target() {
  local goos="$1"
  local goarch="$2"
  local name="anip_${VERSION}_${goos}_${goarch}"
  local staging="$STAGING_ROOT/$name"
  local archive_ext="tar.gz"
  if [[ "$goos" == "windows" ]]; then
    archive_ext="zip"
  fi
  local archive="$DIST_DIR/$name.$archive_ext"
  local binary_name="anip"
  if [[ "$goos" == "windows" ]]; then
    binary_name="anip.exe"
  fi

  mkdir -p "$staging"
  echo "building $name"
  (
    cd "$GO_DIR"
    CGO_ENABLED=0 GOOS="$goos" GOARCH="$goarch" go build \
      -trimpath \
      -ldflags "-s -w -X main.version=$VERSION" \
      -o "$staging/$binary_name" \
      ./cmd/anip
  )

  if [[ "$goos" == "windows" ]]; then
    cat > "$staging/anip-generate.cmd" <<'BAT'
@echo off
"%~dp0anip.exe" generate %*
BAT
    cat > "$staging/anip-verify.cmd" <<'BAT'
@echo off
"%~dp0anip.exe" validate %*
BAT
  else
    cat > "$staging/anip-generate" <<'SH'
#!/bin/sh
exec "$(dirname "$0")/anip" generate "$@"
SH
    cat > "$staging/anip-verify" <<'SH'
#!/bin/sh
exec "$(dirname "$0")/anip" validate "$@"
SH
    chmod +x "$staging/anip" "$staging/anip-generate" "$staging/anip-verify"
  fi

  cat > "$staging/README.md" <<EOF
# ANIP CLI $VERSION

Commands:

- \`anip generate\`
- \`anip validate\`
- \`anip verify\`
- \`anip version\`

Compatibility wrappers:

- \`anip-generate\` runs \`anip generate\`
- \`anip-verify\` runs \`anip validate\`
EOF

  if [[ "$goos" == "windows" ]]; then
    (
      cd "$staging"
      zip -qr "$archive" .
    )
  else
    tar -C "$staging" -czf "$archive" .
  fi
  local checksum
  checksum="$(shasum -a 256 "$archive" | awk '{print $1}')"
  printf "%s  %s\n" "$checksum" "$(basename "$archive")" >> "$CHECKSUMS_FILE"
}

for target in $TARGETS; do
  IFS=/ read -r goos goarch <<< "$target"
  build_target "$goos" "$goarch"
done

render_formula() {
  local template="$GO_DIR/homebrew/anip.rb.template"
  local output_dir="$DIST_DIR/homebrew"
  local output="$output_dir/anip.rb"
  mkdir -p "$output_dir"

  sha_for() {
    local suffix="$1"
    awk -v file="anip_${VERSION}_${suffix}.tar.gz" '$2 == file { print $1 }' "$CHECKSUMS_FILE"
  }

  local darwin_amd64 darwin_arm64 linux_amd64 linux_arm64
  darwin_amd64="$(sha_for darwin_amd64)"
  darwin_arm64="$(sha_for darwin_arm64)"
  linux_amd64="$(sha_for linux_amd64)"
  linux_arm64="$(sha_for linux_arm64)"

  if [[ -z "$darwin_amd64" || -z "$darwin_arm64" || -z "$linux_amd64" || -z "$linux_arm64" ]]; then
    echo "skipping Homebrew formula render because not all default target checksums are present"
    return
  fi

  sed \
    -e "s/__VERSION__/$VERSION/g" \
    -e "s/__DARWIN_AMD64_SHA256__/$darwin_amd64/g" \
    -e "s/__DARWIN_ARM64_SHA256__/$darwin_arm64/g" \
    -e "s/__LINUX_AMD64_SHA256__/$linux_amd64/g" \
    -e "s/__LINUX_ARM64_SHA256__/$linux_arm64/g" \
    "$template" > "$output"
  echo "wrote $output"
}

render_formula

if [[ "${ANIP_CLI_KEEP_STAGING:-0}" != "1" ]]; then
  rm -rf "$STAGING_ROOT"
fi

echo "wrote $CHECKSUMS_FILE"
