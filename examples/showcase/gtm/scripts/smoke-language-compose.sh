#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
GTM_DIR="$ROOT_DIR/examples/showcase/gtm"
PYTHON_BIN="${PYTHON_BIN:-python3}"

LANGUAGES=("${@:-all}")
if [[ "${LANGUAGES[*]}" == "all" ]]; then
  LANGUAGES=(python typescript go java csharp)
fi

compose_file_for() {
  case "$1" in
    python) echo "$GTM_DIR/docker-compose.language-parity-python.yml" ;;
    typescript) echo "$GTM_DIR/docker-compose.language-parity-typescript.yml" ;;
    go) echo "$GTM_DIR/docker-compose.language-parity-go.yml" ;;
    java) echo "$GTM_DIR/docker-compose.language-parity-java.yml" ;;
    csharp) echo "$GTM_DIR/docker-compose.language-parity-csharp.yml" ;;
    *) echo "unknown language: $1" >&2; return 2 ;;
  esac
}

choose_base_port() {
  "$PYTHON_BIN" <<'PY'
import random
import socket

reserved_offsets = (0, 1, 2, 3, 100, 200, 300)
for _ in range(200):
    base = random.randrange(20000, 50000)
    sockets = []
    try:
        for offset in reserved_offsets:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(("127.0.0.1", base + offset))
            sockets.append(sock)
        print(base)
        raise SystemExit(0)
    except OSError:
        pass
    finally:
        for sock in sockets:
            sock.close()
raise SystemExit("could not find a free port block")
PY
}

wait_for_json() {
  local url="$1"
  local label="$2"
  local timeout="${3:-240}"
  local started
  started="$(date +%s)"
  while true; do
    if curl -fsS "$url" >/tmp/anip-gtm-smoke-response.json 2>/dev/null; then
      if "$PYTHON_BIN" -m json.tool /tmp/anip-gtm-smoke-response.json >/dev/null 2>&1; then
        return 0
      fi
    fi
    if (( "$(date +%s)" - started > timeout )); then
      echo "timed out waiting for $label at $url" >&2
      return 1
    fi
    sleep 2
  done
}

assert_min_capability_count() {
	local url="$1"
	local minimum="$2"
	"$PYTHON_BIN" - "$url" "$minimum" <<'PY'
import json
import sys
import urllib.request

url = sys.argv[1]
minimum = int(sys.argv[2])
with urllib.request.urlopen(url, timeout=10) as response:
    payload = json.loads(response.read().decode())
discovery = payload.get("anip_discovery") or payload
capabilities = discovery.get("capabilities")
if isinstance(capabilities, dict):
    count = len(capabilities)
elif isinstance(capabilities, list):
    count = len(capabilities)
else:
    raise SystemExit(f"capabilities missing at {url}: {payload!r}")
if count < minimum:
    raise SystemExit(f"expected at least {minimum} capabilities at {url}, got {count}")
PY
}

assert_union_capability_count() {
  local base_port="$1"
  local expected="$2"
  "$PYTHON_BIN" - "$base_port" "$expected" <<'PY'
import json
import sys
import urllib.request

base_port = int(sys.argv[1])
expected = int(sys.argv[2])
capability_ids: set[str] = set()
for offset in range(4):
    url = f"http://127.0.0.1:{base_port + offset}/.well-known/anip"
    with urllib.request.urlopen(url, timeout=10) as response:
        payload = json.loads(response.read().decode())
    discovery = payload.get("anip_discovery") or payload
    capabilities = discovery.get("capabilities")
    if isinstance(capabilities, dict):
        capability_ids.update(str(key) for key in capabilities)
    elif isinstance(capabilities, list):
        for item in capabilities:
            if isinstance(item, dict):
                capability_id = item.get("capability_id") or item.get("id")
                if capability_id:
                    capability_ids.add(str(capability_id))
if len(capability_ids) != expected:
    raise SystemExit(f"expected {expected} unique capabilities across stack, got {len(capability_ids)}: {sorted(capability_ids)}")
PY
}

cleanup_stack() {
  local compose_file="$1"
  docker compose -f "$compose_file" down -v --remove-orphans >/dev/null
}

for language in "${LANGUAGES[@]}"; do
  compose_file="$(compose_file_for "$language")"
  base_port="$(choose_base_port)"
  agent_port="$((base_port + 100))"
  postgres_port="$((base_port + 200))"
  metabase_port="$((base_port + 300))"

  echo "==> smoke $language on ports ${base_port}-$((base_port + 3)), agent ${agent_port}"
  cleanup_stack "$compose_file"
  trap 'cleanup_stack "$compose_file"' EXIT

  (
    cd "$GTM_DIR"
    ANIP_AGENT_MODEL="${ANIP_AGENT_MODEL:-gpt-5.4-mini}" \
      POSTGRES_PORT="$postgres_port" \
      GTM_METABASE_PORT="$metabase_port" \
      GTM_PIPELINE_PORT="$base_port" \
      GTM_ENRICHMENT_PORT="$((base_port + 1))" \
      GTM_PRIORITIZATION_PORT="$((base_port + 2))" \
      GTM_OUTREACH_PORT="$((base_port + 3))" \
      GTM_AGENT_LLM_UI_PORT="$agent_port" \
      docker compose -f "$compose_file" up -d --build
  )

  for offset in 0 1 2 3; do
    port=$((base_port + offset))
    wait_for_json "http://127.0.0.1:${port}/.well-known/anip" "$language service on ${port}"
    assert_min_capability_count "http://127.0.0.1:${port}/.well-known/anip" 1
  done
  assert_union_capability_count "$base_port" 23
  wait_for_json "http://127.0.0.1:${agent_port}/api/runtime" "$language agent runtime"
  curl -fsS "http://127.0.0.1:${agent_port}/" >/dev/null

  cleanup_stack "$compose_file"
  trap - EXIT
  echo "ok $language"
done
