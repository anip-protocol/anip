#!/usr/bin/env python3
"""Build the GitHub governed fronting showcase package and source docs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
VERSION = "0.1.0"
GENERATED_AT = "2026-05-08T00:00:00Z"
PACKAGE_ID = "github-fronting-showcase"
SYSTEM_NAME = "GitHub Governed Fronting Showcase"
SERVICE_ID = "github-governance-service"
SERVICE_NAME = "GitHub Governance Service"
SOURCE_DIR = "docs/examples/github-fronting-showcase"
SHOWCASE_DIR = "examples/showcase/github_fronting"
PORT = 9150


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
        "id": "github:github.repo.search_context",
        "kind": "atomic",
        "source_kind": "integration_fronting_source_doc",
        "service_id": SERVICE_ID,
        "capability_id": "github.repo.search_context",
        "title": "Search Repository Context",
        "summary": "Search bounded GitHub repository issues and pull requests without exposing raw repository tools.",
        "entity_targeted": True,
        "subject_kind": "github_repository",
        "context_type": "repository_context_search",
        "output_intent": "bounded_repository_results",
        "intent_type": "read_only",
        "operation_type": "read",
        "side_effect_level": "read",
        "backend_operation": "search_repository_context",
        "path_template": "/github/repos/{owner}/{repo}/context/search",
        "output_shape": "bounded_repository_results",
        "minimum_scope": ["github.read"],
        "business_effects": {
            "produces": ["Read bounded data", "Summarize information"],
            "does_not_produce": ["Change repository state", "Export raw data"],
        },
        "inputs": [
            input_field("owner", "string", "GitHub repository owner.", entity_reference=True, semantic_type="repo_owner"),
            input_field("repo", "string", "GitHub repository name.", entity_reference=True, semantic_type="repo_name"),
            input_field("query", "string", "Bounded repository search query."),
            input_field("limit", "integer", "Maximum results to return.", required=False, default="20"),
        ],
    },
    {
        "id": "github:github.issue.prepare",
        "kind": "atomic",
        "grant_policy": grant_policy(),
        "source_kind": "integration_fronting_source_doc",
        "service_id": SERVICE_ID,
        "capability_id": "github.issue.prepare",
        "title": "Prepare Issue",
        "summary": "Prepare a GitHub issue preview with labels and assignees before any issue is created.",
        "entity_targeted": True,
        "subject_kind": "github_issue",
        "context_type": "issue_preparation",
        "output_intent": "issue_creation_preview",
        "intent_type": "prepare_only",
        "operation_type": "write",
        "side_effect_level": "write_adjacent",
        "backend_operation": "prepare_issue",
        "path_template": "/github/repos/{owner}/{repo}/issues/preview",
        "output_shape": "issue_creation_preview",
        "minimum_scope": ["github.write.prepare"],
        "business_effects": {
            "produces": ["Preview a change", "Ask for approval"],
            "does_not_produce": ["Change repository state", "Create issue"],
        },
        "inputs": [
            input_field("owner", "string", "GitHub repository owner.", entity_reference=True, semantic_type="repo_owner"),
            input_field("repo", "string", "GitHub repository name.", entity_reference=True, semantic_type="repo_name"),
            input_field("title", "string", "Issue title."),
            input_field("body", "string", "Issue body."),
            input_field("labels", "array<string>", "Labels to propose.", required=False),
            input_field("assignees", "array<string>", "Assignees to propose.", required=False),
        ],
    },
    {
        "id": "github:github.pr.comment.prepare",
        "kind": "atomic",
        "grant_policy": grant_policy(),
        "source_kind": "integration_fronting_source_doc",
        "service_id": SERVICE_ID,
        "capability_id": "github.pr.comment.prepare",
        "title": "Prepare Pull Request Comment",
        "summary": "Prepare a pull request comment from review or release context without posting it.",
        "entity_targeted": True,
        "subject_kind": "github_pull_request",
        "context_type": "pull_request_comment_preparation",
        "output_intent": "comment_preview",
        "intent_type": "prepare_only",
        "operation_type": "write",
        "side_effect_level": "write_adjacent",
        "backend_operation": "prepare_pull_request_comment",
        "path_template": "/github/repos/{owner}/{repo}/pulls/{pull_number}/comments/preview",
        "output_shape": "comment_preview",
        "minimum_scope": ["github.comment.prepare"],
        "business_effects": {
            "produces": ["Draft content", "Preview a change"],
            "does_not_produce": ["Send outside the system", "Change repository state"],
        },
        "inputs": [
            input_field("owner", "string", "GitHub repository owner.", entity_reference=True, semantic_type="repo_owner"),
            input_field("repo", "string", "GitHub repository name.", entity_reference=True, semantic_type="repo_name"),
            input_field("pull_number", "integer", "Pull request number.", entity_reference=True, semantic_type="pull_request_ref"),
            input_field("comment_purpose", "string", "Purpose of the comment.", allowed_values=["review_note", "release_note", "triage_update"]),
            input_field("context", "string", "Context to include in the comment."),
        ],
    },
    {
        "id": "github:github.workflow.dispatch.request",
        "kind": "atomic",
        "grant_policy": grant_policy(),
        "source_kind": "integration_fronting_source_doc",
        "service_id": SERVICE_ID,
        "capability_id": "github.workflow.dispatch.request",
        "title": "Request Workflow Dispatch",
        "summary": "Prepare a governed GitHub Actions workflow dispatch request and stop for approval.",
        "entity_targeted": True,
        "subject_kind": "github_workflow",
        "context_type": "workflow_dispatch",
        "output_intent": "workflow_dispatch_preview",
        "intent_type": "approval_gated_action",
        "operation_type": "approval_gated",
        "side_effect_level": "write_adjacent",
        "backend_operation": "request_workflow_dispatch",
        "path_template": "/github/repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches/preview",
        "output_shape": "workflow_dispatch_preview",
        "minimum_scope": ["github.workflow.request"],
        "business_effects": {
            "produces": ["Preview a change", "Ask for approval"],
            "does_not_produce": ["Execute approved action", "Bypass workflow policy"],
        },
        "inputs": [
            input_field("owner", "string", "GitHub repository owner.", entity_reference=True, semantic_type="repo_owner"),
            input_field("repo", "string", "GitHub repository name.", entity_reference=True, semantic_type="repo_name"),
            input_field("workflow_id", "string", "Workflow file name or workflow ID.", entity_reference=True, semantic_type="workflow_ref"),
            input_field("ref", "string", "Git ref for dispatch."),
            input_field("inputs", "object", "Workflow inputs.", required=False),
        ],
    },
    {
        "id": "github:github.release_notes.prepare",
        "kind": "atomic",
        "source_kind": "integration_fronting_source_doc",
        "service_id": SERVICE_ID,
        "capability_id": "github.release_notes.prepare",
        "title": "Prepare Release Notes",
        "summary": "Prepare bounded release notes from selected issues or pull requests without creating a GitHub release.",
        "entity_targeted": True,
        "subject_kind": "github_release",
        "context_type": "release_notes_preparation",
        "output_intent": "release_notes_draft",
        "intent_type": "prepare_only",
        "operation_type": "draft",
        "side_effect_level": "read",
        "backend_operation": "prepare_release_notes",
        "path_template": "/github/repos/{owner}/{repo}/release-notes/preview",
        "output_shape": "release_notes_draft",
        "minimum_scope": ["github.read"],
        "business_effects": {
            "produces": ["Draft content", "Summarize information"],
            "does_not_produce": ["Create release", "Change repository state"],
        },
        "inputs": [
            input_field("owner", "string", "GitHub repository owner.", entity_reference=True, semantic_type="repo_owner"),
            input_field("repo", "string", "GitHub repository name.", entity_reference=True, semantic_type="repo_name"),
            input_field("range", "string", "Release range, milestone, or comparison reference."),
            input_field("audience", "string", "Release-note audience.", required=False, allowed_values=["engineering", "customer", "internal"]),
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
            "connection_ref": "github_rest_graphql_api",
            "raw_operation_refs": [f"github.api.{operation}"],
            "backend_input_mode": "explicit",
            "explicit_required_backend_inputs": required_inputs,
            "explicit_optional_backend_inputs": optional_inputs,
            "matched_discovery_record_ids": [f"github-api-{operation}"],
            "status": "ready",
            "status_detail": "Native GitHub REST/GraphQL implementation seam.",
        },
        {
            "backend_kind": "mcp",
            "connection_ref": "github_mcp",
            "raw_operation_refs": [f"github.mcp.{operation}"],
            "backend_input_mode": "explicit",
            "explicit_required_backend_inputs": required_inputs,
            "explicit_optional_backend_inputs": optional_inputs,
            "matched_discovery_record_ids": [f"github-mcp-{operation}"],
            "status": "candidate",
            "status_detail": "Alternative MCP-backed adapter realization for teams that already standardize on GitHub MCP.",
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
        "connection_ref": "github_fronting",
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
        "denial_rule_refs": ["deny.raw_export", "deny.unapproved_mutation", "deny.direct_workflow_bypass"],
        "clarification_rule_refs": [f"clarify.{item}" for item in required_inputs],
        "audit_required": True,
        "outbound_controls": {
            "redact_sensitive_values": True,
            "block_unbounded_payloads": True,
            "block_repository_secret_exfiltration": True,
        },
    }


def source_doc() -> str:
    capabilities = "\n".join(
        f"- `{capability['capability_id']}`: {capability['summary']} Backend bindings: GitHub REST/GraphQL and GitHub MCP."
        for capability in CAPABILITIES
    )
    return f"""# {SYSTEM_NAME} Source Specification

This source document models the fronting use case: raw GitHub REST/GraphQL or GitHub MCP
operations are available downstream, but agents should only see governed ANIP capabilities.

## Purpose

Demonstrate that ANIP can sit in front of native GitHub APIs while preserving the same
governed service contract that could later be backed by GitHub MCP.

## Service Boundary

- Service ID: `{SERVICE_ID}`
- Service name: {SERVICE_NAME}
- Downstream option A: native GitHub REST/GraphQL API adapter
- Downstream option B: GitHub MCP adapter

## Governed Capabilities

{capabilities}

## Review Decisions

- Do not expose raw GitHub API or MCP tools as agent-facing capabilities.
- Repository search is read-only, repository-scoped, and result-bounded.
- Issue creation, PR comments, and workflow dispatches are prepare/request flows. They stop at preview or approval, not direct mutation.
- Release notes are draft content only and must not create a release.
- The same ANIP contract should work with either backend binding; deployment selects the active binding.
- Raw exports, direct workflow bypass, secret exfiltration, and unapproved repository mutations are denied by policy.
"""


def build_definition() -> dict[str, Any]:
    capability_ids = [capability["capability_id"] for capability in CAPABILITIES]
    return {
        "artifact_type": "anip_service_definition",
        "contract_schema_version": "anip-service-definition/v1",
        "compiled_contract_identity": {
            "signature": "local-github-fronting-contract-signature",
            "signature_algorithm": "sha256",
        },
        "generated_at": GENERATED_AT,
        "identity": {
            "system_name": SYSTEM_NAME,
            "domain_name": "github",
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
                "owned_concept_ids": ["github_repository", "github_issue", "github_pull_request", "github_workflow"],
            }
        ],
        "capability_formalizations": CAPABILITIES,
        "permission_intent_bindings": [
            {
                "id": "github_developer_access",
                "actor_id": "developer",
                "business_area": "github_engineering",
                "business_area_label": "GitHub Engineering",
                "access_posture": "bounded",
                "governed_outcome_type": "bounded_result",
                "governed_outcome": "Developers can search repository context and prepare governed previews.",
                "target_service_ids": [SERVICE_ID],
                "target_capability_ids": capability_ids,
                "formalization_strategy": "Generated policy keeps raw GitHub/MCP operations behind reviewed ANIP capabilities.",
            }
        ],
        "runtime_policy_bindings": [
            {
                "id": "github_developer_policy",
                "source_permission_id": "github_developer_access",
                "actor_id": "developer",
                "principal_selector": {"claim": "actor_id", "equals": "developer"},
                "business_area": "github_engineering",
                "business_area_label": "GitHub Engineering",
                "service_ids": [SERVICE_ID],
                "capability_ids": capability_ids,
                "required_scopes": sorted({scope for capability in CAPABILITIES for scope in capability["minimum_scope"]}),
                "decision": "allow_with_limits",
                "business_rule": "Allow only declared governed GitHub capabilities; write-like actions stop at preview or approval.",
                "enforcement_notes": "Raw backend operations remain implementation detail behind the generated adapter seam.",
            }
        ],
        "integration_fronting": {
            "project_type": "governed_service_project",
            "capability_mappings": [fronting_mapping(capability) for capability in CAPABILITIES],
        },
        "source": {
            "source_docs": [f"{SOURCE_DIR}/source-spec.md"],
            "fronting_target": "github_native_api_or_github_mcp",
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
                    "Select native GitHub REST/GraphQL or GitHub MCP backend at deployment time.",
                    "Never route agents directly to raw GitHub API or MCP operations.",
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
            {"id": "github-search-repo-scope", "expected_outcome": "success"},
            {"id": "github-issue-missing-repo", "expected_outcome": "clarification_required"},
            {"id": "github-pr-comment-without-approval", "expected_outcome": "approval_required"},
            {"id": "github-workflow-dispatch-without-approval", "expected_outcome": "approval_required"},
            {"id": "github-raw-export-denied", "expected_outcome": "unsupported"},
        ],
    }
    lineage = {
        "project_ref": "studio-source:github-fronting",
        "product_revision": {
            "ref": "github-fronting:source-spec:v1",
            "artifact_id": "github-fronting-source-spec",
            "revision_number": 1,
            "baseline_locked_at": GENERATED_AT,
        },
        "developer_revision": {
            "ref": "github-fronting:developer-definition:v1",
            "artifact_id": "github-fronting-developer-definition",
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
        "readme": "# GitHub Governed Fronting Showcase\n\nANIP fronting example for native GitHub REST/GraphQL or GitHub MCP backends.\n",
        "usage": {
            "generate_python": f"go run ./cmd/anip-generate --package-bundle ../../examples/showcase/github_fronting/registry-packages/{PACKAGE_ID}-{VERSION}.anip-package.json --target python --dependency-source local --port {PORT} --output ../../examples/showcase/github_fronting/generated/studio_github_fronting --force",
            "verify_definition": f"go run ./cmd/anip-verify --definition ../../examples/showcase/github_fronting/registry-packages/{PACKAGE_ID}-{VERSION}-service-definition.json",
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
            "product_revision_ref": "github-fronting:source-spec:v1",
            "developer_revision_ref": "github-fronting:developer-definition:v1",
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
        "digests": {"manifest": digest(manifest), "service_definition": signature, "lock": digest(lock), "receipt": ""},
    }


def showcase_readme() -> str:
    return f"""# GitHub Governed Fronting Showcase

This example shows the intended ANIP pattern for fronting broad GitHub API or MCP access:
MCP/API operations are downstream implementation details; agents invoke governed ANIP capabilities.

## Build artifacts

```bash
python3 examples/showcase/github_fronting/build_showcase.py
cd packages/go
go run ./cmd/anip-generate \\
  --package-bundle ../../examples/showcase/github_fronting/registry-packages/{PACKAGE_ID}-{VERSION}.anip-package.json \\
  --target python \\
  --dependency-source local \\
  --port {PORT} \\
  --output ../../examples/showcase/github_fronting/generated/studio_github_fronting \\
  --force
```

Verify the local service definition:

```bash
cd packages/go
go run ./cmd/anip-verify \\
  --definition ../../examples/showcase/github_fronting/registry-packages/{PACKAGE_ID}-{VERSION}-service-definition.json
```

## What to inspect

- `registry-packages/{PACKAGE_ID}-{VERSION}-service-definition.json`: signed behavior contract with `integration_fronting` mappings.
- `generated/studio_github_fronting/integration-fronting/adapter-bindings.json`: capability-to-backend binding pack.
- `generated/studio_github_fronting/integration-fronting/backend-selection.example.json`: deployment-time backend selection template.
- `generated/studio_github_fronting/integration-fronting/conformance.json`: static check that raw backend operations are governed.

## Design point

The same ANIP contract can be backed by native GitHub REST/GraphQL or GitHub MCP. The backend shape is replaceable; the governed behavior surface is stable.
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
  --package-bundle ../../examples/showcase/github_fronting/registry-packages/{PACKAGE_ID}-{VERSION}.anip-package.json \\
  --target python \\
  --dependency-source local \\
  --port {PORT} \\
  --output ../../examples/showcase/github_fronting/generated/studio_github_fronting \\
  --force
```

Verify the local service definition:

```bash
cd packages/go
go run ./cmd/anip-verify \\
  --definition ../../examples/showcase/github_fronting/registry-packages/{PACKAGE_ID}-{VERSION}-service-definition.json
```

Package-bundle verification requires a registry-issued receipt signature. This local showcase bundle is intended for generation and inspection before publication.
""",
    )
    print(f"wrote github fronting showcase: {base}")


if __name__ == "__main__":
    main()
