"""Generated runtime target metadata."""
from __future__ import annotations

import json

RUNTIME_TARGET = json.loads(r'''{
  "system_name": "Slack Governed Fronting Showcase",
  "domain_name": "slack",
  "delivery_model": "governed_integration_fronting",
  "architecture_shape": "single_service",
  "protocols": [
    "https",
    "mcp"
  ],
  "services": [
    {
      "service_id": "slack-governance-service",
      "service_name": "Slack Governance Service",
      "source_role": "governed_integration_fronting",
      "source_capabilities": [
        "slack.channel.read_context",
        "slack.thread.summarize",
        "slack.message.prepare",
        "slack.incident_update.prepare",
        "slack.announcement.request"
      ],
      "formalized_capability_ids": [
        "slack.channel.read_context",
        "slack.thread.summarize",
        "slack.message.prepare",
        "slack.incident_update.prepare",
        "slack.announcement.request"
      ],
      "owned_concept_ids": [
        "slack_channel",
        "slack_thread",
        "slack_message"
      ]
    }
  ],
  "policy_bindings": [
    {
      "id": "slack_collaborator_policy",
      "source_permission_id": "slack_collaborator_access",
      "actor_id": "collaborator",
      "principal_selector": {
        "claim": "actor_id",
        "equals": "collaborator"
      },
      "business_area": "slack_collaboration",
      "business_area_label": "Slack Collaboration",
      "service_ids": [
        "slack-governance-service"
      ],
      "capability_ids": [
        "slack.channel.read_context",
        "slack.thread.summarize",
        "slack.message.prepare",
        "slack.incident_update.prepare",
        "slack.announcement.request"
      ],
      "required_scopes": [
        "slack.read",
        "slack.message.prepare",
        "slack.announcement.request"
      ],
      "decision": "allow_with_limits",
      "business_rule": "Allow only declared governed Slack capabilities; send-like actions stop at preview or approval.",
      "enforcement_notes": "Raw backend operations remain implementation detail behind the generated adapter seam."
    }
  ],
  "authority": {
    "approval_expectation": "approval_gated_for_send_actions",
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
    "service_id": "slack-governance-service",
    "service_name": "Slack Governance Service",
    "capability_id": "slack.channel.read_context",
    "title": "Read Channel Context",
    "summary": "Read bounded recent Slack channel messages for declared context without exposing raw workspace tools.",
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
        "Send outside the system",
        "Export raw data"
      ]
    },
    "backend_operation": "read_channel_context",
    "path_template": "/slack/channels/{channel_id}/context",
    "output_shape": "bounded_channel_messages",
    "subject_kind": "slack_channel",
    "context_type": "channel_context",
    "output_intent": "bounded_message_results",
    "minimum_scope": [
      "slack.read"
    ],
    "required_inputs": [
      {
        "input_name": "channel_id",
        "input_type": "string",
        "required": true,
        "summary": "Slack channel ID.",
        "default_value": "",
        "clarification_hint": "Ask for channel_id when it is missing or ambiguous.",
        "entity_reference": true
      }
    ],
    "optional_inputs": [
      {
        "input_name": "query",
        "input_type": "string",
        "required": false,
        "summary": "Optional text filter for recent messages.",
        "default_value": "",
        "clarification_hint": "Ask for query when it is missing or ambiguous."
      },
      {
        "input_name": "limit",
        "input_type": "integer",
        "required": false,
        "summary": "Maximum messages to return.",
        "default_value": "20",
        "clarification_hint": "Ask for limit when it is missing or ambiguous."
      }
    ],
    "sample_parameters": {
      "channel_id": "channel_id-value",
      "limit": 20,
      "query": "query-value"
    },
    "backend_input_mode": "explicit",
    "derived_required_backend_inputs": [],
    "derived_optional_backend_inputs": [],
    "explicit_required_backend_inputs": [
      "channel_id"
    ],
    "explicit_optional_backend_inputs": [
      "query",
      "limit"
    ],
    "backend_bindings": [
      {
        "backend_kind": "native_api",
        "connection_ref": "slack_web_api",
        "raw_operation_refs": [
          "slack.web.read_channel_context"
        ],
        "backend_input_mode": "explicit",
        "explicit_required_backend_inputs": [
          "channel_id"
        ],
        "explicit_optional_backend_inputs": [
          "query",
          "limit"
        ],
        "matched_discovery_record_ids": [
          "slack-web-read_channel_context"
        ],
        "status": "ready",
        "status_detail": "Native Slack Web API implementation seam."
      },
      {
        "backend_kind": "mcp",
        "connection_ref": "slack_mcp",
        "raw_operation_refs": [
          "slack.mcp.read_channel_context"
        ],
        "backend_input_mode": "explicit",
        "explicit_required_backend_inputs": [
          "channel_id"
        ],
        "explicit_optional_backend_inputs": [
          "query",
          "limit"
        ],
        "matched_discovery_record_ids": [
          "slack-mcp-read_channel_context"
        ],
        "status": "candidate",
        "status_detail": "Alternative MCP-backed adapter realization for teams that already standardize on Slack MCP."
      }
    ],
    "governance": {
      "approval_rule_refs": [],
      "denial_rule_refs": [
        "deny.raw_export",
        "deny.unapproved_send",
        "deny.workspace_admin_bypass"
      ],
      "clarification_rule_refs": [
        "clarify.channel_id"
      ],
      "audit_required": true
    },
    "outbound_controls": {
      "block_private_channel_exfiltration": true,
      "block_unbounded_payloads": true,
      "redact_sensitive_values": true
    }
  },
  {
    "service_id": "slack-governance-service",
    "service_name": "Slack Governance Service",
    "capability_id": "slack.thread.summarize",
    "title": "Summarize Thread",
    "summary": "Retrieve bounded Slack thread replies and return context for summarization without posting.",
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
        "Send outside the system",
        "Export raw data"
      ]
    },
    "backend_operation": "summarize_thread",
    "path_template": "/slack/channels/{channel_id}/threads/{thread_ts}/summary",
    "output_shape": "bounded_thread_context",
    "subject_kind": "slack_thread",
    "context_type": "thread_context",
    "output_intent": "thread_summary_context",
    "minimum_scope": [
      "slack.read"
    ],
    "required_inputs": [
      {
        "input_name": "channel_id",
        "input_type": "string",
        "required": true,
        "summary": "Slack channel ID.",
        "default_value": "",
        "clarification_hint": "Ask for channel_id when it is missing or ambiguous.",
        "entity_reference": true
      },
      {
        "input_name": "thread_ts",
        "input_type": "string",
        "required": true,
        "summary": "Slack thread timestamp.",
        "default_value": "",
        "clarification_hint": "Ask for thread_ts when it is missing or ambiguous.",
        "entity_reference": true
      }
    ],
    "optional_inputs": [
      {
        "input_name": "focus",
        "input_type": "string",
        "required": false,
        "summary": "Optional summary focus.",
        "default_value": "",
        "clarification_hint": "Ask for focus when it is missing or ambiguous."
      }
    ],
    "sample_parameters": {
      "channel_id": "channel_id-value",
      "focus": "focus-value",
      "thread_ts": "thread_ts-value"
    },
    "backend_input_mode": "explicit",
    "derived_required_backend_inputs": [],
    "derived_optional_backend_inputs": [],
    "explicit_required_backend_inputs": [
      "channel_id",
      "thread_ts"
    ],
    "explicit_optional_backend_inputs": [
      "focus"
    ],
    "backend_bindings": [
      {
        "backend_kind": "native_api",
        "connection_ref": "slack_web_api",
        "raw_operation_refs": [
          "slack.web.summarize_thread"
        ],
        "backend_input_mode": "explicit",
        "explicit_required_backend_inputs": [
          "channel_id",
          "thread_ts"
        ],
        "explicit_optional_backend_inputs": [
          "focus"
        ],
        "matched_discovery_record_ids": [
          "slack-web-summarize_thread"
        ],
        "status": "ready",
        "status_detail": "Native Slack Web API implementation seam."
      },
      {
        "backend_kind": "mcp",
        "connection_ref": "slack_mcp",
        "raw_operation_refs": [
          "slack.mcp.summarize_thread"
        ],
        "backend_input_mode": "explicit",
        "explicit_required_backend_inputs": [
          "channel_id",
          "thread_ts"
        ],
        "explicit_optional_backend_inputs": [
          "focus"
        ],
        "matched_discovery_record_ids": [
          "slack-mcp-summarize_thread"
        ],
        "status": "candidate",
        "status_detail": "Alternative MCP-backed adapter realization for teams that already standardize on Slack MCP."
      }
    ],
    "governance": {
      "approval_rule_refs": [],
      "denial_rule_refs": [
        "deny.raw_export",
        "deny.unapproved_send",
        "deny.workspace_admin_bypass"
      ],
      "clarification_rule_refs": [
        "clarify.channel_id",
        "clarify.thread_ts"
      ],
      "audit_required": true
    },
    "outbound_controls": {
      "block_private_channel_exfiltration": true,
      "block_unbounded_payloads": true,
      "redact_sensitive_values": true
    }
  },
  {
    "service_id": "slack-governance-service",
    "service_name": "Slack Governance Service",
    "capability_id": "slack.message.prepare",
    "title": "Prepare Channel Message",
    "summary": "Prepare a Slack channel message preview without sending it.",
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
        "Preview a change",
        "Ask for approval"
      ],
      "does_not_produce": [
        "Send outside the system",
        "Change workspace state"
      ]
    },
    "backend_operation": "prepare_channel_message",
    "path_template": "/slack/channels/{channel_id}/messages/preview",
    "output_shape": "message_preview",
    "subject_kind": "slack_message",
    "context_type": "message_preparation",
    "output_intent": "message_preview",
    "minimum_scope": [
      "slack.message.prepare"
    ],
    "required_inputs": [
      {
        "input_name": "channel_id",
        "input_type": "string",
        "required": true,
        "summary": "Slack channel ID.",
        "default_value": "",
        "clarification_hint": "Ask for channel_id when it is missing or ambiguous.",
        "entity_reference": true
      },
      {
        "input_name": "text",
        "input_type": "string",
        "required": true,
        "summary": "Message text to preview.",
        "default_value": "",
        "clarification_hint": "Ask for text when it is missing or ambiguous."
      }
    ],
    "optional_inputs": [
      {
        "input_name": "thread_ts",
        "input_type": "string",
        "required": false,
        "summary": "Optional thread timestamp.",
        "default_value": "",
        "clarification_hint": "Ask for thread_ts when it is missing or ambiguous.",
        "entity_reference": true
      }
    ],
    "sample_parameters": {
      "channel_id": "channel_id-value",
      "text": "text-value",
      "thread_ts": "thread_ts-value"
    },
    "backend_input_mode": "explicit",
    "derived_required_backend_inputs": [],
    "derived_optional_backend_inputs": [],
    "explicit_required_backend_inputs": [
      "channel_id",
      "text"
    ],
    "explicit_optional_backend_inputs": [
      "thread_ts"
    ],
    "backend_bindings": [
      {
        "backend_kind": "native_api",
        "connection_ref": "slack_web_api",
        "raw_operation_refs": [
          "slack.web.prepare_channel_message"
        ],
        "backend_input_mode": "explicit",
        "explicit_required_backend_inputs": [
          "channel_id",
          "text"
        ],
        "explicit_optional_backend_inputs": [
          "thread_ts"
        ],
        "matched_discovery_record_ids": [
          "slack-web-prepare_channel_message"
        ],
        "status": "ready",
        "status_detail": "Native Slack Web API implementation seam."
      },
      {
        "backend_kind": "mcp",
        "connection_ref": "slack_mcp",
        "raw_operation_refs": [
          "slack.mcp.prepare_channel_message"
        ],
        "backend_input_mode": "explicit",
        "explicit_required_backend_inputs": [
          "channel_id",
          "text"
        ],
        "explicit_optional_backend_inputs": [
          "thread_ts"
        ],
        "matched_discovery_record_ids": [
          "slack-mcp-prepare_channel_message"
        ],
        "status": "candidate",
        "status_detail": "Alternative MCP-backed adapter realization for teams that already standardize on Slack MCP."
      }
    ],
    "governance": {
      "approval_rule_refs": [
        "approval.message_send_required"
      ],
      "denial_rule_refs": [
        "deny.raw_export",
        "deny.unapproved_send",
        "deny.workspace_admin_bypass"
      ],
      "clarification_rule_refs": [
        "clarify.channel_id",
        "clarify.text"
      ],
      "audit_required": true
    },
    "outbound_controls": {
      "block_private_channel_exfiltration": true,
      "block_unbounded_payloads": true,
      "redact_sensitive_values": true
    }
  },
  {
    "service_id": "slack-governance-service",
    "service_name": "Slack Governance Service",
    "capability_id": "slack.incident_update.prepare",
    "title": "Prepare Incident Update",
    "summary": "Prepare a structured incident update for a Slack channel and stop before sending.",
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
        "Preview a change",
        "Ask for approval"
      ],
      "does_not_produce": [
        "Send outside the system",
        "Change workspace state"
      ]
    },
    "backend_operation": "prepare_incident_update",
    "path_template": "/slack/channels/{channel_id}/incident-updates/preview",
    "output_shape": "incident_update_preview",
    "subject_kind": "slack_message",
    "context_type": "incident_update",
    "output_intent": "incident_update_preview",
    "minimum_scope": [
      "slack.message.prepare"
    ],
    "required_inputs": [
      {
        "input_name": "channel_id",
        "input_type": "string",
        "required": true,
        "summary": "Slack channel ID.",
        "default_value": "",
        "clarification_hint": "Ask for channel_id when it is missing or ambiguous.",
        "entity_reference": true
      },
      {
        "input_name": "incident_id",
        "input_type": "string",
        "required": true,
        "summary": "Incident identifier.",
        "default_value": "",
        "clarification_hint": "Ask for incident_id when it is missing or ambiguous.",
        "entity_reference": true
      },
      {
        "input_name": "status",
        "input_type": "string",
        "required": true,
        "summary": "Incident status.",
        "default_value": "",
        "allowed_values": [
          "investigating",
          "identified",
          "monitoring",
          "resolved"
        ],
        "clarification_hint": "Ask for status when it is missing or ambiguous."
      },
      {
        "input_name": "summary",
        "input_type": "string",
        "required": true,
        "summary": "Human-readable update summary.",
        "default_value": "",
        "clarification_hint": "Ask for summary when it is missing or ambiguous."
      }
    ],
    "optional_inputs": [
      {
        "input_name": "next_update_time",
        "input_type": "string",
        "required": false,
        "summary": "Optional next update time.",
        "default_value": "",
        "clarification_hint": "Ask for next_update_time when it is missing or ambiguous."
      }
    ],
    "sample_parameters": {
      "channel_id": "channel_id-value",
      "incident_id": "incident_id-value",
      "next_update_time": "next_update_time-value",
      "status": "investigating",
      "summary": "summary-value"
    },
    "backend_input_mode": "explicit",
    "derived_required_backend_inputs": [],
    "derived_optional_backend_inputs": [],
    "explicit_required_backend_inputs": [
      "channel_id",
      "incident_id",
      "status",
      "summary"
    ],
    "explicit_optional_backend_inputs": [
      "next_update_time"
    ],
    "backend_bindings": [
      {
        "backend_kind": "native_api",
        "connection_ref": "slack_web_api",
        "raw_operation_refs": [
          "slack.web.prepare_incident_update"
        ],
        "backend_input_mode": "explicit",
        "explicit_required_backend_inputs": [
          "channel_id",
          "incident_id",
          "status",
          "summary"
        ],
        "explicit_optional_backend_inputs": [
          "next_update_time"
        ],
        "matched_discovery_record_ids": [
          "slack-web-prepare_incident_update"
        ],
        "status": "ready",
        "status_detail": "Native Slack Web API implementation seam."
      },
      {
        "backend_kind": "mcp",
        "connection_ref": "slack_mcp",
        "raw_operation_refs": [
          "slack.mcp.prepare_incident_update"
        ],
        "backend_input_mode": "explicit",
        "explicit_required_backend_inputs": [
          "channel_id",
          "incident_id",
          "status",
          "summary"
        ],
        "explicit_optional_backend_inputs": [
          "next_update_time"
        ],
        "matched_discovery_record_ids": [
          "slack-mcp-prepare_incident_update"
        ],
        "status": "candidate",
        "status_detail": "Alternative MCP-backed adapter realization for teams that already standardize on Slack MCP."
      }
    ],
    "governance": {
      "approval_rule_refs": [
        "approval.message_send_required"
      ],
      "denial_rule_refs": [
        "deny.raw_export",
        "deny.unapproved_send",
        "deny.workspace_admin_bypass"
      ],
      "clarification_rule_refs": [
        "clarify.channel_id",
        "clarify.incident_id",
        "clarify.status",
        "clarify.summary"
      ],
      "audit_required": true
    },
    "outbound_controls": {
      "block_private_channel_exfiltration": true,
      "block_unbounded_payloads": true,
      "redact_sensitive_values": true
    }
  },
  {
    "service_id": "slack-governance-service",
    "service_name": "Slack Governance Service",
    "capability_id": "slack.announcement.request",
    "title": "Request Channel Announcement",
    "summary": "Prepare a channel announcement request that requires approval before posting.",
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
        "Send outside the system",
        "Bypass communication policy"
      ]
    },
    "backend_operation": "request_channel_announcement",
    "path_template": "/slack/channels/{channel_id}/announcements/request",
    "output_shape": "announcement_preview",
    "subject_kind": "slack_message",
    "context_type": "announcement_request",
    "output_intent": "announcement_preview",
    "minimum_scope": [
      "slack.announcement.request"
    ],
    "required_inputs": [
      {
        "input_name": "channel_id",
        "input_type": "string",
        "required": true,
        "summary": "Slack channel ID.",
        "default_value": "",
        "clarification_hint": "Ask for channel_id when it is missing or ambiguous.",
        "entity_reference": true
      },
      {
        "input_name": "announcement",
        "input_type": "string",
        "required": true,
        "summary": "Announcement text.",
        "default_value": "",
        "clarification_hint": "Ask for announcement when it is missing or ambiguous."
      }
    ],
    "optional_inputs": [
      {
        "input_name": "audience",
        "input_type": "string",
        "required": false,
        "summary": "Intended audience.",
        "default_value": "",
        "clarification_hint": "Ask for audience when it is missing or ambiguous."
      }
    ],
    "sample_parameters": {
      "announcement": "announcement-value",
      "audience": "audience-value",
      "channel_id": "channel_id-value"
    },
    "backend_input_mode": "explicit",
    "derived_required_backend_inputs": [],
    "derived_optional_backend_inputs": [],
    "explicit_required_backend_inputs": [
      "channel_id",
      "announcement"
    ],
    "explicit_optional_backend_inputs": [
      "audience"
    ],
    "backend_bindings": [
      {
        "backend_kind": "native_api",
        "connection_ref": "slack_web_api",
        "raw_operation_refs": [
          "slack.web.request_channel_announcement"
        ],
        "backend_input_mode": "explicit",
        "explicit_required_backend_inputs": [
          "channel_id",
          "announcement"
        ],
        "explicit_optional_backend_inputs": [
          "audience"
        ],
        "matched_discovery_record_ids": [
          "slack-web-request_channel_announcement"
        ],
        "status": "ready",
        "status_detail": "Native Slack Web API implementation seam."
      },
      {
        "backend_kind": "mcp",
        "connection_ref": "slack_mcp",
        "raw_operation_refs": [
          "slack.mcp.request_channel_announcement"
        ],
        "backend_input_mode": "explicit",
        "explicit_required_backend_inputs": [
          "channel_id",
          "announcement"
        ],
        "explicit_optional_backend_inputs": [
          "audience"
        ],
        "matched_discovery_record_ids": [
          "slack-mcp-request_channel_announcement"
        ],
        "status": "candidate",
        "status_detail": "Alternative MCP-backed adapter realization for teams that already standardize on Slack MCP."
      }
    ],
    "governance": {
      "approval_rule_refs": [
        "approval.message_send_required"
      ],
      "denial_rule_refs": [
        "deny.raw_export",
        "deny.unapproved_send",
        "deny.workspace_admin_bypass"
      ],
      "clarification_rule_refs": [
        "clarify.channel_id",
        "clarify.announcement"
      ],
      "audit_required": true
    },
    "outbound_controls": {
      "block_private_channel_exfiltration": true,
      "block_unbounded_payloads": true,
      "redact_sensitive_values": true
    }
  }
]
''')
