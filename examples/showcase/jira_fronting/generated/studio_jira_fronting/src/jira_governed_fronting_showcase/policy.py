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

_KNOWN_DECISIONS = {'allow', 'allow_with_limits', 'deny', 'clarify', 'approval_required'}
_REFUSING_PRECEDENCE = ('deny', 'approval_required', 'clarify')

def _effective_decision(binding: dict[str, Any]) -> str:
    decision = str(binding.get('decision') or '')
    # A decision the host does not recognise refuses rather than allows.
    return decision if decision in _KNOWN_DECISIONS else 'deny'

def _decision_for(binding: dict[str, Any]) -> dict[str, Any]:
    decision = _effective_decision(binding)
    detail = binding.get('business_rule') or binding.get('enforcement_notes')
    if decision == 'allow_with_limits':
        return {'decision': 'allow', 'limits': binding, 'detail': detail}
    if decision in _REFUSING_PRECEDENCE:
        return {'decision': decision, 'detail': detail, 'policy_binding_id': binding.get('id')}
    return {'decision': 'allow', 'policy_binding_id': binding.get('id'), 'detail': detail}

async def evaluate_policy(context: dict[str, Any]) -> dict[str, Any]:
    capability = context.get('capability') or {}
    capability_id = capability.get('capability_id')
    bindings = [binding for binding in POLICY_BINDINGS if capability_id in (binding.get('capability_ids') or [])]
    if not bindings:
        # A capability without bindings is allowed: bindings are capability-level overrides.
        return {"decision": "allow"}
    claims = _principal_claims(context.get('root_principal'))
    # Once a capability has bindings they are its allowlist: an actor matching none, or a
    # principal without claims, is refused.
    matching = [binding for binding in bindings if claims and _matches_principal(binding, claims)]
    if not matching:
        return {"decision": "deny", "detail": "No runtime policy binding matches the current actor for this capability."}
    for decision in _REFUSING_PRECEDENCE:
        stop = next((binding for binding in matching if _effective_decision(binding) == decision), None)
        if stop:
            return _decision_for(stop)
    return _decision_for(matching[0])
