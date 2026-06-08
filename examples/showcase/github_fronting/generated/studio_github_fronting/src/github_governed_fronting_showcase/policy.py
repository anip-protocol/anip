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
        return True
    return claims.get(claim) == expected

async def evaluate_policy(context: dict[str, Any]) -> dict[str, Any]:
    capability = context.get('capability') or {}
    capability_id = capability.get('capability_id')
    bindings = [binding for binding in POLICY_BINDINGS if capability_id in (binding.get('capability_ids') or [])]
    if not bindings:
        return {"decision": "allow"}
    claims = _principal_claims(context.get('root_principal'))
    if not claims:
        return {"decision": "allow", "note": "No actor claims were available for generated policy evaluation."}
    for binding in bindings:
        if not _matches_principal(binding, claims):
            continue
        decision = str(binding.get('decision') or 'allow')
        if decision == 'allow_with_limits':
            return {'decision': 'allow', 'limits': binding, 'detail': binding.get('business_rule') or binding.get('enforcement_notes')}
        if decision in {'deny', 'clarify', 'approval_required'}:
            return {'decision': decision, 'detail': binding.get('business_rule') or binding.get('enforcement_notes'), 'policy_binding_id': binding.get('id')}
        return {'decision': 'allow', 'policy_binding_id': binding.get('id')}
    return {"decision": "no_match", "detail": "No runtime policy binding matched the current actor for this capability."}
