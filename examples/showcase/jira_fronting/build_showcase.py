#!/usr/bin/env python3
"""Build the Jira governed fronting showcase package and source docs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
VERSION = "0.1.0"
GENERATED_AT = "2026-05-08T00:00:00Z"
PACKAGE_ID = "jira-fronting-showcase"
SYSTEM_NAME = "Jira Governed Fronting Showcase"
SERVICE_ID = "jira-governance-service"
SERVICE_NAME = "Jira Governance Service"
SOURCE_DIR = "docs/examples/jira-fronting-showcase"
SHOWCASE_DIR = "examples/showcase/jira_fronting"
PORT = 9140


def stable_json(value: Any) -> str:
    # Match Go encoding/json digest behavior used by registry/verifier code.
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
        "id": "jira:jira.backlog.search",
        "kind": "atomic",
        "source_kind": "integration_fronting_source_doc",
        "service_id": SERVICE_ID,
        "capability_id": "jira.backlog.search",
        "title": "Search Team Backlog",
        "summary": "Search Jira issues in an allowed project with bounded query and result limits.",
        "entity_targeted": True,
        "subject_kind": "jira_issue",
        "context_type": "backlog_search",
        "output_intent": "bounded_issue_results",
        "intent_type": "read_only",
        "operation_type": "read",
        "side_effect_level": "read",
        "backend_operation": "search_team_backlog",
        "path_template": "/jira/backlog/search",
        "output_shape": "bounded_issue_results",
        "minimum_scope": ["jira.read"],
        "business_effects": {
            "produces": ["Read bounded data", "Summarize information"],
            "does_not_produce": ["Change system state", "Export raw data"],
        },
        "inputs": [
            input_field("project_key", "string", "Allowed Jira project key.", entity_reference=True, semantic_type="project_scope"),
            input_field("query", "string", "Bounded issue search query."),
            input_field("limit", "integer", "Maximum issues to return.", required=False, default="25"),
        ],
    },
    {
        "id": "jira:jira.bug.prepare",
        "kind": "atomic",
        "grant_policy": grant_policy(),
        "source_kind": "integration_fronting_source_doc",
        "service_id": SERVICE_ID,
        "capability_id": "jira.bug.prepare",
        "title": "Prepare Bug Ticket",
        "summary": "Prepare a Jira bug ticket preview from a bounded incident or defect summary without creating it.",
        "entity_targeted": True,
        "subject_kind": "jira_issue",
        "context_type": "ticket_preparation",
        "output_intent": "issue_creation_preview",
        "intent_type": "prepare_only",
        "operation_type": "write",
        "side_effect_level": "write_adjacent",
        "backend_operation": "prepare_bug_ticket",
        "path_template": "/jira/bugs/preview",
        "output_shape": "issue_creation_preview",
        "minimum_scope": ["jira.write.prepare"],
        "business_effects": {
            "produces": ["Preview a change", "Ask for approval"],
            "does_not_produce": ["Change system state", "Create issue"],
        },
        "inputs": [
            input_field("project_key", "string", "Allowed Jira project key.", entity_reference=True, semantic_type="project_scope"),
            input_field("summary", "string", "Issue summary."),
            input_field("description", "string", "Issue description."),
            input_field("severity", "string", "Business severity.", allowed_values=["sev1", "sev2", "sev3", "sev4"], semantic_type="risk_level"),
            input_field("labels", "array<string>", "Labels to propose.", required=False),
        ],
    },
    {
        "id": "jira:jira.story.prepare",
        "kind": "atomic",
        "grant_policy": grant_policy(),
        "source_kind": "integration_fronting_source_doc",
        "service_id": SERVICE_ID,
        "capability_id": "jira.story.prepare",
        "title": "Prepare Story Ticket",
        "summary": "Prepare a Jira story preview with acceptance criteria before any issue is created.",
        "entity_targeted": True,
        "subject_kind": "jira_issue",
        "context_type": "ticket_preparation",
        "output_intent": "issue_creation_preview",
        "intent_type": "prepare_only",
        "operation_type": "write",
        "side_effect_level": "write_adjacent",
        "backend_operation": "prepare_story_ticket",
        "path_template": "/jira/stories/preview",
        "output_shape": "issue_creation_preview",
        "minimum_scope": ["jira.write.prepare"],
        "business_effects": {
            "produces": ["Preview a change", "Ask for approval"],
            "does_not_produce": ["Change system state", "Create issue"],
        },
        "inputs": [
            input_field("project_key", "string", "Allowed Jira project key.", entity_reference=True, semantic_type="project_scope"),
            input_field("summary", "string", "Story summary."),
            input_field("acceptance_criteria", "array<string>", "Acceptance criteria to include."),
            input_field("priority", "string", "Business priority.", required=False, allowed_values=["low", "medium", "high"]),
        ],
    },
    {
        "id": "jira:jira.transition.request",
        "kind": "atomic",
        "grant_policy": grant_policy(),
        "source_kind": "integration_fronting_source_doc",
        "service_id": SERVICE_ID,
        "capability_id": "jira.transition.request",
        "title": "Request Status Transition",
        "summary": "Request a governed Jira issue transition and stop for approval when policy requires it.",
        "entity_targeted": True,
        "subject_kind": "jira_issue",
        "context_type": "issue_transition",
        "output_intent": "transition_preview",
        "intent_type": "approval_gated_action",
        "operation_type": "approval_gated",
        "side_effect_level": "write_adjacent",
        "backend_operation": "request_status_transition",
        "path_template": "/jira/issues/{issue_key}/transition-request",
        "output_shape": "transition_preview",
        "minimum_scope": ["jira.transition.request"],
        "business_effects": {
            "produces": ["Preview a change", "Ask for approval"],
            "does_not_produce": ["Execute approved action", "Bypass workflow policy"],
        },
        "inputs": [
            input_field("issue_key", "string", "Jira issue key.", entity_reference=True, semantic_type="issue_ref"),
            input_field("target_status", "string", "Requested target status.", allowed_values=["todo", "in_progress", "in_review", "done"]),
            input_field("reason", "string", "Reason for the transition."),
        ],
    },
    {
        "id": "jira:jira.comment.prepare",
        "kind": "atomic",
        "grant_policy": grant_policy(),
        "source_kind": "integration_fronting_source_doc",
        "service_id": SERVICE_ID,
        "capability_id": "jira.comment.prepare",
        "title": "Prepare Triage Comment",
        "summary": "Prepare a Jira issue comment from incident or triage context without posting it.",
        "entity_targeted": True,
        "subject_kind": "jira_issue",
        "context_type": "comment_preparation",
        "output_intent": "comment_preview",
        "intent_type": "prepare_only",
        "operation_type": "write",
        "side_effect_level": "write_adjacent",
        "backend_operation": "prepare_triage_comment",
        "path_template": "/jira/issues/{issue_key}/comment-preview",
        "output_shape": "comment_preview",
        "minimum_scope": ["jira.comment.prepare"],
        "business_effects": {
            "produces": ["Draft content", "Preview a change"],
            "does_not_produce": ["Send outside the system", "Change system state"],
        },
        "inputs": [
            input_field("issue_key", "string", "Jira issue key.", entity_reference=True, semantic_type="issue_ref"),
            input_field("comment_purpose", "string", "Purpose of the comment.", allowed_values=["triage_update", "customer_impact", "release_note"]),
            input_field("context", "string", "Context to summarize in the comment."),
        ],
    },
]


def backend_bindings(capability: dict[str, Any]) -> list[dict[str, Any]]:
    operation = capability["backend_operation"]
    required_inputs = [item["input_name"] for item in capability["inputs"] if item["required"]]
    optional_inputs = [item["input_name"] for item in capability["inputs"] if not item["required"]]
    return [
        {
            "backend_kind": "native_api",
            "connection_ref": "jira_rest_api",
            "raw_operation_refs": [f"jira.rest.{operation}"],
            "backend_input_mode": "explicit",
            "explicit_required_backend_inputs": required_inputs,
            "explicit_optional_backend_inputs": optional_inputs,
            "matched_discovery_record_ids": [f"jira-rest-{operation}"],
            "status": "ready",
            "status_detail": "Native Jira REST implementation seam.",
        },
        {
            "backend_kind": "mcp",
            "connection_ref": "atlassian_mcp",
            "raw_operation_refs": [f"atlassian.mcp.{operation}"],
            "backend_input_mode": "explicit",
            "explicit_required_backend_inputs": required_inputs,
            "explicit_optional_backend_inputs": optional_inputs,
            "matched_discovery_record_ids": [f"atlassian-mcp-{operation}"],
            "status": "candidate",
            "status_detail": "Alternative MCP-backed adapter realization.",
        },
    ]


def fronting_mapping(capability: dict[str, Any]) -> dict[str, Any]:
    bindings = backend_bindings(capability)
    required_inputs = [item["input_name"] for item in capability["inputs"] if item["required"]]
    optional_inputs = [item["input_name"] for item in capability["inputs"] if not item["required"]]
    return {
        "id": f"{capability['capability_id'].replace('.', '_')}_fronting",
        "capability_id": capability["capability_id"],
        "title": capability["title"],
        "intent": capability["summary"],
        "service_id": SERVICE_ID,
        "service_name": SERVICE_NAME,
        "backend_kind": "hybrid",
        "connection_ref": "jira_fronting",
        "raw_operation_refs": [operation for binding in bindings for operation in binding["raw_operation_refs"]],
        "backend_bindings": bindings,
        "execution_posture": capability["intent_type"],
        "side_effect_level": capability["side_effect_level"],
        "subject_kind": capability["subject_kind"],
        "context_type": capability["context_type"],
        "output_intent": capability["output_intent"],
        "required_inputs": required_inputs,
        "optional_inputs": optional_inputs,
        "backend_input_mode": "explicit",
        "explicit_required_backend_inputs": required_inputs,
        "explicit_optional_backend_inputs": optional_inputs,
        "approval_rule_refs": ["approval.write_preview_required"] if capability["side_effect_level"] != "read" else [],
        "denial_rule_refs": ["deny.raw_export", "deny.unapproved_mutation"],
        "clarification_rule_refs": [f"clarify.{item}" for item in required_inputs],
        "audit_required": True,
        "outbound_controls": {
            "redact_sensitive_values": True,
            "block_unbounded_payloads": True,
        },
    }


def source_doc() -> str:
    capabilities = "\n".join(
        f"- `{capability['capability_id']}`: {capability['summary']} Backend bindings: Jira REST and Atlassian MCP."
        for capability in CAPABILITIES
    )
    return f"""# {SYSTEM_NAME} Source Specification

This source document models the fronting use case: raw Jira or Atlassian MCP operations
are available downstream, but agents should only see governed ANIP capabilities.

## Purpose

Demonstrate that ANIP can sit in front of either a native Jira REST API adapter or an
Atlassian MCP adapter while preserving the same governed service contract.

## Service Boundary

- Service ID: `{SERVICE_ID}`
- Service name: {SERVICE_NAME}
- Downstream option A: native Jira REST API adapter
- Downstream option B: Atlassian MCP adapter

## Governed Capabilities

{capabilities}

## Review Decisions

- Do not expose raw MCP tools or raw Jira REST endpoints as agent-facing capabilities.
- Search is read-only and must remain project-scoped and result-bounded.
- Issue creation, comments, and transitions are prepare/request flows. They stop at preview or approval, not direct mutation.
- The same ANIP contract should work with either backend binding; deployment selects the active binding.
- Raw exports, direct workflow bypass, and unapproved Jira mutations are denied by policy.
"""


def build_definition() -> dict[str, Any]:
    capability_ids = [capability["capability_id"] for capability in CAPABILITIES]
    return {
        "artifact_type": "anip_service_definition",
        "contract_schema_version": "anip-service-definition/v1",
        "compiled_contract_identity": {
            "signature": "local-jira-fronting-contract-signature",
            "signature_algorithm": "sha256",
        },
        "generated_at": GENERATED_AT,
        "identity": {
            "system_name": SYSTEM_NAME,
            "domain_name": "jira",
            "delivery_model": "governed_integration_fronting",
            "architecture_shape": "single_service",
        },
        "authority": {
            "approval_expectation": "approval_gated_for_write_like_actions",
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
                "owned_concept_ids": ["jira_issue", "jira_project", "jira_transition"],
            }
        ],
        "capability_formalizations": CAPABILITIES,
        "permission_intent_bindings": [
            {
                "id": "jira_triage_user_access",
                "actor_id": "triage_user",
                "business_area": "jira_triage",
                "business_area_label": "Jira Triage",
                "access_posture": "bounded",
                "governed_outcome_type": "bounded_result",
                "governed_outcome": "Triage users can search backlog items and prepare governed previews.",
                "target_service_ids": [SERVICE_ID],
                "target_capability_ids": capability_ids,
                "formalization_strategy": "Generated policy keeps raw Jira/MCP operations behind reviewed ANIP capabilities.",
            }
        ],
        "runtime_policy_bindings": [
            {
                "id": "jira_triage_user_policy",
                "source_permission_id": "jira_triage_user_access",
                "actor_id": "triage_user",
                "principal_selector": {"claim": "actor_id", "equals": "triage_user"},
                "business_area": "jira_triage",
                "business_area_label": "Jira Triage",
                "service_ids": [SERVICE_ID],
                "capability_ids": capability_ids,
                "required_scopes": sorted({scope for capability in CAPABILITIES for scope in capability["minimum_scope"]}),
                "decision": "allow_with_limits",
                "business_rule": "Allow only declared governed Jira capabilities; write-like actions stop at preview or approval.",
                "enforcement_notes": "Raw backend operations remain implementation detail behind the generated adapter seam.",
            }
        ],
        "integration_fronting": {
            "project_type": "governed_service_project",
            "capability_mappings": [fronting_mapping(capability) for capability in CAPABILITIES],
        },
        "source": {
            "source_docs": [f"{SOURCE_DIR}/source-spec.md"],
            "fronting_target": "jira_native_api_or_atlassian_mcp",
        },
    }


def build_consumability() -> dict[str, Any]:
    return {
        "schema_version": "anip-agent-consumability/v0",
        "capabilities": {
            capability["capability_id"]: {
                "intent": {
                    "category": capability["capability_id"],
                    "summary": capability["summary"],
                },
                "business_effects": capability["business_effects"],
                "app_owned_behavior": [
                    "Select native Jira REST or Atlassian MCP backend at deployment time.",
                    "Never route agents directly to raw Jira or MCP operations.",
                ],
                "required_context": [
                    {
                        "input": item["input_name"],
                        "behavior": "clarify",
                        "summary": item["summary"],
                    }
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
        "summary": {"blockers": 0, "warnings": 0, "info": 0, "probes": 4, "required_app_glue": 0},
        "probes": [
            {"id": "jira-search-project-scope", "expected_outcome": "success"},
            {"id": "jira-bug-missing-project", "expected_outcome": "clarification_required"},
            {"id": "jira-transition-without-approval", "expected_outcome": "approval_required"},
            {"id": "jira-raw-export-denied", "expected_outcome": "unsupported"},
        ],
    }
    lineage = {
        "project_ref": "studio-source:jira-fronting",
        "product_revision": {
            "ref": "jira-fronting:source-spec:v1",
            "artifact_id": "jira-fronting-source-spec",
            "revision_number": 1,
            "baseline_locked_at": GENERATED_AT,
        },
        "developer_revision": {
            "ref": "jira-fronting:developer-definition:v1",
            "artifact_id": "jira-fronting-developer-definition",
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
        "readme": "# Jira Governed Fronting Showcase\n\nANIP fronting example for native Jira REST or Atlassian MCP backends.\n",
        "usage": {
            "generate_python": f"go run ./cmd/anip-generate --package-bundle ../../examples/showcase/jira_fronting/registry-packages/{PACKAGE_ID}-{VERSION}.anip-package.json --target python --dependency-source local --port {PORT} --output ../../examples/showcase/jira_fronting/generated/studio_jira_fronting --force",
            "verify_definition": f"go run ./cmd/anip-verify --definition ../../examples/showcase/jira_fronting/registry-packages/{PACKAGE_ID}-{VERSION}-service-definition.json",
        },
        "source_links": [
            {
                "title": "Source documentation",
                "url": f"https://github.com/anip-protocol/anip/tree/main/{SOURCE_DIR}",
            },
            {
                "title": "Showcase files",
                "url": f"https://github.com/anip-protocol/anip/tree/main/{SHOWCASE_DIR}",
            },
        ],
        "capability_count": len(CAPABILITIES),
        "service_count": 1,
        "service_ids": [SERVICE_ID],
        "lineage": lineage,
        "source": {
            "business_source_path": f"{SOURCE_DIR}/source-spec.md",
            "product_revision_ref": "jira-fronting:source-spec:v1",
            "developer_revision_ref": "jira-fronting:developer-definition:v1",
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
        "agent_consumability": {
            "schema_version": consumability["schema_version"],
            "capability_count": len(consumability["capabilities"]),
        },
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
        "digests": {
            "manifest": digest(manifest),
            "service_definition": signature,
            "lock": digest(lock),
            "receipt": "",
        },
    }


def showcase_readme() -> str:
    return f"""# Jira Governed Fronting Showcase

This example shows the intended ANIP pattern for fronting broad Jira or Atlassian MCP access:
MCP/API operations are downstream implementation details; agents invoke governed ANIP capabilities.

## Build artifacts

```bash
python3 examples/showcase/jira_fronting/build_showcase.py
cd packages/go
go run ./cmd/anip-generate \\
  --package-bundle ../../examples/showcase/jira_fronting/registry-packages/{PACKAGE_ID}-{VERSION}.anip-package.json \\
  --target python \\
  --dependency-source local \\
  --port {PORT} \\
  --output ../../examples/showcase/jira_fronting/generated/studio_jira_fronting \\
  --force
```

Verify the local service definition:

```bash
cd packages/go
go run ./cmd/anip-verify \
  --definition ../../examples/showcase/jira_fronting/registry-packages/jira-fronting-showcase-0.1.0-service-definition.json
```

## What to inspect

- `registry-packages/{PACKAGE_ID}-{VERSION}-service-definition.json`: signed behavior contract with `integration_fronting` mappings.
- `generated/studio_jira_fronting/integration-fronting/adapter-bindings.json`: capability-to-backend binding pack.
- `generated/studio_jira_fronting/integration-fronting/backend-selection.example.json`: deployment-time backend selection template.
- `generated/studio_jira_fronting/integration-fronting/conformance.json`: static check that raw backend operations are governed.

## Design point

The same ANIP contract can be backed by native Jira REST or Atlassian MCP. The backend shape is replaceable; the governed behavior surface is stable.
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
  --package-bundle ../../examples/showcase/jira_fronting/registry-packages/{PACKAGE_ID}-{VERSION}.anip-package.json \\
  --target python \\
  --dependency-source local \\
  --port {PORT} \\
  --output ../../examples/showcase/jira_fronting/generated/studio_jira_fronting \\
  --force
```

Verify the local service definition:

```bash
cd packages/go
go run ./cmd/anip-verify \\
  --definition ../../examples/showcase/jira_fronting/registry-packages/{PACKAGE_ID}-{VERSION}-service-definition.json
```

Package-bundle verification requires a registry-issued receipt signature. This local showcase bundle is intended for generation and inspection before publication.
""",
    )
    print(f"wrote jira fronting showcase: {base}")


if __name__ == "__main__":
    main()
