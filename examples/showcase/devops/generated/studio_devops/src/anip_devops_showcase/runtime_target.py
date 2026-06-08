"""Generated runtime target metadata."""
from __future__ import annotations

import json

RUNTIME_TARGET = json.loads(r'''{
  "system_name": "DevOps Infrastructure Showcase",
  "domain_name": "devops",
  "delivery_model": "single_service",
  "architecture_shape": "single_service",
  "protocols": [
    "https",
    "mcp"
  ],
  "services": [
    {
      "service_id": "devops-infra-service",
      "service_name": "DevOps Infrastructure Service",
      "source_role": "example_service",
      "source_capabilities": [
        "devops.list_deployments",
        "devops.get_service_health",
        "devops.scale_replicas",
        "devops.update_config",
        "devops.rollback_deployment",
        "devops.delete_resource",
        "devops.destroy_environment"
      ],
      "formalized_capability_ids": [
        "devops.list_deployments",
        "devops.get_service_health",
        "devops.scale_replicas",
        "devops.update_config",
        "devops.rollback_deployment",
        "devops.delete_resource",
        "devops.destroy_environment"
      ],
      "owned_concept_ids": []
    }
  ],
  "policy_bindings": [
    {
      "id": "devops_example_user_policy",
      "source_permission_id": "devops_example_user_access",
      "actor_id": "example_user",
      "principal_selector": {
        "claim": "actor_id",
        "equals": "example_user"
      },
      "business_area": "devops",
      "business_area_label": "Devops Example Access",
      "service_ids": [
        "devops-infra-service"
      ],
      "capability_ids": [
        "devops.list_deployments",
        "devops.get_service_health",
        "devops.scale_replicas",
        "devops.update_config",
        "devops.rollback_deployment",
        "devops.delete_resource",
        "devops.destroy_environment"
      ],
      "required_scopes": [
        "infra.read",
        "infra.write",
        "infra.deploy",
        "infra.admin"
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
    "service_id": "devops-infra-service",
    "service_name": "DevOps Infrastructure Service",
    "capability_id": "devops.list_deployments",
    "title": "List deployments",
    "summary": "List current service deployments and status.",
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
        "Change infrastructure"
      ]
    },
    "backend_operation": "list_deployments",
    "path_template": "/list_deployments",
    "output_shape": "deployment_list",
    "subject_kind": "business object",
    "context_type": "devops",
    "output_intent": "deployment_list",
    "minimum_scope": [
      "infra.read"
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
        "connection_ref": "examples/showcase/devops",
        "raw_operation_refs": [
          "list_deployments"
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
    "service_id": "devops-infra-service",
    "service_name": "DevOps Infrastructure Service",
    "capability_id": "devops.get_service_health",
    "title": "Get service health",
    "summary": "Get health and performance metrics for a service.",
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
        "Change infrastructure"
      ]
    },
    "backend_operation": "get_service_health",
    "path_template": "/get_service_health",
    "output_shape": "service_health",
    "subject_kind": "business object",
    "context_type": "devops",
    "output_intent": "service_health",
    "minimum_scope": [
      "infra.read"
    ],
    "required_inputs": [
      {
        "input_name": "service_name",
        "input_type": "string",
        "required": true,
        "summary": "Service to inspect.",
        "default_value": "",
        "clarification_hint": "Ask for service_name when it is missing or ambiguous.",
        "entity_reference": true
      }
    ],
    "optional_inputs": [],
    "sample_parameters": {
      "service_name": "service_name-value"
    },
    "backend_input_mode": "explicit",
    "derived_required_backend_inputs": [],
    "derived_optional_backend_inputs": [],
    "explicit_required_backend_inputs": [
      "service_name"
    ],
    "explicit_optional_backend_inputs": [],
    "backend_bindings": [
      {
        "backend_kind": "python_reference_adapter",
        "connection_ref": "examples/showcase/devops",
        "raw_operation_refs": [
          "get_service_health"
        ],
        "backend_input_mode": "explicit",
        "explicit_required_backend_inputs": [
          "service_name"
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
    "service_id": "devops-infra-service",
    "service_name": "DevOps Infrastructure Service",
    "capability_id": "devops.scale_replicas",
    "title": "Scale replicas",
    "summary": "Scale the replica count for a deployment.",
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
        "Change system state"
      ],
      "does_not_produce": [
        "Delete infrastructure"
      ]
    },
    "backend_operation": "scale_replicas",
    "path_template": "/scale_replicas",
    "output_shape": "scale_confirmation",
    "subject_kind": "business object",
    "context_type": "devops",
    "output_intent": "scale_confirmation",
    "minimum_scope": [
      "infra.write"
    ],
    "required_inputs": [
      {
        "input_name": "service_name",
        "input_type": "string",
        "required": true,
        "summary": "Service to scale.",
        "default_value": "",
        "clarification_hint": "Ask for service_name when it is missing or ambiguous.",
        "entity_reference": true
      },
      {
        "input_name": "replicas",
        "input_type": "integer",
        "required": true,
        "summary": "Target replica count.",
        "default_value": "",
        "clarification_hint": "Ask for replicas when it is missing or ambiguous."
      }
    ],
    "optional_inputs": [],
    "sample_parameters": {
      "replicas": 1,
      "service_name": "service_name-value"
    },
    "backend_input_mode": "explicit",
    "derived_required_backend_inputs": [],
    "derived_optional_backend_inputs": [],
    "explicit_required_backend_inputs": [
      "service_name",
      "replicas"
    ],
    "explicit_optional_backend_inputs": [],
    "backend_bindings": [
      {
        "backend_kind": "python_reference_adapter",
        "connection_ref": "examples/showcase/devops",
        "raw_operation_refs": [
          "scale_replicas"
        ],
        "backend_input_mode": "explicit",
        "explicit_required_backend_inputs": [
          "service_name",
          "replicas"
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
    "service_id": "devops-infra-service",
    "service_name": "DevOps Infrastructure Service",
    "capability_id": "devops.update_config",
    "title": "Update config",
    "summary": "Update a configuration key-value pair for a service.",
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
        "Change system state"
      ],
      "does_not_produce": [
        "Delete infrastructure"
      ]
    },
    "backend_operation": "update_config",
    "path_template": "/update_config",
    "output_shape": "config_change",
    "subject_kind": "business object",
    "context_type": "devops",
    "output_intent": "config_change",
    "minimum_scope": [
      "infra.write"
    ],
    "required_inputs": [
      {
        "input_name": "service_name",
        "input_type": "string",
        "required": true,
        "summary": "Service to configure.",
        "default_value": "",
        "clarification_hint": "Ask for service_name when it is missing or ambiguous.",
        "entity_reference": true
      },
      {
        "input_name": "key",
        "input_type": "string",
        "required": true,
        "summary": "Configuration key.",
        "default_value": "",
        "clarification_hint": "Ask for key when it is missing or ambiguous."
      },
      {
        "input_name": "value",
        "input_type": "string",
        "required": true,
        "summary": "New configuration value.",
        "default_value": "",
        "clarification_hint": "Ask for value when it is missing or ambiguous."
      }
    ],
    "optional_inputs": [],
    "sample_parameters": {
      "key": "key-value",
      "service_name": "service_name-value",
      "value": "value-value"
    },
    "backend_input_mode": "explicit",
    "derived_required_backend_inputs": [],
    "derived_optional_backend_inputs": [],
    "explicit_required_backend_inputs": [
      "service_name",
      "key",
      "value"
    ],
    "explicit_optional_backend_inputs": [],
    "backend_bindings": [
      {
        "backend_kind": "python_reference_adapter",
        "connection_ref": "examples/showcase/devops",
        "raw_operation_refs": [
          "update_config"
        ],
        "backend_input_mode": "explicit",
        "explicit_required_backend_inputs": [
          "service_name",
          "key",
          "value"
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
    "service_id": "devops-infra-service",
    "service_name": "DevOps Infrastructure Service",
    "capability_id": "devops.rollback_deployment",
    "title": "Rollback deployment",
    "summary": "Roll back a service deployment to a previous version.",
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
        "Delete infrastructure"
      ]
    },
    "backend_operation": "rollback_deployment",
    "path_template": "/rollback_deployment",
    "output_shape": "rollback_confirmation",
    "subject_kind": "business object",
    "context_type": "devops",
    "output_intent": "rollback_confirmation",
    "minimum_scope": [
      "infra.deploy"
    ],
    "required_inputs": [
      {
        "input_name": "service_name",
        "input_type": "string",
        "required": true,
        "summary": "Service to roll back.",
        "default_value": "",
        "clarification_hint": "Ask for service_name when it is missing or ambiguous.",
        "entity_reference": true
      },
      {
        "input_name": "target_version",
        "input_type": "string",
        "required": true,
        "summary": "Target version.",
        "default_value": "",
        "clarification_hint": "Ask for target_version when it is missing or ambiguous."
      }
    ],
    "optional_inputs": [],
    "sample_parameters": {
      "service_name": "service_name-value",
      "target_version": "target_version-value"
    },
    "backend_input_mode": "explicit",
    "derived_required_backend_inputs": [],
    "derived_optional_backend_inputs": [],
    "explicit_required_backend_inputs": [
      "service_name",
      "target_version"
    ],
    "explicit_optional_backend_inputs": [],
    "backend_bindings": [
      {
        "backend_kind": "python_reference_adapter",
        "connection_ref": "examples/showcase/devops",
        "raw_operation_refs": [
          "rollback_deployment"
        ],
        "backend_input_mode": "explicit",
        "explicit_required_backend_inputs": [
          "service_name",
          "target_version"
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
    "service_id": "devops-infra-service",
    "service_name": "DevOps Infrastructure Service",
    "capability_id": "devops.delete_resource",
    "title": "Delete resource",
    "summary": "Permanently delete an infrastructure resource.",
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
        "Destroy environment"
      ]
    },
    "backend_operation": "delete_resource",
    "path_template": "/delete_resource",
    "output_shape": "deletion_confirmation",
    "subject_kind": "business object",
    "context_type": "devops",
    "output_intent": "deletion_confirmation",
    "minimum_scope": [
      "infra.admin"
    ],
    "required_inputs": [
      {
        "input_name": "resource_type",
        "input_type": "string",
        "required": true,
        "summary": "Resource type.",
        "default_value": "",
        "allowed_values": [
          "deployment",
          "config",
          "service"
        ],
        "clarification_hint": "Ask for resource_type when it is missing or ambiguous."
      },
      {
        "input_name": "resource_name",
        "input_type": "string",
        "required": true,
        "summary": "Resource name.",
        "default_value": "",
        "clarification_hint": "Ask for resource_name when it is missing or ambiguous.",
        "entity_reference": true
      }
    ],
    "optional_inputs": [],
    "sample_parameters": {
      "resource_name": "resource_name-value",
      "resource_type": "deployment"
    },
    "backend_input_mode": "explicit",
    "derived_required_backend_inputs": [],
    "derived_optional_backend_inputs": [],
    "explicit_required_backend_inputs": [
      "resource_type",
      "resource_name"
    ],
    "explicit_optional_backend_inputs": [],
    "backend_bindings": [
      {
        "backend_kind": "python_reference_adapter",
        "connection_ref": "examples/showcase/devops",
        "raw_operation_refs": [
          "delete_resource"
        ],
        "backend_input_mode": "explicit",
        "explicit_required_backend_inputs": [
          "resource_type",
          "resource_name"
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
    "service_id": "devops-infra-service",
    "service_name": "DevOps Infrastructure Service",
    "capability_id": "devops.destroy_environment",
    "title": "Destroy environment",
    "summary": "Permanently destroy a non-production environment; direct principal action is required.",
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
        "Delegate destructive environment removal"
      ]
    },
    "backend_operation": "destroy_environment",
    "path_template": "/destroy_environment",
    "output_shape": "destroy_confirmation",
    "subject_kind": "business object",
    "context_type": "devops",
    "output_intent": "destroy_confirmation",
    "minimum_scope": [
      "infra.admin"
    ],
    "required_inputs": [
      {
        "input_name": "environment_name",
        "input_type": "string",
        "required": true,
        "summary": "Environment name.",
        "default_value": "",
        "allowed_values": [
          "staging",
          "development",
          "preview"
        ],
        "clarification_hint": "Ask for environment_name when it is missing or ambiguous.",
        "entity_reference": true
      }
    ],
    "optional_inputs": [],
    "sample_parameters": {
      "environment_name": "staging"
    },
    "backend_input_mode": "explicit",
    "derived_required_backend_inputs": [],
    "derived_optional_backend_inputs": [],
    "explicit_required_backend_inputs": [
      "environment_name"
    ],
    "explicit_optional_backend_inputs": [],
    "backend_bindings": [
      {
        "backend_kind": "python_reference_adapter",
        "connection_ref": "examples/showcase/devops",
        "raw_operation_refs": [
          "destroy_environment"
        ],
        "backend_input_mode": "explicit",
        "explicit_required_backend_inputs": [
          "environment_name"
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
