# Slack Governed Fronting Showcase

This example shows the intended ANIP pattern for fronting broad Slack Web API access:
raw Slack operations are downstream implementation details; agents invoke governed ANIP capabilities. Slack MCP is useful as a comparison surface, but this package binds to the native Slack Web API.

## Build artifacts

```bash
python3 examples/showcase/slack_fronting/build_showcase.py
cd packages/go
go run ./cmd/anip-generate \
  --package-bundle ../../examples/showcase/slack_fronting/registry-packages/slack-fronting-showcase-0.2.0.anip-package.json \
  --target python \
  --dependency-source local \
  --custom-code-bundle ../../examples/showcase/slack_fronting/custom-code-bundles/slack_fronting_python \
  --transport http,stdio \
  --port 9160 \
  --output ../../examples/showcase/slack_fronting/generated/studio_slack_fronting \
  --force
```

Generate directly from the reviewed fronting starter:

```bash
cd packages/go
go run ./cmd/anip fronting scaffold \
  --starter ../../docs/examples/slack-fronting-showcase/anip-fronting-starter.json \
  --target python \
  --dependency-source local \
  --transport http,stdio \
  --output ../../examples/showcase/slack_fronting/generated/studio_slack_fronting \
  --force
```

Verify the local service definition:

```bash
cd packages/go
go run ./cmd/anip-verify \
  --definition ../../examples/showcase/slack_fronting/registry-packages/slack-fronting-showcase-0.2.0-service-definition.json
```

## What to inspect

- `registry-packages/slack-fronting-showcase-0.2.0-service-definition.json`: signed behavior contract with `integration_fronting` mappings.
- `generated/studio_slack_fronting/integration-fronting/adapter-bindings.json`: capability-to-backend binding pack.
- `generated/studio_slack_fronting/integration-fronting/backend-selection.example.json`: deployment-time backend selection template.
- `generated/studio_slack_fronting/integration-fronting/conformance.json`: static check that raw backend operations are governed.

## Live Slack tests

The generated Python adapter includes live Slack Web API behavior for:

- `slack.channel.read_context`: executes a bounded channel-history read.
- `slack.thread.summarize`: executes a bounded thread reply read.
- `slack.message.prepare`, `slack.incident_update.prepare`, and `slack.announcement.request`: return message payload previews without sending.
- Optional Slack message sending: disabled by default; requires `ANIP_SLACK_ALLOW_SEND=true` plus a real ANIP approval continuation grant supplied as the top-level `approval_grant` invoke field.

It uses these environment variables:

```bash
export SLACK_BOT_TOKEN="xoxb-your-token"
export SLACK_CHANNEL_ID="C0123456789"
PYTHONPATH="<repo python packages>:<generated src>" \
  python examples/showcase/slack_fronting/scripts/live_smoke.py
```

Run the send smoke test only against a disposable Slack channel:

```bash
export ANIP_SLACK_ALLOW_SEND=true
PYTHONPATH="<repo python packages>:<generated src>" \
  python examples/showcase/slack_fronting/scripts/approved_send_smoke.py
```

The send smoke first invokes `slack.message.prepare` and confirms that it stops at
a preview-only result. It then creates a pending ANIP approval request, issues a
one-time grant, and resubmits the same parameters with the top-level
`approval_grant`. The Slack adapter only posts after the ANIP runtime validates
and reserves that grant.

## Design point

The package uses the native Slack Web API as its execution binding. MCP can be compared separately as a raw tool surface, but the governed ANIP contract remains the agent-facing interface.

## Live smoke

The Python custom bundle can exercise live Slack read paths and preview-only write paths:

```bash
PYTHONPATH="<repo python packages>:<generated src>" \
  python examples/showcase/slack_fronting/scripts/live_smoke.py
```

Required environment:

- `SLACK_BOT_TOKEN`
- `SLACK_CHANNEL_ID`

Optional policy gates:

- `ANIP_SLACK_ALLOWED_CHANNELS`
- `ANIP_SLACK_BLOCKED_CHANNELS`
- `ANIP_SLACK_ALLOW_SEND=true`

By default, write-adjacent capabilities stop at preview and approval-required outcomes.
