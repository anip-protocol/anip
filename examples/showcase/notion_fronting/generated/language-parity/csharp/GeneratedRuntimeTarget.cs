using System.Text.Json;

namespace notiongovernedfrontingshowcase;

public static class GeneratedRuntimeTarget
{
    public static string ContractVersion => "anip-service-definition/v1";

    public static Dictionary<string, object?> RuntimeTarget { get; } =
        JsonSerializer.Deserialize<Dictionary<string, object?>>(RuntimeTargetJson)!;

    public static List<Dictionary<string, object?>> Capabilities { get; } =
        JsonSerializer.Deserialize<List<Dictionary<string, object?>>>(CapabilityMetadataJson)!;

    public const string RuntimeTargetJson = """
{
  "system_name": "Notion Fronting Showcase 0.2.0",
  "domain_name": "notion",
  "delivery_model": "standalone_service",
  "architecture_shape": "single_service",
  "protocols": [
    "anip_http"
  ],
  "services": [
    {
      "service_id": "notion-governance-service",
      "service_name": "Notion Governance",
      "source_role": "implementation service",
      "source_capabilities": [
        "notion.workspace.search_context",
        "notion.database.query_context",
        "notion.page.create.prepare",
        "notion.page.update.prepare",
        "notion.comment.prepare"
      ],
      "formalized_capability_ids": [
        "notion.workspace.search_context",
        "notion.database.query_context",
        "notion.page.create.prepare",
        "notion.page.update.prepare",
        "notion.comment.prepare"
      ],
      "owned_concept_ids": []
    }
  ],
  "policy_bindings": [
    {
      "id": "policy_permission_rule_0",
      "source_permission_id": "permission_rule_0",
      "actor_id": "governed_notion_requester",
      "principal_selector": {
        "claim": "actor_id",
        "equals": "governed_notion_requester"
      },
      "business_area": "workspace_context_search",
      "business_area_label": "Workspace Context Search",
      "service_ids": [
        "notion-governance-service"
      ],
      "capability_ids": [
        "notion.workspace.search_context",
        "notion.database.query_context",
        "notion.page.create.prepare",
        "notion.page.update.prepare",
        "notion.comment.prepare"
      ],
      "required_scopes": [
        "notion.workspace.search_context",
        "notion.database.query_context",
        "notion.page.create.prepare",
        "notion.page.update.prepare",
        "notion.comment.prepare"
      ],
      "decision": "allow_with_limits",
      "business_rule": "Allow bounded workspace search within declared workspace scope and return actor-visible summaries only, not raw workspace tools or exports.",
      "enforcement_notes": "governed_notion_requester bounded access to Workspace Context Search should return bounded_result. Allow bounded workspace search within declared workspace scope and return actor-visible summaries only, not raw workspace tools or exports. Matches the governed search capability and read-only bounded result posture."
    },
    {
      "id": "policy_permission_rule_1",
      "source_permission_id": "permission_rule_1",
      "actor_id": "governed_notion_requester",
      "principal_selector": {
        "claim": "actor_id",
        "equals": "governed_notion_requester"
      },
      "business_area": "database_context_query",
      "business_area_label": "Database Context Query",
      "service_ids": [
        "notion-governance-service"
      ],
      "capability_ids": [
        "notion.workspace.search_context",
        "notion.database.query_context",
        "notion.page.create.prepare",
        "notion.page.update.prepare",
        "notion.comment.prepare"
      ],
      "required_scopes": [
        "notion.workspace.search_context",
        "notion.database.query_context",
        "notion.page.create.prepare",
        "notion.page.update.prepare",
        "notion.comment.prepare"
      ],
      "decision": "allow_with_limits",
      "business_rule": "Allow bounded database query against an explicit database and return summarized context rather than raw export.",
      "enforcement_notes": "governed_notion_requester bounded access to Database Context Query should return bounded_result. Allow bounded database query against an explicit database and return summarized context rather than raw export. Filters, sorting, and backend options remain bounded by scope and policy."
    },
    {
      "id": "policy_permission_rule_2",
      "source_permission_id": "permission_rule_2",
      "actor_id": "governed_notion_requester",
      "principal_selector": {
        "claim": "actor_id",
        "equals": "governed_notion_requester"
      },
      "business_area": "page_creation_preparation",
      "business_area_label": "Page Creation Preparation",
      "service_ids": [
        "notion-governance-service"
      ],
      "capability_ids": [
        "notion.page.create.prepare"
      ],
      "required_scopes": [
        "notion.page.create.prepare"
      ],
      "decision": "approval_required",
      "business_rule": "Allow preparation of a page creation preview under an explicit parent, then stop for approval before creation.",
      "enforcement_notes": "governed_notion_requester approval_required access to Page Creation Preparation should return approval_stop. Allow preparation of a page creation preview under an explicit parent, then stop for approval before creation. No direct page creation is allowed from the governed capability surface."
    },
    {
      "id": "policy_permission_rule_3",
      "source_permission_id": "permission_rule_3",
      "actor_id": "governed_notion_requester",
      "principal_selector": {
        "claim": "actor_id",
        "equals": "governed_notion_requester"
      },
      "business_area": "page_update_preparation",
      "business_area_label": "Page Update Preparation",
      "service_ids": [
        "notion-governance-service"
      ],
      "capability_ids": [
        "notion.page.update.prepare"
      ],
      "required_scopes": [
        "notion.page.update.prepare"
      ],
      "decision": "approval_required",
      "business_rule": "Allow preparation of a page update preview for an explicit page, then stop for approval before applying changes.",
      "enforcement_notes": "governed_notion_requester approval_required access to Page Update Preparation should return approval_stop. Allow preparation of a page update preview for an explicit page, then stop for approval before applying changes. No direct page update is allowed from the governed capability surface."
    },
    {
      "id": "policy_permission_rule_4",
      "source_permission_id": "permission_rule_4",
      "actor_id": "governed_notion_requester",
      "principal_selector": {
        "claim": "actor_id",
        "equals": "governed_notion_requester"
      },
      "business_area": "comment_preparation",
      "business_area_label": "Comment Preparation",
      "service_ids": [
        "notion-governance-service"
      ],
      "capability_ids": [
        "notion.comment.prepare"
      ],
      "required_scopes": [
        "notion.comment.prepare"
      ],
      "decision": "approval_required",
      "business_rule": "Allow preparation of a page comment preview from supplied context, then stop for approval before posting.",
      "enforcement_notes": "governed_notion_requester approval_required access to Comment Preparation should return approval_stop. Allow preparation of a page comment preview from supplied context, then stop for approval before posting. No direct comment posting is allowed from the governed capability surface."
    },
    {
      "id": "policy_permission_rule_5",
      "source_permission_id": "permission_rule_5",
      "actor_id": "governed_notion_requester",
      "principal_selector": {
        "claim": "actor_id",
        "equals": "governed_notion_requester"
      },
      "business_area": "clarification_handling",
      "business_area_label": "Clarification Handling",
      "service_ids": [
        "notion-governance-service"
      ],
      "capability_ids": [
        "notion.workspace.search_context"
      ],
      "required_scopes": [
        "notion.workspace.search_context"
      ],
      "decision": "clarify",
      "business_rule": "Stop and request clarification when workspace scope, query, page id, parent id, or database id is missing or ambiguous.",
      "enforcement_notes": "governed_notion_requester restricted access to Clarification Handling should return clarification_required. Stop and request clarification when workspace scope, query, page id, parent id, or database id is missing or ambiguous. Applies across search, query, and preparation flows."
    },
    {
      "id": "policy_permission_rule_6",
      "source_permission_id": "permission_rule_6",
      "actor_id": "governed_notion_requester",
      "principal_selector": {
        "claim": "actor_id",
        "equals": "governed_notion_requester"
      },
      "business_area": "scope_and_visibility_controls",
      "business_area_label": "Scope and Visibility Controls",
      "service_ids": [
        "notion-governance-service"
      ],
      "capability_ids": [
        "notion.workspace.search_context"
      ],
      "required_scopes": [
        "notion.workspace.search_context"
      ],
      "decision": "deny",
      "business_rule": "Deny requests for hidden page access, private page exfiltration, raw workspace export, arbitrary block mutation, parent override, or workspace-wide unrestricted access.",
      "enforcement_notes": "governed_notion_requester denied access to Scope and Visibility Controls should return deny_request. Deny requests for hidden page access, private page exfiltration, raw workspace export, arbitrary block mutation, parent override, or workspace-wide unrestricted access. Preserves actor-visible scope and bounded provider controls."
    },
    {
      "id": "policy_permission_rule_7",
      "source_permission_id": "permission_rule_7",
      "actor_id": "governed_notion_requester",
      "principal_selector": {
        "claim": "actor_id",
        "equals": "governed_notion_requester"
      },
      "business_area": "approval_gated_changes",
      "business_area_label": "Approval-Gated Changes",
      "service_ids": [
        "notion-governance-service"
      ],
      "capability_ids": [
        "notion.comment.prepare"
      ],
      "required_scopes": [
        "notion.comment.prepare"
      ],
      "decision": "deny",
      "business_rule": "Deny direct mutation attempts when approval has not been granted for page creation, page update, or comment posting.",
      "enforcement_notes": "governed_notion_requester denied access to Approval-Gated Changes should return deny_request. Deny direct mutation attempts when approval has not been granted for page creation, page update, or comment posting. Separates preview preparation from actual mutation authority."
    },
    {
      "id": "policy_permission_rule_8",
      "source_permission_id": "permission_rule_8",
      "actor_id": "notion_change_approver",
      "principal_selector": {
        "claim": "actor_id",
        "equals": "notion_change_approver"
      },
      "business_area": "approval_gated_changes",
      "business_area_label": "Approval-Gated Changes",
      "service_ids": [
        "notion-governance-service"
      ],
      "capability_ids": [
        "notion.workspace.search_context",
        "notion.database.query_context",
        "notion.page.create.prepare",
        "notion.page.update.prepare",
        "notion.comment.prepare"
      ],
      "required_scopes": [
        "notion.workspace.search_context",
        "notion.database.query_context",
        "notion.page.create.prepare",
        "notion.page.update.prepare",
        "notion.comment.prepare"
      ],
      "decision": "allow",
      "business_rule": "Allow review and approval decision handling for prepared page creation, page update, and comment previews.",
      "enforcement_notes": "notion_change_approver allowed access to Approval-Gated Changes should return direct_result. Allow review and approval decision handling for prepared page creation, page update, and comment previews. This rule assumes the approver actor is intended to participate directly in approval flow."
    },
    {
      "id": "policy_permission_rule_9",
      "source_permission_id": "permission_rule_9",
      "actor_id": "notion_governance_reviewer",
      "principal_selector": {
        "claim": "actor_id",
        "equals": "notion_governance_reviewer"
      },
      "business_area": "policy_enforcement_and_audit",
      "business_area_label": "Policy Enforcement and Audit",
      "service_ids": [
        "notion-governance-service"
      ],
      "capability_ids": [
        "notion.workspace.search_context",
        "notion.database.query_context",
        "notion.page.create.prepare",
        "notion.page.update.prepare",
        "notion.comment.prepare"
      ],
      "required_scopes": [
        "notion.workspace.search_context",
        "notion.database.query_context",
        "notion.page.create.prepare",
        "notion.page.update.prepare",
        "notion.comment.prepare"
      ],
      "decision": "allow",
      "business_rule": "Allow governance review of approval records, scope enforcement posture, and audit-relevant outcomes for the governed Notion fronting service.",
      "enforcement_notes": "notion_governance_reviewer allowed access to Policy Enforcement and Audit should return direct_result. Allow governance review of approval records, scope enforcement posture, and audit-relevant outcomes for the governed Notion fronting service. This rule assumes governance review and audit visibility are intended for this actor."
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
""";

    private const string CapabilityMetadataJson = """
[
  {
    "service_id": "notion-governance-service",
    "service_name": "Notion Governance",
    "capability_id": "notion.workspace.search_context",
    "title": "Search Workspace Context",
    "summary": "Search bounded Notion pages and databases without exposing raw workspace tools.",
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
    "backend_operation": "notion.api.workspace_search_context",
    "path_template": "/notion/workspace_search_context",
    "output_shape": "bounded_workspace_results_result",
    "subject_kind": "notion_workspace",
    "context_type": "workspace_context_search",
    "output_intent": "bounded_workspace_results",
    "minimum_scope": [
      "notion.workspace.search_context"
    ],
    "required_inputs": [
      {
        "input_name": "workspace_scope",
        "input_type": "string",
        "required": true,
        "summary": "Declared workspace or team scope.",
        "default_value": "",
        "semantic_type": "workspace_scope",
        "clarification_hint": "Ask for workspace_scope when it is missing or ambiguous.",
        "entity_reference": true,
        "resolution": {
          "mode": "clarify",
          "on_missing": "clarify"
        }
      },
      {
        "input_name": "query",
        "input_type": "string",
        "required": true,
        "summary": "Bounded workspace search query.",
        "default_value": "",
        "clarification_hint": "Ask for query when it is missing or ambiguous.",
        "resolution": {
          "mode": "clarify",
          "on_missing": "clarify"
        }
      }
    ],
    "optional_inputs": [
      {
        "input_name": "limit",
        "input_type": "integer",
        "required": false,
        "summary": "Maximum results to return.",
        "default_value": "20",
        "clarification_hint": "Ask for limit when it is missing or ambiguous.",
        "resolution": {
          "mode": "explicit_only",
          "on_missing": "omit"
        }
      },
      {
        "input_name": "backend_options",
        "input_type": "object",
        "required": false,
        "summary": "Bounded Notion provider options such as selected properties, page size, or safe filter fragments. Must not bypass page scope or approval policy.",
        "default_value": "",
        "semantic_type": "backend_options",
        "clarification_hint": "Do not ask for backend_options unless the user explicitly needs provider-specific controls.",
        "resolution": {
          "mode": "explicit_only",
          "on_missing": "omit"
        }
      }
    ],
    "sample_parameters": {
      "backend_options": {},
      "limit": 20,
      "query": "query-value",
      "workspace_scope": "workspace_scope-value"
    },
    "backend_input_mode": "explicit",
    "derived_required_backend_inputs": [
      "workspace_scope",
      "query"
    ],
    "derived_optional_backend_inputs": [
      "limit",
      "backend_options"
    ],
    "explicit_required_backend_inputs": [
      "workspace_scope",
      "query"
    ],
    "explicit_optional_backend_inputs": [
      "limit",
      "backend_options"
    ],
    "backend_bindings": [
      {
        "backend_kind": "native_api",
        "connection_ref": "d31b4bd9-b05e-4631-afc4-c4c10a8e65ff-notion-api",
        "raw_operation_refs": [
          "notion.api.workspace_search_context"
        ],
        "backend_input_mode": "explicit",
        "derived_required_backend_inputs": [
          "workspace_scope",
          "query"
        ],
        "derived_optional_backend_inputs": [
          "limit",
          "backend_options"
        ],
        "explicit_required_backend_inputs": [
          "workspace_scope",
          "query"
        ],
        "explicit_optional_backend_inputs": [
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
        "clarify.workspace_scope",
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
    "service_id": "notion-governance-service",
    "service_name": "Notion Governance",
    "capability_id": "notion.database.query_context",
    "title": "Query Database Context",
    "summary": "Query a bounded Notion database view with declared filters and return summarized context.",
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
    "backend_operation": "notion.api.database_query_context",
    "path_template": "/notion/database_query_context",
    "output_shape": "bounded_database_rows_result",
    "subject_kind": "notion_database",
    "context_type": "database_query",
    "output_intent": "bounded_database_rows",
    "minimum_scope": [
      "notion.database.query_context"
    ],
    "required_inputs": [
      {
        "input_name": "database_id",
        "input_type": "string",
        "required": true,
        "summary": "Notion database identifier.",
        "default_value": "",
        "semantic_type": "database_ref",
        "clarification_hint": "Ask for database_id when it is missing or ambiguous.",
        "entity_reference": true,
        "resolution": {
          "mode": "clarify",
          "on_missing": "clarify"
        }
      }
    ],
    "optional_inputs": [
      {
        "input_name": "filter",
        "input_type": "string",
        "required": false,
        "summary": "Declared filter expression or business filter.",
        "default_value": "",
        "clarification_hint": "Ask for filter when it is missing or ambiguous.",
        "resolution": {
          "mode": "explicit_only",
          "on_missing": "omit"
        }
      },
      {
        "input_name": "limit",
        "input_type": "integer",
        "required": false,
        "summary": "Maximum rows to return.",
        "default_value": "20",
        "clarification_hint": "Ask for limit when it is missing or ambiguous.",
        "resolution": {
          "mode": "explicit_only",
          "on_missing": "omit"
        }
      },
      {
        "input_name": "backend_options",
        "input_type": "object",
        "required": false,
        "summary": "Bounded Notion provider options such as selected properties, page size, or safe filter fragments. Must not bypass page scope or approval policy.",
        "default_value": "",
        "semantic_type": "backend_options",
        "clarification_hint": "Do not ask for backend_options unless the user explicitly needs provider-specific controls.",
        "resolution": {
          "mode": "explicit_only",
          "on_missing": "omit"
        }
      }
    ],
    "sample_parameters": {
      "backend_options": {},
      "database_id": "database_id-value",
      "filter": "filter-value",
      "limit": 20
    },
    "backend_input_mode": "explicit",
    "derived_required_backend_inputs": [
      "database_id"
    ],
    "derived_optional_backend_inputs": [
      "filter",
      "limit",
      "backend_options"
    ],
    "explicit_required_backend_inputs": [
      "database_id"
    ],
    "explicit_optional_backend_inputs": [
      "filter",
      "limit",
      "backend_options"
    ],
    "backend_bindings": [
      {
        "backend_kind": "native_api",
        "connection_ref": "d31b4bd9-b05e-4631-afc4-c4c10a8e65ff-notion-api",
        "raw_operation_refs": [
          "notion.api.database_query_context"
        ],
        "backend_input_mode": "explicit",
        "derived_required_backend_inputs": [
          "database_id"
        ],
        "derived_optional_backend_inputs": [
          "filter",
          "limit",
          "backend_options"
        ],
        "explicit_required_backend_inputs": [
          "database_id"
        ],
        "explicit_optional_backend_inputs": [
          "filter",
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
        "clarify.database_id"
      ],
      "audit_required": true
    },
    "outbound_controls": {
      "raw_backend_not_agent_visible": true,
      "redaction_required": true
    }
  },
  {
    "service_id": "notion-governance-service",
    "service_name": "Notion Governance",
    "capability_id": "notion.page.create.prepare",
    "title": "Prepare Page Creation",
    "summary": "Prepare a Notion page creation preview under an explicit parent before creating anything.",
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
    "backend_operation": "notion.api.page_create_prepare",
    "path_template": "/notion/page_create_prepare",
    "output_shape": "page_creation_preview_result",
    "subject_kind": "notion_page",
    "context_type": "page_creation_preparation",
    "output_intent": "page_creation_preview",
    "minimum_scope": [
      "notion.page.create.prepare"
    ],
    "required_inputs": [
      {
        "input_name": "parent_id",
        "input_type": "string",
        "required": true,
        "summary": "Parent page or database identifier.",
        "default_value": "",
        "semantic_type": "page_or_database_ref",
        "clarification_hint": "Ask for parent_id when it is missing or ambiguous.",
        "entity_reference": true,
        "resolution": {
          "mode": "clarify",
          "on_missing": "clarify"
        }
      },
      {
        "input_name": "title",
        "input_type": "string",
        "required": true,
        "summary": "Proposed page title.",
        "default_value": "",
        "clarification_hint": "Ask for title when it is missing or ambiguous.",
        "resolution": {
          "mode": "clarify",
          "on_missing": "clarify"
        }
      },
      {
        "input_name": "content_summary",
        "input_type": "string",
        "required": true,
        "summary": "Bounded content summary for the new page.",
        "default_value": "",
        "clarification_hint": "Ask for content_summary when it is missing or ambiguous.",
        "resolution": {
          "mode": "clarify",
          "on_missing": "clarify"
        }
      }
    ],
    "optional_inputs": [
      {
        "input_name": "backend_options",
        "input_type": "object",
        "required": false,
        "summary": "Bounded Notion provider options such as selected properties, page size, or safe filter fragments. Must not bypass page scope or approval policy.",
        "default_value": "",
        "semantic_type": "backend_options",
        "clarification_hint": "Do not ask for backend_options unless the user explicitly needs provider-specific controls.",
        "resolution": {
          "mode": "explicit_only",
          "on_missing": "omit"
        }
      }
    ],
    "sample_parameters": {
      "backend_options": {},
      "content_summary": "content_summary-value",
      "parent_id": "parent_id-value",
      "title": "title-value"
    },
    "backend_input_mode": "explicit",
    "derived_required_backend_inputs": [
      "parent_id",
      "title",
      "content_summary"
    ],
    "derived_optional_backend_inputs": [
      "backend_options"
    ],
    "explicit_required_backend_inputs": [
      "parent_id",
      "title",
      "content_summary"
    ],
    "explicit_optional_backend_inputs": [
      "backend_options"
    ],
    "backend_bindings": [
      {
        "backend_kind": "native_api",
        "connection_ref": "d31b4bd9-b05e-4631-afc4-c4c10a8e65ff-notion-api",
        "raw_operation_refs": [
          "notion.api.page_create_prepare"
        ],
        "backend_input_mode": "explicit",
        "derived_required_backend_inputs": [
          "parent_id",
          "title",
          "content_summary"
        ],
        "derived_optional_backend_inputs": [
          "backend_options"
        ],
        "explicit_required_backend_inputs": [
          "parent_id",
          "title",
          "content_summary"
        ],
        "explicit_optional_backend_inputs": [
          "backend_options"
        ],
        "status": "ready",
        "status_detail": "Materialized from reviewed developer capability evidence."
      }
    ],
    "governance": {
      "approval_rule_refs": [
        "approval.notion-page-create-prepare"
      ],
      "denial_rule_refs": [
        "deny.raw_backend_bypass"
      ],
      "clarification_rule_refs": [
        "clarify.parent_id",
        "clarify.title",
        "clarify.content_summary"
      ],
      "audit_required": true
    },
    "outbound_controls": {
      "raw_backend_not_agent_visible": true,
      "redaction_required": true
    }
  },
  {
    "service_id": "notion-governance-service",
    "service_name": "Notion Governance",
    "capability_id": "notion.page.update.prepare",
    "title": "Prepare Page Update",
    "summary": "Prepare a Notion page update preview for an explicit page without applying the update.",
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
    "backend_operation": "notion.api.page_update_prepare",
    "path_template": "/notion/page_update_prepare",
    "output_shape": "page_update_preview_result",
    "subject_kind": "notion_page",
    "context_type": "page_update_preparation",
    "output_intent": "page_update_preview",
    "minimum_scope": [
      "notion.page.update.prepare"
    ],
    "required_inputs": [
      {
        "input_name": "page_id",
        "input_type": "string",
        "required": true,
        "summary": "Notion page identifier.",
        "default_value": "",
        "semantic_type": "page_ref",
        "clarification_hint": "Ask for page_id when it is missing or ambiguous.",
        "entity_reference": true,
        "resolution": {
          "mode": "clarify",
          "on_missing": "clarify"
        }
      },
      {
        "input_name": "change_summary",
        "input_type": "string",
        "required": true,
        "summary": "Plain-language change summary.",
        "default_value": "",
        "clarification_hint": "Ask for change_summary when it is missing or ambiguous.",
        "resolution": {
          "mode": "clarify",
          "on_missing": "clarify"
        }
      }
    ],
    "optional_inputs": [
      {
        "input_name": "content_patch",
        "input_type": "string",
        "required": false,
        "summary": "Optional bounded content patch.",
        "default_value": "",
        "clarification_hint": "Ask for content_patch when it is missing or ambiguous.",
        "resolution": {
          "mode": "explicit_only",
          "on_missing": "omit"
        }
      },
      {
        "input_name": "backend_options",
        "input_type": "object",
        "required": false,
        "summary": "Bounded Notion provider options such as selected properties, page size, or safe filter fragments. Must not bypass page scope or approval policy.",
        "default_value": "",
        "semantic_type": "backend_options",
        "clarification_hint": "Do not ask for backend_options unless the user explicitly needs provider-specific controls.",
        "resolution": {
          "mode": "explicit_only",
          "on_missing": "omit"
        }
      }
    ],
    "sample_parameters": {
      "backend_options": {},
      "change_summary": "change_summary-value",
      "content_patch": "content_patch-value",
      "page_id": "page_id-value"
    },
    "backend_input_mode": "explicit",
    "derived_required_backend_inputs": [
      "page_id",
      "change_summary"
    ],
    "derived_optional_backend_inputs": [
      "content_patch",
      "backend_options"
    ],
    "explicit_required_backend_inputs": [
      "page_id",
      "change_summary"
    ],
    "explicit_optional_backend_inputs": [
      "content_patch",
      "backend_options"
    ],
    "backend_bindings": [
      {
        "backend_kind": "native_api",
        "connection_ref": "d31b4bd9-b05e-4631-afc4-c4c10a8e65ff-notion-api",
        "raw_operation_refs": [
          "notion.api.page_update_prepare"
        ],
        "backend_input_mode": "explicit",
        "derived_required_backend_inputs": [
          "page_id",
          "change_summary"
        ],
        "derived_optional_backend_inputs": [
          "content_patch",
          "backend_options"
        ],
        "explicit_required_backend_inputs": [
          "page_id",
          "change_summary"
        ],
        "explicit_optional_backend_inputs": [
          "content_patch",
          "backend_options"
        ],
        "status": "ready",
        "status_detail": "Materialized from reviewed developer capability evidence."
      }
    ],
    "governance": {
      "approval_rule_refs": [
        "approval.notion-page-update-prepare"
      ],
      "denial_rule_refs": [
        "deny.raw_backend_bypass"
      ],
      "clarification_rule_refs": [
        "clarify.page_id",
        "clarify.change_summary"
      ],
      "audit_required": true
    },
    "outbound_controls": {
      "raw_backend_not_agent_visible": true,
      "redaction_required": true
    }
  },
  {
    "service_id": "notion-governance-service",
    "service_name": "Notion Governance",
    "capability_id": "notion.comment.prepare",
    "title": "Prepare Page Comment",
    "summary": "Prepare a Notion page comment from supplied context without posting it.",
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
    "backend_operation": "notion.api.comment_prepare",
    "path_template": "/notion/comment_prepare",
    "output_shape": "comment_preview_result",
    "subject_kind": "notion_comment",
    "context_type": "comment_preparation",
    "output_intent": "comment_preview",
    "minimum_scope": [
      "notion.comment.prepare"
    ],
    "required_inputs": [
      {
        "input_name": "page_id",
        "input_type": "string",
        "required": true,
        "summary": "Notion page identifier.",
        "default_value": "",
        "semantic_type": "page_ref",
        "clarification_hint": "Ask for page_id when it is missing or ambiguous.",
        "entity_reference": true,
        "resolution": {
          "mode": "clarify",
          "on_missing": "clarify"
        }
      },
      {
        "input_name": "comment_purpose",
        "input_type": "string",
        "required": true,
        "summary": "Purpose of the comment.",
        "default_value": "",
        "clarification_hint": "Ask for comment_purpose when it is missing or ambiguous.",
        "resolution": {
          "mode": "clarify",
          "on_missing": "clarify"
        }
      },
      {
        "input_name": "context",
        "input_type": "string",
        "required": true,
        "summary": "Bounded context for the proposed comment.",
        "default_value": "",
        "clarification_hint": "Ask for context when it is missing or ambiguous.",
        "resolution": {
          "mode": "clarify",
          "on_missing": "clarify"
        }
      }
    ],
    "optional_inputs": [
      {
        "input_name": "backend_options",
        "input_type": "object",
        "required": false,
        "summary": "Bounded Notion provider options such as selected properties, page size, or safe filter fragments. Must not bypass page scope or approval policy.",
        "default_value": "",
        "semantic_type": "backend_options",
        "clarification_hint": "Do not ask for backend_options unless the user explicitly needs provider-specific controls.",
        "resolution": {
          "mode": "explicit_only",
          "on_missing": "omit"
        }
      }
    ],
    "sample_parameters": {
      "backend_options": {},
      "comment_purpose": "comment_purpose-value",
      "context": "context-value",
      "page_id": "page_id-value"
    },
    "backend_input_mode": "explicit",
    "derived_required_backend_inputs": [
      "page_id",
      "comment_purpose",
      "context"
    ],
    "derived_optional_backend_inputs": [
      "backend_options"
    ],
    "explicit_required_backend_inputs": [
      "page_id",
      "comment_purpose",
      "context"
    ],
    "explicit_optional_backend_inputs": [
      "backend_options"
    ],
    "backend_bindings": [
      {
        "backend_kind": "native_api",
        "connection_ref": "d31b4bd9-b05e-4631-afc4-c4c10a8e65ff-notion-api",
        "raw_operation_refs": [
          "notion.api.comment_prepare"
        ],
        "backend_input_mode": "explicit",
        "derived_required_backend_inputs": [
          "page_id",
          "comment_purpose",
          "context"
        ],
        "derived_optional_backend_inputs": [
          "backend_options"
        ],
        "explicit_required_backend_inputs": [
          "page_id",
          "comment_purpose",
          "context"
        ],
        "explicit_optional_backend_inputs": [
          "backend_options"
        ],
        "status": "ready",
        "status_detail": "Materialized from reviewed developer capability evidence."
      }
    ],
    "governance": {
      "approval_rule_refs": [
        "approval.notion-comment-prepare"
      ],
      "denial_rule_refs": [
        "deny.raw_backend_bypass"
      ],
      "clarification_rule_refs": [
        "clarify.page_id",
        "clarify.comment_purpose",
        "clarify.context"
      ],
      "audit_required": true
    },
    "outbound_controls": {
      "raw_backend_not_agent_visible": true,
      "redaction_required": true
    }
  }
]
""";
}
