"""Delegation chain validation.

Validates the full delegation DAG: token expiry, scope sufficiency,
purpose binding, delegation depth, and concurrent branch constraints.

Tokens are persisted in SQLite for durability and audit trail.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..data.database import load_token as db_load_token
from ..data.database import store_token as db_store_token
from .models import ANIPFailure, ConcurrentBranches, DelegationToken, Resolution

# Active request tracking for concurrent_branches enforcement
_active_requests: set[str] = set()


def validate_parent_exists(token: DelegationToken) -> ANIPFailure | None:
    """Validate that a token's parent exists in the store.

    Returns None if valid (or no parent), or an ANIPFailure if the parent is missing.
    """
    if token.parent is None:
        return None  # root token
    parent = get_token(token.parent)
    if parent is None:
        return ANIPFailure(
            type="parent_not_found",
            detail=f"parent token '{token.parent}' is not registered",
            resolution=Resolution(
                action="register_parent_token_first",
                requires=f"token '{token.parent}' must be registered before its children",
                grantable_by=token.issuer,
            ),
            retry=True,
        )
    return None


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

    # 4. Verify the delegation chain is complete (no missing ancestors)
    chain = get_chain(token)
    # If the token has a parent but get_chain didn't reach a root (parent=None),
    # the chain is broken — an ancestor is unregistered
    if chain[0].parent is not None:
        return ANIPFailure(
            type="broken_delegation_chain",
            detail=f"delegation chain is incomplete — ancestor token '{chain[0].parent}' is not registered",
            resolution=Resolution(
                action="register_missing_ancestor",
                grantable_by=token.issuer,
            ),
            retry=True,
        )

    # 5. Check delegation depth
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

    # 6. Enforce concurrent_branches — reject if exclusive and another request is active
    if token.constraints.concurrent_branches == ConcurrentBranches.EXCLUSIVE:
        root = get_root_principal(token)
        if root in _active_requests:
            return ANIPFailure(
                type="concurrent_request_rejected",
                detail=f"concurrent_branches is exclusive and another request from {root} is in progress",
                resolution=Resolution(
                    action="wait_and_retry",
                    grantable_by=root,
                ),
                retry=True,
            )

    # 7. Validate parent chain — every parent must also be valid and not expired
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


def acquire_exclusive_lock(token: DelegationToken) -> None:
    """Mark a root principal as having an active request."""
    if token.constraints.concurrent_branches == ConcurrentBranches.EXCLUSIVE:
        _active_requests.add(get_root_principal(token))


def release_exclusive_lock(token: DelegationToken) -> None:
    """Release the active request lock for a root principal."""
    if token.constraints.concurrent_branches == ConcurrentBranches.EXCLUSIVE:
        _active_requests.discard(get_root_principal(token))


def validate_scope_narrowing(token: DelegationToken) -> ANIPFailure | None:
    """Validate that a child token's scope is a subset of its parent's scope.

    Returns None if valid (or no parent), or an ANIPFailure if scope widens.
    """
    if token.parent is None:
        return None  # root tokens have no parent to narrow from

    parent = get_token(token.parent)
    if parent is None:
        return ANIPFailure(
            type="parent_not_found",
            detail=f"parent token '{token.parent}' is not registered — cannot validate scope narrowing",
            resolution=Resolution(
                action="register_parent_token_first",
                requires=f"token '{token.parent}' must be registered before its children",
                grantable_by=token.issuer,
            ),
            retry=True,
        )

    parent_scope_bases = {s.split(":")[0] for s in parent.scope}

    for child_scope in token.scope:
        child_base = child_scope.split(":")[0]
        # Child scope base must match or be narrower than a parent scope base
        matched = any(
            child_base == parent_base or child_base.startswith(parent_base + ".")
            for parent_base in parent_scope_bases
        )
        if not matched:
            return ANIPFailure(
                type="scope_escalation",
                detail=f"child token scope '{child_base}' is not a subset of parent token scopes: {', '.join(sorted(parent_scope_bases))}",
                resolution=Resolution(
                    action="narrow_scope",
                    requires=f"child scope must be subset of parent scope",
                    grantable_by=parent.issuer,
                ),
                retry=False,
            )

        # Check budget constraints: if parent has a budget on this scope,
        # child MUST preserve it (same or tighter). Dropping it is escalation.
        for parent_scope_str in parent.scope:
            parent_base = parent_scope_str.split(":")[0]
            if parent_base == child_base and ":max_$" in parent_scope_str:
                parent_budget = float(parent_scope_str.split(":max_$")[1])
                if ":max_$" not in child_scope:
                    # Child dropped the budget constraint entirely
                    return ANIPFailure(
                        type="scope_escalation",
                        detail=f"child dropped budget constraint from scope '{child_base}' (parent has max ${parent_budget})",
                        resolution=Resolution(
                            action="preserve_budget_constraint",
                            requires=f"scope '{child_base}' must include budget <= ${parent_budget}",
                            grantable_by=parent.issuer,
                        ),
                        retry=False,
                    )
                child_budget = float(child_scope.split(":max_$")[1])
                if child_budget > parent_budget:
                    return ANIPFailure(
                        type="scope_escalation",
                        detail=f"child budget ${child_budget} exceeds parent budget ${parent_budget} for scope '{child_base}'",
                        resolution=Resolution(
                            action="narrow_budget",
                            requires=f"budget must be <= ${parent_budget}",
                            grantable_by=parent.issuer,
                        ),
                        retry=False,
                    )

    return None


def validate_constraints_narrowing(token: DelegationToken) -> ANIPFailure | None:
    """Validate that a child token's constraints don't weaken its parent's.

    Returns None if valid (or no parent), or an ANIPFailure if constraints widen.
    """
    if token.parent is None:
        return None

    parent = get_token(token.parent)
    if parent is None:
        return None  # parent existence is checked separately

    # max_delegation_depth: child cannot raise it
    if token.constraints.max_delegation_depth > parent.constraints.max_delegation_depth:
        return ANIPFailure(
            type="constraint_escalation",
            detail=(
                f"child max_delegation_depth ({token.constraints.max_delegation_depth}) "
                f"exceeds parent ({parent.constraints.max_delegation_depth})"
            ),
            resolution=Resolution(
                action="narrow_constraints",
                requires=f"max_delegation_depth must be <= {parent.constraints.max_delegation_depth}",
                grantable_by=parent.issuer,
            ),
            retry=False,
        )

    # concurrent_branches: child cannot weaken from exclusive to allowed
    if (
        parent.constraints.concurrent_branches == ConcurrentBranches.EXCLUSIVE
        and token.constraints.concurrent_branches == ConcurrentBranches.ALLOWED
    ):
        return ANIPFailure(
            type="constraint_escalation",
            detail="child weakened concurrent_branches from 'exclusive' to 'allowed'",
            resolution=Resolution(
                action="preserve_constraint",
                requires="concurrent_branches must remain 'exclusive'",
                grantable_by=parent.issuer,
            ),
            retry=False,
        )

    return None


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
