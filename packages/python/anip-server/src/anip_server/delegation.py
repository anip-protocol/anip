"""Trust-safe delegation engine.

Wraps delegation logic with instance-level storage and enforces trust
boundaries at the API level:

- ``issue_root_token()`` creates root tokens with ``issuer`` derived from
  ``self._service_id`` and ``root_principal`` from ``authenticated_principal``.
- ``delegate()`` creates child tokens with ``issuer`` derived from
  ``parent_token.subject`` and ``root_principal`` inherited from the parent
  chain.  Validates scope narrowing before creation.

There is no raw ``issue_token(issuer_id=..., root_principal=...)`` in the
public API.
"""

from __future__ import annotations

import os
import socket
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from anip_core import (
    ANIPFailure,
    Budget,
    ConcurrentBranches,
    DelegationConstraints,
    DelegationToken,
    Purpose,
    Resolution,
    recovery_class_for_action,
)

from .storage import StorageBackend


class DelegationEngine:
    """Instance-scoped delegation engine backed by a :class:`StorageBackend`."""

    def __init__(
        self,
        storage: StorageBackend,
        *,
        service_id: str,
        exclusive_ttl: int = 60,
    ) -> None:
        self._storage = storage
        self._service_id = service_id
        self._exclusive_ttl = exclusive_ttl

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def issue_root_token(
        self,
        *,
        authenticated_principal: str,
        subject: str,
        scope: list[str],
        capability: str,
        purpose_parameters: dict[str, Any] | None = None,
        ttl_hours: int = 2,
        max_delegation_depth: int = 3,
        budget: Budget | None = None,
    ) -> tuple[DelegationToken, str]:
        """Issue a root delegation token.

        ``issuer`` is always ``self._service_id``.
        ``root_principal`` is always ``authenticated_principal``.

        Returns ``(token, token_id)``.
        """
        return await self._create_token(
            issuer=self._service_id,
            subject=subject,
            scope=scope,
            capability=capability,
            root_principal=authenticated_principal,
            parent_token=None,
            purpose_parameters=purpose_parameters,
            ttl_hours=ttl_hours,
            max_delegation_depth=max_delegation_depth,
            budget=budget,
        )

    async def delegate(
        self,
        *,
        parent_token: DelegationToken,
        subject: str,
        scope: list[str],
        capability: str,
        purpose_parameters: dict[str, Any] | None = None,
        ttl_hours: int = 2,
        budget: Budget | None = None,
    ) -> tuple[DelegationToken, str] | ANIPFailure:
        """Create a child delegation token from *parent_token*.

        ``issuer`` is derived from ``parent_token.subject``.
        ``root_principal`` is inherited from the parent chain.

        Returns ``(token, token_id)`` on success, or :class:`ANIPFailure` if
        scope widening or constraint escalation is detected.
        """
        root_principal = await self.get_root_principal(parent_token)

        # Pre-validate scope narrowing before creating the token
        parent_scope_bases = {s.split(":")[0] for s in parent_token.scope}
        for child_scope in scope:
            child_base = child_scope.split(":")[0]
            matched = any(
                child_base == parent_base or child_base.startswith(parent_base + ".")
                for parent_base in parent_scope_bases
            )
            if not matched:
                return ANIPFailure(
                    type="scope_escalation",
                    detail=(
                        f"child token scope '{child_base}' is not a subset of "
                        f"parent token scopes: {', '.join(sorted(parent_scope_bases))}"
                    ),
                    resolution=Resolution(
                        action="request_new_delegation",
                        recovery_class=recovery_class_for_action("request_new_delegation"),
                        requires="child scope must be subset of parent scope",
                        grantable_by=root_principal,
                    ),
                    retry=False,
                )

            # Check budget constraints
            for parent_scope_str in parent_token.scope:
                p_base = parent_scope_str.split(":")[0]
                if p_base == child_base and ":max_$" in parent_scope_str:
                    parent_budget = float(parent_scope_str.split(":max_$")[1])
                    if ":max_$" not in child_scope:
                        return ANIPFailure(
                            type="scope_escalation",
                            detail=(
                                f"child dropped budget constraint from scope "
                                f"'{child_base}' (parent has max ${parent_budget})"
                            ),
                            resolution=Resolution(
                                action="request_new_delegation",
                                recovery_class=recovery_class_for_action("request_new_delegation"),
                                requires=f"scope '{child_base}' must include budget <= ${parent_budget}",
                                grantable_by=root_principal,
                            ),
                            retry=False,
                        )
                    child_budget_amt = float(child_scope.split(":max_$")[1])
                    if child_budget_amt > parent_budget:
                        return ANIPFailure(
                            type="scope_escalation",
                            detail=(
                                f"child budget ${child_budget_amt} exceeds parent "
                                f"budget ${parent_budget} for scope '{child_base}'"
                            ),
                            resolution=Resolution(
                                action="request_new_delegation",
                                recovery_class=recovery_class_for_action("request_new_delegation"),
                                requires=f"budget must be <= ${parent_budget}",
                                grantable_by=root_principal,
                            ),
                            retry=False,
                        )

        # Enforce budget narrowing on constraints-level budget
        parent_constraints = parent_token.constraints
        if parent_constraints and parent_constraints.budget:
            if budget is None:
                # Child inherits parent budget
                budget = parent_constraints.budget
            elif budget.currency != parent_constraints.budget.currency:
                return ANIPFailure(
                    type="budget_currency_mismatch",
                    detail=f"Child budget currency {budget.currency} does not match parent {parent_constraints.budget.currency}",
                    resolution=Resolution(
                        action="request_matching_currency_delegation",
                        recovery_class=recovery_class_for_action("request_matching_currency_delegation"),
                        requires=f"budget currency must be {parent_constraints.budget.currency}",
                        grantable_by=root_principal,
                    ),
                    retry=False,
                )
            elif budget.max_amount > parent_constraints.budget.max_amount:
                return ANIPFailure(
                    type="budget_exceeded",
                    detail=f"Child budget ${budget.max_amount} exceeds parent budget ${parent_constraints.budget.max_amount}",
                    resolution=Resolution(
                        action="request_new_delegation",
                        recovery_class=recovery_class_for_action("request_new_delegation"),
                        requires=f"budget must be <= ${parent_constraints.budget.max_amount}",
                        grantable_by=root_principal,
                    ),
                    retry=False,
                )

        return await self._create_token(
            issuer=parent_token.subject,
            subject=subject,
            scope=scope,
            capability=capability,
            root_principal=root_principal,
            parent_token=parent_token,
            purpose_parameters=purpose_parameters,
            ttl_hours=ttl_hours,
            max_delegation_depth=min(
                parent_token.constraints.max_delegation_depth,
                parent_token.constraints.max_delegation_depth,
            ),
            budget=budget,
        )

    async def validate_delegation(
        self,
        token: DelegationToken,
        minimum_scope: list[str],
        capability_name: str,
    ) -> DelegationToken | ANIPFailure:
        """Validate a delegation token for invoking a capability.

        Returns the stored :class:`DelegationToken` if valid (callers MUST use
        it for all downstream operations), or an :class:`ANIPFailure`.
        """
        # 0. Resolve to stored token (prevents forged inline fields)
        resolved = await self.resolve_registered_token(token)
        if isinstance(resolved, ANIPFailure):
            return resolved
        token = resolved

        # 1. Check expiry
        if token.expires < datetime.now(timezone.utc):
            return ANIPFailure(
                type="token_expired",
                detail=f"delegation token {token.token_id} expired at {token.expires.isoformat()}",
                resolution=Resolution(
                    action="request_new_delegation",
                    recovery_class=recovery_class_for_action("request_new_delegation"),
                    grantable_by=await self.get_root_principal(token),
                ),
                retry=True,
            )

        # 2. Check scope — token must carry ALL required scopes (prefix match)
        token_scope_bases = [s.split(":")[0] for s in token.scope]
        missing_scopes: list[str] = []
        for required_scope in minimum_scope:
            scope_matched = any(
                scope_base == required_scope
                or required_scope.startswith(scope_base + ".")
                for scope_base in token_scope_bases
            )
            if not scope_matched:
                missing_scopes.append(required_scope)
        if missing_scopes:
            root_principal = await self.get_root_principal(token)
            return ANIPFailure(
                type="scope_insufficient",
                detail=f"delegation chain lacks scope(s): {', '.join(missing_scopes)}",
                resolution=Resolution(
                    action="request_broader_scope",
                    recovery_class=recovery_class_for_action("request_broader_scope"),
                    requires=f"delegation.scope += {', '.join(missing_scopes)}",
                    grantable_by=root_principal,
                ),
                retry=True,
            )

        # 3. Check purpose binding
        if token.purpose.capability != capability_name:
            return ANIPFailure(
                type="purpose_mismatch",
                detail=(
                    f"delegation token purpose is {token.purpose.capability} "
                    f"but request is for {capability_name}"
                ),
                resolution=Resolution(
                    action="request_new_delegation",
                    recovery_class=recovery_class_for_action("request_new_delegation"),
                    grantable_by=await self.get_root_principal(token),
                ),
                retry=True,
            )

        # 4. Verify delegation chain is complete
        chain = await self.get_chain(token)
        if chain[0].parent is not None:
            return ANIPFailure(
                type="broken_delegation_chain",
                detail=(
                    f"delegation chain is incomplete — ancestor token "
                    f"'{chain[0].parent}' is not registered"
                ),
                resolution=Resolution(
                    action="request_deeper_delegation",
                    recovery_class=recovery_class_for_action("request_deeper_delegation"),
                    grantable_by=await self.get_root_principal(token),
                ),
                retry=True,
            )

        # 5. Check delegation depth
        max_depth = token.constraints.max_delegation_depth
        actual_depth = len(chain) - 1
        if actual_depth > max_depth:
            return ANIPFailure(
                type="delegation_depth_exceeded",
                detail=f"delegation chain depth is {actual_depth}, max allowed is {max_depth}",
                resolution=Resolution(
                    action="request_deeper_delegation",
                    recovery_class=recovery_class_for_action("request_deeper_delegation"),
                    requires=f"max_delegation_depth >= {actual_depth}",
                    grantable_by=await self.get_root_principal(token),
                ),
                retry=True,
            )

        # 6. Validate parent chain — every parent must be valid and not expired
        for ancestor in chain[:-1]:
            if ancestor.expires < datetime.now(timezone.utc):
                return ANIPFailure(
                    type="parent_token_expired",
                    detail=f"ancestor token {ancestor.token_id} in delegation chain has expired",
                    resolution=Resolution(
                        action="refresh_binding",
                        recovery_class=recovery_class_for_action("refresh_binding"),
                        grantable_by=await self.get_root_principal(token),
                    ),
                    retry=True,
                )

        return token  # all checks passed

    # ------------------------------------------------------------------
    # Chain helpers
    # ------------------------------------------------------------------

    async def get_chain(self, token: DelegationToken) -> list[DelegationToken]:
        """Walk the DAG upward from *token* to the root, returning root-first."""
        chain = [token]
        current = token
        while current.parent is not None:
            parent = await self.get_token(current.parent)
            if parent is None:
                break
            chain.append(parent)
            current = parent
        return list(reversed(chain))

    async def get_root_principal(self, token: DelegationToken) -> str:
        """Return the root principal (human) from the delegation chain."""
        if token.root_principal is not None:
            return token.root_principal
        # Fallback for v0.1 tokens without root_principal field
        chain = await self.get_chain(token)
        return chain[0].issuer

    async def get_chain_token_ids(self, token: DelegationToken) -> list[str]:
        """Return token IDs in the delegation chain (for audit logging)."""
        return [t.token_id for t in await self.get_chain(token)]

    # ------------------------------------------------------------------
    # Scope / constraint validation helpers
    # ------------------------------------------------------------------

    async def validate_scope_narrowing(
        self, token: DelegationToken
    ) -> ANIPFailure | None:
        """Validate that a child token's scope is a subset of its parent's.

        Returns ``None`` if valid (or no parent), or :class:`ANIPFailure` if
        scope widens.
        """
        if token.parent is None:
            return None

        parent = await self.get_token(token.parent)
        if parent is None:
            return ANIPFailure(
                type="parent_not_found",
                detail=f"parent token '{token.parent}' is not registered — cannot validate scope narrowing",
                resolution=Resolution(
                    action="request_new_delegation",
                    recovery_class=recovery_class_for_action("request_new_delegation"),
                    requires=f"token '{token.parent}' must be registered before its children",
                    grantable_by=token.issuer,
                ),
                retry=True,
            )

        parent_scope_bases = {s.split(":")[0] for s in parent.scope}

        for child_scope in token.scope:
            child_base = child_scope.split(":")[0]
            matched = any(
                child_base == parent_base or child_base.startswith(parent_base + ".")
                for parent_base in parent_scope_bases
            )
            if not matched:
                return ANIPFailure(
                    type="scope_escalation",
                    detail=(
                        f"child token scope '{child_base}' is not a subset of "
                        f"parent token scopes: {', '.join(sorted(parent_scope_bases))}"
                    ),
                    resolution=Resolution(
                        action="request_new_delegation",
                        recovery_class=recovery_class_for_action("request_new_delegation"),
                        requires="child scope must be subset of parent scope",
                        grantable_by=await self.get_root_principal(parent),
                    ),
                    retry=False,
                )

            # Budget constraint enforcement
            for parent_scope_str in parent.scope:
                parent_base = parent_scope_str.split(":")[0]
                if parent_base == child_base and ":max_$" in parent_scope_str:
                    parent_budget = float(parent_scope_str.split(":max_$")[1])
                    if ":max_$" not in child_scope:
                        return ANIPFailure(
                            type="scope_escalation",
                            detail=(
                                f"child dropped budget constraint from scope "
                                f"'{child_base}' (parent has max ${parent_budget})"
                            ),
                            resolution=Resolution(
                                action="request_new_delegation",
                                recovery_class=recovery_class_for_action("request_new_delegation"),
                                requires=f"scope '{child_base}' must include budget <= ${parent_budget}",
                                grantable_by=await self.get_root_principal(parent),
                            ),
                            retry=False,
                        )
                    child_budget = float(child_scope.split(":max_$")[1])
                    if child_budget > parent_budget:
                        return ANIPFailure(
                            type="scope_escalation",
                            detail=(
                                f"child budget ${child_budget} exceeds parent "
                                f"budget ${parent_budget} for scope '{child_base}'"
                            ),
                            resolution=Resolution(
                                action="request_new_delegation",
                                recovery_class=recovery_class_for_action("request_new_delegation"),
                                requires=f"budget must be <= ${parent_budget}",
                                grantable_by=await self.get_root_principal(parent),
                            ),
                            retry=False,
                        )

        return None

    async def validate_constraints_narrowing(
        self, token: DelegationToken
    ) -> ANIPFailure | None:
        """Validate that a child token's constraints don't weaken its parent's.

        Returns ``None`` if valid (or no parent), or :class:`ANIPFailure` if
        constraints widen.
        """
        if token.parent is None:
            return None

        parent = await self.get_token(token.parent)
        if parent is None:
            return None  # parent existence is checked separately

        if token.constraints.max_delegation_depth > parent.constraints.max_delegation_depth:
            return ANIPFailure(
                type="constraint_escalation",
                detail=(
                    f"child max_delegation_depth ({token.constraints.max_delegation_depth}) "
                    f"exceeds parent ({parent.constraints.max_delegation_depth})"
                ),
                resolution=Resolution(
                    action="request_new_delegation",
                    recovery_class=recovery_class_for_action("request_new_delegation"),
                    requires=f"max_delegation_depth must be <= {parent.constraints.max_delegation_depth}",
                    grantable_by=await self.get_root_principal(parent),
                ),
                retry=False,
            )

        if (
            parent.constraints.concurrent_branches == ConcurrentBranches.EXCLUSIVE
            and token.constraints.concurrent_branches == ConcurrentBranches.ALLOWED
        ):
            return ANIPFailure(
                type="constraint_escalation",
                detail="child weakened concurrent_branches from 'exclusive' to 'allowed'",
                resolution=Resolution(
                    action="request_new_delegation",
                    recovery_class=recovery_class_for_action("request_new_delegation"),
                    requires="concurrent_branches must remain 'exclusive'",
                    grantable_by=await self.get_root_principal(parent),
                ),
                retry=False,
            )

        return None

    async def check_budget_authority(
        self, token: DelegationToken, amount: float
    ) -> ANIPFailure | None:
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
                            recovery_class=recovery_class_for_action("request_budget_increase"),
                            requires=f"delegation.scope budget raised to ${amount}",
                            grantable_by=await self.get_root_principal(token),
                        ),
                        retry=True,
                    )
        return None

    # ------------------------------------------------------------------
    # Exclusive locking (concurrent_branches enforcement)
    # ------------------------------------------------------------------

    def _get_holder_id(self) -> str:
        """Return a unique holder identifier for this process."""
        return f"{socket.gethostname()}:{os.getpid()}"

    async def acquire_exclusive_lock(
        self, token: DelegationToken
    ) -> ANIPFailure | None:
        """Atomically acquire the exclusive lock for a root principal.

        Returns ``None`` on success, or :class:`ANIPFailure` if another
        request is active.  Uses storage-backed leases so the lock is
        visible across multiple processes/hosts.
        """
        if token.constraints.concurrent_branches != ConcurrentBranches.EXCLUSIVE:
            return None
        root = await self.get_root_principal(token)
        key = f"exclusive:{self._service_id}:{root}"
        holder = self._get_holder_id()
        acquired = await self._storage.try_acquire_exclusive(key, holder, self._exclusive_ttl)
        if not acquired:
            return ANIPFailure(
                type="concurrent_request_rejected",
                detail=f"concurrent_branches is exclusive and another request from {root} is in progress",
                resolution=Resolution(
                    action="wait_and_retry",
                    recovery_class=recovery_class_for_action("wait_and_retry"),
                    grantable_by=root,
                ),
                retry=True,
            )
        return None

    async def release_exclusive_lock(self, token: DelegationToken) -> None:
        """Release the storage-backed exclusive lease for a root principal."""
        if token.constraints.concurrent_branches == ConcurrentBranches.EXCLUSIVE:
            root = await self.get_root_principal(token)
            key = f"exclusive:{self._service_id}:{root}"
            holder = self._get_holder_id()
            await self._storage.release_exclusive(key, holder)

    # ------------------------------------------------------------------
    # Token registration and lookup
    # ------------------------------------------------------------------

    async def register_token(self, token: DelegationToken) -> None:
        """Persist a delegation token to storage."""
        data: dict[str, Any] = {
            "token_id": token.token_id,
            "issuer": token.issuer,
            "subject": token.subject,
            "scope": token.scope,
            "purpose": token.purpose.model_dump(),
            "parent": token.parent,
            "expires": token.expires.isoformat(),
            "constraints": token.constraints.model_dump(),
            "root_principal": token.root_principal,
        }
        if token.caller_class is not None:
            data["caller_class"] = token.caller_class
        await self._storage.store_token(data)

    async def get_token(self, token_id: str) -> DelegationToken | None:
        """Load a delegation token from storage."""
        data = await self._storage.load_token(token_id)
        if data is None:
            return None
        return DelegationToken(**data)

    async def resolve_registered_token(
        self, token: DelegationToken
    ) -> DelegationToken | ANIPFailure:
        """Look up the stored version of a token.

        Returns the stored :class:`DelegationToken` if registered, or
        :class:`ANIPFailure` if not.  Callers MUST use the returned token for
        all downstream operations — this prevents forged inline fields from
        bypassing registration-time validation.
        """
        stored = await self.get_token(token.token_id)
        if stored is None:
            return ANIPFailure(
                type="token_not_registered",
                detail=(
                    f"delegation token '{token.token_id}' is not registered "
                    f"— register via /anip/tokens first"
                ),
                resolution=Resolution(
                    action="request_new_delegation",
                    recovery_class=recovery_class_for_action("request_new_delegation"),
                    requires="token must be registered before use",
                    grantable_by=token.issuer,
                ),
                retry=True,
            )
        return stored

    async def _create_token(
        self,
        *,
        issuer: str,
        subject: str,
        scope: list[str],
        capability: str,
        root_principal: str,
        parent_token: DelegationToken | None,
        purpose_parameters: dict[str, Any] | None,
        ttl_hours: int,
        max_delegation_depth: int,
        budget: Budget | None = None,
    ) -> tuple[DelegationToken, str]:
        """Internal token creation shared by ``issue_root_token`` and ``delegate``."""
        token_id = f"anip-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)
        expires = now + timedelta(hours=ttl_hours)

        concurrent = ConcurrentBranches.ALLOWED
        if parent_token is not None:
            max_delegation_depth = min(
                max_delegation_depth,
                parent_token.constraints.max_delegation_depth,
            )
            concurrent = parent_token.constraints.concurrent_branches

        # task_id: use caller-supplied value if present in purpose_parameters,
        # auto-generate only if purpose_parameters is absent or empty
        pp = dict(purpose_parameters) if purpose_parameters else {}
        caller_task_id = pp.pop("task_id", None)
        if caller_task_id is not None:
            resolved_task_id = caller_task_id  # Caller explicitly set it
        elif purpose_parameters is None:
            resolved_task_id = f"task-{token_id}"  # No purpose_parameters at all — auto-generate
        else:
            resolved_task_id = None  # Caller sent purpose_parameters but without task_id — unbound

        token = DelegationToken(
            token_id=token_id,
            issuer=issuer,
            subject=subject,
            scope=scope,
            purpose=Purpose(
                capability=capability,
                parameters=pp,
                task_id=resolved_task_id,
            ),
            parent=parent_token.token_id if parent_token else None,
            expires=expires,
            constraints=DelegationConstraints(
                max_delegation_depth=max_delegation_depth,
                concurrent_branches=concurrent,
                budget=budget,
            ),
            root_principal=root_principal,
        )

        # Validate narrowing for child tokens (post-creation, using stored parent)
        if parent_token is not None:
            constraint_failure = await self.validate_constraints_narrowing(token)
            if constraint_failure is not None:
                return constraint_failure  # type: ignore[return-value]

        await self.register_token(token)
        return token, token_id
