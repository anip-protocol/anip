#!/usr/bin/env bash
# The quickstart walkthrough: every request the quickstart page shows, in order.
#
# The page embeds the regions of this file, and CI runs the file against each
# language's quickstart service, so the page cannot show a command that fails.
# Lines starting with "check" are assertions for CI and are not shown on the page.
#
# Usage: walkthrough.sh [base-url]        (default http://localhost:9100)
set -euo pipefail
BASE="${1:-http://localhost:9100}"

field() { python3 -c 'import json,sys; d=json.load(sys.stdin)
for k in sys.argv[1].split("."): d=d[int(k)] if isinstance(d,list) else d[k]
print(d if isinstance(d,str) else json.dumps(d))' "$1"; }
check() { # check <description> <actual> <expected>
  if [ "$2" != "$3" ]; then echo "FAILED: $1: expected '$3', got '$2'" >&2; exit 1; fi
  echo "ok: $1"
}

echo "== 1. Discovery"
DISCOVERY=$(
# region: discovery
curl -s $BASE/.well-known/anip
# endregion
)
echo "$DISCOVERY"
check "protocol" "$(echo "$DISCOVERY" | field anip_discovery.protocol)" "anip/0.24"
check "search_flights is declared as read" "$(echo "$DISCOVERY" | field anip_discovery.capabilities.search_flights.side_effect)" "read"
check "book_flight is declared as irreversible" "$(echo "$DISCOVERY" | field anip_discovery.capabilities.book_flight.side_effect)" "irreversible"

echo "== 2. Issue a token"
# region: token
TOKEN=$(curl -s -X POST $BASE/anip/tokens \
  -H "Authorization: Bearer demo-key" \
  -H "Content-Type: application/json" \
  -d '{"subject": "agent:demo", "scope": ["travel.search"], "capability": "search_flights"}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])')
echo $TOKEN
# endregion
check "a token was issued" "$([ -n "$TOKEN" ] && echo yes)" "yes"

echo "== 3. Check permissions"
PERMISSIONS=$(
# region: permissions
curl -s -X POST $BASE/anip/permissions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}'
# endregion
)
echo "$PERMISSIONS"
check "search_flights is available to this token" "$(echo "$PERMISSIONS" | field available.0.capability)" "search_flights"

echo "== 4. Invoke"
INVOKE=$(
# region: invoke
curl -s -X POST $BASE/anip/invoke/search_flights \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"parameters": {"origin": "SEA", "destination": "SFO"}}'
# endregion
)
echo "$INVOKE"
check "the search succeeded" "$(echo "$INVOKE" | field success)" "true"
check "the search returned flights" "$(echo "$INVOKE" | field result.flights.0.flight_number)" "AA100"

echo "== 5. A refusal"
REFUSAL=$(
# region: refusal
curl -s -X POST $BASE/anip/invoke/book_flight \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"parameters": {"flight_number": "AA100"}}'
# endregion
)
echo "$REFUSAL"
check "the booking was refused" "$(echo "$REFUSAL" | field success)" "false"
check "the refusal says why" "$(echo "$REFUSAL" | field failure.type)" "scope_insufficient"

echo "== 6. Audit"
AUDIT=$(
# region: audit
curl -s -X POST $BASE/anip/audit \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}'
# endregion
)
echo "$AUDIT"
check "the audit log has both calls" "$(echo "$AUDIT" | python3 -c 'import json,sys; e=json.load(sys.stdin)["entries"]; print(sorted((x["capability"], x["success"]) for x in e))')" "[('book_flight', False), ('search_flights', True)]"

echo
echo "Quickstart walkthrough passed against $BASE"
