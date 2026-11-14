"""Generated runtime target metadata."""
from __future__ import annotations

import json

RUNTIME_TARGET = json.loads(r'''{
  "system_name": "GitHub Fronting Showcase 0.2.0",
  "domain_name": "developer tools",
  "delivery_model": "standalone_service",
  "architecture_shape": "single_service",
  "protocols": [
    "anip_http"
  ],
  "services": [
    {
      "service_id": "github-governance-service",
      "service_name": "GitHub Governance Service",
      "source_role": "public governed fronting service",
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
      "owned_concept_ids": []
    }
  ],
  "policy_bindings": [
    {
      "id": "policy_permission_rule_0",
      "source_permission_id": "permission_rule_0",
      "actor_id": "repository_operator",
      "principal_selector": {
        "claim": "actor_id",
        "equals": "repository_operator"
      },
      "business_area": "repository_context_access",
      "business_area_label": "Repository Context Access",
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
        "github.repo.search_context",
        "github.issue.prepare",
        "github.pr.comment.prepare",
        "github.workflow.dispatch.request",
        "github.release_notes.prepare"
      ],
      "decision": "allow_with_limits",
      "business_rule": "Allow bounded issue and pull-request context search within an explicit allowlisted repository. Return summaries only, not raw repository export.",
      "enforcement_notes": "repository_operator bounded access to Repository Context Access should return bounded_result. Allow bounded issue and pull-request context search within an explicit allowlisted repository. Return summaries only, not raw repository export. Supported by github.repo.search_context and the read-only bounded search posture."
    },
    {
      "id": "policy_permission_rule_1",
      "source_permission_id": "permission_rule_1",
      "actor_id": "issue_requester",
      "principal_selector": {
        "claim": "actor_id",
        "equals": "issue_requester"
      },
      "business_area": "issue_preparation_and_creation_governance",
      "business_area_label": "Issue Preparation and Creation Governance",
      "service_ids": [
        "github-governance-service"
      ],
      "capability_ids": [
        "github.issue.prepare"
      ],
      "required_scopes": [
        "github.issue.prepare"
      ],
      "decision": "approval_required",
      "business_rule": "Allow issue preparation preview with labels and assignees, but stop for approval before any issue is created downstream.",
      "enforcement_notes": "issue_requester approval_required access to Issue Preparation and Creation Governance should return approval_stop. Allow issue preparation preview with labels and assignees, but stop for approval before any issue is created downstream. Preview-only posture from github.issue.prepare; creation is not executed without approval."
    },
    {
      "id": "policy_permission_rule_2",
      "source_permission_id": "permission_rule_2",
      "actor_id": "pr_comment_requester",
      "principal_selector": {
        "claim": "actor_id",
        "equals": "pr_comment_requester"
      },
      "business_area": "pull_request_comment_governance",
      "business_area_label": "Pull Request Comment Governance",
      "service_ids": [
        "github-governance-service"
      ],
      "capability_ids": [
        "github.pr.comment.prepare"
      ],
      "required_scopes": [
        "github.pr.comment.prepare"
      ],
      "decision": "approval_required",
      "business_rule": "Allow pull-request comment preparation preview from review or release context, but stop for approval before posting any comment.",
      "enforcement_notes": "pr_comment_requester approval_required access to Pull Request Comment Governance should return approval_stop. Allow pull-request comment preparation preview from review or release context, but stop for approval before posting any comment. Preview-only posture from github.pr.comment.prepare; posting is not executed without approval."
    },
    {
      "id": "policy_permission_rule_3",
      "source_permission_id": "permission_rule_3",
      "actor_id": "workflow_requester",
      "principal_selector": {
        "claim": "actor_id",
        "equals": "workflow_requester"
      },
      "business_area": "workflow_dispatch_governance",
      "business_area_label": "Workflow Dispatch Governance",
      "service_ids": [
        "github-governance-service"
      ],
      "capability_ids": [
        "github.workflow.dispatch.request"
      ],
      "required_scopes": [
        "github.workflow.dispatch.request"
      ],
      "decision": "approval_required",
      "business_rule": "Allow a workflow dispatch request to be prepared for an allowlisted repository and ref, but require approval before dispatch. Restricted workflows require explicit grant.",
      "enforcement_notes": "workflow_requester approval_required access to Workflow Dispatch Governance should return approval_stop. Allow a workflow dispatch request to be prepared for an allowlisted repository and ref, but require approval before dispatch. Restricted workflows require explicit grant. Supported by github.workflow.dispatch.request and policy semantics for restricted workflows."
    },
    {
      "id": "policy_permission_rule_4",
      "source_permission_id": "permission_rule_4",
      "actor_id": "release_notes_drafter",
      "principal_selector": {
        "claim": "actor_id",
        "equals": "release_notes_drafter"
      },
      "business_area": "release_notes_drafting",
      "business_area_label": "Release Notes Drafting",
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
        "github.repo.search_context",
        "github.issue.prepare",
        "github.pr.comment.prepare",
        "github.workflow.dispatch.request",
        "github.release_notes.prepare"
      ],
      "decision": "allow_with_limits",
      "business_rule": "Allow draft release notes from bounded repository context only. Do not create or publish a release.",
      "enforcement_notes": "release_notes_drafter bounded access to Release Notes Drafting should return bounded_result. Allow draft release notes from bounded repository context only. Do not create or publish a release. Supported by github.release_notes.prepare and the draft-only posture."
    },
    {
      "id": "policy_permission_rule_5",
      "source_permission_id": "permission_rule_5",
      "actor_id": "repository_operator",
      "principal_selector": {
        "claim": "actor_id",
        "equals": "repository_operator"
      },
      "business_area": "governed_repository_policy_and_audit",
      "business_area_label": "Governed Repository Policy and Audit",
      "service_ids": [
        "github-governance-service"
      ],
      "capability_ids": [
        "github.repo.search_context",
        "github.workflow.dispatch.request"
      ],
      "required_scopes": [
        "github.repo.search_context",
        "github.workflow.dispatch.request"
      ],
      "decision": "deny",
      "business_rule": "Deny requests for secret exfiltration, raw file export, unbounded codebase dumps, or direct workflow bypass.",
      "enforcement_notes": "repository_operator denied access to Governed Repository Policy and Audit should return deny_request. Deny requests for secret exfiltration, raw file export, unbounded codebase dumps, or direct workflow bypass. Cross-cutting denial posture stated in policy semantics."
    },
    {
      "id": "policy_permission_rule_6",
      "source_permission_id": "permission_rule_6",
      "actor_id": "repository_operator",
      "principal_selector": {
        "claim": "actor_id",
        "equals": "repository_operator"
      },
      "business_area": "repository_context_access",
      "business_area_label": "Repository Context Access",
      "service_ids": [
        "github-governance-service"
      ],
      "capability_ids": [
        "github.repo.search_context"
      ],
      "required_scopes": [
        "github.repo.search_context"
      ],
      "decision": "clarify",
      "business_rule": "Stop and request clarification when repository context is missing or repository scope is not explicit.",
      "enforcement_notes": "repository_operator restricted access to Repository Context Access should return clarification_required. Stop and request clarification when repository context is missing or repository scope is not explicit. The source requires explicit repository scope and clarification on missing context."
    },
    {
      "id": "policy_permission_rule_7",
      "source_permission_id": "permission_rule_7",
      "actor_id": "pr_comment_requester",
      "principal_selector": {
        "claim": "actor_id",
        "equals": "pr_comment_requester"
      },
      "business_area": "pull_request_comment_governance",
      "business_area_label": "Pull Request Comment Governance",
      "service_ids": [
        "github-governance-service"
      ],
      "capability_ids": [
        "github.repo.search_context"
      ],
      "required_scopes": [
        "github.repo.search_context"
      ],
      "decision": "clarify",
      "business_rule": "Stop and request clarification when pull request context is missing.",
      "enforcement_notes": "pr_comment_requester restricted access to Pull Request Comment Governance should return clarification_required. Stop and request clarification when pull request context is missing. The source explicitly calls out missing pull request context as clarification_required."
    },
    {
      "id": "policy_permission_rule_8",
      "source_permission_id": "permission_rule_8",
      "actor_id": "workflow_requester",
      "principal_selector": {
        "claim": "actor_id",
        "equals": "workflow_requester"
      },
      "business_area": "workflow_dispatch_governance",
      "business_area_label": "Workflow Dispatch Governance",
      "service_ids": [
        "github-governance-service"
      ],
      "capability_ids": [
        "github.workflow.dispatch.request"
      ],
      "required_scopes": [
        "github.workflow.dispatch.request"
      ],
      "decision": "clarify",
      "business_rule": "Stop and request clarification when workflow context is missing.",
      "enforcement_notes": "workflow_requester restricted access to Workflow Dispatch Governance should return clarification_required. Stop and request clarification when workflow context is missing. The source explicitly calls out missing workflow context as clarification_required."
    },
    {
      "id": "policy_permission_rule_9",
      "source_permission_id": "permission_rule_9",
      "actor_id": "release_notes_drafter",
      "principal_selector": {
        "claim": "actor_id",
        "equals": "release_notes_drafter"
      },
      "business_area": "release_notes_drafting",
      "business_area_label": "Release Notes Drafting",
      "service_ids": [
        "github-governance-service"
      ],
      "capability_ids": [
        "github.release_notes.prepare"
      ],
      "required_scopes": [
        "github.release_notes.prepare"
      ],
      "decision": "clarify",
      "business_rule": "Stop and request clarification when release-note range context is missing.",
      "enforcement_notes": "release_notes_drafter restricted access to Release Notes Drafting should return clarification_required. Stop and request clarification when release-note range context is missing. The source explicitly calls out missing range context as clarification_required."
    }
  ],
  "authority": {
    "approval_expectation": "not_specified",
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
    "title": "Search Context",
    "summary": "Search bounded GitHub repository issues and pull requests without raw repository export",
    "kind": "atomic",
    "intent_type": "read_only",
    "operation_type": "read",
    "execution_posture": "read_only",
    "side_effect_level": "read",
    "implementation_fit": {
      "category": "custom_service_logic",
      "rationale": "ANIP can expose and govern this capability, but the service still needs domain/backend implementation logic."
    },
    "business_effects": {
      "produces": [
        "content.summary",
        "data.read"
      ],
      "does_not_produce": [
        "raw_data_export",
        "system.mutation"
      ]
    },
    "backend_operation": "github.api.search_repository_context",
    "path_template": "/github/repo/search-context",
    "output_shape": "bounded_repository_results_result",
    "subject_kind": "github_repository",
    "context_type": "repository_context_search",
    "output_intent": "bounded_repository_results",
    "minimum_scope": [
      "github.repo.search_context"
    ],
    "required_inputs": [
      {
        "input_name": "owner",
        "input_type": "string",
        "required": true,
        "summary": "GitHub repository owner or organization",
        "default_value": "",
        "semantic_type": "repo_owner",
        "clarification_hint": "Ask which repository owner to use",
        "entity_reference": true,
        "catalog_ref": "github.repository_catalog",
        "resolution": {
          "mode": "backend_resolved",
          "resolver_ref": "github.repository_catalog",
          "on_missing": "clarify",
          "on_ambiguous": "clarify",
          "on_unresolved": "clarify"
        }
      },
      {
        "input_name": "repo",
        "input_type": "string",
        "required": true,
        "summary": "GitHub repository name",
        "default_value": "",
        "semantic_type": "repo_name",
        "clarification_hint": "Ask which repository to use",
        "entity_reference": true,
        "catalog_ref": "github.repository_catalog",
        "resolution": {
          "mode": "backend_resolved",
          "resolver_ref": "github.repository_catalog",
          "on_missing": "clarify",
          "on_ambiguous": "clarify",
          "on_unresolved": "clarify"
        }
      },
      {
        "input_name": "query",
        "input_type": "string",
        "required": true,
        "summary": "Bounded issue and pull request search intent",
        "default_value": "",
        "semantic_type": "search_query",
        "clarification_hint": "Ask what repository context to search for",
        "resolution": {
          "mode": "clarify",
          "on_missing": "clarify",
          "on_ambiguous": "clarify",
          "on_unresolved": "clarify"
        }
      }
    ],
    "optional_inputs": [
      {
        "input_name": "state",
        "input_type": "string",
        "required": false,
        "summary": "Issue or pull request state filter",
        "default_value": "open",
        "allowed_values": [
          "open",
          "closed",
          "all"
        ],
        "semantic_type": "issue_state",
        "resolution": {
          "mode": "closed_values",
          "on_missing": "use_default",
          "on_ambiguous": "clarify",
          "on_unresolved": "clarify"
        }
      },
      {
        "input_name": "labels",
        "input_type": "array\u003cstring\u003e",
        "required": false,
        "summary": "Optional GitHub label filters",
        "default_value": "",
        "semantic_type": "label_filter",
        "entity_reference": true,
        "catalog_ref": "github.label_catalog",
        "resolution": {
          "mode": "explicit_only",
          "resolver_ref": "github.label_catalog",
          "on_missing": "omit",
          "on_ambiguous": "clarify",
          "on_unresolved": "clarify"
        }
      },
      {
        "input_name": "limit",
        "input_type": "integer",
        "required": false,
        "summary": "Maximum bounded result count",
        "default_value": "20",
        "semantic_type": "quantity_limit",
        "resolution": {
          "mode": "explicit_only",
          "on_missing": "use_default",
          "on_ambiguous": "clarify",
          "on_unresolved": "clarify"
        }
      },
      {
        "input_name": "backend_options",
        "input_type": "object",
        "required": false,
        "summary": "Bounded provider options only",
        "default_value": "",
        "semantic_type": "backend_options",
        "resolution": {
          "mode": "explicit_only",
          "on_missing": "omit",
          "on_ambiguous": "clarify",
          "on_unresolved": "clarify"
        }
      }
    ],
    "sample_parameters": {
      "backend_options": {},
      "labels": [],
      "limit": 20,
      "owner": "owner-value",
      "query": "query-value",
      "repo": "repo-value",
      "state": "open"
    },
    "backend_input_mode": "explicit",
    "derived_required_backend_inputs": [
      "owner",
      "repo",
      "query"
    ],
    "derived_optional_backend_inputs": [
      "state",
      "labels",
      "limit",
      "backend_options"
    ],
    "explicit_required_backend_inputs": [
      "owner",
      "repo",
      "query"
    ],
    "explicit_optional_backend_inputs": [
      "state",
      "labels",
      "limit",
      "backend_options"
    ],
    "backend_bindings": [
      {
        "backend_kind": "native_api",
        "connection_ref": "github-fronting-showcase-0-2-0-developer-tools-api",
        "raw_operation_refs": [
          "github.api.search_repository_context"
        ],
        "backend_input_mode": "explicit",
        "derived_required_backend_inputs": [
          "owner",
          "repo",
          "query"
        ],
        "derived_optional_backend_inputs": [
          "state",
          "labels",
          "limit",
          "backend_options"
        ],
        "explicit_required_backend_inputs": [
          "owner",
          "repo",
          "query"
        ],
        "explicit_optional_backend_inputs": [
          "state",
          "labels",
          "limit",
          "backend_options"
        ],
        "status": "ready",
        "status_detail": "Materialized from reviewed developer capability evidence."
      }
    ],
    "governance": {
      "approval_rule_refs": [],
      "denial_rule_refs": [
        "deny.raw_backend_bypass"
      ],
      "clarification_rule_refs": [
        "clarify.owner",
        "clarify.repo",
        "clarify.query"
      ],
      "audit_required": true
    },
    "outbound_controls": {
      "raw_backend_not_agent_visible": true,
      "redaction_required": true
    }
  },
  {
    "service_id": "github-governance-service",
    "service_name": "GitHub Governance Service",
    "capability_id": "github.issue.prepare",
    "title": "Prepare",
    "summary": "Prepare a GitHub issue preview before any issue is created",
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
    "implementation_fit": {
      "category": "custom_service_logic",
      "rationale": "ANIP can expose and govern this capability, but the service still needs domain/backend implementation logic."
    },
    "business_effects": {
      "produces": [
        "approval.request",
        "system.preview_mutation",
        "content.draft"
      ],
      "does_not_produce": [
        "approval.execute",
        "system.mutation",
        "raw_data_export"
      ]
    },
    "backend_operation": "github.api.prepare_issue",
    "path_template": "/github/issue/prepare",
    "output_shape": "issue_creation_preview_result",
    "subject_kind": "github_issue",
    "context_type": "issue_preparation",
    "output_intent": "issue_creation_preview",
    "minimum_scope": [
      "github.issue.prepare"
    ],
    "required_inputs": [
      {
        "input_name": "owner",
        "input_type": "string",
        "required": true,
        "summary": "GitHub repository owner or organization",
        "default_value": "",
        "semantic_type": "repo_owner",
        "clarification_hint": "Ask which repository owner to use",
        "entity_reference": true,
        "catalog_ref": "github.repository_catalog",
        "resolution": {
          "mode": "backend_resolved",
          "resolver_ref": "github.repository_catalog",
          "on_missing": "clarify",
          "on_ambiguous": "clarify",
          "on_unresolved": "clarify"
        }
      },
      {
        "input_name": "repo",
        "input_type": "string",
        "required": true,
        "summary": "GitHub repository name",
        "default_value": "",
        "semantic_type": "repo_name",
        "clarification_hint": "Ask which repository to use",
        "entity_reference": true,
        "catalog_ref": "github.repository_catalog",
        "resolution": {
          "mode": "backend_resolved",
          "resolver_ref": "github.repository_catalog",
          "on_missing": "clarify",
          "on_ambiguous": "clarify",
          "on_unresolved": "clarify"
        }
      },
      {
        "input_name": "title",
        "input_type": "string",
        "required": true,
        "summary": "Issue title",
        "default_value": "",
        "semantic_type": "issue_title",
        "clarification_hint": "Ask for the issue title",
        "resolution": {
          "mode": "clarify",
          "on_missing": "clarify",
          "on_ambiguous": "clarify",
          "on_unresolved": "clarify"
        }
      },
      {
        "input_name": "body",
        "input_type": "string",
        "required": true,
        "summary": "Issue body",
        "default_value": "",
        "semantic_type": "issue_body",
        "clarification_hint": "Ask for the issue body",
        "resolution": {
          "mode": "clarify",
          "on_missing": "clarify",
          "on_ambiguous": "clarify",
          "on_unresolved": "clarify"
        }
      }
    ],
    "optional_inputs": [
      {
        "input_name": "labels",
        "input_type": "array\u003cstring\u003e",
        "required": false,
        "summary": "Optional labels for the issue preview",
        "default_value": "",
        "semantic_type": "label_filter",
        "entity_reference": true,
        "catalog_ref": "github.label_catalog",
        "resolution": {
          "mode": "backend_resolved",
          "resolver_ref": "github.label_catalog",
          "on_missing": "omit",
          "on_ambiguous": "clarify",
          "on_unresolved": "clarify"
        }
      },
      {
        "input_name": "assignees",
        "input_type": "array\u003cstring\u003e",
        "required": false,
        "summary": "Optional assignees for the issue preview",
        "default_value": "",
        "semantic_type": "user_reference",
        "entity_reference": true,
        "catalog_ref": "github.user_catalog",
        "resolution": {
          "mode": "backend_resolved",
          "resolver_ref": "github.user_catalog",
          "on_missing": "omit",
          "on_ambiguous": "clarify",
          "on_unresolved": "clarify"
        }
      },
      {
        "input_name": "milestone",
        "input_type": "string",
        "required": false,
        "summary": "Optional milestone for the issue preview",
        "default_value": "",
        "semantic_type": "milestone_reference",
        "entity_reference": true,
        "catalog_ref": "github.milestone_catalog",
        "resolution": {
          "mode": "backend_resolved",
          "resolver_ref": "github.milestone_catalog",
          "on_missing": "omit",
          "on_ambiguous": "clarify",
          "on_unresolved": "clarify"
        }
      },
      {
        "input_name": "backend_options",
        "input_type": "object",
        "required": false,
        "summary": "Bounded provider options only",
        "default_value": "",
        "semantic_type": "backend_options",
        "resolution": {
          "mode": "explicit_only",
          "on_missing": "omit",
          "on_ambiguous": "clarify",
          "on_unresolved": "clarify"
        }
      }
    ],
    "sample_parameters": {
      "assignees": [],
      "backend_options": {},
      "body": "body-value",
      "labels": [],
      "milestone": "milestone-value",
      "owner": "owner-value",
      "repo": "repo-value",
      "title": "title-value"
    },
    "backend_input_mode": "explicit",
    "derived_required_backend_inputs": [
      "owner",
      "repo",
      "title",
      "body"
    ],
    "derived_optional_backend_inputs": [
      "labels",
      "assignees",
      "milestone",
      "backend_options"
    ],
    "explicit_required_backend_inputs": [
      "owner",
      "repo",
      "title",
      "body"
    ],
    "explicit_optional_backend_inputs": [
      "labels",
      "assignees",
      "milestone",
      "backend_options"
    ],
    "backend_bindings": [
      {
        "backend_kind": "native_api",
        "connection_ref": "github-fronting-showcase-0-2-0-developer-tools-api",
        "raw_operation_refs": [
          "github.api.prepare_issue"
        ],
        "backend_input_mode": "explicit",
        "derived_required_backend_inputs": [
          "owner",
          "repo",
          "title",
          "body"
        ],
        "derived_optional_backend_inputs": [
          "labels",
          "assignees",
          "milestone",
          "backend_options"
        ],
        "explicit_required_backend_inputs": [
          "owner",
          "repo",
          "title",
          "body"
        ],
        "explicit_optional_backend_inputs": [
          "labels",
          "assignees",
          "milestone",
          "backend_options"
        ],
        "status": "ready",
        "status_detail": "Materialized from reviewed developer capability evidence."
      }
    ],
    "governance": {
      "approval_rule_refs": [
        "approval.github-issue-prepare"
      ],
      "denial_rule_refs": [
        "deny.raw_backend_bypass"
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
      "raw_backend_not_agent_visible": true,
      "redaction_required": true
    }
  },
  {
    "service_id": "github-governance-service",
    "service_name": "GitHub Governance Service",
    "capability_id": "github.pr.comment.prepare",
    "title": "Prepare",
    "summary": "Prepare a pull request comment preview without posting it",
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
    "implementation_fit": {
      "category": "custom_service_logic",
      "rationale": "ANIP can expose and govern this capability, but the service still needs domain/backend implementation logic."
    },
    "business_effects": {
      "produces": [
        "approval.request",
        "system.preview_mutation",
        "content.draft"
      ],
      "does_not_produce": [
        "approval.execute",
        "system.mutation",
        "raw_data_export"
      ]
    },
    "backend_operation": "github.api.prepare_pull_request_comment",
    "path_template": "/github/pr/comment/prepare",
    "output_shape": "comment_preview_result",
    "subject_kind": "github_pull_request",
    "context_type": "pull_request_comment_preparation",
    "output_intent": "comment_preview",
    "minimum_scope": [
      "github.pr.comment.prepare"
    ],
    "required_inputs": [
      {
        "input_name": "owner",
        "input_type": "string",
        "required": true,
        "summary": "GitHub repository owner or organization",
        "default_value": "",
        "semantic_type": "repo_owner",
        "clarification_hint": "Ask which repository owner to use",
        "entity_reference": true,
        "catalog_ref": "github.repository_catalog",
        "resolution": {
          "mode": "backend_resolved",
          "resolver_ref": "github.repository_catalog",
          "on_missing": "clarify",
          "on_ambiguous": "clarify",
          "on_unresolved": "clarify"
        }
      },
      {
        "input_name": "repo",
        "input_type": "string",
        "required": true,
        "summary": "GitHub repository name",
        "default_value": "",
        "semantic_type": "repo_name",
        "clarification_hint": "Ask which repository to use",
        "entity_reference": true,
        "catalog_ref": "github.repository_catalog",
        "resolution": {
          "mode": "backend_resolved",
          "resolver_ref": "github.repository_catalog",
          "on_missing": "clarify",
          "on_ambiguous": "clarify",
          "on_unresolved": "clarify"
        }
      },
      {
        "input_name": "pull_number",
        "input_type": "integer",
        "required": true,
        "summary": "Pull request number",
        "default_value": "",
        "semantic_type": "pull_request_ref",
        "clarification_hint": "Ask which pull request to comment on",
        "entity_reference": true,
        "catalog_ref": "github.pull_request_catalog",
        "resolution": {
          "mode": "backend_resolved",
          "resolver_ref": "github.pull_request_catalog",
          "on_missing": "clarify",
          "on_ambiguous": "clarify",
          "on_unresolved": "clarify"
        }
      },
      {
        "input_name": "comment_purpose",
        "input_type": "string",
        "required": true,
        "summary": "Purpose of the prepared pull request comment",
        "default_value": "",
        "allowed_values": [
          "review_note",
          "release_note",
          "triage_update"
        ],
        "semantic_type": "comment_purpose",
        "clarification_hint": "Ask what kind of comment to prepare",
        "resolution": {
          "mode": "closed_values",
          "on_missing": "clarify",
          "on_ambiguous": "clarify",
          "on_unresolved": "clarify"
        }
      },
      {
        "input_name": "context",
        "input_type": "string",
        "required": true,
        "summary": "Context to use for the prepared comment",
        "default_value": "",
        "semantic_type": "comment_context",
        "clarification_hint": "Ask for the comment context",
        "resolution": {
          "mode": "clarify",
          "on_missing": "clarify",
          "on_ambiguous": "clarify",
          "on_unresolved": "clarify"
        }
      }
    ],
    "optional_inputs": [
      {
        "input_name": "visibility",
        "input_type": "string",
        "required": false,
        "summary": "Comment visibility posture",
        "default_value": "internal",
        "allowed_values": [
          "internal",
          "public"
        ],
        "semantic_type": "visibility",
        "resolution": {
          "mode": "closed_values",
          "on_missing": "use_default",
          "on_ambiguous": "clarify",
          "on_unresolved": "clarify"
        }
      },
      {
        "input_name": "backend_options",
        "input_type": "object",
        "required": false,
        "summary": "Bounded provider options only",
        "default_value": "",
        "semantic_type": "backend_options",
        "resolution": {
          "mode": "explicit_only",
          "on_missing": "omit",
          "on_ambiguous": "clarify",
          "on_unresolved": "clarify"
        }
      }
    ],
    "sample_parameters": {
      "backend_options": {},
      "comment_purpose": "review_note",
      "context": "context-value",
      "owner": "owner-value",
      "pull_number": 1,
      "repo": "repo-value",
      "visibility": "internal"
    },
    "backend_input_mode": "explicit",
    "derived_required_backend_inputs": [
      "owner",
      "repo",
      "pull_number",
      "comment_purpose",
      "context"
    ],
    "derived_optional_backend_inputs": [
      "visibility",
      "backend_options"
    ],
    "explicit_required_backend_inputs": [
      "owner",
      "repo",
      "pull_number",
      "comment_purpose",
      "context"
    ],
    "explicit_optional_backend_inputs": [
      "visibility",
      "backend_options"
    ],
    "backend_bindings": [
      {
        "backend_kind": "native_api",
        "connection_ref": "github-fronting-showcase-0-2-0-developer-tools-api",
        "raw_operation_refs": [
          "github.api.prepare_pull_request_comment"
        ],
        "backend_input_mode": "explicit",
        "derived_required_backend_inputs": [
          "owner",
          "repo",
          "pull_number",
          "comment_purpose",
          "context"
        ],
        "derived_optional_backend_inputs": [
          "visibility",
          "backend_options"
        ],
        "explicit_required_backend_inputs": [
          "owner",
          "repo",
          "pull_number",
          "comment_purpose",
          "context"
        ],
        "explicit_optional_backend_inputs": [
          "visibility",
          "backend_options"
        ],
        "status": "ready",
        "status_detail": "Materialized from reviewed developer capability evidence."
      }
    ],
    "governance": {
      "approval_rule_refs": [
        "approval.github-pr-comment-prepare"
      ],
      "denial_rule_refs": [
        "deny.raw_backend_bypass"
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
      "raw_backend_not_agent_visible": true,
      "redaction_required": true
    }
  },
  {
    "service_id": "github-governance-service",
    "service_name": "GitHub Governance Service",
    "capability_id": "github.workflow.dispatch.request",
    "title": "Request",
    "summary": "Prepare a governed workflow dispatch request and stop for approval",
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
    "implementation_fit": {
      "category": "custom_service_logic",
      "rationale": "ANIP can expose and govern this capability, but the service still needs domain/backend implementation logic."
    },
    "business_effects": {
      "produces": [
        "approval.request",
        "system.preview_mutation",
        "content.draft"
      ],
      "does_not_produce": [
        "approval.execute",
        "system.mutation",
        "raw_data_export"
      ]
    },
    "backend_operation": "github.api.request_workflow_dispatch",
    "path_template": "/github/workflow/dispatch/request",
    "output_shape": "workflow_dispatch_preview_result",
    "subject_kind": "github_workflow",
    "context_type": "workflow_dispatch",
    "output_intent": "workflow_dispatch_preview",
    "minimum_scope": [
      "github.workflow.dispatch.request"
    ],
    "required_inputs": [
      {
        "input_name": "owner",
        "input_type": "string",
        "required": true,
        "summary": "GitHub repository owner or organization",
        "default_value": "",
        "semantic_type": "repo_owner",
        "clarification_hint": "Ask which repository owner to use",
        "entity_reference": true,
        "catalog_ref": "github.repository_catalog",
        "resolution": {
          "mode": "backend_resolved",
          "resolver_ref": "github.repository_catalog",
          "on_missing": "clarify",
          "on_ambiguous": "clarify",
          "on_unresolved": "clarify"
        }
      },
      {
        "input_name": "repo",
        "input_type": "string",
        "required": true,
        "summary": "GitHub repository name",
        "default_value": "",
        "semantic_type": "repo_name",
        "clarification_hint": "Ask which repository to use",
        "entity_reference": true,
        "catalog_ref": "github.repository_catalog",
        "resolution": {
          "mode": "backend_resolved",
          "resolver_ref": "github.repository_catalog",
          "on_missing": "clarify",
          "on_ambiguous": "clarify",
          "on_unresolved": "clarify"
        }
      },
      {
        "input_name": "workflow_id",
        "input_type": "string",
        "required": true,
        "summary": "Workflow id or filename",
        "default_value": "",
        "semantic_type": "workflow_ref",
        "clarification_hint": "Ask which workflow to request",
        "entity_reference": true,
        "catalog_ref": "github.workflow_catalog",
        "resolution": {
          "mode": "backend_resolved",
          "resolver_ref": "github.workflow_catalog",
          "on_missing": "clarify",
          "on_ambiguous": "clarify",
          "on_unresolved": "clarify"
        }
      },
      {
        "input_name": "ref",
        "input_type": "string",
        "required": true,
        "summary": "Branch or tag ref",
        "default_value": "",
        "semantic_type": "git_ref",
        "clarification_hint": "Ask which branch or tag to dispatch",
        "entity_reference": true,
        "resolution": {
          "mode": "explicit_only",
          "on_missing": "clarify",
          "on_ambiguous": "clarify",
          "on_unresolved": "clarify"
        }
      }
    ],
    "optional_inputs": [
      {
        "input_name": "inputs",
        "input_type": "object",
        "required": false,
        "summary": "Optional workflow input object",
        "default_value": "",
        "semantic_type": "workflow_inputs",
        "resolution": {
          "mode": "explicit_only",
          "on_missing": "omit",
          "on_ambiguous": "clarify",
          "on_unresolved": "clarify"
        }
      },
      {
        "input_name": "backend_options",
        "input_type": "object",
        "required": false,
        "summary": "Bounded provider options only",
        "default_value": "",
        "semantic_type": "backend_options",
        "resolution": {
          "mode": "explicit_only",
          "on_missing": "omit",
          "on_ambiguous": "clarify",
          "on_unresolved": "clarify"
        }
      }
    ],
    "sample_parameters": {
      "backend_options": {},
      "inputs": {},
      "owner": "owner-value",
      "ref": "ref-value",
      "repo": "repo-value",
      "workflow_id": "workflow_id-value"
    },
    "backend_input_mode": "explicit",
    "derived_required_backend_inputs": [
      "owner",
      "repo",
      "workflow_id",
      "ref"
    ],
    "derived_optional_backend_inputs": [
      "inputs",
      "backend_options"
    ],
    "explicit_required_backend_inputs": [
      "owner",
      "repo",
      "workflow_id",
      "ref"
    ],
    "explicit_optional_backend_inputs": [
      "inputs",
      "backend_options"
    ],
    "backend_bindings": [
      {
        "backend_kind": "native_api",
        "connection_ref": "github-fronting-showcase-0-2-0-developer-tools-api",
        "raw_operation_refs": [
          "github.api.request_workflow_dispatch"
        ],
        "backend_input_mode": "explicit",
        "derived_required_backend_inputs": [
          "owner",
          "repo",
          "workflow_id",
          "ref"
        ],
        "derived_optional_backend_inputs": [
          "inputs",
          "backend_options"
        ],
        "explicit_required_backend_inputs": [
          "owner",
          "repo",
          "workflow_id",
          "ref"
        ],
        "explicit_optional_backend_inputs": [
          "inputs",
          "backend_options"
        ],
        "status": "ready",
        "status_detail": "Materialized from reviewed developer capability evidence."
      }
    ],
    "governance": {
      "approval_rule_refs": [
        "approval.github-workflow-dispatch-request"
      ],
      "denial_rule_refs": [
        "deny.raw_backend_bypass"
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
      "raw_backend_not_agent_visible": true,
      "redaction_required": true
    }
  },
  {
    "service_id": "github-governance-service",
    "service_name": "GitHub Governance Service",
    "capability_id": "github.release_notes.prepare",
    "title": "Prepare",
    "summary": "Prepare bounded release notes without creating or publishing a release",
    "kind": "atomic",
    "intent_type": "read_only",
    "operation_type": "read",
    "execution_posture": "read_only",
    "side_effect_level": "read",
    "implementation_fit": {
      "category": "custom_service_logic",
      "rationale": "ANIP can expose and govern this capability, but the service still needs domain/backend implementation logic."
    },
    "business_effects": {
      "produces": [
        "content.draft",
        "data.aggregate"
      ],
      "does_not_produce": [
        "external_dispatch",
        "system.mutation",
        "raw_data_export"
      ]
    },
    "backend_operation": "github.api.prepare_release_notes",
    "path_template": "/github/release-notes/prepare",
    "output_shape": "release_notes_draft_result",
    "subject_kind": "github_release",
    "context_type": "release_notes_preparation",
    "output_intent": "release_notes_draft",
    "minimum_scope": [
      "github.release_notes.prepare"
    ],
    "required_inputs": [
      {
        "input_name": "owner",
        "input_type": "string",
        "required": true,
        "summary": "GitHub repository owner or organization",
        "default_value": "",
        "semantic_type": "repo_owner",
        "clarification_hint": "Ask which repository owner to use",
        "entity_reference": true,
        "catalog_ref": "github.repository_catalog",
        "resolution": {
          "mode": "backend_resolved",
          "resolver_ref": "github.repository_catalog",
          "on_missing": "clarify",
          "on_ambiguous": "clarify",
          "on_unresolved": "clarify"
        }
      },
      {
        "input_name": "repo",
        "input_type": "string",
        "required": true,
        "summary": "GitHub repository name",
        "default_value": "",
        "semantic_type": "repo_name",
        "clarification_hint": "Ask which repository to use",
        "entity_reference": true,
        "catalog_ref": "github.repository_catalog",
        "resolution": {
          "mode": "backend_resolved",
          "resolver_ref": "github.repository_catalog",
          "on_missing": "clarify",
          "on_ambiguous": "clarify",
          "on_unresolved": "clarify"
        }
      },
      {
        "input_name": "range",
        "input_type": "string",
        "required": true,
        "summary": "Tag range or comparison range",
        "default_value": "",
        "semantic_type": "release_range",
        "clarification_hint": "Ask which release range to summarize",
        "resolution": {
          "mode": "clarify",
          "on_missing": "clarify",
          "on_ambiguous": "clarify",
          "on_unresolved": "clarify"
        }
      }
    ],
    "optional_inputs": [
      {
        "input_name": "audience",
        "input_type": "string",
        "required": false,
        "summary": "Release note audience",
        "default_value": "engineering",
        "allowed_values": [
          "engineering",
          "customer",
          "internal"
        ],
        "semantic_type": "audience",
        "resolution": {
          "mode": "closed_values",
          "on_missing": "use_default",
          "on_ambiguous": "clarify",
          "on_unresolved": "clarify"
        }
      },
      {
        "input_name": "include_prs",
        "input_type": "boolean",
        "required": false,
        "summary": "Whether to include pull request details",
        "default_value": "true",
        "semantic_type": "include_prs",
        "resolution": {
          "mode": "explicit_only",
          "on_missing": "use_default",
          "on_ambiguous": "clarify",
          "on_unresolved": "clarify"
        }
      },
      {
        "input_name": "backend_options",
        "input_type": "object",
        "required": false,
        "summary": "Bounded provider options only",
        "default_value": "",
        "semantic_type": "backend_options",
        "resolution": {
          "mode": "explicit_only",
          "on_missing": "omit",
          "on_ambiguous": "clarify",
          "on_unresolved": "clarify"
        }
      }
    ],
    "sample_parameters": {
      "audience": "engineering",
      "backend_options": {},
      "include_prs": true,
      "owner": "owner-value",
      "range": "range-value",
      "repo": "repo-value"
    },
    "backend_input_mode": "explicit",
    "derived_required_backend_inputs": [
      "owner",
      "repo",
      "range"
    ],
    "derived_optional_backend_inputs": [
      "audience",
      "include_prs",
      "backend_options"
    ],
    "explicit_required_backend_inputs": [
      "owner",
      "repo",
      "range"
    ],
    "explicit_optional_backend_inputs": [
      "audience",
      "include_prs",
      "backend_options"
    ],
    "backend_bindings": [
      {
        "backend_kind": "native_api",
        "connection_ref": "github-fronting-showcase-0-2-0-developer-tools-api",
        "raw_operation_refs": [
          "github.api.prepare_release_notes"
        ],
        "backend_input_mode": "explicit",
        "derived_required_backend_inputs": [
          "owner",
          "repo",
          "range"
        ],
        "derived_optional_backend_inputs": [
          "audience",
          "include_prs",
          "backend_options"
        ],
        "explicit_required_backend_inputs": [
          "owner",
          "repo",
          "range"
        ],
        "explicit_optional_backend_inputs": [
          "audience",
          "include_prs",
          "backend_options"
        ],
        "status": "ready",
        "status_detail": "Materialized from reviewed developer capability evidence."
      }
    ],
    "governance": {
      "approval_rule_refs": [],
      "denial_rule_refs": [
        "deny.raw_backend_bypass"
      ],
      "clarification_rule_refs": [
        "clarify.owner",
        "clarify.repo",
        "clarify.range"
      ],
      "audit_required": true
    },
    "outbound_controls": {
      "raw_backend_not_agent_visible": true,
      "redaction_required": true
    }
  }
]
''')
