"""Permission discovery — query what you can do before trying it."""
from __future__ import annotations

from anip_core import (
    AvailableCapability,
    CapabilityDeclaration,
    DelegationToken,
    DeniedCapability,
    PermissionResponse,
    RestrictedCapability,
)


def discover_permissions(
    token: DelegationToken,
    capabilities: dict[str, CapabilityDeclaration],
) -> PermissionResponse:
    """Given a delegation token, return what the agent can and can't do."""
    available: list[AvailableCapability] = []
    restricted: list[RestrictedCapability] = []
    denied: list[DeniedCapability] = []

    token_scope_bases = [(s.split(":")[0], s) for s in token.scope]
    root_principal = token.root_principal or token.issuer
    constraints_obj = token.constraints

    for name, cap in capabilities.items():
        required_scopes = cap.minimum_scope
        matched_scope_strs: list[str] = []
        missing: list[str] = []
        for required in required_scopes:
            matched_full = None
            for scope_base, full_scope in token_scope_bases:
                if scope_base == required or required.startswith(scope_base + "."):
                    matched_full = full_scope
                    break
            if matched_full is not None:
                matched_scope_strs.append(matched_full)
            else:
                missing.append(required)

        if missing:
            if len(missing) == len(required_scopes):
                # No scope overlap at all — completely inaccessible
                denied.append(
                    DeniedCapability(
                        capability=name,
                        reason=f"delegation chain lacks all required scope(s): {', '.join(missing)}",
                        reason_type="insufficient_scope",
                    )
                )
            else:
                restricted.append(
                    RestrictedCapability(
                        capability=name,
                        reason=f"delegation chain lacks scope(s): {', '.join(missing)}",
                        reason_type="insufficient_scope",
                        grantable_by=root_principal,
                        resolution_hint="request_broader_scope",
                    )
                )
            continue

        # Scope matched — check token-evaluable control requirements
        unmet: list[str] = []
        for req in cap.control_requirements:
            if req.type == "cost_ceiling" and (not constraints_obj or not constraints_obj.budget):
                unmet.append("cost_ceiling")
            elif req.type == "stronger_delegation_required":
                # Check if token has explicit capability binding via purpose
                token_has_explicit_binding = (
                    token.purpose is not None
                    and token.purpose.capability == name
                )
                if not token_has_explicit_binding:
                    unmet.append("stronger_delegation_required")

        if unmet and any(
            r.enforcement == "reject"
            for r in cap.control_requirements
            if r.type in unmet
        ):
            # Determine the most specific resolution hint based on unmet requirements
            if "cost_ceiling" in unmet:
                ctrl_resolution_hint = "request_budget_bound_delegation"
            else:
                ctrl_resolution_hint = "request_capability_binding"
            restricted.append(
                RestrictedCapability(
                    capability=name,
                    reason=f"missing control requirements: {', '.join(unmet)}",
                    reason_type="unmet_control_requirement",
                    grantable_by=root_principal,
                    unmet_token_requirements=unmet,
                    resolution_hint=ctrl_resolution_hint,
                )
            )
            continue

        # All checks passed — capability is available
        constraints: dict = {}
        for scope_str in matched_scope_strs:
            if ":max_$" in scope_str:
                max_budget = float(scope_str.split(":max_$")[1])
                constraints["budget_remaining"] = max_budget
                constraints["currency"] = "USD"
        # Include constraints-level budget info if present
        if constraints_obj and constraints_obj.budget:
            constraints["budget_remaining"] = constraints_obj.budget.max_amount
            constraints["currency"] = constraints_obj.budget.currency
        available.append(
            AvailableCapability(
                capability=name,
                scope_match=", ".join(matched_scope_strs),
                constraints=constraints,
            )
        )

    return PermissionResponse(
        available=available, restricted=restricted, denied=denied
    )
