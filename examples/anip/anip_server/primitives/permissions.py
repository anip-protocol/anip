"""Permission discovery — query what you can do before trying it."""

from __future__ import annotations

from .delegation import get_root_principal
from .models import (
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

    token_scopes = {s.split(":")[0]: s for s in token.scope}
    root_principal = get_root_principal(token)

    for name, cap in capabilities.items():
        required_scopes = cap.minimum_scope

        # Check if all required scopes are present in token
        missing = [s for s in required_scopes if s not in token_scopes]

        if not missing:
            # All scopes matched — collect constraints from all matching scopes
            constraints: dict = {}
            matched_scope_strs = [token_scopes[s] for s in required_scopes if s in token_scopes]

            # Extract budget constraint if present in any matched scope
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
        elif any(_is_admin_scope(s) for s in missing):
            denied.append(
                DeniedCapability(
                    capability=name,
                    reason=f"requires admin principal, current chain root is standard user",
                )
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
        available=available,
        restricted=restricted,
        denied=denied,
    )


def _is_admin_scope(scope: str) -> bool:
    return scope.startswith("admin.")
