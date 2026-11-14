"""Generated runtime target metadata."""
from __future__ import annotations

import json

RUNTIME_TARGET = json.loads(r'''{
  "system_name": "slack_governed_fronting_showcase",
  "domain_name": "slack",
  "delivery_model": "governed_integration_fronting",
  "architecture_shape": "single_service",
  "protocols": [
    "https"
  ],
  "services": [
    {
      "service_id": "slack-governance-service",
      "service_name": "Slack Governance Service",
      "source_role": "integration_fronting",
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
        "fronted_resource"
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
        "slack.channel.read_context",
        "slack.thread.summarize",
        "slack.message.prepare",
        "slack.incident_update.prepare",
        "slack.announcement.request"
      ],
      "decision": "allow_with_limits",
      "business_rule": "Allow only declared governed Slack capabilities; send-like actions stop at preview or approval.",
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
    "backend_operation": "slack_channel_read_context",
    "path_template": "/slack/channels/{channel_id}/context",
    "output_shape": "slack_channel_read_context_result",
    "subject_kind": "slack_channel",
    "context_type": "channel_context",
    "output_intent": "bounded_message_results",
    "minimum_scope": [
      "slack.channel.read_context"
    ],
    "required_inputs": [
      {
        "input_name": "channel_id",
        "input_type": "string",
        "required": true,
        "summary": "Slack channel ID.",
        "default_value": "",
        "semantic_type": "channel_ref",
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
      },
      {
        "input_name": "backend_options",
        "input_type": "object",
        "required": false,
        "summary": "Bounded Slack provider options such as formatting mode or unfurl posture. Must not bypass channel scope, approval, or send policy.",
        "default_value": "",
        "semantic_type": "backend_options",
        "clarification_hint": "Do not ask for backend_options unless the user explicitly needs provider-specific controls."
      }
    ],
    "sample_parameters": {
      "backend_options": {},
      "channel_id": "channel_id-value",
      "limit": 20,
      "query": "query-value"
    },
    "backend_input_mode": "explicit",
    "derived_required_backend_inputs": [],
    "derived_optional_backend_inputs": [],
    "explicit_required_backend_inputs": [],
    "explicit_optional_backend_inputs": [],
    "backend_bindings": [
      {
        "backend_kind": "native_api",
        "connection_ref": "slack_fronting",
        "raw_operation_refs": [
          "slack.web.read_channel_context"
        ],
        "backend_input_mode": "explicit",
        "status": "ready"
      }
    ],
    "governance": {
      "approval_rule_refs": [],
      "denial_rule_refs": [],
      "clarification_rule_refs": [
        "missing_required_inputs"
      ],
      "audit_required": true
    },
    "outbound_controls": {
      "raw_backend_not_agent_visible": true,
      "redaction_required": true
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
    "backend_operation": "slack_thread_summarize",
    "path_template": "/slack/channels/{channel_id}/threads/{thread_ts}/summary",
    "output_shape": "slack_thread_summarize_result",
    "subject_kind": "slack_thread",
    "context_type": "thread_context",
    "output_intent": "thread_summary_context",
    "minimum_scope": [
      "slack.thread.summarize"
    ],
    "required_inputs": [
      {
        "input_name": "channel_id",
        "input_type": "string",
        "required": true,
        "summary": "Slack channel ID.",
        "default_value": "",
        "semantic_type": "channel_ref",
        "clarification_hint": "Ask for channel_id when it is missing or ambiguous.",
        "entity_reference": true
      },
      {
        "input_name": "thread_ts",
        "input_type": "string",
        "required": true,
        "summary": "Slack thread timestamp.",
        "default_value": "",
        "semantic_type": "thread_ref",
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
      },
      {
        "input_name": "limit",
        "input_type": "integer",
        "required": false,
        "summary": "Maximum thread replies to return; the adapter caps it at 100.",
        "default_value": "50",
        "clarification_hint": "Ask for limit when it is missing or ambiguous."
      },
      {
        "input_name": "backend_options",
        "input_type": "object",
        "required": false,
        "summary": "Bounded Slack provider options such as formatting mode or unfurl posture. Must not bypass channel scope, approval, or send policy.",
        "default_value": "",
        "semantic_type": "backend_options",
        "clarification_hint": "Do not ask for backend_options unless the user explicitly needs provider-specific controls."
      }
    ],
    "sample_parameters": {
      "backend_options": {},
      "channel_id": "channel_id-value",
      "focus": "focus-value",
      "limit": 50,
      "thread_ts": "thread_ts-value"
    },
    "backend_input_mode": "explicit",
    "derived_required_backend_inputs": [],
    "derived_optional_backend_inputs": [],
    "explicit_required_backend_inputs": [],
    "explicit_optional_backend_inputs": [],
    "backend_bindings": [
      {
        "backend_kind": "native_api",
        "connection_ref": "slack_fronting",
        "raw_operation_refs": [
          "slack.web.summarize_thread"
        ],
        "backend_input_mode": "explicit",
        "status": "ready"
      }
    ],
    "governance": {
      "approval_rule_refs": [],
      "denial_rule_refs": [],
      "clarification_rule_refs": [
        "missing_required_inputs"
      ],
      "audit_required": true
    },
    "outbound_controls": {
      "raw_backend_not_agent_visible": true,
      "redaction_required": true
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
    "backend_operation": "slack_message_prepare",
    "path_template": "/slack/channels/{channel_id}/messages/preview",
    "output_shape": "slack_message_prepare_result",
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
        "semantic_type": "channel_ref",
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
        "semantic_type": "thread_ref",
        "clarification_hint": "Ask for thread_ts when it is missing or ambiguous.",
        "entity_reference": true
      },
      {
        "input_name": "backend_options",
        "input_type": "object",
        "required": false,
        "summary": "Bounded Slack provider options such as formatting mode or unfurl posture. Must not bypass channel scope, approval, or send policy.",
        "default_value": "",
        "semantic_type": "backend_options",
        "clarification_hint": "Do not ask for backend_options unless the user explicitly needs provider-specific controls."
      }
    ],
    "sample_parameters": {
      "backend_options": {},
      "channel_id": "channel_id-value",
      "text": "text-value",
      "thread_ts": "thread_ts-value"
    },
    "backend_input_mode": "explicit",
    "derived_required_backend_inputs": [],
    "derived_optional_backend_inputs": [],
    "explicit_required_backend_inputs": [],
    "explicit_optional_backend_inputs": [],
    "backend_bindings": [
      {
        "backend_kind": "native_api",
        "connection_ref": "slack_fronting",
        "raw_operation_refs": [
          "slack.web.prepare_channel_message"
        ],
        "backend_input_mode": "explicit",
        "status": "ready"
      }
    ],
    "governance": {
      "approval_rule_refs": [],
      "denial_rule_refs": [],
      "clarification_rule_refs": [
        "missing_required_inputs"
      ],
      "audit_required": true
    },
    "outbound_controls": {
      "raw_backend_not_agent_visible": true,
      "redaction_required": true
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
    "backend_operation": "slack_incident_update_prepare",
    "path_template": "/slack/channels/{channel_id}/incident-updates/preview",
    "output_shape": "slack_incident_update_prepare_result",
    "subject_kind": "slack_message",
    "context_type": "incident_update",
    "output_intent": "incident_update_preview",
    "minimum_scope": [
      "slack.incident_update.prepare"
    ],
    "required_inputs": [
      {
        "input_name": "channel_id",
        "input_type": "string",
        "required": true,
        "summary": "Slack channel ID.",
        "default_value": "",
        "semantic_type": "channel_ref",
        "clarification_hint": "Ask for channel_id when it is missing or ambiguous.",
        "entity_reference": true
      },
      {
        "input_name": "incident_id",
        "input_type": "string",
        "required": true,
        "summary": "Incident identifier.",
        "default_value": "",
        "semantic_type": "incident_ref",
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
      },
      {
        "input_name": "backend_options",
        "input_type": "object",
        "required": false,
        "summary": "Bounded Slack provider options such as formatting mode or unfurl posture. Must not bypass channel scope, approval, or send policy.",
        "default_value": "",
        "semantic_type": "backend_options",
        "clarification_hint": "Do not ask for backend_options unless the user explicitly needs provider-specific controls."
      }
    ],
    "sample_parameters": {
      "backend_options": {},
      "channel_id": "channel_id-value",
      "incident_id": "incident_id-value",
      "next_update_time": "next_update_time-value",
      "status": "investigating",
      "summary": "summary-value"
    },
    "backend_input_mode": "explicit",
    "derived_required_backend_inputs": [],
    "derived_optional_backend_inputs": [],
    "explicit_required_backend_inputs": [],
    "explicit_optional_backend_inputs": [],
    "backend_bindings": [
      {
        "backend_kind": "native_api",
        "connection_ref": "slack_fronting",
        "raw_operation_refs": [
          "slack.web.prepare_incident_update"
        ],
        "backend_input_mode": "explicit",
        "status": "ready"
      }
    ],
    "governance": {
      "approval_rule_refs": [],
      "denial_rule_refs": [],
      "clarification_rule_refs": [
        "missing_required_inputs"
      ],
      "audit_required": true
    },
    "outbound_controls": {
      "raw_backend_not_agent_visible": true,
      "redaction_required": true
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
    "intent_type": "prepare_only",
    "operation_type": "write",
    "execution_posture": "prepare_only",
    "side_effect_level": "write_adjacent",
    "backend_operation": "slack_announcement_request",
    "path_template": "/slack/channels/{channel_id}/announcements/request",
    "output_shape": "slack_announcement_request_result",
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
        "semantic_type": "channel_ref",
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
      },
      {
        "input_name": "backend_options",
        "input_type": "object",
        "required": false,
        "summary": "Bounded Slack provider options such as formatting mode or unfurl posture. Must not bypass channel scope, approval, or send policy.",
        "default_value": "",
        "semantic_type": "backend_options",
        "clarification_hint": "Do not ask for backend_options unless the user explicitly needs provider-specific controls."
      }
    ],
    "sample_parameters": {
      "announcement": "announcement-value",
      "audience": "audience-value",
      "backend_options": {},
      "channel_id": "channel_id-value"
    },
    "backend_input_mode": "explicit",
    "derived_required_backend_inputs": [],
    "derived_optional_backend_inputs": [],
    "explicit_required_backend_inputs": [],
    "explicit_optional_backend_inputs": [],
    "backend_bindings": [
      {
        "backend_kind": "native_api",
        "connection_ref": "slack_fronting",
        "raw_operation_refs": [
          "slack.web.request_channel_announcement"
        ],
        "backend_input_mode": "explicit",
        "status": "ready"
      }
    ],
    "governance": {
      "approval_rule_refs": [],
      "denial_rule_refs": [],
      "clarification_rule_refs": [
        "missing_required_inputs"
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
