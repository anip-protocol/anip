"""Generated runtime target metadata."""
from __future__ import annotations

import json

RUNTIME_TARGET = json.loads(r'''{
  "system_name": "GitHub Governed Fronting Showcase",
  "domain_name": "github",
  "delivery_model": "governed_integration_fronting",
  "architecture_shape": "single_service",
  "protocols": [
    "https",
    "mcp"
  ],
  "services": [
    {
      "service_id": "github-governance-service",
      "service_name": "GitHub Governance Service",
      "source_role": "governed_integration_fronting",
      "source_capabilities": [
        "github.repo.search_context",
        "github.issue.prepare",
        "github.pr.comment.prepare",
        "github.workflow.dispatch.request",
        "github.release_notes.prepare"
      ],
      "formalized_capability_ids": [
        "github.repo.search_context",
        "github.issue.prepare",
        "github.pr.comment.prepare",
        "github.workflow.dispatch.request",
        "github.release_notes.prepare"
      ],
      "owned_concept_ids": [
        "github_repository",
        "github_issue",
        "github_pull_request",
        "github_workflow"
      ]
    }
  ],
  "policy_bindings": [
    {
      "id": "github_developer_policy",
      "source_permission_id": "github_developer_access",
      "actor_id": "developer",
      "principal_selector": {
        "claim": "actor_id",
        "equals": "developer"
      },
      "business_area": "github_engineering",
      "business_area_label": "GitHub Engineering",
      "service_ids": [
        "github-governance-service"
      ],
      "capability_ids": [
        "github.repo.search_context",
        "github.issue.prepare",
        "github.pr.comment.prepare",
        "github.workflow.dispatch.request",
        "github.release_notes.prepare"
      ],
      "required_scopes": [
        "github.read",
        "github.write.prepare",
        "github.comment.prepare",
        "github.workflow.request"
      ],
      "decision": "allow_with_limits",
      "business_rule": "Allow only declared governed GitHub capabilities; write-like actions stop at preview or approval.",
      "enforcement_notes": "Raw backend operations remain implementation detail behind the generated adapter seam."
    }
  ],
  "authority": {
    "approval_expectation": "approval_gated_for_write_like_actions",
    "blocked_failure_posture": "clarify_or_stop"
  },
  "audit": {
    "durable_records_required": true,
    "searchable_history_required": true
  }
}
''')
GENERATED_RUNTIME_TARGET = RUNTIME_TARGET

GENERATED_CAPABILITY_METADATA = json.loads(r'''[
  {
    "service_id": "github-governance-service",
    "service_name": "GitHub Governance Service",
    "capability_id": "github.repo.search_context",
    "title": "Search Repository Context",
    "summary": "Search bounded GitHub repository issues and pull requests without exposing raw repository tools.",
    "kind": "atomic",
    "intent_type": "read_only",
    "operation_type": "read",
    "execution_posture": "read_only",
    "side_effect_level": "read",
    "business_effects": {
      "produces": [
        "Read bounded data",
        "Summarize information"
      ],
      "does_not_produce": [
        "Change repository state",
        "Export raw data"
      ]
    },
    "backend_operation": "search_repository_context",
    "path_template": "/github/repos/{owner}/{repo}/context/search",
    "output_shape": "bounded_repository_results",
    "subject_kind": "github_repository",
    "context_type": "repository_context_search",
    "output_intent": "bounded_repository_results",
    "minimum_scope": [
      "github.read"
    ],
    "required_inputs": [
      {
        "input_name": "owner",
        "input_type": "string",
        "required": true,
        "summary": "GitHub repository owner.",
        "default_value": "",
        "clarification_hint": "Ask for owner when it is missing or ambiguous.",
        "entity_reference": true
      },
      {
        "input_name": "repo",
        "input_type": "string",
        "required": true,
        "summary": "GitHub repository name.",
        "default_value": "",
        "clarification_hint": "Ask for repo when it is missing or ambiguous.",
        "entity_reference": true
      },
      {
        "input_name": "query",
        "input_type": "string",
        "required": true,
        "summary": "Bounded repository search query.",
        "default_value": "",
        "clarification_hint": "Ask for query when it is missing or ambiguous."
      }
    ],
    "optional_inputs": [
      {
        "input_name": "limit",
        "input_type": "integer",
        "required": false,
        "summary": "Maximum results to return.",
        "default_value": "20",
        "clarification_hint": "Ask for limit when it is missing or ambiguous."
      }
    ],
    "sample_parameters": {
      "limit": 20,
      "owner": "owner-value",
      "query": "query-value",
      "repo": "repo-value"
    },
    "backend_input_mode": "explicit",
    "derived_required_backend_inputs": [],
    "derived_optional_backend_inputs": [],
    "explicit_required_backend_inputs": [
      "owner",
      "repo",
      "query"
    ],
    "explicit_optional_backend_inputs": [
      "limit"
    ],
    "backend_bindings": [
      {
        "backend_kind": "native_api",
        "connection_ref": "github_rest_graphql_api",
        "raw_operation_refs": [
          "github.api.search_repository_context"
        ],
        "backend_input_mode": "explicit",
        "explicit_required_backend_inputs": [
          "owner",
          "repo",
          "query"
        ],
        "explicit_optional_backend_inputs": [
          "limit"
        ],
        "matched_discovery_record_ids": [
          "github-api-search_repository_context"
        ],
        "status": "ready",
        "status_detail": "Native GitHub REST/GraphQL implementation seam."
      },
      {
        "backend_kind": "mcp",
        "connection_ref": "github_mcp",
        "raw_operation_refs": [
          "github.mcp.search_repository_context"
        ],
        "backend_input_mode": "explicit",
        "explicit_required_backend_inputs": [
          "owner",
          "repo",
          "query"
        ],
        "explicit_optional_backend_inputs": [
          "limit"
        ],
        "matched_discovery_record_ids": [
          "github-mcp-search_repository_context"
        ],
        "status": "candidate",
        "status_detail": "Alternative MCP-backed adapter realization for teams that already standardize on GitHub MCP."
      }
    ],
    "governance": {
      "approval_rule_refs": [],
      "denial_rule_refs": [
        "deny.raw_export",
        "deny.unapproved_mutation",
        "deny.direct_workflow_bypass"
      ],
      "clarification_rule_refs": [
        "clarify.owner",
        "clarify.repo",
        "clarify.query"
      ],
      "audit_required": true
    },
    "outbound_controls": {
      "block_repository_secret_exfiltration": true,
      "block_unbounded_payloads": true,
      "redact_sensitive_values": true
    }
  },
  {
    "service_id": "github-governance-service",
    "service_name": "GitHub Governance Service",
    "capability_id": "github.issue.prepare",
    "title": "Prepare Issue",
    "summary": "Prepare a GitHub issue preview with labels and assignees before any issue is created.",
    "kind": "atomic",
    "grant_policy": {
      "allowed_grant_types": [
        "one_time",
        "session_bound"
      ],
      "default_grant_type": "one_time",
      "expires_in_seconds": 900,
      "max_uses": 1
    },
    "intent_type": "prepare_only",
    "operation_type": "write",
    "execution_posture": "prepare_only",
    "side_effect_level": "write_adjacent",
    "business_effects": {
      "produces": [
        "Preview a change",
        "Ask for approval"
      ],
      "does_not_produce": [
        "Change repository state",
        "Create issue"
      ]
    },
    "backend_operation": "prepare_issue",
    "path_template": "/github/repos/{owner}/{repo}/issues/preview",
    "output_shape": "issue_creation_preview",
    "subject_kind": "github_issue",
    "context_type": "issue_preparation",
    "output_intent": "issue_creation_preview",
    "minimum_scope": [
      "github.write.prepare"
    ],
    "required_inputs": [
      {
        "input_name": "owner",
        "input_type": "string",
        "required": true,
        "summary": "GitHub repository owner.",
        "default_value": "",
        "clarification_hint": "Ask for owner when it is missing or ambiguous.",
        "entity_reference": true
      },
      {
        "input_name": "repo",
        "input_type": "string",
        "required": true,
        "summary": "GitHub repository name.",
        "default_value": "",
        "clarification_hint": "Ask for repo when it is missing or ambiguous.",
        "entity_reference": true
      },
      {
        "input_name": "title",
        "input_type": "string",
        "required": true,
        "summary": "Issue title.",
        "default_value": "",
        "clarification_hint": "Ask for title when it is missing or ambiguous."
      },
      {
        "input_name": "body",
        "input_type": "string",
        "required": true,
        "summary": "Issue body.",
        "default_value": "",
        "clarification_hint": "Ask for body when it is missing or ambiguous."
      }
    ],
    "optional_inputs": [
      {
        "input_name": "labels",
        "input_type": "array\u003cstring\u003e",
        "required": false,
        "summary": "Labels to propose.",
        "default_value": "",
        "clarification_hint": "Ask for labels when it is missing or ambiguous."
      },
      {
        "input_name": "assignees",
        "input_type": "array\u003cstring\u003e",
        "required": false,
        "summary": "Assignees to propose.",
        "default_value": "",
        "clarification_hint": "Ask for assignees when it is missing or ambiguous."
      }
    ],
    "sample_parameters": {
      "assignees": [],
      "body": "body-value",
      "labels": [],
      "owner": "owner-value",
      "repo": "repo-value",
      "title": "title-value"
    },
    "backend_input_mode": "explicit",
    "derived_required_backend_inputs": [],
    "derived_optional_backend_inputs": [],
    "explicit_required_backend_inputs": [
      "owner",
      "repo",
      "title",
      "body"
    ],
    "explicit_optional_backend_inputs": [
      "labels",
      "assignees"
    ],
    "backend_bindings": [
      {
        "backend_kind": "native_api",
        "connection_ref": "github_rest_graphql_api",
        "raw_operation_refs": [
          "github.api.prepare_issue"
        ],
        "backend_input_mode": "explicit",
        "explicit_required_backend_inputs": [
          "owner",
          "repo",
          "title",
          "body"
        ],
        "explicit_optional_backend_inputs": [
          "labels",
          "assignees"
        ],
        "matched_discovery_record_ids": [
          "github-api-prepare_issue"
        ],
        "status": "ready",
        "status_detail": "Native GitHub REST/GraphQL implementation seam."
      },
      {
        "backend_kind": "mcp",
        "connection_ref": "github_mcp",
        "raw_operation_refs": [
          "github.mcp.prepare_issue"
        ],
        "backend_input_mode": "explicit",
        "explicit_required_backend_inputs": [
          "owner",
          "repo",
          "title",
          "body"
        ],
        "explicit_optional_backend_inputs": [
          "labels",
          "assignees"
        ],
        "matched_discovery_record_ids": [
          "github-mcp-prepare_issue"
        ],
        "status": "candidate",
        "status_detail": "Alternative MCP-backed adapter realization for teams that already standardize on GitHub MCP."
      }
    ],
    "governance": {
      "approval_rule_refs": [
        "approval.write_preview_required"
      ],
      "denial_rule_refs": [
        "deny.raw_export",
        "deny.unapproved_mutation",
        "deny.direct_workflow_bypass"
      ],
      "clarification_rule_refs": [
        "clarify.owner",
        "clarify.repo",
        "clarify.title",
        "clarify.body"
      ],
      "audit_required": true
    },
    "outbound_controls": {
      "block_repository_secret_exfiltration": true,
      "block_unbounded_payloads": true,
      "redact_sensitive_values": true
    }
  },
  {
    "service_id": "github-governance-service",
    "service_name": "GitHub Governance Service",
    "capability_id": "github.pr.comment.prepare",
    "title": "Prepare Pull Request Comment",
    "summary": "Prepare a pull request comment from review or release context without posting it.",
    "kind": "atomic",
    "grant_policy": {
      "allowed_grant_types": [
        "one_time",
        "session_bound"
      ],
      "default_grant_type": "one_time",
      "expires_in_seconds": 900,
      "max_uses": 1
    },
    "intent_type": "prepare_only",
    "operation_type": "write",
    "execution_posture": "prepare_only",
    "side_effect_level": "write_adjacent",
    "business_effects": {
      "produces": [
        "Draft content",
        "Preview a change"
      ],
      "does_not_produce": [
        "Send outside the system",
        "Change repository state"
      ]
    },
    "backend_operation": "prepare_pull_request_comment",
    "path_template": "/github/repos/{owner}/{repo}/pulls/{pull_number}/comments/preview",
    "output_shape": "comment_preview",
    "subject_kind": "github_pull_request",
    "context_type": "pull_request_comment_preparation",
    "output_intent": "comment_preview",
    "minimum_scope": [
      "github.comment.prepare"
    ],
    "required_inputs": [
      {
        "input_name": "owner",
        "input_type": "string",
        "required": true,
        "summary": "GitHub repository owner.",
        "default_value": "",
        "clarification_hint": "Ask for owner when it is missing or ambiguous.",
        "entity_reference": true
      },
      {
        "input_name": "repo",
        "input_type": "string",
        "required": true,
        "summary": "GitHub repository name.",
        "default_value": "",
        "clarification_hint": "Ask for repo when it is missing or ambiguous.",
        "entity_reference": true
      },
      {
        "input_name": "pull_number",
        "input_type": "integer",
        "required": true,
        "summary": "Pull request number.",
        "default_value": "",
        "clarification_hint": "Ask for pull_number when it is missing or ambiguous.",
        "entity_reference": true
      },
      {
        "input_name": "comment_purpose",
        "input_type": "string",
        "required": true,
        "summary": "Purpose of the comment.",
        "default_value": "",
        "allowed_values": [
          "review_note",
          "release_note",
          "triage_update"
        ],
        "clarification_hint": "Ask for comment_purpose when it is missing or ambiguous."
      },
      {
        "input_name": "context",
        "input_type": "string",
        "required": true,
        "summary": "Context to include in the comment.",
        "default_value": "",
        "clarification_hint": "Ask for context when it is missing or ambiguous."
      }
    ],
    "optional_inputs": [],
    "sample_parameters": {
      "comment_purpose": "review_note",
      "context": "context-value",
      "owner": "owner-value",
      "pull_number": 1,
      "repo": "repo-value"
    },
    "backend_input_mode": "explicit",
    "derived_required_backend_inputs": [],
    "derived_optional_backend_inputs": [],
    "explicit_required_backend_inputs": [
      "owner",
      "repo",
      "pull_number",
      "comment_purpose",
      "context"
    ],
    "explicit_optional_backend_inputs": [],
    "backend_bindings": [
      {
        "backend_kind": "native_api",
        "connection_ref": "github_rest_graphql_api",
        "raw_operation_refs": [
          "github.api.prepare_pull_request_comment"
        ],
        "backend_input_mode": "explicit",
        "explicit_required_backend_inputs": [
          "owner",
          "repo",
          "pull_number",
          "comment_purpose",
          "context"
        ],
        "matched_discovery_record_ids": [
          "github-api-prepare_pull_request_comment"
        ],
        "status": "ready",
        "status_detail": "Native GitHub REST/GraphQL implementation seam."
      },
      {
        "backend_kind": "mcp",
        "connection_ref": "github_mcp",
        "raw_operation_refs": [
          "github.mcp.prepare_pull_request_comment"
        ],
        "backend_input_mode": "explicit",
        "explicit_required_backend_inputs": [
          "owner",
          "repo",
          "pull_number",
          "comment_purpose",
          "context"
        ],
        "matched_discovery_record_ids": [
          "github-mcp-prepare_pull_request_comment"
        ],
        "status": "candidate",
        "status_detail": "Alternative MCP-backed adapter realization for teams that already standardize on GitHub MCP."
      }
    ],
    "governance": {
      "approval_rule_refs": [
        "approval.write_preview_required"
      ],
      "denial_rule_refs": [
        "deny.raw_export",
        "deny.unapproved_mutation",
        "deny.direct_workflow_bypass"
      ],
      "clarification_rule_refs": [
        "clarify.owner",
        "clarify.repo",
        "clarify.pull_number",
        "clarify.comment_purpose",
        "clarify.context"
      ],
      "audit_required": true
    },
    "outbound_controls": {
      "block_repository_secret_exfiltration": true,
      "block_unbounded_payloads": true,
      "redact_sensitive_values": true
    }
  },
  {
    "service_id": "github-governance-service",
    "service_name": "GitHub Governance Service",
    "capability_id": "github.workflow.dispatch.request",
    "title": "Request Workflow Dispatch",
    "summary": "Prepare a governed GitHub Actions workflow dispatch request and stop for approval.",
    "kind": "atomic",
    "grant_policy": {
      "allowed_grant_types": [
        "one_time",
        "session_bound"
      ],
      "default_grant_type": "one_time",
      "expires_in_seconds": 900,
      "max_uses": 1
    },
    "intent_type": "approval_gated_action",
    "operation_type": "approval_gated",
    "execution_posture": "approval_gated_action",
    "side_effect_level": "write_adjacent",
    "business_effects": {
      "produces": [
        "Preview a change",
        "Ask for approval"
      ],
      "does_not_produce": [
        "Execute approved action",
        "Bypass workflow policy"
      ]
    },
    "backend_operation": "request_workflow_dispatch",
    "path_template": "/github/repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches/preview",
    "output_shape": "workflow_dispatch_preview",
    "subject_kind": "github_workflow",
    "context_type": "workflow_dispatch",
    "output_intent": "workflow_dispatch_preview",
    "minimum_scope": [
      "github.workflow.request"
    ],
    "required_inputs": [
      {
        "input_name": "owner",
        "input_type": "string",
        "required": true,
        "summary": "GitHub repository owner.",
        "default_value": "",
        "clarification_hint": "Ask for owner when it is missing or ambiguous.",
        "entity_reference": true
      },
      {
        "input_name": "repo",
        "input_type": "string",
        "required": true,
        "summary": "GitHub repository name.",
        "default_value": "",
        "clarification_hint": "Ask for repo when it is missing or ambiguous.",
        "entity_reference": true
      },
      {
        "input_name": "workflow_id",
        "input_type": "string",
        "required": true,
        "summary": "Workflow file name or workflow ID.",
        "default_value": "",
        "clarification_hint": "Ask for workflow_id when it is missing or ambiguous.",
        "entity_reference": true
      },
      {
        "input_name": "ref",
        "input_type": "string",
        "required": true,
        "summary": "Git ref for dispatch.",
        "default_value": "",
        "clarification_hint": "Ask for ref when it is missing or ambiguous."
      }
    ],
    "optional_inputs": [
      {
        "input_name": "inputs",
        "input_type": "object",
        "required": false,
        "summary": "Workflow inputs.",
        "default_value": "",
        "clarification_hint": "Ask for inputs when it is missing or ambiguous."
      }
    ],
    "sample_parameters": {
      "inputs": {},
      "owner": "owner-value",
      "ref": "ref-value",
      "repo": "repo-value",
      "workflow_id": "workflow_id-value"
    },
    "backend_input_mode": "explicit",
    "derived_required_backend_inputs": [],
    "derived_optional_backend_inputs": [],
    "explicit_required_backend_inputs": [
      "owner",
      "repo",
      "workflow_id",
      "ref"
    ],
    "explicit_optional_backend_inputs": [
      "inputs"
    ],
    "backend_bindings": [
      {
        "backend_kind": "native_api",
        "connection_ref": "github_rest_graphql_api",
        "raw_operation_refs": [
          "github.api.request_workflow_dispatch"
        ],
        "backend_input_mode": "explicit",
        "explicit_required_backend_inputs": [
          "owner",
          "repo",
          "workflow_id",
          "ref"
        ],
        "explicit_optional_backend_inputs": [
          "inputs"
        ],
        "matched_discovery_record_ids": [
          "github-api-request_workflow_dispatch"
        ],
        "status": "ready",
        "status_detail": "Native GitHub REST/GraphQL implementation seam."
      },
      {
        "backend_kind": "mcp",
        "connection_ref": "github_mcp",
        "raw_operation_refs": [
          "github.mcp.request_workflow_dispatch"
        ],
        "backend_input_mode": "explicit",
        "explicit_required_backend_inputs": [
          "owner",
          "repo",
          "workflow_id",
          "ref"
        ],
        "explicit_optional_backend_inputs": [
          "inputs"
        ],
        "matched_discovery_record_ids": [
          "github-mcp-request_workflow_dispatch"
        ],
        "status": "candidate",
        "status_detail": "Alternative MCP-backed adapter realization for teams that already standardize on GitHub MCP."
      }
    ],
    "governance": {
      "approval_rule_refs": [
        "approval.write_preview_required"
      ],
      "denial_rule_refs": [
        "deny.raw_export",
        "deny.unapproved_mutation",
        "deny.direct_workflow_bypass"
      ],
      "clarification_rule_refs": [
        "clarify.owner",
        "clarify.repo",
        "clarify.workflow_id",
        "clarify.ref"
      ],
      "audit_required": true
    },
    "outbound_controls": {
      "block_repository_secret_exfiltration": true,
      "block_unbounded_payloads": true,
      "redact_sensitive_values": true
    }
  },
  {
    "service_id": "github-governance-service",
    "service_name": "GitHub Governance Service",
    "capability_id": "github.release_notes.prepare",
    "title": "Prepare Release Notes",
    "summary": "Prepare bounded release notes from selected issues or pull requests without creating a GitHub release.",
    "kind": "atomic",
    "intent_type": "prepare_only",
    "operation_type": "draft",
    "execution_posture": "prepare_only",
    "side_effect_level": "read",
    "business_effects": {
      "produces": [
        "Draft content",
        "Summarize information"
      ],
      "does_not_produce": [
        "Create release",
        "Change repository state"
      ]
    },
    "backend_operation": "prepare_release_notes",
    "path_template": "/github/repos/{owner}/{repo}/release-notes/preview",
    "output_shape": "release_notes_draft",
    "subject_kind": "github_release",
    "context_type": "release_notes_preparation",
    "output_intent": "release_notes_draft",
    "minimum_scope": [
      "github.read"
    ],
    "required_inputs": [
      {
        "input_name": "owner",
        "input_type": "string",
        "required": true,
        "summary": "GitHub repository owner.",
        "default_value": "",
        "clarification_hint": "Ask for owner when it is missing or ambiguous.",
        "entity_reference": true
      },
      {
        "input_name": "repo",
        "input_type": "string",
        "required": true,
        "summary": "GitHub repository name.",
        "default_value": "",
        "clarification_hint": "Ask for repo when it is missing or ambiguous.",
        "entity_reference": true
      },
      {
        "input_name": "range",
        "input_type": "string",
        "required": true,
        "summary": "Release range, milestone, or comparison reference.",
        "default_value": "",
        "clarification_hint": "Ask for range when it is missing or ambiguous."
      }
    ],
    "optional_inputs": [
      {
        "input_name": "audience",
        "input_type": "string",
        "required": false,
        "summary": "Release-note audience.",
        "default_value": "",
        "allowed_values": [
          "engineering",
          "customer",
          "internal"
        ],
        "clarification_hint": "Ask for audience when it is missing or ambiguous."
      }
    ],
    "sample_parameters": {
      "audience": "engineering",
      "owner": "owner-value",
      "range": "range-value",
      "repo": "repo-value"
    },
    "backend_input_mode": "explicit",
    "derived_required_backend_inputs": [],
    "derived_optional_backend_inputs": [],
    "explicit_required_backend_inputs": [
      "owner",
      "repo",
      "range"
    ],
    "explicit_optional_backend_inputs": [
      "audience"
    ],
    "backend_bindings": [
      {
        "backend_kind": "native_api",
        "connection_ref": "github_rest_graphql_api",
        "raw_operation_refs": [
          "github.api.prepare_release_notes"
        ],
        "backend_input_mode": "explicit",
        "explicit_required_backend_inputs": [
          "owner",
          "repo",
          "range"
        ],
        "explicit_optional_backend_inputs": [
          "audience"
        ],
        "matched_discovery_record_ids": [
          "github-api-prepare_release_notes"
        ],
        "status": "ready",
        "status_detail": "Native GitHub REST/GraphQL implementation seam."
      },
      {
        "backend_kind": "mcp",
        "connection_ref": "github_mcp",
        "raw_operation_refs": [
          "github.mcp.prepare_release_notes"
        ],
        "backend_input_mode": "explicit",
        "explicit_required_backend_inputs": [
          "owner",
          "repo",
          "range"
        ],
        "explicit_optional_backend_inputs": [
          "audience"
        ],
        "matched_discovery_record_ids": [
          "github-mcp-prepare_release_notes"
        ],
        "status": "candidate",
        "status_detail": "Alternative MCP-backed adapter realization for teams that already standardize on GitHub MCP."
      }
    ],
    "governance": {
      "approval_rule_refs": [],
      "denial_rule_refs": [
        "deny.raw_export",
        "deny.unapproved_mutation",
        "deny.direct_workflow_bypass"
      ],
      "clarification_rule_refs": [
        "clarify.owner",
        "clarify.repo",
        "clarify.range"
      ],
      "audit_required": true
    },
    "outbound_controls": {
      "block_repository_secret_exfiltration": true,
      "block_unbounded_payloads": true,
      "redact_sensitive_values": true
    }
  }
]
''')
