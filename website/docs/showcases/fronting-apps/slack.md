---
title: Slack Fronting
description: Governed Slack fronting showcase for channel reads, thread summaries, prepared messages, incident updates, and announcements.
---

# Slack Fronting

Slack demonstrates governed communication behavior. It is the clearest fronting example for why "agent can post to Slack" is not enough.

The package is:

```text
slack-fronting-showcase@0.2.0
```

## What It Proves

Slack has a deceptively simple API surface: read messages and post messages. The risk is organizational, not technical. A message can reach the wrong audience, disclose private context, or create an official-looking statement.

ANIP turns that into a governed capability contract:

- Channel reads are bounded by allowed channel IDs and actor visibility.
- Thread summaries are scoped and result-limited.
- Messages are prepared before sending.
- Incident updates and announcements can require stronger approval.
- Private channel exfiltration, hidden recipients, raw exports, and unapproved sends are denied.

## Capability Surface

| Capability | Intent |
| --- | --- |
| `slack.channel.read_context` | Read bounded channel context. |
| `slack.thread.summarize` | Summarize a bounded thread. |
| `slack.message.prepare` | Prepare a message preview. |
| `slack.incident_update.prepare` | Prepare a governed incident update. |
| `slack.announcement.request` | Request an announcement through approval posture. |

## Backend Boundary

The backend is Slack Web API. The contract does not expose raw `chat.postMessage` as the agent product interface. The agent asks for a governed communication outcome; the service decides whether that is available, requires clarification, requires approval, or must be denied.

## Artifacts

| Artifact | Path |
| --- | --- |
| Source spec | `docs/examples/slack-fronting-showcase/source-spec.md` |
| Package | `examples/showcase/slack_fronting/registry-packages/slack-fronting-showcase-0.2.0.anip-package.json` |
| Service definition | `examples/showcase/slack_fronting/registry-packages/slack-fronting-showcase-0.2.0-service-definition.json` |
| Custom bundles | `examples/showcase/slack_fronting/custom-code-bundles/` |
| Generated services | `examples/showcase/slack_fronting/generated/` |

## Live Validation

Credential file:

```text
/tmp/anip-slack.env
```

Typical scope:

- a dedicated public test channel;
- read and summary smoke;
- prepared-message smoke;
- approved send only when `ANIP_SLACK_ALLOW_SEND=true` and a valid approval grant is supplied.

