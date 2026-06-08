"""Policy seam for generated capabilities."""
from __future__ import annotations

from typing import Any

from .runtime_target import GENERATED_RUNTIME_TARGET

POLICY_BINDINGS = GENERATED_RUNTIME_TARGET.get('policy_bindings', [])

def _principal_claims(root_principal: str | None) -> dict[str, str]:
    raw = (root_principal or '').strip()
    if not raw:
        return {}
    pieces = raw.split('|')
    claims: dict[str, str] = {'principal': pieces[0]}
    for piece in pieces[1:]:
        if '=' not in piece:
            continue
        key, value = piece.split('=', 1)
        claims[key.strip()] = value.strip()
    return claims

def _matches_principal(binding: dict[str, Any], claims: dict[str, str]) -> bool:
    selector = binding.get('principal_selector') or {}
    claim = str(selector.get('claim') or 'actor_id')
    expected = str(selector.get('equals') or binding.get('actor_id') or '')
    if not expected:
        return True
    if claim not in claims:
        return False
    return claims.get(claim) == expected

def _requires_governed_stop(capability: dict[str, Any]) -> bool:
    return bool(capability.get('grant_policy')) or capability.get('side_effect_level') == 'approval_required' or capability.get('execution_posture') == 'approval_required' or capability.get('operation_type') == 'approval_gated'

def _decision_for(binding: dict[str, Any]) -> dict[str, Any]:
    decision = str(binding.get('decision') or 'allow')
    detail = binding.get('business_rule') or binding.get('enforcement_notes')
    if decision == 'allow_with_limits':
        return {'decision': 'allow', 'limits': binding, 'detail': detail}
    if decision in {'deny', 'clarify', 'approval_required'}:
        return {'decision': decision, 'detail': detail, 'policy_binding_id': binding.get('id')}
    return {'decision': 'allow', 'policy_binding_id': binding.get('id'), 'detail': detail}

async def evaluate_policy(context: dict[str, Any]) -> dict[str, Any]:
    capability = context.get('capability') or {}
    capability_id = capability.get('capability_id')
    bindings = [binding for binding in POLICY_BINDINGS if capability_id in (binding.get('capability_ids') or [])]
    if not bindings:
        return {"decision": "allow"}
    claims = _principal_claims(context.get('root_principal'))
    if not claims:
        return {"decision": "allow", "note": "No actor claims were available for generated policy evaluation."}
    matching = [binding for binding in bindings if _matches_principal(binding, claims)]
    if _requires_governed_stop(capability):
        denied = next((binding for binding in matching if binding.get('decision') == 'deny'), None)
        if denied:
            return _decision_for(denied)
        approval = next((binding for binding in matching if binding.get('decision') == 'approval_required'), None)
        if approval:
            return _decision_for(approval)
        clarify = next((binding for binding in matching if binding.get('decision') == 'clarify'), None)
        if clarify:
            return _decision_for(clarify)
    allowed = next((binding for binding in matching if binding.get('decision') not in {'deny', 'clarify', 'approval_required'}), None)
    if allowed:
        return _decision_for(allowed)
    return {"decision": "allow", "detail": "No matching runtime policy binding; continuing."}
