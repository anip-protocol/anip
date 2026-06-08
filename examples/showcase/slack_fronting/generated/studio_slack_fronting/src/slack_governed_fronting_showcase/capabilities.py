"""Generated capability declarations and handlers."""
from __future__ import annotations

import inspect
import re
from typing import Any

from anip_core import CapabilityDeclaration, CapabilityInput, CapabilityOutput, SessionInfo, SideEffect
from anip_service import ANIPError, Capability, InvocationContext

from .backend_adapter import backend_adapter
from .policy import evaluate_policy
from .runtime_target import GENERATED_CAPABILITY_METADATA

DEFAULT_SERVICE_ID = "slack-governance-service"

def _first_non_empty(*values: str) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value
    return ""

def _unique_strings(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if not value or value in result:
            continue
        result.append(value)
    return result

def _effective_backend_input_contract(capability: dict[str, Any], selected_binding: dict[str, Any] | None) -> dict[str, Any]:
    mode = (selected_binding or {}).get("backend_input_mode") or capability.get("backend_input_mode") or "implicit"
    derived_required = (selected_binding or {}).get("derived_required_backend_inputs") or capability.get("derived_required_backend_inputs", [])
    derived_optional = (selected_binding or {}).get("derived_optional_backend_inputs") or capability.get("derived_optional_backend_inputs", [])
    explicit_required = (selected_binding or {}).get("explicit_required_backend_inputs") or capability.get("explicit_required_backend_inputs", [])
    explicit_optional = (selected_binding or {}).get("explicit_optional_backend_inputs") or capability.get("explicit_optional_backend_inputs", [])
    if mode == "explicit":
        required = _unique_strings(explicit_required)
        optional = [item for item in _unique_strings(explicit_optional) if item not in required]
        return {"mode": "explicit", "required": required, "optional": optional}
    if mode == "hybrid":
        required = _unique_strings([*derived_required, *explicit_required])
        optional = [item for item in _unique_strings([*derived_optional, *explicit_optional]) if item not in required]
        return {"mode": "hybrid", "required": required, "optional": optional}
    required = _unique_strings(derived_required)
    optional = [item for item in _unique_strings(derived_optional) if item not in required]
    return {"mode": "implicit", "required": required, "optional": optional}

def generated_metadata_for_capability(capability_id: str) -> dict[str, Any]:
    for metadata in GENERATED_CAPABILITY_METADATA:
        if metadata.get('capability_id') == capability_id:
            return metadata
    raise KeyError(f'Unknown generated capability: {capability_id}')

def generated_declaration_for_capability(capability_id: str) -> CapabilityDeclaration:
    return _build_declaration(generated_metadata_for_capability(capability_id))

def _select_backend_binding(capability: dict[str, Any]) -> dict[str, Any] | None:
    bindings = capability.get("backend_bindings", [])
    if not bindings:
        return None
    return bindings[0]

def _build_backend_invocation_plan(capability: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    selected_binding = _select_backend_binding(capability)
    contract = _effective_backend_input_contract(capability, selected_binding)
    semantic_keys = {item['input_name'] for item in capability.get('required_inputs', [])} | {item['input_name'] for item in capability.get('optional_inputs', [])}
    semantic_input = {key: value for key, value in params.items() if key in semantic_keys}
    adapter_keys = semantic_keys | set(contract["required"]) | set(contract["optional"])
    adapter_input = {key: value for key, value in params.items() if key in adapter_keys}
    unresolved = [key for key in contract['required'] if key not in params]
    return {
        "selected_binding": selected_binding,
        "semantic_input": semantic_input,
        "adapter_input": adapter_input,
        "backend_input_contract": contract,
        "unresolved_required_backend_inputs": unresolved,
    }

def _assert_required_semantic_inputs(capability: dict[str, Any], params: dict[str, Any]) -> None:
    missing = [item['input_name'] for item in capability.get('required_inputs', []) if not item.get('default_value') and params.get(item['input_name']) in (None, '')]
    if missing:
        raise ANIPError(
            "clarification_required",
            f"Required semantic inputs are missing for {capability['capability_id']}.",
            {"action": "clarify", "missing_inputs": missing, "required_by": capability["capability_id"]},
            retry=False,
        )

def _apply_input_defaults(capability: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(params)
    for item in [*capability.get('required_inputs', []), *capability.get('optional_inputs', [])]:
        name = item.get('input_name')
        default_value = item.get('default_value')
        if name and default_value not in (None, '') and normalized.get(name) in (None, ''):
            normalized[name] = default_value
    return normalized

def _validate_input_behavior(capability: dict[str, Any], params: dict[str, Any]) -> None:
    for item in [*capability.get('required_inputs', []), *capability.get('optional_inputs', [])]:
        name = item.get('input_name')
        if not name or params.get(name) in (None, ''):
            continue
        value = params.get(name)
        allowed_values = item.get('allowed_values') or []
        if allowed_values and str(value) not in {str(allowed) for allowed in allowed_values}:
            raise ANIPError(
                "clarification_required",
                item.get("clarification_hint") or f"Input {name} must use one of the declared allowed values.",
                {"action": "provide_allowed_value", "requires": name, "allowed_values": allowed_values},
                retry=False,
            )
        pattern = item.get('validation_pattern')
        if not pattern and item.get("input_format") == "business_quarter":
            pattern = r"^\d{4}-Q[1-4]$"
        if pattern and not re.match(str(pattern), str(value)):
            raise ANIPError(
                "clarification_required",
                item.get("clarification_hint") or f"Input {name} does not match the declared format.",
                {"action": "provide_valid_input", "requires": name, "format": item.get("input_format") or pattern},
                retry=False,
            )

def _side_effect_type(side_effect_level: str) -> str:
    value = side_effect_level.lower()
    if "irreversible" in value:
        return "irreversible"
    if "transaction" in value:
        return "transactional"
    if "write" in value:
        return "write"
    return "read"

def _resolve_json_path(payload: dict[str, Any], path: str | None) -> Any:
    if not path or not path.startswith('$.'):
        return None
    current: Any = payload
    for part in path[2:].split('.'):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current

def _is_empty_result(payload: Any) -> bool:
    target = payload.get('result') if isinstance(payload, dict) else payload
    if isinstance(target, dict):
        if target.get('empty') is True:
            return True
        for key in ('accounts', 'items', 'rows', 'results', 'tasks'):
            if key in target and target.get(key) == []:
                return True
    return target == []

async def _invoke_composition_child(capability_registry: dict[str, Capability], capability_id: str, ctx: InvocationContext, params: dict[str, Any]) -> Any:
    child = capability_registry.get(capability_id)
    if child is None:
        raise ANIPError('temporarily_unavailable', f'Generated composition child {capability_id} is not registered.')
    result = child.handler(ctx, params)
    if inspect.isawaitable(result):
        result = await result
    return result

async def _execute_generated_composition(capability: dict[str, Any], ctx: InvocationContext, params: dict[str, Any], capability_registry: dict[str, Capability] | None) -> dict[str, Any]:
    if capability_registry is None:
        raise ANIPError('temporarily_unavailable', f'Generated composition {capability["capability_id"]} requires a capability registry.')
    composition = capability.get('composition') or {}
    if composition.get('authority_boundary') != 'same_service':
        raise ANIPError('temporarily_unavailable', 'Generated Python host only executes same-service composition locally.')
    state: dict[str, Any] = {'steps': {}}
    input_mapping = composition.get('input_mapping') or {}
    for step in composition.get('steps') or []:
        step_id = step.get('id')
        child_capability = step.get('capability')
        if not step_id or not child_capability:
            raise ANIPError('temporarily_unavailable', 'Generated composition step is missing id or capability.')
        child_params = dict(params)
        mapping = input_mapping.get(step_id) or {}
        context = _resolve_json_path(state, mapping.get('context')) if isinstance(mapping, dict) else None
        if context is not None:
            child_params['context'] = context
        child_output = await _invoke_composition_child(capability_registry, child_capability, ctx, child_params)
        state['steps'][step_id] = {'output': child_output}
        if step.get('empty_result_source') is True and _is_empty_result(child_output):
            if composition.get('empty_result_policy') == 'return_success_no_results':
                return composition.get('empty_result_output') or {'result': None, 'empty': True}
    output_mapping = composition.get('output_mapping') or {}
    result = _resolve_json_path(state, output_mapping.get('result'))
    if result is None:
        return {'result': state}
    if isinstance(result, dict) and 'result' in result and len(result) == 1:
        return result
    return {'result': result}

async def _handle_generated_capability(capability: dict[str, Any], ctx: InvocationContext, params: dict[str, Any], capability_registry: dict[str, Capability] | None = None) -> dict[str, Any]:
    params = _apply_input_defaults(capability, params)
    _assert_required_semantic_inputs(capability, params)
    _validate_input_behavior(capability, params)
    policy = await evaluate_policy({"capability": capability, "params": params, "root_principal": ctx.root_principal, "token": ctx.token})
    if policy.get("decision") == "deny":
        raise ANIPError("denied", policy.get("detail") or f"Request denied for {capability['capability_id']}.")
    if policy.get("decision") == "no_match" and (capability.get("kind") or "atomic") != "composed":
        raise ANIPError("denied", policy.get("detail") or f"Request denied for {capability['capability_id']}.")
    if policy.get("decision") == "clarify":
        raise ANIPError("clarification_required", policy.get("detail") or f"Clarification required for {capability['capability_id']}.")
    if (capability.get("kind") or "atomic") == "composed":
        return await _execute_generated_composition(capability, ctx, params, capability_registry)
    plan = _build_backend_invocation_plan(capability, params)
    if policy.get("decision") == "approval_required" or capability.get("execution_posture") == "approval_gated":
        if capability["capability_id"] == "slack.announcement.request":
            prepared = await backend_adapter.execute(capability, plan, plan["adapter_input"], ctx)
            if prepared.get("execution_status") != "backend_execution_stub":
                if ctx.approval_grant is None:
                    raise ANIPError(
                        "approval_required",
                        "Slack announcement posting requires an ANIP approval grant before send.",
                        approval_required={"preview": prepared},
                    )
                return prepared
        return {
            "execution_status": "approval_required",
            "capability_id": capability["capability_id"],
            "title": capability["title"],
            "summary": capability["summary"],
            "semantic_input": plan["semantic_input"],
            "backend_input_contract": plan["backend_input_contract"],
            "approval_rule_refs": capability.get("governance", {}).get("approval_rule_refs", []),
            "note": "Generated host requires approval before backend execution.",
        }
    if capability.get("execution_posture") == "prepare_only":
        if capability["capability_id"] in {"slack.message.prepare", "slack.incident_update.prepare"}:
            prepared = await backend_adapter.execute(capability, plan, plan["adapter_input"], ctx)
            if prepared.get("execution_status") != "backend_execution_stub":
                if params.get("request_send_approval") is True and ctx.approval_grant is None:
                    raise ANIPError(
                        "approval_required",
                        "Slack message sending requires an ANIP approval grant before send.",
                        approval_required={"preview": prepared},
                    )
                return prepared
        return {
            "execution_status": "prepared",
            "capability_id": capability["capability_id"],
            "semantic_input": plan["semantic_input"],
            "backend_input_contract": plan["backend_input_contract"],
            "note": "Generated host prepared a governed preview and did not execute the backend.",
        }
    return await backend_adapter.execute(capability, plan, plan["adapter_input"], ctx)

def _build_declaration(capability: dict[str, Any]) -> CapabilityDeclaration:
    inputs = [
        CapabilityInput(name=item['input_name'], type=item.get('input_type') or 'string', required=True, default=item.get('default_value') or None, allowed_values=item.get('allowed_values') or [], description=item.get('summary') or item['input_name'])
        for item in capability.get('required_inputs', [])
    ] + [
        CapabilityInput(name=item['input_name'], type=item.get('input_type') or 'string', required=False, default=item.get('default_value') or None, allowed_values=item.get('allowed_values') or [], description=item.get('summary') or item['input_name'])
        for item in capability.get('optional_inputs', [])
    ]
    rollback_window = 'not_applicable' if _side_effect_type(capability.get('side_effect_level', 'read')) == 'read' else 'none' if _side_effect_type(capability.get('side_effect_level', 'read')) == 'irreversible' else 'PT15M'
    return CapabilityDeclaration(
        name=capability["capability_id"],
        description=capability["summary"],
        contract_version="1.0",
        inputs=inputs,
        output=CapabilityOutput(type=capability.get('output_shape') or 'governed_result', fields=['execution_status', 'capability_id', 'semantic_input']),
        side_effect=SideEffect(type=_side_effect_type(capability.get('side_effect_level', 'read')), rollback_window=rollback_window),
        minimum_scope=capability.get("minimum_scope", []),
        requires=[],
        composes_with=[],
        session=SessionInfo(type='stateless'),
        response_modes=['unary'],
        requires_binding=[],
        control_requirements=[],
        refresh_via=[],
        verify_via=[],
        kind=capability.get("kind") or "atomic",
        composition=capability.get("composition"),
        grant_policy=capability.get("grant_policy"),
    )

def build_capabilities(service_id: str | None = None, capability_registry: dict[str, Capability] | None = None) -> list[Capability]:
    capabilities: list[Capability] = []
    registry: dict[str, Capability] = dict(capability_registry or {})
    for metadata in GENERATED_CAPABILITY_METADATA:
        if service_id is not None and metadata.get('service_id') != service_id:
            continue
        if metadata['capability_id'] in registry:
            continue
        async def handler(ctx: InvocationContext, params: dict[str, Any], capability: dict[str, Any] = metadata, registry: dict[str, Capability] = registry) -> dict[str, Any]:
            return await _handle_generated_capability(capability, ctx, params, registry)
        capability = Capability(declaration=_build_declaration(metadata), handler=handler)
        capabilities.append(capability)
        registry[metadata['capability_id']] = capability
    return capabilities

def generated_capabilities_for_service(service_id: str, capability_registry: dict[str, Capability] | None = None) -> list[Capability]:
    return build_capabilities(service_id, capability_registry)

generated_capabilities = generated_capabilities_for_service(DEFAULT_SERVICE_ID)
