"""Generated runtime target metadata."""
from __future__ import annotations

import json

RUNTIME_TARGET = json.loads(r'''{
  "system_name": "Travel Booking Showcase",
  "domain_name": "travel",
  "delivery_model": "single_service",
  "architecture_shape": "single_service",
  "protocols": [
    "https",
    "mcp"
  ],
  "services": [
    {
      "service_id": "travel-booking-service",
      "service_name": "Travel Booking Service",
      "source_role": "example_service",
      "source_capabilities": [
        "travel.search_flights",
        "travel.check_availability",
        "travel.book_flight",
        "travel.cancel_booking"
      ],
      "formalized_capability_ids": [
        "travel.search_flights",
        "travel.check_availability",
        "travel.book_flight",
        "travel.cancel_booking"
      ],
      "owned_concept_ids": []
    }
  ],
  "policy_bindings": [
    {
      "id": "travel_example_user_policy",
      "source_permission_id": "travel_example_user_access",
      "actor_id": "example_user",
      "principal_selector": {
        "claim": "actor_id",
        "equals": "example_user"
      },
      "business_area": "travel",
      "business_area_label": "Travel Example Access",
      "service_ids": [
        "travel-booking-service"
      ],
      "capability_ids": [
        "travel.search_flights",
        "travel.check_availability",
        "travel.book_flight",
        "travel.cancel_booking"
      ],
      "required_scopes": [
        "travel.search",
        "travel.book"
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
    "service_id": "travel-booking-service",
    "service_name": "Travel Booking Service",
    "capability_id": "travel.search_flights",
    "title": "Search flights",
    "summary": "Search available flights by origin and destination and return priced quote references.",
    "kind": "atomic",
    "intent_type": "search",
    "operation_type": "read",
    "execution_posture": "search",
    "side_effect_level": "read",
    "implementation_fit": {
      "category": "custom_service_logic",
      "rationale": "The generated ANIP substrate exposes the contract; the legacy showcase app remains useful implementation material."
    },
    "business_effects": {
      "produces": [
        "Summarize information",
        "Return bounded options"
      ],
      "does_not_produce": [
        "Book travel",
        "Charge payment"
      ]
    },
    "backend_operation": "search_flights",
    "path_template": "/search_flights",
    "output_shape": "flight_list",
    "subject_kind": "business object",
    "context_type": "travel",
    "output_intent": "flight_list",
    "minimum_scope": [
      "travel.search"
    ],
    "required_inputs": [
      {
        "input_name": "origin",
        "input_type": "airport_code",
        "required": true,
        "summary": "Departure airport IATA code.",
        "default_value": "",
        "clarification_hint": "Ask for origin when it is missing or ambiguous.",
        "entity_reference": true
      },
      {
        "input_name": "destination",
        "input_type": "airport_code",
        "required": true,
        "summary": "Arrival airport IATA code.",
        "default_value": "",
        "clarification_hint": "Ask for destination when it is missing or ambiguous.",
        "entity_reference": true
      }
    ],
    "optional_inputs": [],
    "sample_parameters": {
      "destination": "destination-value",
      "origin": "origin-value"
    },
    "backend_input_mode": "explicit",
    "derived_required_backend_inputs": [],
    "derived_optional_backend_inputs": [],
    "explicit_required_backend_inputs": [
      "origin",
      "destination"
    ],
    "explicit_optional_backend_inputs": [],
    "backend_bindings": [
      {
        "backend_kind": "python_reference_adapter",
        "connection_ref": "examples/showcase/travel",
        "raw_operation_refs": [
          "search_flights"
        ],
        "backend_input_mode": "explicit",
        "explicit_required_backend_inputs": [
          "origin",
          "destination"
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
    "service_id": "travel-booking-service",
    "service_name": "Travel Booking Service",
    "capability_id": "travel.check_availability",
    "title": "Check availability",
    "summary": "Check seat availability and current price for a specific flight.",
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
        "Book travel",
        "Charge payment"
      ]
    },
    "backend_operation": "check_availability",
    "path_template": "/check_availability",
    "output_shape": "availability_info",
    "subject_kind": "business object",
    "context_type": "travel",
    "output_intent": "availability_info",
    "minimum_scope": [
      "travel.search"
    ],
    "required_inputs": [
      {
        "input_name": "flight_number",
        "input_type": "string",
        "required": true,
        "summary": "Flight number to check.",
        "default_value": "",
        "clarification_hint": "Ask for flight_number when it is missing or ambiguous.",
        "entity_reference": true
      }
    ],
    "optional_inputs": [],
    "sample_parameters": {
      "flight_number": "flight_number-value"
    },
    "backend_input_mode": "explicit",
    "derived_required_backend_inputs": [],
    "derived_optional_backend_inputs": [],
    "explicit_required_backend_inputs": [
      "flight_number"
    ],
    "explicit_optional_backend_inputs": [],
    "backend_bindings": [
      {
        "backend_kind": "python_reference_adapter",
        "connection_ref": "examples/showcase/travel",
        "raw_operation_refs": [
          "check_availability"
        ],
        "backend_input_mode": "explicit",
        "explicit_required_backend_inputs": [
          "flight_number"
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
    "service_id": "travel-booking-service",
    "service_name": "Travel Booking Service",
    "capability_id": "travel.book_flight",
    "title": "Book flight",
    "summary": "Book a confirmed flight reservation from a current quote.",
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
        "Book without quote",
        "Ignore budget authority"
      ]
    },
    "backend_operation": "book_flight",
    "path_template": "/book_flight",
    "output_shape": "booking_confirmation",
    "subject_kind": "business object",
    "context_type": "travel",
    "output_intent": "booking_confirmation",
    "minimum_scope": [
      "travel.book"
    ],
    "required_inputs": [
      {
        "input_name": "flight_number",
        "input_type": "string",
        "required": true,
        "summary": "Flight to book.",
        "default_value": "",
        "clarification_hint": "Ask for flight_number when it is missing or ambiguous.",
        "entity_reference": true
      },
      {
        "input_name": "quote_id",
        "input_type": "object",
        "required": true,
        "summary": "Priced quote returned by search_flights.",
        "default_value": "",
        "clarification_hint": "Ask for quote_id when it is missing or ambiguous.",
        "entity_reference": true
      }
    ],
    "optional_inputs": [
      {
        "input_name": "passengers",
        "input_type": "integer",
        "required": false,
        "summary": "Number of passengers.",
        "default_value": "1",
        "clarification_hint": "Ask for passengers when it is missing or ambiguous."
      }
    ],
    "sample_parameters": {
      "flight_number": "flight_number-value",
      "passengers": 1,
      "quote_id": {}
    },
    "backend_input_mode": "explicit",
    "derived_required_backend_inputs": [],
    "derived_optional_backend_inputs": [],
    "explicit_required_backend_inputs": [
      "flight_number",
      "quote_id"
    ],
    "explicit_optional_backend_inputs": [
      "passengers"
    ],
    "backend_bindings": [
      {
        "backend_kind": "python_reference_adapter",
        "connection_ref": "examples/showcase/travel",
        "raw_operation_refs": [
          "book_flight"
        ],
        "backend_input_mode": "explicit",
        "explicit_required_backend_inputs": [
          "flight_number",
          "quote_id"
        ],
        "explicit_optional_backend_inputs": [
          "passengers"
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
    "service_id": "travel-booking-service",
    "service_name": "Travel Booking Service",
    "capability_id": "travel.cancel_booking",
    "title": "Cancel booking",
    "summary": "Cancel an existing booking within the transactional cancellation window.",
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
        "Delete booking history"
      ]
    },
    "backend_operation": "cancel_booking",
    "path_template": "/cancel_booking",
    "output_shape": "cancellation_confirmation",
    "subject_kind": "business object",
    "context_type": "travel",
    "output_intent": "cancellation_confirmation",
    "minimum_scope": [
      "travel.book"
    ],
    "required_inputs": [
      {
        "input_name": "booking_id",
        "input_type": "string",
        "required": true,
        "summary": "Booking identifier to cancel.",
        "default_value": "",
        "clarification_hint": "Ask for booking_id when it is missing or ambiguous.",
        "entity_reference": true
      }
    ],
    "optional_inputs": [],
    "sample_parameters": {
      "booking_id": "booking_id-value"
    },
    "backend_input_mode": "explicit",
    "derived_required_backend_inputs": [],
    "derived_optional_backend_inputs": [],
    "explicit_required_backend_inputs": [
      "booking_id"
    ],
    "explicit_optional_backend_inputs": [],
    "backend_bindings": [
      {
        "backend_kind": "python_reference_adapter",
        "connection_ref": "examples/showcase/travel",
        "raw_operation_refs": [
          "cancel_booking"
        ],
        "backend_input_mode": "explicit",
        "explicit_required_backend_inputs": [
          "booking_id"
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
