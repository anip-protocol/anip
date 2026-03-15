# ANIP Service Runtime Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `anip-service` / `@anip/service` and `anip-fastapi` / `@anip/hono` packages that turn ANIP from a primitive toolkit into a configurable service runtime, then restructure examples to prove the approach.

**Architecture:** Two new packages per language layered on top of the existing `core → crypto → server` stack. `service` owns lifecycle, orchestration, and domain-level operations. Framework bindings own transport only. Examples shrink from ~1,000+ lines to ~150 lines of pure business logic + configuration.

**Tech Stack:** Python 3.11+ / FastAPI / pytest. TypeScript / Hono / vitest. Existing ANIP SDK packages (`anip-core`, `anip-crypto`, `anip-server`, `@anip/core`, `@anip/crypto`, `@anip/server`).

**Design doc:** `docs/plans/2026-03-14-service-runtime-design.md`

---

## Task 1: Scaffold Python `anip-service` package

**Files:**
- Create: `packages/python/anip-service/pyproject.toml`
- Create: `packages/python/anip-service/src/anip_service/__init__.py`
- Create: `packages/python/anip-service/src/anip_service/types.py`
- Test: `packages/python/anip-service/tests/test_types.py`

**Step 1: Create pyproject.toml**

```toml
[project]
name = "anip-service"
version = "0.3.0"
description = "ANIP service runtime — configure and run an ANIP service"
requires-python = ">=3.11"
dependencies = [
    "anip-core>=0.3.0",
    "anip-crypto>=0.3.0",
    "anip-server>=0.3.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

**Step 2: Create the `Capability`, `InvocationContext`, and `ANIPError` types**

`types.py`:
```python
"""Core types for the ANIP service runtime."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from anip_core import CapabilityDeclaration, DelegationToken


@dataclass
class InvocationContext:
    """Context passed to capability handlers during invocation."""
    token: DelegationToken
    root_principal: str
    subject: str
    scopes: list[str]
    delegation_chain: list[str]
    _cost_actual: dict[str, Any] | None = field(default=None, repr=False)

    def set_cost_actual(self, cost: dict[str, Any]) -> None:
        """Set actual cost for variance tracking against declared cost."""
        self._cost_actual = cost


# Handler type: (ctx, params) -> result dict
Handler = Callable[[InvocationContext, dict[str, Any]], dict[str, Any]]


@dataclass
class Capability:
    """Bundles a capability declaration with its handler function."""
    declaration: CapabilityDeclaration
    handler: Handler
    exclusive_lock: bool = False


class ANIPError(Exception):
    """Structured error raised by capability handlers.

    Maps to an ANIP failure response with the given type and detail.
    """
    def __init__(self, error_type: str, detail: str) -> None:
        self.error_type = error_type
        self.detail = detail
        super().__init__(f"{error_type}: {detail}")
```

`__init__.py`:
```python
"""ANIP Service — configure and run an ANIP service."""
from .types import Capability, InvocationContext, ANIPError, Handler

__all__ = [
    "Capability",
    "InvocationContext",
    "ANIPError",
    "Handler",
]
```

**Step 3: Write tests for types**

`tests/test_types.py`:
```python
from anip_service import Capability, InvocationContext, ANIPError
from anip_core import CapabilityDeclaration, CapabilityInput, CapabilityOutput, SideEffect, SideEffectType


def _minimal_declaration(name: str = "test_cap") -> CapabilityDeclaration:
    return CapabilityDeclaration(
        name=name,
        description="A test capability",
        contract_version="1.0",
        inputs=[CapabilityInput(name="x", type="string", required=True, description="input")],
        output=CapabilityOutput(type="object", fields=["result"]),
        side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
        minimum_scope=["test.read"],
    )


def test_capability_bundles_declaration_and_handler():
    handler = lambda ctx, params: {"ok": True}
    cap = Capability(declaration=_minimal_declaration(), handler=handler)
    assert cap.declaration.name == "test_cap"
    assert cap.handler is handler
    assert cap.exclusive_lock is False


def test_invocation_context_cost_tracking():
    ctx = InvocationContext(
        token=None,  # type: ignore — simplified for test
        root_principal="human:alice@example.com",
        subject="agent:bot-1",
        scopes=["test.read"],
        delegation_chain=["tok-1"],
    )
    assert ctx._cost_actual is None
    ctx.set_cost_actual({"financial": {"amount": 10.0, "currency": "USD"}})
    assert ctx._cost_actual["financial"]["amount"] == 10.0


def test_anip_error():
    err = ANIPError("not_found", "Flight does not exist")
    assert err.error_type == "not_found"
    assert err.detail == "Flight does not exist"
    assert "not_found" in str(err)
```

**Step 4: Run tests**

```bash
cd packages/python/anip-service
pip install -e ".[dev]" -e ../anip-core -e ../anip-crypto -e ../anip-server
pytest tests/test_types.py -v
```
Expected: 3 tests PASS

**Step 5: Commit**

```bash
git add packages/python/anip-service/
git commit -m "feat(anip-service): scaffold Python package with Capability, InvocationContext, ANIPError"
```

---

## Task 2: Python `ANIPService` builder — construction and singleton ownership

**Files:**
- Create: `packages/python/anip-service/src/anip_service/service.py`
- Modify: `packages/python/anip-service/src/anip_service/__init__.py`
- Test: `packages/python/anip-service/tests/test_service_init.py`

**Step 1: Implement ANIPService construction**

`service.py` — this is the core of the runtime. It creates and owns all SDK instances.

```python
"""ANIP service runtime — the main developer-facing class."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Callable

from anip_core import (
    ANIPFailure,
    ANIPManifest,
    CapabilityDeclaration,
    DelegationToken,
    ServiceIdentity,
    TrustPosture,
    AnchoringPolicy,
)
from anip_crypto import KeyManager
from anip_server import (
    AuditLog,
    CheckpointPolicy,
    CheckpointScheduler,
    DelegationEngine,
    MerkleTree,
    SQLiteStorage,
    StorageBackend,
    build_manifest,
    create_checkpoint,
    discover_permissions,
    CheckpointSink,
)

from .types import ANIPError, Capability, InvocationContext


class ANIPService:
    """High-level ANIP service runtime.

    Owns all SDK instances (keys, storage, delegation engine, audit log).
    Exposes domain-level operations — no HTTP types.
    """

    def __init__(
        self,
        *,
        service_id: str,
        capabilities: list[Capability],
        storage: str | StorageBackend = "sqlite:///anip.db",
        key_path: str = "./anip-keys",
        trust: str | dict[str, Any] = "signed",
        checkpoint_policy: CheckpointPolicy | None = None,
        audit_signer: Any | None = None,
        authenticate: Callable[[str], str | None] | None = None,
    ) -> None:
        self._service_id = service_id

        # --- Bootstrap authentication ---
        # Maps a bearer token string to an authenticated principal.
        # Used for first-token issuance before any ANIP tokens exist.
        # If not provided, only existing ANIP JWT tokens can authenticate.
        self._authenticate = authenticate

        # --- Capability registry ---
        self._capabilities: dict[str, Capability] = {}
        cap_declarations: dict[str, CapabilityDeclaration] = {}
        for cap in capabilities:
            name = cap.declaration.name
            self._capabilities[name] = cap
            cap_declarations[name] = cap.declaration

        # --- Storage ---
        if isinstance(storage, str):
            if storage == ":memory:":
                self._storage = SQLiteStorage(":memory:")
            elif storage.startswith("sqlite:///"):
                db_path = storage[len("sqlite:///"):]
                self._storage = SQLiteStorage(db_path)
            else:
                raise ValueError(f"Unknown storage string: {storage!r}. Use 'sqlite:///path' or ':memory:'.")
        else:
            self._storage = storage

        # --- Keys ---
        self._keys = KeyManager(key_path)

        # --- Delegation engine ---
        self._engine = DelegationEngine(self._storage, service_id=service_id)

        # --- Audit log ---
        signer = audit_signer or self._keys.sign_audit_entry
        self._audit = AuditLog(self._storage, signer=signer)
        self._merkle = MerkleTree()

        # --- Trust ---
        if isinstance(trust, str):
            trust_level = trust
            anchoring = None
            self._sinks: list[CheckpointSink] = []
        else:
            trust_level = trust.get("level", "signed")
            anchoring_cfg = trust.get("anchoring")
            if anchoring_cfg:
                self._sinks = anchoring_cfg.get("sinks", [])
                # Derive sink URIs for the manifest from sink objects.
                # Each sink must declare its URI scheme via a .uri property.
                # LocalFileSink → "file://..." (non-qualifying, dev only).
                sink_uris = []
                for s in self._sinks:
                    if hasattr(s, "uri"):
                        sink_uris.append(s.uri)
                    elif hasattr(s, "directory"):
                        sink_uris.append(f"file://{s.directory}")
                anchoring = AnchoringPolicy(
                    cadence=anchoring_cfg.get("cadence"),
                    max_lag=anchoring_cfg.get("max_lag"),
                    sink=sink_uris or None,
                )
            else:
                anchoring = None
                self._sinks = []

        if trust_level == "attested":
            raise ValueError("Attested trust requires witness sinks — not yet supported.")

        self._trust_level = trust_level
        trust_posture = TrustPosture(level=trust_level, anchoring=anchoring)

        # --- Manifest ---
        service_identity = ServiceIdentity(
            id=service_id,
            jwks_uri="/.well-known/jwks.json",
            issuer_mode="first-party",
        )
        self._manifest = build_manifest(
            capabilities=cap_declarations,
            trust=trust_posture,
            service_identity=service_identity,
        )

        # --- Checkpoint scheduling (anchored mode only) ---
        self._checkpoint_policy = checkpoint_policy
        self._scheduler: CheckpointScheduler | None = None
        self._entries_since_checkpoint = 0
        self._last_checkpoint_time = datetime.now(timezone.utc)

        if trust_level == "anchored" and checkpoint_policy:
            self._scheduler = CheckpointScheduler(
                interval_seconds=checkpoint_policy.interval_seconds or 60,
                create_fn=lambda: self._create_and_publish_checkpoint(),
                has_new_entries_fn=lambda: self._entries_since_checkpoint > 0,
            )

    # --- Public domain-level operations ---

    def get_discovery(self) -> dict[str, Any]:
        """Return lightweight discovery document."""
        caps_summary = {}
        for name, cap in self._capabilities.items():
            decl = cap.declaration
            caps_summary[name] = {
                "description": decl.description,
                "side_effect": decl.side_effect.type.value if decl.side_effect else None,
                "minimum_scope": decl.minimum_scope,
                "contract_version": decl.contract_version,
            }

        return {
            "anip_discovery": {
                "profile": "full",
                "capabilities": caps_summary,
                "trust_level": self._trust_level,
                "endpoints": {
                    "manifest": "/anip/manifest",
                    "tokens": "/anip/tokens",
                    "invoke": "/anip/invoke/{capability}",
                    "permissions": "/anip/permissions",
                    "audit": "/anip/audit",
                    "checkpoints": "/anip/checkpoints",
                    "jwks": "/.well-known/jwks.json",
                },
            }
        }

    def get_manifest(self) -> ANIPManifest:
        """Return the full capability manifest."""
        return self._manifest

    def get_jwks(self) -> dict[str, Any]:
        """Return the JWKS document for this service."""
        return self._keys.get_jwks()

    def authenticate_bearer(self, bearer_value: str) -> str | None:
        """Resolve a bearer token to an authenticated principal.

        Tries bootstrap authentication first (API keys, external auth),
        then falls back to ANIP JWT verification.
        Returns the principal string, or None if unauthenticated.
        """
        # Try bootstrap auth (API keys, external auth)
        if self._authenticate:
            principal = self._authenticate(bearer_value)
            if principal is not None:
                return principal

        # Try ANIP JWT
        try:
            claims = self._keys.verify_jwt(bearer_value, audience=self._service_id)
            token_id = claims.get("jti")
            if token_id:
                stored = self._engine.get_token(token_id)
                if stored:
                    return stored.root_principal
        except Exception:
            pass

        return None

    def resolve_bearer_token(self, jwt_string: str) -> DelegationToken:
        """Verify a JWT and return the stored DelegationToken.

        Raises ANIPError if token is invalid, expired, or unknown.
        """
        try:
            claims = self._keys.verify_jwt(jwt_string, audience=self._service_id)
        except Exception as exc:
            raise ANIPError("invalid_token", str(exc)) from exc

        token_id = claims.get("jti")
        if not token_id:
            raise ANIPError("invalid_token", "JWT missing jti claim")

        stored = self._engine.get_token(token_id)
        if stored is None:
            raise ANIPError("invalid_token", f"Unknown token: {token_id}")

        return stored

    def issue_token(
        self,
        authenticated_principal: str,
        request: dict[str, Any],
    ) -> dict[str, Any]:
        """Issue a root token or delegate from a parent.

        Returns {token_id, token (JWT string), expires}.
        """
        parent_token_id = request.get("parent_token")
        ttl_hours = request.get("ttl_hours", 2)

        if parent_token_id:
            # Delegation from existing token
            parent = self._engine.get_token(parent_token_id)
            if parent is None:
                raise ANIPError("invalid_token", f"Parent token not found: {parent_token_id}")

            result = self._engine.delegate(
                parent_token=parent,
                subject=request.get("subject", authenticated_principal),
                scope=request.get("scope", []),
                capability=request.get("capability"),
                purpose_parameters=request.get("purpose_parameters"),
                ttl_hours=ttl_hours,
            )
        else:
            # Root token
            result = self._engine.issue_root_token(
                authenticated_principal=authenticated_principal,
                subject=request.get("subject", authenticated_principal),
                scope=request.get("scope", []),
                capability=request.get("capability"),
                purpose_parameters=request.get("purpose_parameters"),
                ttl_hours=ttl_hours,
            )

        # Check for delegation failure (ANIPFailure is a Pydantic model)
        if isinstance(result, ANIPFailure):
            raise ANIPError(result.type, result.detail)

        token, token_id = result

        # Build and sign JWT
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        expires = now + timedelta(hours=ttl_hours)

        claims = {
            "jti": token_id,
            "iss": self._service_id,
            "sub": token.subject,
            "aud": self._service_id,
            "iat": int(now.timestamp()),
            "exp": int(expires.timestamp()),
            "scope": token.scope,
            "root_principal": token.root_principal,
        }
        if token.purpose:
            claims["purpose"] = token.purpose.model_dump() if hasattr(token.purpose, "model_dump") else token.purpose
        if token.constraints:
            claims["constraints"] = token.constraints.model_dump() if hasattr(token.constraints, "model_dump") else token.constraints

        jwt_str = self._keys.sign_jwt(claims)

        return {
            "issued": True,
            "token_id": token_id,
            "token": jwt_str,
            "expires": expires.isoformat(),
        }

    def discover_permissions(self, token: DelegationToken) -> dict[str, Any]:
        """Return the permissions granted by a token."""
        return discover_permissions(token, self._manifest.capabilities)

    def invoke(
        self,
        capability_name: str,
        token: DelegationToken,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Invoke a capability with full validation, audit, and error handling.

        This is the core runtime method. It:
        1. Validates the token against the capability
        2. Optionally acquires an exclusive lock
        3. Calls the handler with an InvocationContext
        4. Wraps the result in an InvokeResponse
        5. Logs to audit
        6. Handles checkpoint triggers
        """
        # 1. Check capability exists
        if capability_name not in self._capabilities:
            return {
                "success": False,
                "failure": {
                    "type": "unknown_capability",
                    "detail": f"Capability '{capability_name}' not found",
                },
            }

        cap = self._capabilities[capability_name]
        decl = cap.declaration

        # 2. Validate delegation
        min_scope = decl.minimum_scope or []
        validation_result = self._engine.validate_delegation(
            token, min_scope, capability_name,
        )

        # Check for validation failure (ANIPFailure is a Pydantic model)
        if isinstance(validation_result, ANIPFailure):
            failure = {"type": validation_result.type, "detail": validation_result.detail}
            self._log_audit(
                capability_name, token, success=False,
                failure_type=failure["type"], result_summary=None,
                cost_actual=None, cost_variance=None,
            )
            return {"success": False, "failure": failure}

        # Use the resolved/stored token from validation
        resolved_token = validation_result

        # 3. Build invocation context
        chain = self._engine.get_chain(resolved_token)
        ctx = InvocationContext(
            token=resolved_token,
            root_principal=self._engine.get_root_principal(resolved_token),
            subject=resolved_token.subject,
            scopes=resolved_token.scope or [],
            delegation_chain=[t.token_id for t in chain],
        )

        # 4. Acquire lock if configured
        locked = False
        if cap.exclusive_lock:
            lock_result = self._engine.acquire_exclusive_lock(resolved_token)
            if lock_result is not None:
                # Lock acquisition failed
                self._log_audit(
                    capability_name, resolved_token, success=False,
                    failure_type="concurrent_lock",
                    result_summary=None, cost_actual=None, cost_variance=None,
                )
                return {"success": False, "failure": {"type": lock_result.type, "detail": lock_result.detail}}
            locked = True

        try:
            # 5. Call handler
            try:
                result = cap.handler(ctx, params)
            except ANIPError as e:
                self._log_audit(
                    capability_name, resolved_token, success=False,
                    failure_type=e.error_type,
                    result_summary={"detail": e.detail},
                    cost_actual=None, cost_variance=None,
                )
                return {
                    "success": False,
                    "failure": {"type": e.error_type, "detail": e.detail},
                }
            except Exception:
                self._log_audit(
                    capability_name, resolved_token, success=False,
                    failure_type="internal_error",
                    result_summary=None, cost_actual=None, cost_variance=None,
                )
                return {
                    "success": False,
                    "failure": {"type": "internal_error", "detail": "Internal error"},
                }

            # 6. Compute cost variance
            cost_actual = ctx._cost_actual
            cost_variance = self._compute_cost_variance(decl, cost_actual)

            # 7. Log audit (success)
            self._log_audit(
                capability_name, resolved_token, success=True,
                failure_type=None,
                result_summary=self._summarize_result(result),
                cost_actual=cost_actual,
                cost_variance=cost_variance,
            )

            # 8. Build response
            response: dict[str, Any] = {"success": True, "result": result}
            if cost_actual:
                response["cost_actual"] = cost_actual

            return response

        finally:
            if locked:
                self._engine.release_exclusive_lock(resolved_token)

    def query_audit(
        self,
        token: DelegationToken,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Query audit entries scoped to the token's root principal."""
        root_principal = self._engine.get_root_principal(token)
        filters = filters or {}

        entries = self._audit.query(
            root_principal=root_principal,
            capability=filters.get("capability"),
            since=filters.get("since"),
            limit=min(filters.get("limit", 50), 1000),
        )

        return {
            "entries": entries,
            "count": len(entries),
            "root_principal": root_principal,
            "capability_filter": filters.get("capability"),
            "since_filter": filters.get("since"),
        }

    def get_checkpoints(self, limit: int = 10) -> dict[str, Any]:
        """Return recent checkpoints."""
        limit = min(limit, 100)
        rows = self._storage.get_checkpoints(limit)

        checkpoints = []
        for row in rows:
            rng = row.get("range", {})
            checkpoints.append({
                "checkpoint_id": row["checkpoint_id"],
                "range": {
                    "first_sequence": rng.get("first_sequence", row.get("first_sequence")),
                    "last_sequence": rng.get("last_sequence", row.get("last_sequence")),
                },
                "merkle_root": row["merkle_root"],
                "previous_checkpoint": row.get("previous_checkpoint"),
                "timestamp": row["timestamp"],
                "entry_count": row["entry_count"],
                "signature": row["signature"],
            })

        return {"checkpoints": checkpoints}

    def get_checkpoint(
        self,
        checkpoint_id: str,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Return a checkpoint by ID, optionally with proofs."""
        row = self._storage.get_checkpoint_by_id(checkpoint_id)
        if row is None:
            return None

        rng = row.get("range", {})
        result: dict[str, Any] = {
            "checkpoint": {
                "checkpoint_id": row["checkpoint_id"],
                "range": {
                    "first_sequence": rng.get("first_sequence", row.get("first_sequence")),
                    "last_sequence": rng.get("last_sequence", row.get("last_sequence")),
                },
                "merkle_root": row["merkle_root"],
                "previous_checkpoint": row.get("previous_checkpoint"),
                "timestamp": row["timestamp"],
                "entry_count": row["entry_count"],
                "signature": row["signature"],
            }
        }

        options = options or {}

        # Inclusion proof
        if options.get("include_proof") and options.get("leaf_index") is not None:
            leaf_index = int(options["leaf_index"])
            last_seq = rng.get("last_sequence", row.get("last_sequence", 0))
            tree = self._rebuild_merkle_to(last_seq)
            try:
                proof = tree.inclusion_proof(leaf_index)
                result["inclusion_proof"] = {
                    "leaf_index": leaf_index,
                    "path": proof,
                    "merkle_root": tree.root,
                    "leaf_count": tree.leaf_count,
                }
            except (IndexError, ValueError):
                pass

        # Consistency proof
        consistency_from = options.get("consistency_from")
        if consistency_from:
            old_row = self._storage.get_checkpoint_by_id(consistency_from)
            if old_row:
                old_rng = old_row.get("range", {})
                old_last = old_rng.get("last_sequence", old_row.get("last_sequence", 0))
                new_last = rng.get("last_sequence", row.get("last_sequence", 0))
                old_tree = self._rebuild_merkle_to(old_last)
                new_tree = self._rebuild_merkle_to(new_last)
                try:
                    path = new_tree.consistency_proof(old_tree.leaf_count)
                    result["consistency_proof"] = {
                        "old_checkpoint_id": consistency_from,
                        "new_checkpoint_id": checkpoint_id,
                        "old_size": old_tree.leaf_count,
                        "new_size": new_tree.leaf_count,
                        "old_root": old_tree.root,
                        "new_root": new_tree.root,
                        "path": path,
                    }
                except (IndexError, ValueError):
                    pass

        return result

    def start(self) -> None:
        """Start background services (checkpoint scheduler)."""
        if self._scheduler:
            self._scheduler.start()

    def stop(self) -> None:
        """Stop background services."""
        if self._scheduler:
            self._scheduler.stop()

    # --- Internal helpers ---

    def _log_audit(
        self,
        capability: str,
        token: DelegationToken,
        *,
        success: bool,
        failure_type: str | None,
        result_summary: dict[str, Any] | None,
        cost_actual: dict[str, Any] | None,
        cost_variance: dict[str, Any] | None,
    ) -> None:
        """Log an audit entry through the SDK's AuditLog."""
        chain = self._engine.get_chain(token)
        self._audit.log_entry({
            "capability": capability,
            "token_id": token.token_id,
            "root_principal": self._engine.get_root_principal(token),
            "success": success,
            "failure_type": failure_type,
            "result_summary": result_summary,
            "cost_actual": cost_actual,
            "delegation_chain": [t.token_id for t in chain],
        })

        self._entries_since_checkpoint += 1
        if self._checkpoint_policy and self._checkpoint_policy.should_checkpoint(
            self._entries_since_checkpoint
        ):
            self._create_and_publish_checkpoint()

    def _create_and_publish_checkpoint(self) -> None:
        """Create a checkpoint and publish to configured sinks."""
        try:
            snapshot = self._audit.get_merkle_snapshot()
            body, signature = create_checkpoint(
                merkle_snapshot=snapshot,
                service_id=self._service_id,
                previous_checkpoint=self._get_last_checkpoint(),
                sign_fn=self._keys.sign_jws_detached,
            )
            self._storage.store_checkpoint(body, signature)
            for sink in self._sinks:
                sink.publish({"body": body, "signature": signature})
            self._entries_since_checkpoint = 0
            self._last_checkpoint_time = datetime.now(timezone.utc)
        except Exception:
            pass  # Checkpoint failures are non-fatal

    def _get_last_checkpoint(self) -> dict[str, Any] | None:
        """Return the most recent checkpoint, or None."""
        rows = self._storage.get_checkpoints(1)
        return rows[-1] if rows else None

    def _rebuild_merkle_to(self, sequence_number: int) -> MerkleTree:
        """Rebuild a Merkle tree from audit entries 1..sequence_number."""
        entries = self._storage.get_audit_entries_range(1, sequence_number)
        tree = MerkleTree()
        for row in entries:
            filtered = {
                k: v for k, v in sorted(row.items())
                if k not in ("signature", "id")
            }
            tree.add_leaf(json.dumps(filtered, separators=(",", ":"), sort_keys=True).encode())
        return tree

    @staticmethod
    def _summarize_result(result: dict[str, Any]) -> dict[str, Any]:
        """Create a lightweight summary of a handler result for audit."""
        summary: dict[str, Any] = {}
        for key in list(result.keys())[:5]:
            val = result[key]
            if isinstance(val, (str, int, float, bool, type(None))):
                summary[key] = val
            elif isinstance(val, list):
                summary[key] = f"[{len(val)} items]"
            else:
                summary[key] = "..."
        return summary

    @staticmethod
    def _compute_cost_variance(
        decl: CapabilityDeclaration,
        cost_actual: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        """Compute variance between declared and actual cost."""
        if not cost_actual:
            return None
        if not decl.cost or not decl.cost.financial:
            return None

        declared = decl.cost.financial
        actual_financial = cost_actual.get("financial", {})
        actual_amount = actual_financial.get("amount")
        if actual_amount is None:
            return None

        typical = getattr(declared, "typical", None)
        if typical is None:
            return None

        return {
            "declared_typical": typical,
            "actual": actual_amount,
            "delta": round(actual_amount - typical, 2),
            "percent": round((actual_amount - typical) / typical * 100, 1) if typical else None,
        }
```

**Step 2: Update `__init__.py`**

Add `ANIPService` to exports:
```python
"""ANIP Service — configure and run an ANIP service."""
from .types import Capability, InvocationContext, ANIPError, Handler
from .service import ANIPService

__all__ = [
    "ANIPService",
    "Capability",
    "InvocationContext",
    "ANIPError",
    "Handler",
]
```

**Step 3: Write tests for ANIPService construction and core operations**

`tests/test_service_init.py`:
```python
import pytest
from anip_service import ANIPService, Capability, InvocationContext, ANIPError
from anip_core import CapabilityDeclaration, CapabilityInput, CapabilityOutput, SideEffect, SideEffectType


def _test_cap(name: str = "greet", scope: list[str] | None = None) -> Capability:
    return Capability(
        declaration=CapabilityDeclaration(
            name=name,
            description="Say hello",
            contract_version="1.0",
            inputs=[CapabilityInput(name="name", type="string", required=True, description="Who to greet")],
            output=CapabilityOutput(type="object", fields=["message"]),
            side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
            minimum_scope=scope or ["greet"],
        ),
        handler=lambda ctx, params: {"message": f"Hello, {params['name']}!"},
    )


class TestANIPServiceInit:
    def test_minimal_construction(self):
        service = ANIPService(
            service_id="test-service",
            capabilities=[_test_cap()],
            storage=":memory:",
        )
        assert service._service_id == "test-service"
        assert "greet" in service._capabilities

    def test_manifest_built_from_capabilities(self):
        service = ANIPService(
            service_id="test-service",
            capabilities=[_test_cap()],
            storage=":memory:",
        )
        manifest = service.get_manifest()
        assert "greet" in manifest.capabilities

    def test_discovery_document(self):
        service = ANIPService(
            service_id="test-service",
            capabilities=[_test_cap()],
            storage=":memory:",
        )
        disc = service.get_discovery()
        assert "anip_discovery" in disc
        assert "greet" in disc["anip_discovery"]["capabilities"]
        assert disc["anip_discovery"]["trust_level"] == "signed"

    def test_jwks_available(self):
        service = ANIPService(
            service_id="test-service",
            capabilities=[_test_cap()],
            storage=":memory:",
        )
        jwks = service.get_jwks()
        assert "keys" in jwks

    def test_attested_trust_rejected(self):
        with pytest.raises(ValueError, match="not yet supported"):
            ANIPService(
                service_id="test-service",
                capabilities=[_test_cap()],
                storage=":memory:",
                trust="attested",
            )

    def test_sqlite_storage_string(self, tmp_path):
        db = tmp_path / "test.db"
        service = ANIPService(
            service_id="test-service",
            capabilities=[_test_cap()],
            storage=f"sqlite:///{db}",
        )
        assert service._storage is not None


class TestANIPServiceInvoke:
    def _make_service(self, caps=None):
        return ANIPService(
            service_id="test-service",
            capabilities=caps or [_test_cap()],
            storage=":memory:",
        )

    def test_invoke_unknown_capability(self):
        service = self._make_service()
        token = self._issue_test_token(service)
        result = service.invoke("nonexistent", token, {})
        assert result["success"] is False
        assert result["failure"]["type"] == "unknown_capability"

    def test_invoke_success(self):
        service = self._make_service()
        token = self._issue_test_token(service)
        result = service.invoke("greet", token, {"name": "World"})
        assert result["success"] is True
        assert result["result"]["message"] == "Hello, World!"

    def test_invoke_handler_anip_error(self):
        def failing_handler(ctx, params):
            raise ANIPError("not_found", "Thing not found")

        cap = Capability(
            declaration=CapabilityDeclaration(
                name="fail_cap",
                description="Always fails",
                contract_version="1.0",
                inputs=[],
                output=CapabilityOutput(type="object", fields=[]),
                side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
                minimum_scope=["test"],
            ),
            handler=failing_handler,
        )
        service = self._make_service(caps=[cap])
        token = self._issue_test_token(service, scope=["test"], capability="fail_cap")
        result = service.invoke("fail_cap", token, {})
        assert result["success"] is False
        assert result["failure"]["type"] == "not_found"

    def test_invoke_handler_unexpected_error(self):
        def crashing_handler(ctx, params):
            raise RuntimeError("boom")

        cap = Capability(
            declaration=CapabilityDeclaration(
                name="crash_cap",
                description="Crashes",
                contract_version="1.0",
                inputs=[],
                output=CapabilityOutput(type="object", fields=[]),
                side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
                minimum_scope=["test"],
            ),
            handler=crashing_handler,
        )
        service = self._make_service(caps=[cap])
        token = self._issue_test_token(service, scope=["test"], capability="crash_cap")
        result = service.invoke("crash_cap", token, {})
        assert result["success"] is False
        assert result["failure"]["type"] == "internal_error"
        # Detail should NOT leak the actual exception
        assert "boom" not in result["failure"]["detail"]

    def test_invoke_cost_tracking(self):
        def handler_with_cost(ctx, params):
            ctx.set_cost_actual({"financial": {"amount": 450.0, "currency": "USD"}})
            return {"booked": True}

        cap = Capability(
            declaration=CapabilityDeclaration(
                name="cost_cap",
                description="Tracks cost",
                contract_version="1.0",
                inputs=[],
                output=CapabilityOutput(type="object", fields=[]),
                side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
                minimum_scope=["test"],
            ),
            handler=handler_with_cost,
        )
        service = self._make_service(caps=[cap])
        token = self._issue_test_token(service, scope=["test"], capability="cost_cap")
        result = service.invoke("cost_cap", token, {})
        assert result["success"] is True
        assert result["cost_actual"]["financial"]["amount"] == 450.0

    def _issue_test_token(self, service, scope=None, capability=None):
        """Helper to issue a root token for testing."""
        result = service._engine.issue_root_token(
            authenticated_principal="human:test@example.com",
            subject="human:test@example.com",
            scope=scope or ["greet"],
            capability=capability or "greet",
            purpose={"capability": capability or "greet", "parameters": {}, "task_id": "test"},
            ttl_seconds=3600,
        )
        token, token_id = result
        return token
```

**Step 4: Run tests**

```bash
cd packages/python/anip-service
pytest tests/ -v
```
Expected: All tests PASS

**Step 5: Commit**

```bash
git add packages/python/anip-service/
git commit -m "feat(anip-service): add ANIPService builder with invoke, audit, checkpoints"
```

---

## Task 3: Scaffold Python `anip-fastapi` package with `mount_anip`

**Files:**
- Create: `packages/python/anip-fastapi/pyproject.toml`
- Create: `packages/python/anip-fastapi/src/anip_fastapi/__init__.py`
- Create: `packages/python/anip-fastapi/src/anip_fastapi/routes.py`
- Test: `packages/python/anip-fastapi/tests/test_routes.py`

**Step 1: Create pyproject.toml**

```toml
[project]
name = "anip-fastapi"
version = "0.3.0"
description = "ANIP FastAPI bindings — mount an ANIPService as HTTP routes"
requires-python = ">=3.11"
dependencies = [
    "anip-service>=0.3.0",
    "fastapi>=0.115.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "httpx>=0.27.0"]

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

**Step 2: Implement `mount_anip`**

`routes.py`:
```python
"""Mount ANIP routes onto a FastAPI application."""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from anip_service import ANIPService, ANIPError


def mount_anip(
    app: FastAPI,
    service: ANIPService,
    prefix: str = "",
) -> None:
    """Mount all ANIP protocol routes onto a FastAPI app.

    Routes:
        GET  {prefix}/.well-known/anip          → discovery
        GET  {prefix}/.well-known/jwks.json     → JWKS
        GET  {prefix}/anip/manifest             → full manifest (signed)
        POST {prefix}/anip/tokens               → issue token
        GET  {prefix}/anip/permissions           → discover permissions
        POST {prefix}/anip/invoke/{capability}   → invoke capability
        GET  {prefix}/anip/audit                → query audit log
        GET  {prefix}/anip/checkpoints          → list checkpoints
        GET  {prefix}/anip/checkpoints/{id}     → get checkpoint
    """

    # --- Lifecycle: wire start/stop into FastAPI events ---

    @app.on_event("startup")
    async def _anip_startup():
        service.start()

    @app.on_event("shutdown")
    async def _anip_shutdown():
        service.stop()

    # --- Discovery & Identity ---

    @app.get(f"{prefix}/.well-known/anip")
    async def discovery():
        return service.get_discovery()

    @app.get(f"{prefix}/.well-known/jwks.json")
    async def jwks():
        return service.get_jwks()

    @app.get(f"{prefix}/anip/manifest")
    async def manifest():
        m = service.get_manifest()
        manifest_dict = m.model_dump() if hasattr(m, "model_dump") else m
        # Sign the manifest
        try:
            import json
            canonical = json.dumps(manifest_dict, sort_keys=True, separators=(",", ":"))
            sig = service._keys.sign_jws_detached(canonical.encode())
            return Response(
                content=json.dumps(manifest_dict),
                media_type="application/json",
                headers={"X-ANIP-Signature": sig},
            )
        except Exception:
            return manifest_dict

    # --- Tokens ---

    @app.post(f"{prefix}/anip/tokens")
    async def issue_token(request: Request):
        principal = _extract_principal(request, service)
        if principal is None:
            return JSONResponse({"error": "Authentication required"}, status_code=401)

        body = await request.json()
        try:
            result = service.issue_token(principal, body)
            return result
        except ANIPError as e:
            return _error_response(e)

    # --- Permissions ---

    @app.get(f"{prefix}/anip/permissions")
    async def permissions(request: Request):
        token = _resolve_token(request, service)
        if token is None:
            return JSONResponse({"error": "Authentication required"}, status_code=401)
        return service.discover_permissions(token)

    # --- Invoke ---

    @app.post(f"{prefix}/anip/invoke/{{capability}}")
    async def invoke(capability: str, request: Request):
        token = _resolve_token(request, service)
        if token is None:
            return JSONResponse({"error": "Authentication required"}, status_code=401)

        body = await request.json()
        params = body.get("parameters", body)
        result = service.invoke(capability, token, params)

        if not result.get("success"):
            status = _failure_status(result.get("failure", {}).get("type"))
            return JSONResponse(result, status_code=status)

        return result

    # --- Audit ---

    @app.get(f"{prefix}/anip/audit")
    async def audit(request: Request):
        token = _resolve_token(request, service)
        if token is None:
            return JSONResponse({"error": "Authentication required"}, status_code=401)

        filters = {
            "capability": request.query_params.get("capability"),
            "since": request.query_params.get("since"),
            "limit": int(request.query_params.get("limit", "50")),
        }
        return service.query_audit(token, filters)

    # --- Checkpoints ---

    @app.get(f"{prefix}/anip/checkpoints")
    async def list_checkpoints(request: Request):
        limit = int(request.query_params.get("limit", "10"))
        return service.get_checkpoints(limit)

    @app.get(f"{prefix}/anip/checkpoints/{{checkpoint_id}}")
    async def get_checkpoint(checkpoint_id: str, request: Request):
        options = {
            "include_proof": request.query_params.get("include_proof") == "true",
            "leaf_index": request.query_params.get("leaf_index"),
            "consistency_from": request.query_params.get("consistency_from"),
        }
        result = service.get_checkpoint(checkpoint_id, options)
        if result is None:
            return JSONResponse({"error": "Checkpoint not found"}, status_code=404)
        return result


def _extract_principal(request: Request, service: ANIPService) -> str | None:
    """Extract authenticated principal from the request.

    Uses service.authenticate_bearer() which tries bootstrap auth (API keys,
    external auth) first, then ANIP JWT verification. This is critical for
    first-token issuance before any ANIP tokens exist.
    """
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return None
    bearer_value = auth[7:].strip()
    return service.authenticate_bearer(bearer_value)


def _resolve_token(request: Request, service: ANIPService):
    """Resolve a bearer token from the Authorization header."""
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return None
    jwt_str = auth[7:].strip()
    try:
        return service.resolve_bearer_token(jwt_str)
    except ANIPError:
        return None


def _failure_status(failure_type: str | None) -> int:
    """Map ANIP failure types to HTTP status codes."""
    mapping = {
        "invalid_token": 401,
        "token_expired": 401,
        "scope_insufficient": 403,
        "insufficient_authority": 403,
        "purpose_mismatch": 403,
        "unknown_capability": 404,
        "not_found": 404,
        "unavailable": 409,
        "concurrent_lock": 409,
        "internal_error": 500,
    }
    return mapping.get(failure_type or "", 400)


def _error_response(error: ANIPError) -> JSONResponse:
    """Map an ANIPError to a JSONResponse."""
    status = _failure_status(error.error_type)
    return JSONResponse(
        {"success": False, "failure": {"type": error.error_type, "detail": error.detail}},
        status_code=status,
    )
```

`__init__.py`:
```python
"""ANIP FastAPI bindings — mount an ANIPService as HTTP routes."""
from .routes import mount_anip

__all__ = ["mount_anip"]
```

**Step 3: Write route tests**

`tests/test_routes.py`:
```python
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from anip_service import ANIPService, Capability, ANIPError
from anip_fastapi import mount_anip
from anip_core import CapabilityDeclaration, CapabilityInput, CapabilityOutput, SideEffect, SideEffectType


def _greet_cap():
    return Capability(
        declaration=CapabilityDeclaration(
            name="greet",
            description="Say hello",
            contract_version="1.0",
            inputs=[CapabilityInput(name="name", type="string", required=True, description="Who")],
            output=CapabilityOutput(type="object", fields=["message"]),
            side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
            minimum_scope=["greet"],
        ),
        handler=lambda ctx, params: {"message": f"Hello, {params['name']}!"},
    )


@pytest.fixture
def client():
    service = ANIPService(
        service_id="test-service",
        capabilities=[_greet_cap()],
        storage=":memory:",
    )
    app = FastAPI()
    mount_anip(app, service)
    return TestClient(app)


class TestDiscoveryRoutes:
    def test_well_known_anip(self, client):
        resp = client.get("/.well-known/anip")
        assert resp.status_code == 200
        data = resp.json()
        assert "anip_discovery" in data
        assert "greet" in data["anip_discovery"]["capabilities"]

    def test_jwks(self, client):
        resp = client.get("/.well-known/jwks.json")
        assert resp.status_code == 200
        data = resp.json()
        assert "keys" in data

    def test_manifest(self, client):
        resp = client.get("/anip/manifest")
        assert resp.status_code == 200

    def test_checkpoints_list(self, client):
        resp = client.get("/anip/checkpoints")
        assert resp.status_code == 200
        assert "checkpoints" in resp.json()

    def test_checkpoint_not_found(self, client):
        resp = client.get("/anip/checkpoints/ckpt-nonexistent")
        assert resp.status_code == 404
```

**Step 4: Run tests**

```bash
cd packages/python/anip-fastapi
pip install -e ".[dev]" -e ../anip-service -e ../anip-server -e ../anip-crypto -e ../anip-core
pytest tests/ -v
```
Expected: All tests PASS

**Step 5: Commit**

```bash
git add packages/python/anip-fastapi/
git commit -m "feat(anip-fastapi): add mount_anip() FastAPI bindings"
```

---

## Task 4: Rewrite Python example to use `anip-service` + `anip-fastapi`

**Files:**
- Create: `examples/anip/app.py`
- Modify: `examples/anip/anip_flight_demo/main.py` → slim down to bootstrap
- Modify: `examples/anip/anip_flight_demo/capabilities/search_flights.py` → Capability object
- Modify: `examples/anip/anip_flight_demo/capabilities/book_flight.py` → Capability object
- Create: `examples/anip/anip_flight_demo/domain/flights.py` (extract from data/)
- Modify: `examples/anip/pyproject.toml` → add new dependencies
- Delete: `examples/anip/anip_flight_demo/engine.py`
- Delete: `examples/anip/anip_flight_demo/data/database.py`

This task is about restructuring the example to prove the new packages work. The exact implementation depends on what the `anip-service` and `anip-fastapi` packages look like after Tasks 1-3 are done. The implementation engineer should:

**Step 1: Update `pyproject.toml`**

Add dependencies:
```toml
dependencies = [
    "anip-service @ file:../../packages/python/anip-service",
    "anip-fastapi @ file:../../packages/python/anip-fastapi",
    "uvicorn>=0.34.0",
]
```

Remove the old direct SDK dependencies (`anip-core`, `anip-crypto`, `anip-server`) — they come transitively through `anip-service`.

**Step 2: Create `app.py`**

This is the new main entrypoint — one `ANIPService` call + `mount_anip`:

```python
"""ANIP Flight Demo — configured via the ANIP service runtime."""
import os
from fastapi import FastAPI
from anip_service import ANIPService
from anip_fastapi import mount_anip

from anip_flight_demo.capabilities.search_flights import search_flights
from anip_flight_demo.capabilities.book_flight import book_flight

# Bootstrap authentication: API keys → principal identities.
# This is how first-token issuance works before any ANIP tokens exist.
API_KEYS = {
    "demo-human-key": "human:samir@example.com",
    "demo-agent-key": "agent:demo-agent",
}

service = ANIPService(
    service_id=os.getenv("ANIP_SERVICE_ID", "anip-flight-service"),
    capabilities=[search_flights, book_flight],
    storage=f"sqlite:///{os.getenv('ANIP_DB_PATH', 'anip.db')}",
    trust=os.getenv("ANIP_TRUST_LEVEL", "signed"),
    key_path=os.getenv("ANIP_KEY_PATH", "./anip-keys"),
    authenticate=lambda bearer: API_KEYS.get(bearer),
)

app = FastAPI(title="ANIP Flight Service")
mount_anip(app, service)
```

**Step 3: Slim down `main.py` to trivial bootstrap**

```python
"""Server bootstrap."""
import uvicorn

def run():
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)

if __name__ == "__main__":
    run()
```

**Step 4: Convert capabilities to `Capability` objects**

Each capability file becomes declaration + handler using the `InvocationContext` pattern. The handler receives `(ctx, params)` and returns plain result data. Business logic stays in `domain/flights.py`.

**Step 5: Extract domain logic**

Move flight-specific business logic (search, booking, data) into `domain/flights.py`, keeping it ANIP-free.

**Step 6: Delete obsolete files**

- `engine.py` — singletons owned by ANIPService
- `data/database.py` — audit/storage owned by ANIPService
- `primitives/checkpoint.py` — remaining checkpoint queue functions owned by runtime

**Step 7: Run existing tests**

```bash
cd examples/anip
pip install -e ".[dev]"
pytest tests/ -v
```

Expect: Many tests will need updating because the API surface has changed. Update test imports and fixtures to use the new `ANIPService` + `mount_anip` approach. Tests that directly called `logAuditEntry` or `database.py` functions should be rewritten to go through `service.invoke()` or `service.query_audit()`.

**Step 8: Commit**

```bash
git add examples/anip/
git commit -m "refactor(example-py): rewrite flight demo using anip-service + anip-fastapi"
```

---

## Task 5: Scaffold TypeScript `@anip/service` package

**Files:**
- Create: `packages/typescript/service/package.json`
- Create: `packages/typescript/service/tsconfig.json`
- Create: `packages/typescript/service/vitest.config.ts`
- Create: `packages/typescript/service/src/index.ts`
- Create: `packages/typescript/service/src/types.ts`

**Step 1: Create `package.json`**

```json
{
  "name": "@anip/service",
  "version": "0.3.0",
  "description": "ANIP service runtime — configure and run an ANIP service",
  "type": "module",
  "main": "dist/index.js",
  "types": "dist/index.d.ts",
  "scripts": {
    "build": "tsc",
    "test": "vitest run"
  },
  "dependencies": {
    "@anip/core": "0.3.0",
    "@anip/crypto": "0.3.0",
    "@anip/server": "0.3.0"
  },
  "devDependencies": {
    "typescript": "^5.5.0",
    "vitest": "^4.1.0"
  }
}
```

**Step 2: Create `tsconfig.json`**

```json
{
  "extends": "../tsconfig.base.json",
  "compilerOptions": {
    "outDir": "dist",
    "rootDir": "src"
  },
  "include": ["src"]
}
```

**Step 3: Create `vitest.config.ts`**

```typescript
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["tests/**/*.test.ts"],
  },
});
```

**Step 4: Create types**

`src/types.ts`:
```typescript
/**
 * Core types for the ANIP service runtime.
 */
import type { CapabilityDeclaration, DelegationToken } from "@anip/core";

export interface InvocationContext {
  token: DelegationToken;
  rootPrincipal: string;
  subject: string;
  scopes: string[];
  delegationChain: string[];
  /** Set actual cost for variance tracking. */
  setCostActual(cost: Record<string, unknown>): void;
}

export type Handler = (
  ctx: InvocationContext,
  params: Record<string, unknown>,
) => Record<string, unknown> | Promise<Record<string, unknown>>;

export interface CapabilityDef {
  declaration: CapabilityDeclaration;
  handler: Handler;
  exclusiveLock?: boolean;
}

export class ANIPError extends Error {
  readonly errorType: string;
  readonly detail: string;

  constructor(errorType: string, detail: string) {
    super(`${errorType}: ${detail}`);
    this.errorType = errorType;
    this.detail = detail;
    this.name = "ANIPError";
  }
}
```

`src/index.ts`:
```typescript
export { ANIPError } from "./types.js";
export type { InvocationContext, Handler, CapabilityDef } from "./types.js";
```

**Step 5: Run type check**

```bash
cd packages/typescript/service
npm install
npx tsc --noEmit
```
Expected: No errors

**Step 6: Commit**

```bash
git add packages/typescript/service/
git commit -m "feat(@anip/service): scaffold TypeScript package with types"
```

---

## Task 6: TypeScript `createANIPService` — builder + invoke + operations

**Files:**
- Create: `packages/typescript/service/src/service.ts`
- Modify: `packages/typescript/service/src/index.ts`
- Test: `packages/typescript/service/tests/service.test.ts`

**Step 1: Implement `createANIPService`**

`src/service.ts` — TypeScript equivalent of the Python `ANIPService`. Follow the same structure:

- Constructor takes `serviceId`, `capabilities`, `storage`, `keyPath`, `trust`
- Storage string parsing: `{ type: "sqlite", path: "..." }` or `":memory:"`
- Creates KeyManager, StorageBackend, DelegationEngine, AuditLog, MerkleTree
- Builds manifest from capability declarations
- Exposes domain-level operations: `getDiscovery()`, `getManifest()`, `getJwks()`, `resolveBearerToken()`, `issueToken()`, `discoverPermissions()`, `invoke()`, `queryAudit()`, `getCheckpoints()`, `getCheckpoint()`

Use the Python `service.py` (Task 2) as the reference — the logic is identical, translated to TypeScript idioms:
- `async logEntry()` (AuditLog is async in TS)
- `async invoke()` (handler can be async)
- `async issueToken()` (JWT signing is async)
- `async resolveBearerToken()` (JWT verification is async)

Key differences from Python:
- Handler type allows `Promise` returns: `(ctx, params) => Record | Promise<Record>`
- AuditLog.logEntry() is async (awaits signer)
- KeyManager methods are async (jose library)
- `defineCapability()` factory function instead of `Capability` class

**Step 2: Add `defineCapability` factory**

```typescript
export function defineCapability(opts: CapabilityDef): CapabilityDef {
  return opts;
}
```

**Step 3: Export from index**

```typescript
export { ANIPError } from "./types.js";
export type { InvocationContext, Handler, CapabilityDef } from "./types.js";
export { createANIPService, defineCapability } from "./service.js";
export type { ANIPServiceOpts, ANIPService } from "./service.js";
```

**Step 4: Write tests**

`tests/service.test.ts` — mirror the Python tests:
- Construction with minimal config
- Manifest built from capabilities
- Discovery document structure
- JWKS available
- Invoke success path
- Invoke with ANIPError
- Invoke with unexpected error
- Cost tracking via setCostActual

**Step 5: Run tests**

```bash
cd packages/typescript/service
npx vitest run
```
Expected: All tests PASS

**Step 6: Commit**

```bash
git add packages/typescript/service/
git commit -m "feat(@anip/service): add createANIPService builder with invoke, audit, checkpoints"
```

---

## Task 7: Scaffold TypeScript `@anip/hono` package with `mountAnip`

**Files:**
- Create: `packages/typescript/hono/package.json`
- Create: `packages/typescript/hono/tsconfig.json`
- Create: `packages/typescript/hono/vitest.config.ts`
- Create: `packages/typescript/hono/src/index.ts`
- Create: `packages/typescript/hono/src/routes.ts`
- Test: `packages/typescript/hono/tests/routes.test.ts`

**Step 1: Create package scaffolding**

`package.json`:
```json
{
  "name": "@anip/hono",
  "version": "0.3.0",
  "description": "ANIP Hono bindings — mount an ANIPService as HTTP routes",
  "type": "module",
  "main": "dist/index.js",
  "types": "dist/index.d.ts",
  "scripts": {
    "build": "tsc",
    "test": "vitest run"
  },
  "dependencies": {
    "@anip/service": "0.3.0",
    "hono": "^4.0.0"
  },
  "devDependencies": {
    "typescript": "^5.5.0",
    "vitest": "^4.1.0"
  }
}
```

**Step 2: Implement `mountAnip`**

`src/routes.ts` — TypeScript equivalent of Python's `mount_anip`:

Same route table:
- `GET /.well-known/anip` → `service.getDiscovery()`
- `GET /.well-known/jwks.json` → `service.getJwks()`
- `GET /anip/manifest` → `service.getManifest()` with X-ANIP-Signature header
- `POST /anip/tokens` → `service.issueToken()`
- `GET /anip/permissions` → `service.discoverPermissions()`
- `POST /anip/invoke/:capability` → `service.invoke()`
- `GET /anip/audit` → `service.queryAudit()`
- `GET /anip/checkpoints` → `service.getCheckpoints()`
- `GET /anip/checkpoints/:id` → `service.getCheckpoint()`

Same binding responsibilities:
- Parse Authorization header → call `service.resolveBearerToken()`
- Parse body/query params
- Map failures to HTTP status codes
- Set response headers

`src/index.ts`:
```typescript
export { mountAnip } from "./routes.js";
```

**Step 3: Write route tests**

Mirror the Python route tests: discovery, JWKS, manifest, checkpoints list, checkpoint 404.

**Step 4: Run tests**

```bash
cd packages/typescript/hono
npm install
npx vitest run
```
Expected: All tests PASS

**Step 5: Commit**

```bash
git add packages/typescript/hono/
git commit -m "feat(@anip/hono): add mountAnip() Hono bindings"
```

---

## Task 8: Rewrite TypeScript example to use `@anip/service` + `@anip/hono`

**Files:**
- Create: `examples/anip-ts/src/app.ts`
- Modify: `examples/anip-ts/src/main.ts` → trivial bootstrap
- Modify: `examples/anip-ts/src/capabilities/search-flights.ts` → defineCapability
- Modify: `examples/anip-ts/src/capabilities/book-flight.ts` → defineCapability
- Create: `examples/anip-ts/src/domain/flights.ts` (extract business logic)
- Modify: `examples/anip-ts/package.json` → add new deps
- Delete: `examples/anip-ts/src/sdk.ts`
- Delete: `examples/anip-ts/src/data/database.ts`
- Delete: `examples/anip-ts/src/delegation-helpers.ts`
- Delete: `examples/anip-ts/src/sink-queue.ts`

This mirrors Task 4 for TypeScript. The implementation engineer should:

**Step 1: Update `package.json`**

Add `@anip/service` and `@anip/hono` dependencies (via `file:` protocol). Remove direct `@anip/core`, `@anip/crypto`, `@anip/server` dependencies.

**Step 2: Create `app.ts`**

```typescript
import { Hono } from "hono";
import { createANIPService } from "@anip/service";
import { mountAnip } from "@anip/hono";
import { searchFlights } from "./capabilities/search-flights.js";
import { bookFlight } from "./capabilities/book-flight.js";

const service = createANIPService({
  serviceId: process.env.ANIP_SERVICE_ID ?? "anip-flight-service",
  capabilities: [searchFlights, bookFlight],
  storage: {
    type: process.env.ANIP_DB_PATH ? "sqlite" : "memory",
    path: process.env.ANIP_DB_PATH ?? ":memory:",
  },
  trust: (process.env.ANIP_TRUST_LEVEL as "signed" | "anchored") ?? "signed",
  keyPath: process.env.ANIP_KEY_PATH ?? "./anip-keys",
});

const app = new Hono();
mountAnip(app, service);

export { app, service };
```

**Step 3: Slim down `main.ts` to bootstrap**

```typescript
import { serve } from "@hono/node-server";
import { app, service } from "./app.js";

service.start();
serve({ fetch: app.fetch, port: 4100 }, (info) => {
  console.log(`ANIP Flight Service running on http://localhost:${info.port}`);
});
```

**Step 4: Convert capabilities to `defineCapability`**

Each capability file becomes declaration + handler. Handlers use `InvocationContext`, return plain data. Business logic in `domain/flights.ts`.

**Step 5: Extract domain logic and delete obsolete files**

Same approach as Python: move flight data/logic into `domain/flights.ts`, delete `sdk.ts`, `database.ts`, `delegation-helpers.ts`, `sink-queue.ts`, and the old `server.ts`.

**Step 6: Update tests**

Tests should use `app.request()` (Hono test client) against the new `app.ts` export, or call `service.invoke()` directly.

**Step 7: Run tests**

```bash
cd examples/anip-ts
npm install
npx vitest run
```

**Step 8: Commit**

```bash
git add examples/anip-ts/
git commit -m "refactor(example-ts): rewrite flight demo using @anip/service + @anip/hono"
```

---

## Task 9: Update documentation and README

**Files:**
- Modify: `README.md` (root)
- Modify: `examples/anip/README.md`
- Modify: `examples/anip-ts/README.md`

**Step 1: Update root README**

Lead with the lightweight path. Show the target developer experience first:

```python
from anip_service import ANIPService, Capability
from anip_fastapi import mount_anip
from fastapi import FastAPI

service = ANIPService(
    service_id="my-service",
    capabilities=[...],
    storage="sqlite:///anip.db",
    trust="signed",
)

app = FastAPI()
mount_anip(app, service)
```

Then show TypeScript equivalent. Then link to advanced/primitive usage for Tier 2 adopters.

**Step 2: Update example READMEs**

Reflect the simplified structure. Highlight that the example is ~150 lines of business logic, not protocol plumbing.

**Step 3: Commit**

```bash
git add README.md examples/anip/README.md examples/anip-ts/README.md
git commit -m "docs: lead with service runtime in README, update example docs"
```

---

## Execution Notes

### Dependency installation order

Python:
```bash
pip install -e packages/python/anip-core
pip install -e packages/python/anip-crypto
pip install -e packages/python/anip-server
pip install -e "packages/python/anip-service[dev]"
pip install -e "packages/python/anip-fastapi[dev]"
```

TypeScript:
```bash
cd packages/typescript/service && npm install && npx tsc
cd packages/typescript/hono && npm install && npx tsc
```

### What to watch for

- **Python signing is sync, TS signing is async**: The service `invoke()` method must be async in TypeScript but can be sync in Python.
- **DelegationEngine API differences**: Method names follow language conventions (`issue_root_token` in Python, `issueRootToken` in TypeScript). Follow the existing patterns.
- **DelegationEngine parameter names**: Use `purpose_parameters` (not `purpose`), `ttl_hours` (not `ttl_seconds`). TS uses `purposeParameters` and `ttlHours`. Neither SDK accepts `constraints` or `authenticated_principal` in `delegate()` — only in `issue_root_token()`.
- **ANIPFailure is a Pydantic model**: Use `isinstance(result, ANIPFailure)`, not `isinstance(result, dict)`. Access fields as attributes: `result.type`, `result.detail`. In TypeScript, use duck-type checking: `"type" in result && "detail" in result && "resolution" in result`.
- **KeyManager method names**: Python uses `get_jwks()` (not `build_jwks()`). TypeScript uses `getJWKS()`. Python `verify_jwt()` requires `audience=` keyword arg; TypeScript `verifyJWT()` does not take an audience parameter.
- **ServiceIdentity fields**: `id`, `jwks_uri`, `issuer_mode` (not `service_id`, `organization`).
- **Bootstrap authentication**: The `authenticate` callback is essential for first-token issuance. Without it, there's no way to get the first ANIP token (chicken-and-egg problem).
- **Lifecycle management**: The framework binding must wire `service.start()`/`service.stop()` into app startup/shutdown events. Without this, the checkpoint scheduler never starts in anchored mode.
- **Storage string parsing**: The `"sqlite:///path"` shorthand should work cross-platform.
- **Test isolation**: Always use `:memory:` storage in tests to avoid state leakage.

### PR strategy

This is a large change. Consider splitting into multiple PRs:
1. PR: `anip-service` + `anip-fastapi` (Python packages)
2. PR: `@anip/service` + `@anip/hono` (TypeScript packages)
3. PR: Example rewrites + docs
