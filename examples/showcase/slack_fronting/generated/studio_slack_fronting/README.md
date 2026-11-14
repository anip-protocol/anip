# Slack Fronting Python Custom Bundle

This bundle fills the generated Python backend adapter seam for the Slack fronting showcase.

It is implementation material, not part of the signed ANIP behavior contract. Generate the
service from the signed Registry package, then apply this bundle explicitly:

```bash
go run ./cmd/anip-generate \
  --registry-url http://127.0.0.1:8200/registry-api/v1 \
  --package-id slack-fronting-showcase \
  --package-version 0.1.0 \
  --target python \
  --transport http,stdio \
  --dependency-source registry \
  --custom-code-bundle examples/showcase/slack_fronting/custom-code-bundles/slack_fronting_python \
  --output /tmp/anip-slack-fronting-python \
  --force
```

Runtime credentials and policy are read from environment variables:

- `SLACK_BOT_TOKEN`
- `SLACK_CHANNEL_ID` for live smoke defaults
- `ANIP_SLACK_ALLOWED_CHANNELS`, optional comma-separated channel allowlist
- `ANIP_SLACK_BLOCKED_CHANNELS`, optional comma-separated channel denylist
- `ANIP_SLACK_ALLOW_SEND=true`, optional mutation gate for approved send tests

The adapter performs live Slack read calls when credentials are present. Write-adjacent
capabilities return governed previews by default. Sending requires both an ANIP approval grant
and `ANIP_SLACK_ALLOW_SEND=true`.
