"""Generated capability declarations and handlers."""
from __future__ import annotations

from typing import Any

from anip_core import CapabilityDeclaration, CapabilityInput, CapabilityOutput, SessionInfo, SideEffect
from anip_service import ANIPError, Capability, InvocationContext

from .backend_adapter import backend_adapter
from .policy import evaluate_policy
from .runtime_target import GENERATED_CAPABILITY_METADATA

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
    unresolved = [key for key in contract['required'] if key not in params]
    return {
        "selected_binding": selected_binding,
        "semantic_input": semantic_input,
        "backend_input_contract": contract,
        "unresolved_required_backend_inputs": unresolved,
    }

def _assert_required_semantic_inputs(capability: dict[str, Any], params: dict[str, Any]) -> None:
    missing = [item['input_name'] for item in capability.get('required_inputs', []) if params.get(item['input_name']) in (None, '')]
    if missing:
        raise ANIPError(
            "clarification_required",
            f"Required semantic inputs are missing for {capability['capability_id']}.",
            {"action": "clarify", "missing_inputs": missing, "required_by": capability["capability_id"]},
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

async def _handle_generated_capability(capability: dict[str, Any], _ctx: InvocationContext, params: dict[str, Any]) -> dict[str, Any]:
    _assert_required_semantic_inputs(capability, params)
    policy = await evaluate_policy({"capability": capability, "params": params})
    if policy.get("decision") == "deny":
        raise ANIPError("access_denied", policy.get("detail") or f"Request denied for {capability['capability_id']}.")
    if policy.get("decision") == "clarify":
        raise ANIPError("clarification_required", policy.get("detail") or f"Clarification required for {capability['capability_id']}.")
    plan = _build_backend_invocation_plan(capability, params)
    if policy.get("decision") == "approval_required" or capability.get("execution_posture") == "approval_gated":
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
        return {
            "execution_status": "prepared",
            "capability_id": capability["capability_id"],
            "semantic_input": plan["semantic_input"],
            "backend_input_contract": plan["backend_input_contract"],
            "note": "Generated host prepared a governed preview and did not execute the backend.",
        }
    return await backend_adapter.execute(capability, plan, params)

def _build_declaration(capability: dict[str, Any]) -> CapabilityDeclaration:
    inputs = [
        CapabilityInput(name=item['input_name'], type=item.get('input_type') or 'string', required=True, default=None, description=item.get('summary') or item['input_name'])
        for item in capability.get('required_inputs', [])
    ] + [
        CapabilityInput(name=item['input_name'], type=item.get('input_type') or 'string', required=False, default=None, description=item.get('summary') or item['input_name'])
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
    )

def build_capabilities() -> list[Capability]:
    capabilities: list[Capability] = []
    for metadata in GENERATED_CAPABILITY_METADATA:
        async def handler(ctx: InvocationContext, params: dict[str, Any], capability: dict[str, Any] = metadata) -> dict[str, Any]:
            return await _handle_generated_capability(capability, ctx, params)
        capabilities.append(Capability(declaration=_build_declaration(metadata), handler=handler))
    return capabilities

generated_capabilities = build_capabilities()
