"""Delegation chain validation.

Validates the full delegation DAG: token expiry, scope sufficiency,
purpose binding, delegation depth, and concurrent branch constraints.

Tokens are persisted in SQLite for durability and audit trail.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..data.database import load_token as db_load_token
from ..data.database import store_token as db_store_token
from .models import ANIPFailure, DelegationToken, Resolution


def register_token(token: DelegationToken) -> None:
    """Register a delegation token, persisting to SQLite."""
    db_store_token({
        "token_id": token.token_id,
        "issuer": token.issuer,
        "subject": token.subject,
        "scope": token.scope,
        "purpose": token.purpose.model_dump(),
        "parent": token.parent,
        "expires": token.expires.isoformat(),
        "constraints": token.constraints.model_dump(),
    })


def get_token(token_id: str) -> DelegationToken | None:
    """Load a delegation token from the persistent store."""
    data = db_load_token(token_id)
    if data is None:
        return None
    return DelegationToken(**data)


def get_chain(token: DelegationToken) -> list[DelegationToken]:
    """Walk the DAG upward from a token to the root, returning the full chain."""
    chain = [token]
    current = token
    while current.parent is not None:
        parent = get_token(current.parent)
        if parent is None:
            break
        chain.append(parent)
        current = parent
    return list(reversed(chain))  # root first


def get_root_principal(token: DelegationToken) -> str:
    """Get the root principal (human) from a delegation chain."""
    chain = get_chain(token)
    return chain[0].issuer


def get_chain_token_ids(token: DelegationToken) -> list[str]:
    """Get the list of token IDs in the delegation chain (for audit logging)."""
    return [t.token_id for t in get_chain(token)]


def validate_delegation(
    token: DelegationToken,
    minimum_scope: list[str],
    capability_name: str,
) -> ANIPFailure | None:
    """Validate a delegation token for invoking a capability.

    Returns None if valid, or an ANIPFailure describing what's wrong.
    """
    # 1. Check expiry
    if token.expires < datetime.now(timezone.utc):
        return ANIPFailure(
            type="token_expired",
            detail=f"delegation token {token.token_id} expired at {token.expires.isoformat()}",
            resolution=Resolution(
                action="request_new_delegation",
                grantable_by=token.issuer,
            ),
            retry=True,
        )

    # 2. Check scope — the token must carry ALL required scopes (prefix match)
    token_scope_bases = [s.split(":")[0] for s in token.scope]  # "travel.book:max_$500" → "travel.book"
    missing_scopes = []
    for required_scope in minimum_scope:
        scope_matched = any(
            scope_base == required_scope or required_scope.startswith(scope_base + ".")
            for scope_base in token_scope_bases
        )
        if not scope_matched:
            missing_scopes.append(required_scope)
    if missing_scopes:
        root_principal = get_root_principal(token)
        return ANIPFailure(
            type="insufficient_authority",
            detail=f"delegation chain lacks scope(s): {', '.join(missing_scopes)}",
            resolution=Resolution(
                action="request_scope_grant",
                requires=f"delegation.scope += {', '.join(missing_scopes)}",
                grantable_by=root_principal,
            ),
            retry=True,
        )

    # 3. Check purpose binding — token purpose must match the capability
    if token.purpose.capability != capability_name:
        return ANIPFailure(
            type="purpose_mismatch",
            detail=(
                f"delegation token purpose is {token.purpose.capability} "
                f"but request is for {capability_name}"
            ),
            resolution=Resolution(
                action="request_new_delegation",
                grantable_by=token.issuer,
            ),
            retry=True,
        )

    # 4. Check delegation depth — walk the chain and count
    chain = get_chain(token)
    max_depth = token.constraints.max_delegation_depth
    # Depth is number of delegations (edges), not nodes
    actual_depth = len(chain) - 1
    if actual_depth > max_depth:
        return ANIPFailure(
            type="delegation_depth_exceeded",
            detail=f"delegation chain depth is {actual_depth}, max allowed is {max_depth}",
            resolution=Resolution(
                action="reduce_delegation_depth",
                requires=f"max_delegation_depth >= {actual_depth}",
                grantable_by=get_root_principal(token),
            ),
            retry=True,
        )

    # 5. concurrent_branches — NOT YET ENFORCED
    # The spec requires that when constraints.concurrent_branches == "exclusive",
    # the service MUST reject concurrent requests from the same root principal.
    # Enforcement requires session-level state tracking (e.g., active request
    # counting per root_principal). This is declared but not enforced in v0.1.
    # See: SPEC.md § Delegation Chain, concurrent_branches constraint.

    # 6. Validate parent chain — every parent must also be valid and not expired
    for ancestor in chain[:-1]:  # all except the current token
        if ancestor.expires < datetime.now(timezone.utc):
            return ANIPFailure(
                type="parent_token_expired",
                detail=f"ancestor token {ancestor.token_id} in delegation chain has expired",
                resolution=Resolution(
                    action="refresh_delegation_chain",
                    grantable_by=ancestor.issuer,
                ),
                retry=True,
            )

    return None  # all checks passed


def check_budget_authority(token: DelegationToken, amount: float) -> ANIPFailure | None:
    """Check if the delegation chain carries sufficient budget authority."""
    for scope in token.scope:
        if ":max_$" in scope:
            max_budget = float(scope.split(":max_$")[1])
            if amount > max_budget:
                return ANIPFailure(
                    type="budget_exceeded",
                    detail=f"capability costs ${amount} but delegation chain authority is max ${max_budget}",
                    resolution=Resolution(
                        action="request_budget_increase",
                        requires=f"delegation.scope budget raised to ${amount}",
                        grantable_by=get_root_principal(token),
                    ),
                    retry=True,
                )
    return None
