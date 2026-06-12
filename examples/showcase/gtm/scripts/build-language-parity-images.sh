#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
GTM_DIR="$ROOT_DIR/examples/showcase/gtm"
TAG="${ANIP_GTM_IMAGE_TAG:-0.4.3}"
PUSH="${ANIP_GTM_PUSH:-0}"
TAG_LATEST="${ANIP_GTM_TAG_LATEST:-1}"
IMAGES=(
  "anipprotocol/showcase-gtm-agent-ui:${TAG}"
  "anipprotocol/showcase-gtm-python:${TAG}"
  "anipprotocol/showcase-gtm-typescript:${TAG}"
  "anipprotocol/showcase-gtm-go:${TAG}"
  "anipprotocol/showcase-gtm-java:${TAG}"
  "anipprotocol/showcase-gtm-csharp:${TAG}"
)
REPOSITORIES=(
  "anipprotocol/showcase-gtm-agent-ui"
  "anipprotocol/showcase-gtm-python"
  "anipprotocol/showcase-gtm-typescript"
  "anipprotocol/showcase-gtm-go"
  "anipprotocol/showcase-gtm-java"
  "anipprotocol/showcase-gtm-csharp"
)

verify_generated_contracts() {
  echo "==> Verifying generated GTM service definitions against package contract"
  python3 - <<'PY'
import json
import sys
from pathlib import Path

gtm_dir = Path("examples/showcase/gtm")
package_path = gtm_dir / "registry-packages/gtm-pipeline-q2-review-0.4.3.anip-package.json"
generated_root = gtm_dir / "generated/language-parity"
languages = ["python", "typescript", "go", "java", "csharp"]

capability_keys = [
    "capability_id",
    "kind",
    "grant_policy",
    "service_id",
    "operation_type",
    "side_effect_level",
    "business_effects",
    "backend_operation",
    "path_template",
    "output_shape",
]
input_keys = [
    "input_name",
    "input_type",
    "required",
    "semantic_type",
    "entity_reference",
    "catalog_ref",
    "allowed_values",
    "default_value",
    "resolution",
]


def normalized_value(key, value):
    if key == "allowed_values" and value is None:
        return []
    if key == "entity_reference" and value is None:
        return False
    return value


def capability_surface(service_definition):
    capabilities = []
    for capability in service_definition.get("capability_formalizations", []):
        projected = {
            key: normalized_value(key, capability.get(key))
            for key in capability_keys
        }
        projected["inputs"] = [
            {
                key: normalized_value(key, input_spec.get(key))
                for key in input_keys
            }
            for input_spec in capability.get("inputs", [])
        ]
        capabilities.append(projected)
    return sorted(capabilities, key=lambda item: item["capability_id"])


package = json.loads(package_path.read_text())
expected = capability_surface(package["service_definition"])
failures = []

for language in languages:
    definition_path = generated_root / language / "anip-service-definition.json"
    actual = capability_surface(json.loads(definition_path.read_text()))
    if actual != expected:
        failures.append(language)

if failures:
    print(
        "FAIL: generated GTM service definitions are stale or do not match "
        f"{package_path}: {', '.join(failures)}",
        file=sys.stderr,
    )
    sys.exit(1)

print("OK: generated GTM service definitions match package capability/input surface")
PY
}

compose_build() {
  local language="$1"
  local compose_file="$GTM_DIR/docker-compose.language-parity-${language}.yml"
  echo "==> Building GTM ${language} service image (${TAG})"
  ANIP_GTM_IMAGE_TAG="$TAG" docker compose -f "$compose_file" build gtm-pipeline-service
}

cd "$ROOT_DIR"
verify_generated_contracts

echo "==> Building shared GTM agent UI image (${TAG})"
ANIP_GTM_IMAGE_TAG="$TAG" docker compose -f "$GTM_DIR/docker-compose.language-parity-python.yml" build gtm-agent-llm-ui

compose_build python
compose_build typescript
compose_build go
compose_build java
compose_build csharp

echo "==> Built GTM images"
docker images --format '{{.Repository}}:{{.Tag}} {{.ID}} {{.Size}}' | grep 'anipprotocol/showcase-gtm'

if [[ "$TAG_LATEST" == "1" && "$TAG" != "latest" ]]; then
  echo "==> Tagging GTM images as latest"
  for repository in "${REPOSITORIES[@]}"; do
    docker tag "${repository}:${TAG}" "${repository}:latest"
  done
  docker images --format '{{.Repository}}:{{.Tag}} {{.ID}} {{.Size}}' | grep 'anipprotocol/showcase-gtm'
fi

if [[ "$PUSH" == "1" ]]; then
  for image in "${IMAGES[@]}"; do
    echo "==> Pushing ${image}"
    docker push "$image"
  done
  if [[ "$TAG_LATEST" == "1" && "$TAG" != "latest" ]]; then
    for repository in "${REPOSITORIES[@]}"; do
      echo "==> Pushing ${repository}:latest"
      docker push "${repository}:latest"
    done
  fi
fi
