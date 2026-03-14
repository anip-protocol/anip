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

        if not missing:
            constraints: dict = {}
            for scope_str in matched_scope_strs:
                if ":max_$" in scope_str:
                    max_budget = float(scope_str.split(":max_$")[1])
                    constraints["budget_remaining"] = max_budget
                    constraints["currency"] = "USD"
            available.append(
                AvailableCapability(
                    capability=name,
                    scope_match=", ".join(matched_scope_strs),
                    constraints=constraints,
                )
            )
        elif any(s.startswith("admin.") for s in missing):
            denied.append(
                DeniedCapability(capability=name, reason="requires admin principal")
            )
        else:
            restricted.append(
                RestrictedCapability(
                    capability=name,
                    reason=f"delegation chain lacks scope(s): {', '.join(missing)}",
                    grantable_by=root_principal,
                )
            )

    return PermissionResponse(
        available=available, restricted=restricted, denied=denied
    )
