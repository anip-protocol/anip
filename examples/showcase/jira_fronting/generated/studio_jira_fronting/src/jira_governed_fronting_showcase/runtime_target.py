"""Generated runtime target metadata."""
from __future__ import annotations

import json

RUNTIME_TARGET = json.loads(r'''{
  "system_name": "Jira Governed Fronting Showcase",
  "domain_name": "jira",
  "delivery_model": "governed_integration_fronting",
  "architecture_shape": "single_service",
  "protocols": [
    "https",
    "mcp"
  ],
  "services": [
    {
      "service_id": "jira-governance-service",
      "service_name": "Jira Governance Service",
      "source_role": "governed_integration_fronting",
      "source_capabilities": [
        "jira.backlog.search",
        "jira.bug.prepare",
        "jira.story.prepare",
        "jira.transition.request",
        "jira.comment.prepare"
      ],
      "formalized_capability_ids": [
        "jira.backlog.search",
        "jira.bug.prepare",
        "jira.story.prepare",
        "jira.transition.request",
        "jira.comment.prepare"
      ],
      "owned_concept_ids": [
        "jira_issue",
        "jira_project",
        "jira_transition"
      ]
    }
  ],
  "policy_bindings": [
    {
      "id": "jira_triage_user_policy",
      "source_permission_id": "jira_triage_user_access",
      "actor_id": "triage_user",
      "principal_selector": {
        "claim": "actor_id",
        "equals": "triage_user"
      },
      "business_area": "jira_triage",
      "business_area_label": "Jira Triage",
      "service_ids": [
        "jira-governance-service"
      ],
      "capability_ids": [
        "jira.backlog.search",
        "jira.bug.prepare",
        "jira.story.prepare",
        "jira.transition.request",
        "jira.comment.prepare"
      ],
      "required_scopes": [
        "jira.read",
        "jira.write.prepare",
        "jira.transition.request",
        "jira.comment.prepare"
      ],
      "decision": "allow_with_limits",
      "business_rule": "Allow only declared governed Jira capabilities; write-like actions stop at preview or approval.",
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
    "service_id": "jira-governance-service",
    "service_name": "Jira Governance Service",
    "capability_id": "jira.backlog.search",
    "title": "Search Team Backlog",
    "summary": "Search Jira issues in an allowed project with bounded query and result limits.",
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
        "Change system state",
        "Export raw data"
      ]
    },
    "backend_operation": "search_team_backlog",
    "path_template": "/jira/backlog/search",
    "output_shape": "bounded_issue_results",
    "subject_kind": "jira_issue",
    "context_type": "backlog_search",
    "output_intent": "bounded_issue_results",
    "minimum_scope": [
      "jira.read"
    ],
    "required_inputs": [
      {
        "input_name": "project_key",
        "input_type": "string",
        "required": true,
        "summary": "Allowed Jira project key.",
        "default_value": "",
        "clarification_hint": "Ask for project_key when it is missing or ambiguous.",
        "entity_reference": true
      },
      {
        "input_name": "query",
        "input_type": "string",
        "required": true,
        "summary": "Bounded issue search query.",
        "default_value": "",
        "clarification_hint": "Ask for query when it is missing or ambiguous."
      }
    ],
    "optional_inputs": [
      {
        "input_name": "limit",
        "input_type": "integer",
        "required": false,
        "summary": "Maximum issues to return.",
        "default_value": "25",
        "clarification_hint": "Ask for limit when it is missing or ambiguous."
      }
    ],
    "sample_parameters": {
      "limit": 25,
      "project_key": "project_key-value",
      "query": "query-value"
    },
    "backend_input_mode": "explicit",
    "derived_required_backend_inputs": [],
    "derived_optional_backend_inputs": [],
    "explicit_required_backend_inputs": [
      "project_key",
      "query"
    ],
    "explicit_optional_backend_inputs": [
      "limit"
    ],
    "backend_bindings": [
      {
        "backend_kind": "native_api",
        "connection_ref": "jira_rest_api",
        "raw_operation_refs": [
          "jira.rest.search_team_backlog"
        ],
        "backend_input_mode": "explicit",
        "explicit_required_backend_inputs": [
          "project_key",
          "query"
        ],
        "explicit_optional_backend_inputs": [
          "limit"
        ],
        "matched_discovery_record_ids": [
          "jira-rest-search_team_backlog"
        ],
        "status": "ready",
        "status_detail": "Native Jira REST implementation seam."
      },
      {
        "backend_kind": "mcp",
        "connection_ref": "atlassian_mcp",
        "raw_operation_refs": [
          "atlassian.mcp.search_team_backlog"
        ],
        "backend_input_mode": "explicit",
        "explicit_required_backend_inputs": [
          "project_key",
          "query"
        ],
        "explicit_optional_backend_inputs": [
          "limit"
        ],
        "matched_discovery_record_ids": [
          "atlassian-mcp-search_team_backlog"
        ],
        "status": "candidate",
        "status_detail": "Alternative MCP-backed adapter realization."
      }
    ],
    "governance": {
      "approval_rule_refs": [],
      "denial_rule_refs": [
        "deny.raw_export",
        "deny.unapproved_mutation"
      ],
      "clarification_rule_refs": [
        "clarify.project_key",
        "clarify.query"
      ],
      "audit_required": true
    },
    "outbound_controls": {
      "block_unbounded_payloads": true,
      "redact_sensitive_values": true
    }
  },
  {
    "service_id": "jira-governance-service",
    "service_name": "Jira Governance Service",
    "capability_id": "jira.bug.prepare",
    "title": "Prepare Bug Ticket",
    "summary": "Prepare a Jira bug ticket preview from a bounded incident or defect summary without creating it.",
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
        "Change system state",
        "Create issue"
      ]
    },
    "backend_operation": "prepare_bug_ticket",
    "path_template": "/jira/bugs/preview",
    "output_shape": "issue_creation_preview",
    "subject_kind": "jira_issue",
    "context_type": "ticket_preparation",
    "output_intent": "issue_creation_preview",
    "minimum_scope": [
      "jira.write.prepare"
    ],
    "required_inputs": [
      {
        "input_name": "project_key",
        "input_type": "string",
        "required": true,
        "summary": "Allowed Jira project key.",
        "default_value": "",
        "clarification_hint": "Ask for project_key when it is missing or ambiguous.",
        "entity_reference": true
      },
      {
        "input_name": "summary",
        "input_type": "string",
        "required": true,
        "summary": "Issue summary.",
        "default_value": "",
        "clarification_hint": "Ask for summary when it is missing or ambiguous."
      },
      {
        "input_name": "description",
        "input_type": "string",
        "required": true,
        "summary": "Issue description.",
        "default_value": "",
        "clarification_hint": "Ask for description when it is missing or ambiguous."
      },
      {
        "input_name": "severity",
        "input_type": "string",
        "required": true,
        "summary": "Business severity.",
        "default_value": "",
        "allowed_values": [
          "sev1",
          "sev2",
          "sev3",
          "sev4"
        ],
        "clarification_hint": "Ask for severity when it is missing or ambiguous."
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
      }
    ],
    "sample_parameters": {
      "description": "description-value",
      "labels": [],
      "project_key": "project_key-value",
      "severity": "sev1",
      "summary": "summary-value"
    },
    "backend_input_mode": "explicit",
    "derived_required_backend_inputs": [],
    "derived_optional_backend_inputs": [],
    "explicit_required_backend_inputs": [
      "project_key",
      "summary",
      "description",
      "severity"
    ],
    "explicit_optional_backend_inputs": [
      "labels"
    ],
    "backend_bindings": [
      {
        "backend_kind": "native_api",
        "connection_ref": "jira_rest_api",
        "raw_operation_refs": [
          "jira.rest.prepare_bug_ticket"
        ],
        "backend_input_mode": "explicit",
        "explicit_required_backend_inputs": [
          "project_key",
          "summary",
          "description",
          "severity"
        ],
        "explicit_optional_backend_inputs": [
          "labels"
        ],
        "matched_discovery_record_ids": [
          "jira-rest-prepare_bug_ticket"
        ],
        "status": "ready",
        "status_detail": "Native Jira REST implementation seam."
      },
      {
        "backend_kind": "mcp",
        "connection_ref": "atlassian_mcp",
        "raw_operation_refs": [
          "atlassian.mcp.prepare_bug_ticket"
        ],
        "backend_input_mode": "explicit",
        "explicit_required_backend_inputs": [
          "project_key",
          "summary",
          "description",
          "severity"
        ],
        "explicit_optional_backend_inputs": [
          "labels"
        ],
        "matched_discovery_record_ids": [
          "atlassian-mcp-prepare_bug_ticket"
        ],
        "status": "candidate",
        "status_detail": "Alternative MCP-backed adapter realization."
      }
    ],
    "governance": {
      "approval_rule_refs": [
        "approval.write_preview_required"
      ],
      "denial_rule_refs": [
        "deny.raw_export",
        "deny.unapproved_mutation"
      ],
      "clarification_rule_refs": [
        "clarify.project_key",
        "clarify.summary",
        "clarify.description",
        "clarify.severity"
      ],
      "audit_required": true
    },
    "outbound_controls": {
      "block_unbounded_payloads": true,
      "redact_sensitive_values": true
    }
  },
  {
    "service_id": "jira-governance-service",
    "service_name": "Jira Governance Service",
    "capability_id": "jira.story.prepare",
    "title": "Prepare Story Ticket",
    "summary": "Prepare a Jira story preview with acceptance criteria before any issue is created.",
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
        "Change system state",
        "Create issue"
      ]
    },
    "backend_operation": "prepare_story_ticket",
    "path_template": "/jira/stories/preview",
    "output_shape": "issue_creation_preview",
    "subject_kind": "jira_issue",
    "context_type": "ticket_preparation",
    "output_intent": "issue_creation_preview",
    "minimum_scope": [
      "jira.write.prepare"
    ],
    "required_inputs": [
      {
        "input_name": "project_key",
        "input_type": "string",
        "required": true,
        "summary": "Allowed Jira project key.",
        "default_value": "",
        "clarification_hint": "Ask for project_key when it is missing or ambiguous.",
        "entity_reference": true
      },
      {
        "input_name": "summary",
        "input_type": "string",
        "required": true,
        "summary": "Story summary.",
        "default_value": "",
        "clarification_hint": "Ask for summary when it is missing or ambiguous."
      },
      {
        "input_name": "acceptance_criteria",
        "input_type": "array\u003cstring\u003e",
        "required": true,
        "summary": "Acceptance criteria to include.",
        "default_value": "",
        "clarification_hint": "Ask for acceptance_criteria when it is missing or ambiguous."
      }
    ],
    "optional_inputs": [
      {
        "input_name": "priority",
        "input_type": "string",
        "required": false,
        "summary": "Business priority.",
        "default_value": "",
        "allowed_values": [
          "low",
          "medium",
          "high"
        ],
        "clarification_hint": "Ask for priority when it is missing or ambiguous."
      }
    ],
    "sample_parameters": {
      "acceptance_criteria": [],
      "priority": "low",
      "project_key": "project_key-value",
      "summary": "summary-value"
    },
    "backend_input_mode": "explicit",
    "derived_required_backend_inputs": [],
    "derived_optional_backend_inputs": [],
    "explicit_required_backend_inputs": [
      "project_key",
      "summary",
      "acceptance_criteria"
    ],
    "explicit_optional_backend_inputs": [
      "priority"
    ],
    "backend_bindings": [
      {
        "backend_kind": "native_api",
        "connection_ref": "jira_rest_api",
        "raw_operation_refs": [
          "jira.rest.prepare_story_ticket"
        ],
        "backend_input_mode": "explicit",
        "explicit_required_backend_inputs": [
          "project_key",
          "summary",
          "acceptance_criteria"
        ],
        "explicit_optional_backend_inputs": [
          "priority"
        ],
        "matched_discovery_record_ids": [
          "jira-rest-prepare_story_ticket"
        ],
        "status": "ready",
        "status_detail": "Native Jira REST implementation seam."
      },
      {
        "backend_kind": "mcp",
        "connection_ref": "atlassian_mcp",
        "raw_operation_refs": [
          "atlassian.mcp.prepare_story_ticket"
        ],
        "backend_input_mode": "explicit",
        "explicit_required_backend_inputs": [
          "project_key",
          "summary",
          "acceptance_criteria"
        ],
        "explicit_optional_backend_inputs": [
          "priority"
        ],
        "matched_discovery_record_ids": [
          "atlassian-mcp-prepare_story_ticket"
        ],
        "status": "candidate",
        "status_detail": "Alternative MCP-backed adapter realization."
      }
    ],
    "governance": {
      "approval_rule_refs": [
        "approval.write_preview_required"
      ],
      "denial_rule_refs": [
        "deny.raw_export",
        "deny.unapproved_mutation"
      ],
      "clarification_rule_refs": [
        "clarify.project_key",
        "clarify.summary",
        "clarify.acceptance_criteria"
      ],
      "audit_required": true
    },
    "outbound_controls": {
      "block_unbounded_payloads": true,
      "redact_sensitive_values": true
    }
  },
  {
    "service_id": "jira-governance-service",
    "service_name": "Jira Governance Service",
    "capability_id": "jira.transition.request",
    "title": "Request Status Transition",
    "summary": "Request a governed Jira issue transition and stop for approval when policy requires it.",
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
    "backend_operation": "request_status_transition",
    "path_template": "/jira/issues/{issue_key}/transition-request",
    "output_shape": "transition_preview",
    "subject_kind": "jira_issue",
    "context_type": "issue_transition",
    "output_intent": "transition_preview",
    "minimum_scope": [
      "jira.transition.request"
    ],
    "required_inputs": [
      {
        "input_name": "issue_key",
        "input_type": "string",
        "required": true,
        "summary": "Jira issue key.",
        "default_value": "",
        "clarification_hint": "Ask for issue_key when it is missing or ambiguous.",
        "entity_reference": true
      },
      {
        "input_name": "target_status",
        "input_type": "string",
        "required": true,
        "summary": "Requested target status.",
        "default_value": "",
        "allowed_values": [
          "todo",
          "in_progress",
          "in_review",
          "done"
        ],
        "clarification_hint": "Ask for target_status when it is missing or ambiguous."
      },
      {
        "input_name": "reason",
        "input_type": "string",
        "required": true,
        "summary": "Reason for the transition.",
        "default_value": "",
        "clarification_hint": "Ask for reason when it is missing or ambiguous."
      }
    ],
    "optional_inputs": [],
    "sample_parameters": {
      "issue_key": "issue_key-value",
      "reason": "reason-value",
      "target_status": "todo"
    },
    "backend_input_mode": "explicit",
    "derived_required_backend_inputs": [],
    "derived_optional_backend_inputs": [],
    "explicit_required_backend_inputs": [
      "issue_key",
      "target_status",
      "reason"
    ],
    "explicit_optional_backend_inputs": [],
    "backend_bindings": [
      {
        "backend_kind": "native_api",
        "connection_ref": "jira_rest_api",
        "raw_operation_refs": [
          "jira.rest.request_status_transition"
        ],
        "backend_input_mode": "explicit",
        "explicit_required_backend_inputs": [
          "issue_key",
          "target_status",
          "reason"
        ],
        "matched_discovery_record_ids": [
          "jira-rest-request_status_transition"
        ],
        "status": "ready",
        "status_detail": "Native Jira REST implementation seam."
      },
      {
        "backend_kind": "mcp",
        "connection_ref": "atlassian_mcp",
        "raw_operation_refs": [
          "atlassian.mcp.request_status_transition"
        ],
        "backend_input_mode": "explicit",
        "explicit_required_backend_inputs": [
          "issue_key",
          "target_status",
          "reason"
        ],
        "matched_discovery_record_ids": [
          "atlassian-mcp-request_status_transition"
        ],
        "status": "candidate",
        "status_detail": "Alternative MCP-backed adapter realization."
      }
    ],
    "governance": {
      "approval_rule_refs": [
        "approval.write_preview_required"
      ],
      "denial_rule_refs": [
        "deny.raw_export",
        "deny.unapproved_mutation"
      ],
      "clarification_rule_refs": [
        "clarify.issue_key",
        "clarify.target_status",
        "clarify.reason"
      ],
      "audit_required": true
    },
    "outbound_controls": {
      "block_unbounded_payloads": true,
      "redact_sensitive_values": true
    }
  },
  {
    "service_id": "jira-governance-service",
    "service_name": "Jira Governance Service",
    "capability_id": "jira.comment.prepare",
    "title": "Prepare Triage Comment",
    "summary": "Prepare a Jira issue comment from incident or triage context without posting it.",
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
        "Change system state"
      ]
    },
    "backend_operation": "prepare_triage_comment",
    "path_template": "/jira/issues/{issue_key}/comment-preview",
    "output_shape": "comment_preview",
    "subject_kind": "jira_issue",
    "context_type": "comment_preparation",
    "output_intent": "comment_preview",
    "minimum_scope": [
      "jira.comment.prepare"
    ],
    "required_inputs": [
      {
        "input_name": "issue_key",
        "input_type": "string",
        "required": true,
        "summary": "Jira issue key.",
        "default_value": "",
        "clarification_hint": "Ask for issue_key when it is missing or ambiguous.",
        "entity_reference": true
      },
      {
        "input_name": "comment_purpose",
        "input_type": "string",
        "required": true,
        "summary": "Purpose of the comment.",
        "default_value": "",
        "allowed_values": [
          "triage_update",
          "customer_impact",
          "release_note"
        ],
        "clarification_hint": "Ask for comment_purpose when it is missing or ambiguous."
      },
      {
        "input_name": "context",
        "input_type": "string",
        "required": true,
        "summary": "Context to summarize in the comment.",
        "default_value": "",
        "clarification_hint": "Ask for context when it is missing or ambiguous."
      }
    ],
    "optional_inputs": [],
    "sample_parameters": {
      "comment_purpose": "triage_update",
      "context": "context-value",
      "issue_key": "issue_key-value"
    },
    "backend_input_mode": "explicit",
    "derived_required_backend_inputs": [],
    "derived_optional_backend_inputs": [],
    "explicit_required_backend_inputs": [
      "issue_key",
      "comment_purpose",
      "context"
    ],
    "explicit_optional_backend_inputs": [],
    "backend_bindings": [
      {
        "backend_kind": "native_api",
        "connection_ref": "jira_rest_api",
        "raw_operation_refs": [
          "jira.rest.prepare_triage_comment"
        ],
        "backend_input_mode": "explicit",
        "explicit_required_backend_inputs": [
          "issue_key",
          "comment_purpose",
          "context"
        ],
        "matched_discovery_record_ids": [
          "jira-rest-prepare_triage_comment"
        ],
        "status": "ready",
        "status_detail": "Native Jira REST implementation seam."
      },
      {
        "backend_kind": "mcp",
        "connection_ref": "atlassian_mcp",
        "raw_operation_refs": [
          "atlassian.mcp.prepare_triage_comment"
        ],
        "backend_input_mode": "explicit",
        "explicit_required_backend_inputs": [
          "issue_key",
          "comment_purpose",
          "context"
        ],
        "matched_discovery_record_ids": [
          "atlassian-mcp-prepare_triage_comment"
        ],
        "status": "candidate",
        "status_detail": "Alternative MCP-backed adapter realization."
      }
    ],
    "governance": {
      "approval_rule_refs": [
        "approval.write_preview_required"
      ],
      "denial_rule_refs": [
        "deny.raw_export",
        "deny.unapproved_mutation"
      ],
      "clarification_rule_refs": [
        "clarify.issue_key",
        "clarify.comment_purpose",
        "clarify.context"
      ],
      "audit_required": true
    },
    "outbound_controls": {
      "block_unbounded_payloads": true,
      "redact_sensitive_values": true
    }
  }
]
''')
