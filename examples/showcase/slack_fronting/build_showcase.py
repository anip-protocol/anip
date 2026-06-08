#!/usr/bin/env python3
"""Build the Slack governed fronting showcase package and source docs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
VERSION = "0.1.0"
GENERATED_AT = "2026-05-08T00:00:00Z"
PACKAGE_ID = "slack-fronting-showcase"
SYSTEM_NAME = "Slack Governed Fronting Showcase"
SERVICE_ID = "slack-governance-service"
SERVICE_NAME = "Slack Governance Service"
SOURCE_DIR = "docs/examples/slack-fronting-showcase"
SHOWCASE_DIR = "examples/showcase/slack_fronting"
PORT = 9160


def stable_json(value: Any) -> str:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"))
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def write_json(path: Path, payload: Any) -> None:
    write_text(path, json.dumps(payload, indent=2, sort_keys=False))


def input_field(
    name: str,
    type_: str,
    summary: str,
    *,
    required: bool = True,
    default: str = "",
    allowed_values: list[str] | None = None,
    entity_reference: bool = False,
    semantic_type: str = "",
) -> dict[str, Any]:
    return {
        "input_name": name,
        "input_type": type_,
        "required": required,
        "summary": summary,
        "default_value": default,
        "allowed_values": allowed_values or [],
        "entity_reference": entity_reference,
        "semantic_type": semantic_type,
        "clarification_hint": f"Ask for {name} when it is missing or ambiguous.",
    }


def grant_policy() -> dict[str, Any]:
    return {
        "allowed_grant_types": ["one_time", "session_bound"],
        "default_grant_type": "one_time",
        "expires_in_seconds": 900,
        "max_uses": 1,
    }


CAPABILITIES: list[dict[str, Any]] = [
    {
        "capability_id": "slack.channel.read_context",
        "title": "Read Channel Context",
        "summary": "Read bounded recent Slack channel messages for declared context without exposing raw workspace tools.",
        "intent_type": "read_only",
        "operation_type": "read",
        "side_effect_level": "read",
        "backend_operation": "read_channel_context",
        "path_template": "/slack/channels/{channel_id}/context",
        "output_shape": "bounded_channel_messages",
        "minimum_scope": ["slack.read"],
        "subject_kind": "slack_channel",
        "context_type": "channel_context",
        "output_intent": "bounded_message_results",
        "business_effects": {
            "produces": ["Read bounded data", "Summarize information"],
            "does_not_produce": ["Send outside the system", "Export raw data"],
        },
        "inputs": [
            input_field("channel_id", "string", "Slack channel ID.", entity_reference=True, semantic_type="channel_ref"),
            input_field("query", "string", "Optional text filter for recent messages.", required=False),
            input_field("limit", "integer", "Maximum messages to return.", required=False, default="20"),
        ],
    },
    {
        "capability_id": "slack.thread.summarize",
        "title": "Summarize Thread",
        "summary": "Retrieve bounded Slack thread replies and return context for summarization without posting.",
        "intent_type": "read_only",
        "operation_type": "read",
        "side_effect_level": "read",
        "backend_operation": "summarize_thread",
        "path_template": "/slack/channels/{channel_id}/threads/{thread_ts}/summary",
        "output_shape": "bounded_thread_context",
        "minimum_scope": ["slack.read"],
        "subject_kind": "slack_thread",
        "context_type": "thread_context",
        "output_intent": "thread_summary_context",
        "business_effects": {
            "produces": ["Read bounded data", "Summarize information"],
            "does_not_produce": ["Send outside the system", "Export raw data"],
        },
        "inputs": [
            input_field("channel_id", "string", "Slack channel ID.", entity_reference=True, semantic_type="channel_ref"),
            input_field("thread_ts", "string", "Slack thread timestamp.", entity_reference=True, semantic_type="thread_ref"),
            input_field("focus", "string", "Optional summary focus.", required=False),
        ],
    },
    {
        "capability_id": "slack.message.prepare",
        "title": "Prepare Channel Message",
        "summary": "Prepare a Slack channel message preview without sending it.",
        "intent_type": "prepare_only",
        "operation_type": "write",
        "side_effect_level": "write_adjacent",
        "backend_operation": "prepare_channel_message",
        "path_template": "/slack/channels/{channel_id}/messages/preview",
        "output_shape": "message_preview",
        "minimum_scope": ["slack.message.prepare"],
        "subject_kind": "slack_message",
        "context_type": "message_preparation",
        "output_intent": "message_preview",
        "grant_policy": grant_policy(),
        "business_effects": {
            "produces": ["Draft content", "Preview a change", "Ask for approval"],
            "does_not_produce": ["Send outside the system", "Change workspace state"],
        },
        "inputs": [
            input_field("channel_id", "string", "Slack channel ID.", entity_reference=True, semantic_type="channel_ref"),
            input_field("text", "string", "Message text to preview."),
            input_field("thread_ts", "string", "Optional thread timestamp.", required=False, entity_reference=True, semantic_type="thread_ref"),
        ],
    },
    {
        "capability_id": "slack.incident_update.prepare",
        "title": "Prepare Incident Update",
        "summary": "Prepare a structured incident update for a Slack channel and stop before sending.",
        "intent_type": "prepare_only",
        "operation_type": "write",
        "side_effect_level": "write_adjacent",
        "backend_operation": "prepare_incident_update",
        "path_template": "/slack/channels/{channel_id}/incident-updates/preview",
        "output_shape": "incident_update_preview",
        "minimum_scope": ["slack.message.prepare"],
        "subject_kind": "slack_message",
        "context_type": "incident_update",
        "output_intent": "incident_update_preview",
        "grant_policy": grant_policy(),
        "business_effects": {
            "produces": ["Draft content", "Preview a change", "Ask for approval"],
            "does_not_produce": ["Send outside the system", "Change workspace state"],
        },
        "inputs": [
            input_field("channel_id", "string", "Slack channel ID.", entity_reference=True, semantic_type="channel_ref"),
            input_field("incident_id", "string", "Incident identifier.", entity_reference=True, semantic_type="incident_ref"),
            input_field("status", "string", "Incident status.", allowed_values=["investigating", "identified", "monitoring", "resolved"]),
            input_field("summary", "string", "Human-readable update summary."),
            input_field("next_update_time", "string", "Optional next update time.", required=False),
        ],
    },
    {
        "capability_id": "slack.announcement.request",
        "title": "Request Channel Announcement",
        "summary": "Prepare a channel announcement request that requires approval before posting.",
        "intent_type": "approval_gated_action",
        "operation_type": "approval_gated",
        "side_effect_level": "write_adjacent",
        "backend_operation": "request_channel_announcement",
        "path_template": "/slack/channels/{channel_id}/announcements/request",
        "output_shape": "announcement_preview",
        "minimum_scope": ["slack.announcement.request"],
        "subject_kind": "slack_message",
        "context_type": "announcement_request",
        "output_intent": "announcement_preview",
        "grant_policy": grant_policy(),
        "business_effects": {
            "produces": ["Preview a change", "Ask for approval"],
            "does_not_produce": ["Send outside the system", "Bypass communication policy"],
        },
        "inputs": [
            input_field("channel_id", "string", "Slack channel ID.", entity_reference=True, semantic_type="channel_ref"),
            input_field("announcement", "string", "Announcement text."),
            input_field("audience", "string", "Intended audience.", required=False),
        ],
    },
]


def capability_record(capability: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": f"slack:{capability['capability_id']}",
        "kind": "atomic",
        "source_kind": "integration_fronting_source_doc",
        "service_id": SERVICE_ID,
        "entity_targeted": True,
        **capability,
        "required_inputs": [item for item in capability["inputs"] if item["required"]],
        "optional_inputs": [item for item in capability["inputs"] if not item["required"]],
        "backend_bindings": backend_bindings(capability),
        "governance": {
            "approval_rule_refs": ["approval.message_send_required"] if capability["side_effect_level"] != "read" else [],
            "denial_rule_refs": ["deny.raw_export", "deny.unapproved_send", "deny.workspace_admin_bypass"],
            "clarification_rule_refs": [f"clarify.{item['input_name']}" for item in capability["inputs"] if item["required"]],
            "audit_required": True,
        },
        "outbound_controls": {
            "redact_sensitive_values": True,
            "block_unbounded_payloads": True,
            "block_private_channel_exfiltration": True,
        },
    }


def backend_bindings(capability: dict[str, Any]) -> list[dict[str, Any]]:
    operation = capability["backend_operation"]
    required = [item["input_name"] for item in capability["inputs"] if item["required"]]
    optional = [item["input_name"] for item in capability["inputs"] if not item["required"]]
    return [
        {
            "backend_kind": "native_api",
            "connection_ref": "slack_web_api",
            "raw_operation_refs": [f"slack.web.{operation}"],
            "backend_input_mode": "explicit",
            "explicit_required_backend_inputs": required,
            "explicit_optional_backend_inputs": optional,
            "matched_discovery_record_ids": [f"slack-web-{operation}"],
            "status": "ready",
            "status_detail": "Native Slack Web API implementation seam.",
        },
        {
            "backend_kind": "mcp",
            "connection_ref": "slack_mcp",
            "raw_operation_refs": [f"slack.mcp.{operation}"],
            "backend_input_mode": "explicit",
            "explicit_required_backend_inputs": required,
            "explicit_optional_backend_inputs": optional,
            "matched_discovery_record_ids": [f"slack-mcp-{operation}"],
            "status": "candidate",
            "status_detail": "Alternative MCP-backed adapter realization for teams that already standardize on Slack MCP.",
        },
    ]


def fronting_mapping(capability: dict[str, Any]) -> dict[str, Any]:
    required = [item["input_name"] for item in capability["inputs"] if item["required"]]
    optional = [item["input_name"] for item in capability["inputs"] if not item["required"]]
    bindings = backend_bindings(capability)
    return {
        "id": f"{capability['capability_id'].replace('.', '_')}_fronting",
        "capability_id": capability["capability_id"],
        "title": capability["title"],
        "intent": capability["summary"],
        "service_id": SERVICE_ID,
        "service_name": SERVICE_NAME,
        "backend_kind": "hybrid",
        "connection_ref": "slack_fronting",
        "raw_operation_refs": [operation for binding in bindings for operation in binding["raw_operation_refs"]],
        "backend_bindings": bindings,
        "execution_posture": capability["intent_type"],
        "side_effect_level": capability["side_effect_level"],
        "subject_kind": capability["subject_kind"],
        "context_type": capability["context_type"],
        "output_intent": capability["output_intent"],
        "required_inputs": required,
        "optional_inputs": optional,
        "backend_input_mode": "explicit",
        "explicit_required_backend_inputs": required,
        "explicit_optional_backend_inputs": optional,
        "approval_rule_refs": ["approval.message_send_required"] if capability["side_effect_level"] != "read" else [],
        "denial_rule_refs": ["deny.raw_export", "deny.unapproved_send", "deny.workspace_admin_bypass"],
        "clarification_rule_refs": [f"clarify.{item}" for item in required],
        "audit_required": True,
        "outbound_controls": {
            "redact_sensitive_values": True,
            "block_unbounded_payloads": True,
            "block_private_channel_exfiltration": True,
        },
    }


def formalized_capabilities() -> list[dict[str, Any]]:
    return [capability_record(capability) for capability in CAPABILITIES]


def source_doc() -> str:
    capabilities = "\n".join(
        f"- `{capability['capability_id']}`: {capability['summary']} Backend bindings: Slack Web API and Slack MCP."
        for capability in CAPABILITIES
    )
    return f"""# {SYSTEM_NAME} Source Specification

This source document models the fronting use case: raw Slack Web API or Slack MCP
operations are available downstream, but agents should only see governed ANIP capabilities.

## Purpose

Demonstrate that ANIP can sit in front of native Slack APIs while preserving the same
governed service contract that could later be backed by Slack MCP.

## Service Boundary

- Service ID: `{SERVICE_ID}`
- Service name: {SERVICE_NAME}
- Downstream option A: native Slack Web API adapter
- Downstream option B: Slack MCP adapter

## Governed Capabilities

{capabilities}

## Review Decisions

- Do not expose raw Slack Web API or MCP tools as agent-facing capabilities.
- Channel and thread reads are bounded by channel/thread and result limits.
- Message sends are prepare/request flows. They stop at preview or approval, not direct posting.
- Private channel exfiltration, raw exports, workspace admin bypass, and unapproved sends are denied by policy.
"""


def build_definition() -> dict[str, Any]:
    capability_ids = [capability["capability_id"] for capability in CAPABILITIES]
    return {
        "artifact_type": "anip_service_definition",
        "contract_schema_version": "anip-service-definition/v1",
        "compiled_contract_identity": {
            "signature": "local-slack-fronting-contract-signature",
            "signature_algorithm": "sha256",
        },
        "generated_at": GENERATED_AT,
        "identity": {
            "system_name": SYSTEM_NAME,
            "domain_name": "slack",
            "delivery_model": "governed_integration_fronting",
            "architecture_shape": "single_service",
        },
        "authority": {
            "approval_expectation": "approval_gated_for_send_actions",
            "blocked_failure_posture": "clarify_or_stop",
        },
        "audit": {
            "durable_records_required": True,
            "searchable_history_required": True,
        },
        "generation": {
            "protocols": ["https", "mcp"],
            "layout_strategy": "service_oriented",
            "selected_service_ids": [SERVICE_ID],
        },
        "service_topology_bindings": [
            {
                "id": SERVICE_ID,
                "service_id": SERVICE_ID,
                "service_name": SERVICE_NAME,
                "source_role": "governed_integration_fronting",
                "source_capabilities": capability_ids,
                "formalized_capability_ids": capability_ids,
                "owned_concept_ids": ["slack_channel", "slack_thread", "slack_message"],
            }
        ],
        "capability_formalizations": formalized_capabilities(),
        "permission_intent_bindings": [
            {
                "id": "slack_collaborator_access",
                "actor_id": "collaborator",
                "business_area": "slack_collaboration",
                "business_area_label": "Slack Collaboration",
                "access_posture": "bounded",
                "governed_outcome_type": "bounded_result",
                "governed_outcome": "Collaborators can read bounded Slack context and prepare governed message previews.",
                "target_service_ids": [SERVICE_ID],
                "target_capability_ids": capability_ids,
                "formalization_strategy": "Generated policy keeps raw Slack/MCP operations behind reviewed ANIP capabilities.",
            }
        ],
        "runtime_policy_bindings": [
            {
                "id": "slack_collaborator_policy",
                "source_permission_id": "slack_collaborator_access",
                "actor_id": "collaborator",
                "principal_selector": {"claim": "actor_id", "equals": "collaborator"},
                "business_area": "slack_collaboration",
                "business_area_label": "Slack Collaboration",
                "service_ids": [SERVICE_ID],
                "capability_ids": capability_ids,
                "required_scopes": sorted({scope for capability in CAPABILITIES for scope in capability["minimum_scope"]}),
                "decision": "allow_with_limits",
                "business_rule": "Allow only declared governed Slack capabilities; send-like actions stop at preview or approval.",
                "enforcement_notes": "Raw backend operations remain implementation detail behind the generated adapter seam.",
            }
        ],
        "integration_fronting": {
            "project_type": "governed_service_project",
            "capability_mappings": [fronting_mapping(capability) for capability in CAPABILITIES],
        },
        "source": {
            "source_docs": [f"{SOURCE_DIR}/source-spec.md"],
            "fronting_target": "slack_native_api_or_slack_mcp",
        },
    }


def build_consumability() -> dict[str, Any]:
    return {
        "schema_version": "anip-agent-consumability/v0",
        "capabilities": {
            capability["capability_id"]: {
                "intent": {"category": capability["capability_id"], "summary": capability["summary"]},
                "business_effects": capability["business_effects"],
                "app_owned_behavior": [
                    "Select native Slack Web API or Slack MCP backend at deployment time.",
                    "Never route agents directly to raw Slack API or MCP operations.",
                ],
                "required_context": [
                    {"input": item["input_name"], "behavior": "clarify", "summary": item["summary"]}
                    for item in capability["inputs"]
                    if item["required"]
                ],
            }
            for capability in CAPABILITIES
        },
    }


def build_package(definition: dict[str, Any]) -> dict[str, Any]:
    signature = digest(definition)
    consumability = build_consumability()
    readiness = {
        "status": "ready",
        "score": 100,
        "summary": {"blockers": 0, "warnings": 0, "info": 0, "probes": 5, "required_app_glue": 0},
        "probes": [
            {"id": "slack-channel-read-scope", "expected_outcome": "success"},
            {"id": "slack-message-missing-channel", "expected_outcome": "clarification_required"},
            {"id": "slack-send-without-approval", "expected_outcome": "approval_required"},
            {"id": "slack-announcement-without-approval", "expected_outcome": "approval_required"},
            {"id": "slack-raw-export-denied", "expected_outcome": "unsupported"},
        ],
    }
    lineage = {
        "project_ref": "studio-source:slack-fronting",
        "product_revision": {
            "ref": "slack-fronting:source-spec:v1",
            "artifact_id": "slack-fronting-source-spec",
            "revision_number": 1,
            "baseline_locked_at": GENERATED_AT,
        },
        "developer_revision": {
            "ref": "slack-fronting:developer-definition:v1",
            "artifact_id": "slack-fronting-developer-definition",
            "revision_number": 1,
            "contract_signature": signature,
        },
    }
    manifest = {
        "package_kind": "anip_service_blueprint",
        "artifact_type": "anip_package_manifest",
        "blueprint_id": PACKAGE_ID,
        "package_id": PACKAGE_ID,
        "name": f"{SYSTEM_NAME} Service Blueprint",
        "version": VERSION,
        "package_version": VERSION,
        "schema_version": definition["contract_schema_version"],
        "publisher": {"id": "local-studio-source", "display_name": "Local Studio Source Export"},
        "service_definition": "anip-service-definition.json",
        "service_definition_digest": signature,
        "service_definition_digest_algorithm": "sha256",
        "build_packs": {"recommended": ["anip-build-pack@local"]},
        "verifier_packs": {"recommended": ["anip-verifier@local"]},
        "readme": "# Slack Governed Fronting Showcase\n\nANIP fronting example for native Slack Web API or Slack MCP backends.\n",
        "usage": {
            "generate_python": f"go run ./cmd/anip-generate --package-bundle ../../examples/showcase/slack_fronting/registry-packages/{PACKAGE_ID}-{VERSION}.anip-package.json --target python --dependency-source local --port {PORT} --output ../../examples/showcase/slack_fronting/generated/studio_slack_fronting --force",
            "verify_definition": f"go run ./cmd/anip-verify --definition ../../examples/showcase/slack_fronting/registry-packages/{PACKAGE_ID}-{VERSION}-service-definition.json",
        },
        "source_links": [
            {"title": "Source documentation", "url": f"https://github.com/anip-protocol/anip/tree/main/{SOURCE_DIR}"},
            {"title": "Showcase files", "url": f"https://github.com/anip-protocol/anip/tree/main/{SHOWCASE_DIR}"},
        ],
        "capability_count": len(CAPABILITIES),
        "service_count": 1,
        "service_ids": [SERVICE_ID],
        "lineage": lineage,
        "source": {
            "business_source_path": f"{SOURCE_DIR}/source-spec.md",
            "product_revision_ref": "slack-fronting:source-spec:v1",
            "developer_revision_ref": "slack-fronting:developer-definition:v1",
        },
        "agent_consumption_readiness": readiness,
        "agent_consumability": consumability,
        "integration_fronting_summary": {
            "backend_options": ["native_api", "mcp"],
            "raw_backend_operations": 10,
            "agent_facing_surface": "governed_anip_capabilities_only",
        },
        "generated_at": GENERATED_AT,
    }
    lock = {
        "lock_kind": "publisher_recommended_lock",
        "artifact_type": "anip_package_lock",
        "blueprint_id": PACKAGE_ID,
        "blueprint_version": VERSION,
        "package_id": PACKAGE_ID,
        "package_version": VERSION,
        "service_definition_digest": signature,
        "schema_version": manifest["schema_version"],
        "build_packs": manifest["build_packs"]["recommended"],
        "verifier_packs": manifest["verifier_packs"]["recommended"],
        "runtime_packages": [],
        "extension_packs": [],
        "regression_packs": [],
        "selected_service_ids": [SERVICE_ID],
        "capability_ids": [capability["capability_id"] for capability in CAPABILITIES],
        "contract_signature": signature,
        "lineage": lineage,
        "agent_consumption_readiness": readiness,
        "agent_consumability": {"schema_version": consumability["schema_version"], "capability_count": len(CAPABILITIES)},
        "generated_at": GENERATED_AT,
    }
    return {
        "bundle_schema_version": "anip-package-bundle/v1",
        "authority": "local-studio",
        "publication": {
            "package_id": PACKAGE_ID,
            "package_version": VERSION,
            "project_ref": lineage["project_ref"],
            "product_revision_ref": lineage["product_revision"]["ref"],
            "developer_revision_ref": lineage["developer_revision"]["ref"],
            "contract_signature": signature,
            "publisher_id": "local-studio-source",
            "publisher_type": "local",
            "lineage": lineage,
            "published_at": GENERATED_AT,
        },
        "package": {
            "package_id": PACKAGE_ID,
            "package_version": VERSION,
            "contract_signature": signature,
            "publisher_id": "local-studio-source",
            "publisher_type": "local",
            "lineage": lineage,
            "schema_version": definition["contract_schema_version"],
            "manifest_digest": digest(manifest),
            "definition_digest": signature,
            "lock_digest": digest(lock),
            "manifest": manifest,
            "service_definition": definition,
            "recommended_lock": lock,
        },
        "receipt": {"registry_signature": "", "issued_at": GENERATED_AT, "authority": "local-studio"},
        "lineage": lineage,
        "manifest": manifest,
        "service_definition": definition,
        "lock": lock,
        "registry_keys": [],
        "digests": {"manifest": digest(manifest), "service_definition": signature, "lock": digest(lock), "receipt": ""},
    }


def showcase_readme() -> str:
    return f"""# Slack Governed Fronting Showcase

This example shows the intended ANIP pattern for fronting broad Slack Web API or MCP access:
MCP/API operations are downstream implementation details; agents invoke governed ANIP capabilities.

## Build artifacts

```bash
python3 examples/showcase/slack_fronting/build_showcase.py
cd packages/go
go run ./cmd/anip-generate \\
  --package-bundle ../../examples/showcase/slack_fronting/registry-packages/{PACKAGE_ID}-{VERSION}.anip-package.json \\
  --target python \\
  --dependency-source local \\
  --port {PORT} \\
  --output ../../examples/showcase/slack_fronting/generated/studio_slack_fronting \\
  --force
```

Verify the local service definition:

```bash
cd packages/go
go run ./cmd/anip-verify \\
  --definition ../../examples/showcase/slack_fronting/registry-packages/{PACKAGE_ID}-{VERSION}-service-definition.json
```

## What to inspect

- `registry-packages/{PACKAGE_ID}-{VERSION}-service-definition.json`: signed behavior contract with `integration_fronting` mappings.
- `generated/studio_slack_fronting/integration-fronting/adapter-bindings.json`: capability-to-backend binding pack.
- `generated/studio_slack_fronting/integration-fronting/backend-selection.example.json`: deployment-time backend selection template.
- `generated/studio_slack_fronting/integration-fronting/conformance.json`: static check that raw backend operations are governed.

## Design point

The same ANIP contract can be backed by native Slack Web API or Slack MCP. The backend shape is replaceable; the governed behavior surface is stable.
"""


def main() -> None:
    definition = build_definition()
    package = build_package(definition)
    package_dir = REPO_ROOT / SHOWCASE_DIR / "registry-packages"
    base = package_dir / f"{PACKAGE_ID}-{VERSION}"

    write_text(REPO_ROOT / SOURCE_DIR / "source-spec.md", source_doc())
    write_text(REPO_ROOT / SHOWCASE_DIR / "README.md", showcase_readme())
    write_json(base.with_name(base.name + "-service-definition.json"), definition)
    write_json(base.with_name(base.name + "-manifest.json"), package["manifest"])
    write_json(base.with_name(base.name + "-lock.json"), package["lock"])
    write_json(base.with_name(base.name + ".anip-package.json"), package)
    write_text(
        package_dir / "README.md",
        f"""# {SYSTEM_NAME} Registry Package

Generated from `{SOURCE_DIR}/source-spec.md`.

Generate Python code:

```bash
cd packages/go
go run ./cmd/anip-generate \\
  --package-bundle ../../examples/showcase/slack_fronting/registry-packages/{PACKAGE_ID}-{VERSION}.anip-package.json \\
  --target python \\
  --dependency-source local \\
  --port {PORT} \\
  --output ../../examples/showcase/slack_fronting/generated/studio_slack_fronting \\
  --force
```

Verify the local service definition:

```bash
cd packages/go
go run ./cmd/anip-verify \\
  --definition ../../examples/showcase/slack_fronting/registry-packages/{PACKAGE_ID}-{VERSION}-service-definition.json
```

Package-bundle verification requires a registry-issued receipt signature. This local showcase bundle is intended for generation and inspection before publication.
""",
    )
    print(f"wrote slack fronting showcase: {base}")


if __name__ == "__main__":
    main()
