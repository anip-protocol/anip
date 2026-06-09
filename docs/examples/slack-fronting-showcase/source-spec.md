# Slack Governed Fronting Showcase Source Specification

This source document models a realistic fronting use case: Slack Web API exists downstream, but agents should only see governed communication capabilities.

## Purpose

Demonstrate that ANIP can govern internal communication behavior before messages are posted, announcements are sent, or private channel context is exposed.

The ANIP contract owns communication semantics. The Slack Web API is the backend for this showcase. Slack MCP may be useful as a comparison point for raw tool exposure, but this package does not use MCP as the ANIP execution interface.

## Service Boundary

- Service ID: `slack-governance-service`
- Service name: Slack Governance Service
- Primary backend: native Slack Web API adapter
- Deployment posture: centralized ANIP fronting service with channel allowlists, actor-aware visibility, outbound redaction, approval records, and audit.

## Backend Evidence

Native Slack API supply:

- Channel and thread read operations with bounded history.
- Message preview mapped to chat post/update payloads.
- Incident update preparation mapped to structured channel message payloads.
- Announcement request mapped to approved channel-post operation.
- Channel, user, group, and message metadata discovery.

MCP comparison:

- Slack MCP may expose search/read/post operations.
- This showcase intentionally does not bind ANIP capabilities to Slack MCP tools. The agent-facing surface remains ANIP capabilities backed by bounded Slack Web API operations.

## Governed Capability Surface

| Capability | User intent | Required inputs | Optional governed inputs | Outcome posture |
| --- | --- | --- | --- | --- |
| `slack.channel.read_context` | Read bounded channel context. | `channel_id` | `query`, `limit`, `time_window`, `backend_options` | Read-only. Actor-visible messages only. |
| `slack.thread.summarize` | Summarize a bounded thread. | `channel_id`, `thread_ts` | `focus`, `limit`, `backend_options` | Read-only. Returns summary context, not raw dump. |
| `slack.message.prepare` | Prepare a channel or thread message. | `channel_id`, `text` | `thread_ts`, `audience`, `backend_options` | Preview-only. Requires approval before send. |
| `slack.incident_update.prepare` | Prepare a structured incident update. | `channel_id`, `incident_id`, `status`, `summary` | `next_update_time`, `backend_options` | Preview-only. Requires approval before send. |
| `slack.announcement.request` | Request a broader announcement. | `channel_id`, `announcement` | `audience`, `schedule_hint`, `backend_options` | Approval-gated. High-reach channels require explicit grant. |

`backend_options` is limited to safe provider controls such as formatting mode, unfurl posture, and bounded metadata. It must not allow arbitrary channel selection, user impersonation, hidden recipients, or unbounded message export.

## Policy Semantics

- Reads are bounded by channel, thread, actor visibility, and result limits.
- Missing channel or thread context returns `clarification_required`.
- Sends are never direct by default. They produce previews or approval-required outcomes.
- Private channel exfiltration, unapproved sends, workspace admin actions, hidden recipient expansion, and raw exports are denied.
- Outbound messages must be auditable and may require redaction before preview or approval.

## Why ANIP Helps

Slack tool access is easy to overexpose. ANIP creates a reviewed communication surface where the service, not a prompt, decides when to clarify, restrict, preview, approve, or deny.
