# Slack fronting TypeScript custom bundle

Adds a Slack Web API backend adapter and live smoke test for the generated TypeScript Slack fronting service.

Required live-smoke environment:

- `SLACK_BOT_TOKEN`
- `SLACK_CHANNEL_ID`
- `ANIP_SLACK_ALLOWED_CHANNELS`

The live test reads bounded channel/thread context from Slack and verifies prepare-only message capabilities do not mutate Slack.
