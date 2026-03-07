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
        required = cap.required_scope

        if required in token_scopes:
            scope_str = token_scopes[required]
            constraints: dict = {}

            # Extract budget constraint if present
            if ":max_$" in scope_str:
                max_budget = float(scope_str.split(":max_$")[1])
                constraints["budget_remaining"] = max_budget
                constraints["currency"] = "USD"

            available.append(
                AvailableCapability(
                    capability=name,
                    scope_match=scope_str,
                    constraints=constraints,
                )
            )
        elif _is_admin_scope(required):
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
                    reason=f"delegation chain lacks scope: {required}",
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
