"""Generated runtime target metadata."""
from __future__ import annotations

import json

RUNTIME_TARGET = json.loads(r'''{
  "system_name": "Finance Operations Showcase",
  "domain_name": "finance",
  "delivery_model": "single_service",
  "architecture_shape": "single_service",
  "protocols": [
    "https",
    "mcp"
  ],
  "services": [
    {
      "service_id": "finance-ops-service",
      "service_name": "Finance Operations Service",
      "source_role": "example_service",
      "source_capabilities": [
        "finance.query_portfolio",
        "finance.get_market_data",
        "finance.execute_trade",
        "finance.transfer_funds",
        "finance.generate_report"
      ],
      "formalized_capability_ids": [
        "finance.query_portfolio",
        "finance.get_market_data",
        "finance.execute_trade",
        "finance.transfer_funds",
        "finance.generate_report"
      ],
      "owned_concept_ids": []
    }
  ],
  "policy_bindings": [
    {
      "id": "finance_example_user_policy",
      "source_permission_id": "finance_example_user_access",
      "actor_id": "example_user",
      "principal_selector": {
        "claim": "actor_id",
        "equals": "example_user"
      },
      "business_area": "finance",
      "business_area_label": "Finance Example Access",
      "service_ids": [
        "finance-ops-service"
      ],
      "capability_ids": [
        "finance.query_portfolio",
        "finance.get_market_data",
        "finance.execute_trade",
        "finance.transfer_funds",
        "finance.generate_report"
      ],
      "required_scopes": [
        "finance.read",
        "finance.trade",
        "finance.transfer"
      ],
      "decision": "allow_with_limits",
      "business_rule": "Use the declared capability scope and required inputs as the tutorial boundary.",
      "enforcement_notes": "Generated examples use simple policy so the contract remains readable."
    }
  ],
  "authority": {
    "approval_expectation": "project_specific",
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
    "service_id": "finance-ops-service",
    "service_name": "Finance Operations Service",
    "capability_id": "finance.query_portfolio",
    "title": "Query portfolio",
    "summary": "Query current holdings and valuations.",
    "kind": "atomic",
    "intent_type": "inspect",
    "operation_type": "read",
    "execution_posture": "inspect",
    "side_effect_level": "read",
    "implementation_fit": {
      "category": "custom_service_logic",
      "rationale": "The generated ANIP substrate exposes the contract; the legacy showcase app remains useful implementation material."
    },
    "business_effects": {
      "produces": [
        "Summarize information"
      ],
      "does_not_produce": [
        "Trade",
        "Transfer funds"
      ]
    },
    "backend_operation": "query_portfolio",
    "path_template": "/query_portfolio",
    "output_shape": "portfolio_summary",
    "subject_kind": "business object",
    "context_type": "finance",
    "output_intent": "portfolio_summary",
    "minimum_scope": [
      "finance.read"
    ],
    "required_inputs": [],
    "optional_inputs": [],
    "sample_parameters": {},
    "backend_input_mode": "explicit",
    "derived_required_backend_inputs": [],
    "derived_optional_backend_inputs": [],
    "explicit_required_backend_inputs": [],
    "explicit_optional_backend_inputs": [],
    "backend_bindings": [
      {
        "backend_kind": "python_reference_adapter",
        "connection_ref": "examples/showcase/finance",
        "raw_operation_refs": [
          "query_portfolio"
        ],
        "backend_input_mode": "explicit",
        "status": "ready"
      }
    ],
    "governance": {
      "approval_rule_refs": [],
      "denial_rule_refs": [],
      "clarification_rule_refs": [],
      "audit_required": true
    },
    "outbound_controls": {}
  },
  {
    "service_id": "finance-ops-service",
    "service_name": "Finance Operations Service",
    "capability_id": "finance.get_market_data",
    "title": "Get market data",
    "summary": "Get current market data for a ticker symbol.",
    "kind": "atomic",
    "intent_type": "inspect",
    "operation_type": "read",
    "execution_posture": "inspect",
    "side_effect_level": "read",
    "implementation_fit": {
      "category": "custom_service_logic",
      "rationale": "The generated ANIP substrate exposes the contract; the legacy showcase app remains useful implementation material."
    },
    "business_effects": {
      "produces": [
        "Read bounded data"
      ],
      "does_not_produce": [
        "Trade"
      ]
    },
    "backend_operation": "get_market_data",
    "path_template": "/get_market_data",
    "output_shape": "market_data",
    "subject_kind": "business object",
    "context_type": "finance",
    "output_intent": "market_data",
    "minimum_scope": [
      "finance.read"
    ],
    "required_inputs": [
      {
        "input_name": "symbol",
        "input_type": "string",
        "required": true,
        "summary": "Ticker symbol.",
        "default_value": "",
        "clarification_hint": "Ask for symbol when it is missing or ambiguous.",
        "entity_reference": true
      }
    ],
    "optional_inputs": [],
    "sample_parameters": {
      "symbol": "symbol-value"
    },
    "backend_input_mode": "explicit",
    "derived_required_backend_inputs": [],
    "derived_optional_backend_inputs": [],
    "explicit_required_backend_inputs": [
      "symbol"
    ],
    "explicit_optional_backend_inputs": [],
    "backend_bindings": [
      {
        "backend_kind": "python_reference_adapter",
        "connection_ref": "examples/showcase/finance",
        "raw_operation_refs": [
          "get_market_data"
        ],
        "backend_input_mode": "explicit",
        "explicit_required_backend_inputs": [
          "symbol"
        ],
        "status": "ready"
      }
    ],
    "governance": {
      "approval_rule_refs": [],
      "denial_rule_refs": [],
      "clarification_rule_refs": [],
      "audit_required": true
    },
    "outbound_controls": {}
  },
  {
    "service_id": "finance-ops-service",
    "service_name": "Finance Operations Service",
    "capability_id": "finance.execute_trade",
    "title": "Execute trade",
    "summary": "Execute a buy or sell trade after current market data is available.",
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
    "intent_type": "business_action",
    "operation_type": "approval_gated",
    "execution_posture": "business_action",
    "side_effect_level": "irreversible",
    "implementation_fit": {
      "category": "custom_service_logic",
      "rationale": "The generated ANIP substrate exposes the contract; the legacy showcase app remains useful implementation material."
    },
    "business_effects": {
      "produces": [
        "Execute approved action"
      ],
      "does_not_produce": [
        "Trade without authority",
        "Ignore price context"
      ]
    },
    "backend_operation": "execute_trade",
    "path_template": "/execute_trade",
    "output_shape": "trade_confirmation",
    "subject_kind": "business object",
    "context_type": "finance",
    "output_intent": "trade_confirmation",
    "minimum_scope": [
      "finance.trade"
    ],
    "required_inputs": [
      {
        "input_name": "symbol",
        "input_type": "string",
        "required": true,
        "summary": "Ticker symbol.",
        "default_value": "",
        "clarification_hint": "Ask for symbol when it is missing or ambiguous.",
        "entity_reference": true
      },
      {
        "input_name": "quantity",
        "input_type": "integer",
        "required": true,
        "summary": "Number of shares to trade.",
        "default_value": "",
        "clarification_hint": "Ask for quantity when it is missing or ambiguous."
      }
    ],
    "optional_inputs": [
      {
        "input_name": "side",
        "input_type": "string",
        "required": false,
        "summary": "Trade side.",
        "default_value": "buy",
        "allowed_values": [
          "buy",
          "sell"
        ],
        "clarification_hint": "Ask for side when it is missing or ambiguous."
      }
    ],
    "sample_parameters": {
      "quantity": 1,
      "side": "buy",
      "symbol": "symbol-value"
    },
    "backend_input_mode": "explicit",
    "derived_required_backend_inputs": [],
    "derived_optional_backend_inputs": [],
    "explicit_required_backend_inputs": [
      "symbol",
      "quantity"
    ],
    "explicit_optional_backend_inputs": [
      "side"
    ],
    "backend_bindings": [
      {
        "backend_kind": "python_reference_adapter",
        "connection_ref": "examples/showcase/finance",
        "raw_operation_refs": [
          "execute_trade"
        ],
        "backend_input_mode": "explicit",
        "explicit_required_backend_inputs": [
          "symbol",
          "quantity"
        ],
        "explicit_optional_backend_inputs": [
          "side"
        ],
        "status": "ready"
      }
    ],
    "governance": {
      "approval_rule_refs": [],
      "denial_rule_refs": [],
      "clarification_rule_refs": [],
      "audit_required": true
    },
    "outbound_controls": {}
  },
  {
    "service_id": "finance-ops-service",
    "service_name": "Finance Operations Service",
    "capability_id": "finance.transfer_funds",
    "title": "Transfer funds",
    "summary": "Transfer funds between accounts with transactional recovery posture.",
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
    "intent_type": "business_action",
    "operation_type": "approval_gated",
    "execution_posture": "business_action",
    "side_effect_level": "transactional",
    "implementation_fit": {
      "category": "custom_service_logic",
      "rationale": "The generated ANIP substrate exposes the contract; the legacy showcase app remains useful implementation material."
    },
    "business_effects": {
      "produces": [
        "Change system state"
      ],
      "does_not_produce": [
        "Transfer without authority"
      ]
    },
    "backend_operation": "transfer_funds",
    "path_template": "/transfer_funds",
    "output_shape": "transfer_confirmation",
    "subject_kind": "business object",
    "context_type": "finance",
    "output_intent": "transfer_confirmation",
    "minimum_scope": [
      "finance.transfer"
    ],
    "required_inputs": [
      {
        "input_name": "from_account",
        "input_type": "string",
        "required": true,
        "summary": "Source account.",
        "default_value": "",
        "clarification_hint": "Ask for from_account when it is missing or ambiguous.",
        "entity_reference": true
      },
      {
        "input_name": "to_account",
        "input_type": "string",
        "required": true,
        "summary": "Destination account.",
        "default_value": "",
        "clarification_hint": "Ask for to_account when it is missing or ambiguous.",
        "entity_reference": true
      },
      {
        "input_name": "amount",
        "input_type": "number",
        "required": true,
        "summary": "Transfer amount in USD.",
        "default_value": "",
        "clarification_hint": "Ask for amount when it is missing or ambiguous."
      }
    ],
    "optional_inputs": [],
    "sample_parameters": {
      "amount": 1,
      "from_account": "from_account-value",
      "to_account": "to_account-value"
    },
    "backend_input_mode": "explicit",
    "derived_required_backend_inputs": [],
    "derived_optional_backend_inputs": [],
    "explicit_required_backend_inputs": [
      "from_account",
      "to_account",
      "amount"
    ],
    "explicit_optional_backend_inputs": [],
    "backend_bindings": [
      {
        "backend_kind": "python_reference_adapter",
        "connection_ref": "examples/showcase/finance",
        "raw_operation_refs": [
          "transfer_funds"
        ],
        "backend_input_mode": "explicit",
        "explicit_required_backend_inputs": [
          "from_account",
          "to_account",
          "amount"
        ],
        "status": "ready"
      }
    ],
    "governance": {
      "approval_rule_refs": [],
      "denial_rule_refs": [],
      "clarification_rule_refs": [],
      "audit_required": true
    },
    "outbound_controls": {}
  },
  {
    "service_id": "finance-ops-service",
    "service_name": "Finance Operations Service",
    "capability_id": "finance.generate_report",
    "title": "Generate report",
    "summary": "Generate a daily, holdings, or transaction report.",
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
    "intent_type": "business_action",
    "operation_type": "write",
    "execution_posture": "business_action",
    "side_effect_level": "write",
    "implementation_fit": {
      "category": "custom_service_logic",
      "rationale": "The generated ANIP substrate exposes the contract; the legacy showcase app remains useful implementation material."
    },
    "business_effects": {
      "produces": [
        "Draft content",
        "Summarize information"
      ],
      "does_not_produce": [
        "Trade",
        "Transfer funds"
      ]
    },
    "backend_operation": "generate_report",
    "path_template": "/generate_report",
    "output_shape": "financial_report",
    "subject_kind": "business object",
    "context_type": "finance",
    "output_intent": "financial_report",
    "minimum_scope": [
      "finance.read"
    ],
    "required_inputs": [
      {
        "input_name": "report_type",
        "input_type": "string",
        "required": true,
        "summary": "Report type.",
        "default_value": "",
        "allowed_values": [
          "daily_summary",
          "holdings",
          "transactions"
        ],
        "clarification_hint": "Ask for report_type when it is missing or ambiguous."
      }
    ],
    "optional_inputs": [],
    "sample_parameters": {
      "report_type": "daily_summary"
    },
    "backend_input_mode": "explicit",
    "derived_required_backend_inputs": [],
    "derived_optional_backend_inputs": [],
    "explicit_required_backend_inputs": [
      "report_type"
    ],
    "explicit_optional_backend_inputs": [],
    "backend_bindings": [
      {
        "backend_kind": "python_reference_adapter",
        "connection_ref": "examples/showcase/finance",
        "raw_operation_refs": [
          "generate_report"
        ],
        "backend_input_mode": "explicit",
        "explicit_required_backend_inputs": [
          "report_type"
        ],
        "status": "ready"
      }
    ],
    "governance": {
      "approval_rule_refs": [],
      "denial_rule_refs": [],
      "clarification_rule_refs": [],
      "audit_required": true
    },
    "outbound_controls": {}
  }
]
''')
