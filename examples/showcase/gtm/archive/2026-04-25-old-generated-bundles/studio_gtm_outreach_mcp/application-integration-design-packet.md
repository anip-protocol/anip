# Application Integration Design Packet: GTM Outreach Service

Generated: 2026-04-14T02:18:05.849727+00:00

## Backend
- Type: mcp_server
- System: Outreach Drafting MCP
- Base URL: mcp://gtm-outreach-drafting
- Auth: bearer_token
- Implementation language: typescript

## Objects
- Prospect Context: Bounded GTM target context used to condition outreach drafts.
- Draft Message: Draft-only message output with bounded rationale and context.
- Conversation Pattern: Bounded content pattern or objection-response variant.

## Capabilities
- Draft Outreach Message (summarize, read, read_only) -> draft_outreach_message
- Suggest Follow-Up Content (summarize, read, read_only) -> suggest_followup_content
- Objection Response Variants (summarize, read, read_only) -> objection_response_variants

## Governance
- Permission rules: 1
- Clarification rules: 2
- Restriction rules: 2
- Denial rules: 2
- Approval rules: 0

## Scenarios
- Draft first-touch outreach: available
- Clarify missing target: clarification_required
- Deny send request: denied
- Deny raw transcript export: denied