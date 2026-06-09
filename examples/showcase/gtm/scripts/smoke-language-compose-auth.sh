#!/usr/bin/env bash
set -euo pipefail

language="${1:-}"
if [[ -z "$language" ]]; then
  echo "Usage: $0 <python|typescript|go|java|csharp>" >&2
  exit 2
fi

case "$language" in
  python)
    ports=(4210 4211 4212 4213)
    ;;
  typescript)
    ports=(4220 4221 4222 4223)
    ;;
  go)
    ports=(4230 4231 4232 4233)
    ;;
  java)
    ports=(4240 4241 4242 4243)
    ;;
  csharp)
    ports=(4250 4251 4252 4253)
    ;;
  *)
    echo "Unknown language '$language'" >&2
    exit 2
    ;;
esac

names=(pipeline enrichment prioritization outreach)
scopes=(
  "gtm.pipeline_summary"
  "gtm.account_enrichment_summary"
  "gtm.prioritize_accounts"
  "gtm.draft_outreach_message"
)

for index in "${!ports[@]}"; do
  port="${ports[$index]}"
  name="${names[$index]}"
  scope="${scopes[$index]}"
  body="{\"requested_scope\":[\"${scope}\"],\"caller_class\":\"agent\"}"

  curl -fsS -X POST "http://127.0.0.1:${port}/anip/tokens" \
    -H "Authorization: Bearer demo-sales-leader-key" \
    -H "Content-Type: application/json" \
    --data "$body" >/dev/null

  echo "OK ${language}/${name} accepted demo-sales-leader-key"
done
