#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
GTM_DIR="$ROOT_DIR/examples/showcase/gtm"
TAG="${ANIP_GTM_IMAGE_TAG:-0.4.3}"
PUSH="${ANIP_GTM_PUSH:-0}"
IMAGES=(
  "anipprotocol/showcase-gtm-agent-ui:${TAG}"
  "anipprotocol/showcase-gtm-python:${TAG}"
  "anipprotocol/showcase-gtm-typescript:${TAG}"
  "anipprotocol/showcase-gtm-go:${TAG}"
  "anipprotocol/showcase-gtm-java:${TAG}"
  "anipprotocol/showcase-gtm-csharp:${TAG}"
)

compose_build() {
  local language="$1"
  local compose_file="$GTM_DIR/docker-compose.language-parity-${language}.yml"
  echo "==> Building GTM ${language} service image (${TAG})"
  ANIP_GTM_IMAGE_TAG="$TAG" docker compose -f "$compose_file" build gtm-pipeline-service
}

echo "==> Building shared GTM agent UI image (${TAG})"
ANIP_GTM_IMAGE_TAG="$TAG" docker compose -f "$GTM_DIR/docker-compose.language-parity-python.yml" build gtm-agent-llm-ui

compose_build python
compose_build typescript
compose_build go
compose_build java
compose_build csharp

echo "==> Built GTM images"
docker images --format '{{.Repository}}:{{.Tag}} {{.ID}} {{.Size}}' | grep 'anipprotocol/showcase-gtm'

if [[ "$PUSH" == "1" ]]; then
  for image in "${IMAGES[@]}"; do
    echo "==> Pushing ${image}"
    docker push "$image"
  done
fi
