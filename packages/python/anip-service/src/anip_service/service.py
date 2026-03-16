"""ANIP service runtime — the main developer-facing class."""
from __future__ import annotations

import inspect
import json
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable

from anip_core import (
    ANIPFailure,
    ANIPManifest,
    CapabilityDeclaration,
    DelegationToken,
    ResponseMode,
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

    def get_signed_manifest(self) -> tuple[bytes, str]:
        """Return the manifest body bytes and its detached JWS signature.

        Returns (body_bytes, signature) where body_bytes is the exact
        byte sequence that was signed. The framework binding MUST serve
        body_bytes as the response body so that clients can verify
        X-ANIP-Signature against the served content byte-for-byte.
        """
        manifest_dict = self._manifest.model_dump() if hasattr(self._manifest, "model_dump") else self._manifest
        body_bytes = json.dumps(manifest_dict, sort_keys=True, separators=(",", ":")).encode()
        signature = self._keys.sign_jws_detached(body_bytes)
        return body_bytes, signature

    def get_jwks(self) -> dict[str, Any]:
        """Return the JWKS document for this service."""
        return self._keys.get_jwks()

    async def authenticate_bearer(self, bearer_value: str) -> str | None:
        """Resolve a bearer token to an authenticated principal.

        Tries bootstrap authentication first (API keys, external auth),
        then falls back to full ANIP JWT verification via resolve_bearer_token()
        which includes claim-vs-store integrity checks and expiry validation.

        Returns the principal string, or None if unauthenticated.
        """
        # Try bootstrap auth (API keys, external auth)
        if self._authenticate:
            principal = self._authenticate(bearer_value)
            if principal is not None:
                return principal

        # Try ANIP JWT — reuse resolve_bearer_token() for full trust checks
        try:
            stored = await self.resolve_bearer_token(bearer_value)
            return await self._engine.get_root_principal(stored)
        except ANIPError:
            pass

        return None

    async def resolve_bearer_token(self, jwt_string: str) -> DelegationToken:
        """Verify a JWT and return the stored DelegationToken.

        TRUST BOUNDARY: After verifying the JWT signature and loading the
        stored token, compares ALL trust-critical signed claims against
        stored values. This prevents a mutated storage record from being
        accepted as valid.

        Raises ANIPError if token is invalid, expired, unknown, or if
        signed claims do not match stored token fields.
        """
        try:
            claims = self._keys.verify_jwt(jwt_string, audience=self._service_id)
        except Exception as exc:
            raise ANIPError("invalid_token", str(exc)) from exc

        token_id = claims.get("jti")
        if not token_id:
            raise ANIPError("invalid_token", "JWT missing jti claim")

        stored = await self._engine.get_token(token_id)
        if stored is None:
            raise ANIPError("invalid_token", f"Unknown token: {token_id}")

        # TRUST BOUNDARY: compare signed claims against stored token fields.
        mismatches = []
        if claims.get("sub") != stored.subject:
            mismatches.append(f"sub: jwt={claims.get('sub')} store={stored.subject}")
        if sorted(claims.get("scope", [])) != sorted(stored.scope or []):
            mismatches.append(f"scope: jwt={claims.get('scope')} store={stored.scope}")
        if claims.get("capability") != getattr(stored.purpose, "capability", None):
            mismatches.append(
                f"capability: jwt={claims.get('capability')} "
                f"store={getattr(stored.purpose, 'capability', None)}"
            )
        jwt_root = claims.get("root_principal")
        stored_root = await self._engine.get_root_principal(stored)
        if jwt_root is None:
            mismatches.append("root_principal: missing from JWT claims")
        elif jwt_root != stored_root:
            mismatches.append(f"root_principal: jwt={jwt_root} store={stored_root}")
        jwt_parent = claims.get("parent_token_id")
        if jwt_parent != stored.parent:
            mismatches.append(f"parent: jwt={jwt_parent} store={stored.parent}")
        jwt_constraints = claims.get("constraints")
        if jwt_constraints is None:
            mismatches.append("constraints: missing from JWT claims")
        else:
            stored_constraints = (
                stored.constraints.model_dump(mode="json")
                if hasattr(stored.constraints, "model_dump")
                else stored.constraints
            )
            if jwt_constraints != stored_constraints:
                mismatches.append(f"constraints: jwt={jwt_constraints} store={stored_constraints}")

        if mismatches:
            raise ANIPError(
                "invalid_token",
                f"JWT/store mismatch: {'; '.join(mismatches)}",
            )

        return stored

    async def issue_token(
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
            parent = await self._engine.get_token(parent_token_id)
            if parent is None:
                raise ANIPError("invalid_token", f"Parent token not found: {parent_token_id}")

            # TRUST BOUNDARY: only the delegatee (parent's subject) can sub-delegate.
            if authenticated_principal != parent.subject:
                raise ANIPError(
                    "insufficient_authority",
                    f"Caller '{authenticated_principal}' is not the parent token's "
                    f"subject ('{parent.subject}') — only the delegatee can sub-delegate",
                )

            result = await self._engine.delegate(
                parent_token=parent,
                subject=request.get("subject", authenticated_principal),
                scope=request.get("scope", []),
                capability=request.get("capability"),
                purpose_parameters=request.get("purpose_parameters"),
                ttl_hours=ttl_hours,
            )
        else:
            # Root token
            result = await self._engine.issue_root_token(
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
        # Top-level claims checked by resolve_bearer_token trust boundary
        if token.purpose:
            claims["capability"] = getattr(token.purpose, "capability", None)
        claims["parent_token_id"] = token.parent

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

    def get_capability_declaration(self, capability_name: str) -> CapabilityDeclaration | None:
        """Return the capability declaration or None. Used by HTTP bindings for pre-validation."""
        cap = self._capabilities.get(capability_name)
        return cap.declaration if cap else None

    async def invoke(
        self,
        capability_name: str,
        token: DelegationToken,
        params: dict[str, Any],
        *,
        client_reference_id: str | None = None,
        stream: bool = False,
        _progress_sink: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
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
        invocation_id = f"inv-{uuid.uuid4().hex[:12]}"

        # 1. Check capability exists
        if capability_name not in self._capabilities:
            return {
                "success": False,
                "failure": {
                    "type": "unknown_capability",
                    "detail": f"Capability '{capability_name}' not found",
                },
                "invocation_id": invocation_id,
                "client_reference_id": client_reference_id,
            }

        cap = self._capabilities[capability_name]
        decl = cap.declaration

        # Check streaming support
        if stream:
            response_modes = [m.value if hasattr(m, 'value') else m for m in (decl.response_modes or ["unary"])]
            if "streaming" not in response_modes:
                return {
                    "success": False,
                    "failure": {
                        "type": "streaming_not_supported",
                        "detail": f"Capability '{capability_name}' does not support streaming",
                    },
                    "invocation_id": invocation_id,
                    "client_reference_id": client_reference_id,
                }

        # 2. Validate delegation
        min_scope = decl.minimum_scope or []
        validation_result = await self._engine.validate_delegation(
            token, min_scope, capability_name,
        )

        # Check for validation failure (ANIPFailure is a Pydantic model)
        if isinstance(validation_result, ANIPFailure):
            failure = {
                "type": validation_result.type,
                "detail": validation_result.detail,
                "resolution": validation_result.resolution.model_dump() if hasattr(validation_result.resolution, "model_dump") else validation_result.resolution,
            }
            await self._log_audit(
                capability_name, token, success=False,
                failure_type=failure["type"], result_summary=None,
                cost_actual=None, cost_variance=None,
                invocation_id=invocation_id, client_reference_id=client_reference_id,
            )
            return {
                "success": False,
                "failure": failure,
                "invocation_id": invocation_id,
                "client_reference_id": client_reference_id,
            }

        # Use the resolved/stored token from validation
        resolved_token = validation_result

        # Set up progress tracking for streaming
        events_emitted = 0
        events_delivered = 0
        client_disconnected = False
        stream_start = time.monotonic() if stream else 0

        async def _internal_progress_sink(payload: dict[str, Any]) -> None:
            nonlocal events_emitted, events_delivered, client_disconnected
            events_emitted += 1
            if _progress_sink is not None:
                try:
                    await _progress_sink({
                        "invocation_id": invocation_id,
                        "client_reference_id": client_reference_id,
                        "payload": payload,
                    })
                    events_delivered += 1
                except Exception:
                    client_disconnected = True

        # 3. Build invocation context
        chain = await self._engine.get_chain(resolved_token)
        ctx = InvocationContext(
            token=resolved_token,
            root_principal=await self._engine.get_root_principal(resolved_token),
            subject=resolved_token.subject,
            scopes=resolved_token.scope or [],
            delegation_chain=[t.token_id for t in chain],
            invocation_id=invocation_id,
            client_reference_id=client_reference_id,
            _progress_sink=_internal_progress_sink if stream else None,
        )

        # 4. Acquire lock if configured
        locked = False
        if cap.exclusive_lock:
            lock_result = await self._engine.acquire_exclusive_lock(resolved_token)
            if lock_result is not None:
                await self._log_audit(
                    capability_name, resolved_token, success=False,
                    failure_type="concurrent_lock",
                    result_summary=None, cost_actual=None, cost_variance=None,
                    invocation_id=invocation_id, client_reference_id=client_reference_id,
                )
                return {
                    "success": False,
                    "failure": {"type": lock_result.type, "detail": lock_result.detail},
                    "invocation_id": invocation_id,
                    "client_reference_id": client_reference_id,
                }
            locked = True

        try:
            # 5. Call handler (supports both sync and async handlers)
            try:
                result = cap.handler(ctx, params)
                if inspect.isawaitable(result):
                    result = await result
            except ANIPError as e:
                fail_stream_summary: dict[str, Any] | None = None
                if stream:
                    fail_stream_summary = {
                        "response_mode": "streaming",
                        "events_emitted": events_emitted,
                        "events_delivered": events_delivered,
                        "duration_ms": int((time.monotonic() - stream_start) * 1000),
                        "client_disconnected": client_disconnected,
                    }
                await self._log_audit(
                    capability_name, resolved_token, success=False,
                    failure_type=e.error_type,
                    result_summary={"detail": e.detail},
                    cost_actual=None, cost_variance=None,
                    invocation_id=invocation_id, client_reference_id=client_reference_id,
                    stream_summary=fail_stream_summary,
                )
                fail_response: dict[str, Any] = {
                    "success": False,
                    "failure": {"type": e.error_type, "detail": e.detail},
                    "invocation_id": invocation_id,
                    "client_reference_id": client_reference_id,
                }
                if fail_stream_summary:
                    fail_response["stream_summary"] = fail_stream_summary
                return fail_response
            except Exception:
                fail_stream_summary_exc: dict[str, Any] | None = None
                if stream:
                    fail_stream_summary_exc = {
                        "response_mode": "streaming",
                        "events_emitted": events_emitted,
                        "events_delivered": events_delivered,
                        "duration_ms": int((time.monotonic() - stream_start) * 1000),
                        "client_disconnected": client_disconnected,
                    }
                await self._log_audit(
                    capability_name, resolved_token, success=False,
                    failure_type="internal_error",
                    result_summary=None, cost_actual=None, cost_variance=None,
                    invocation_id=invocation_id, client_reference_id=client_reference_id,
                    stream_summary=fail_stream_summary_exc,
                )
                fail_response_exc: dict[str, Any] = {
                    "success": False,
                    "failure": {"type": "internal_error", "detail": "Internal error"},
                    "invocation_id": invocation_id,
                    "client_reference_id": client_reference_id,
                }
                if fail_stream_summary_exc:
                    fail_response_exc["stream_summary"] = fail_stream_summary_exc
                return fail_response_exc

            # 6. Compute cost variance
            cost_actual = ctx._cost_actual
            cost_variance = self._compute_cost_variance(decl, cost_actual)

            # 7. Build stream summary (before audit so it can be persisted)
            stream_summary: dict[str, Any] | None = None
            if stream:
                stream_summary = {
                    "response_mode": "streaming",
                    "events_emitted": events_emitted,
                    "events_delivered": events_emitted,
                    "duration_ms": int((time.monotonic() - stream_start) * 1000),
                    "client_disconnected": False,
                }

            # 8. Log audit (success)
            await self._log_audit(
                capability_name, resolved_token, success=True,
                failure_type=None,
                result_summary=self._summarize_result(result),
                cost_actual=cost_actual,
                cost_variance=cost_variance,
                invocation_id=invocation_id, client_reference_id=client_reference_id,
                stream_summary=stream_summary,
            )

            # 9. Build response
            response: dict[str, Any] = {
                "success": True,
                "result": result,
                "invocation_id": invocation_id,
                "client_reference_id": client_reference_id,
            }
            if cost_actual:
                response["cost_actual"] = cost_actual

            if stream_summary:
                response["stream_summary"] = stream_summary

            return response

        finally:
            if locked:
                await self._engine.release_exclusive_lock(resolved_token)

    async def query_audit(
        self,
        token: DelegationToken,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Query audit entries scoped to the token's root principal."""
        root_principal = await self._engine.get_root_principal(token)
        filters = filters or {}

        entries = await self._audit.query(
            root_principal=root_principal,
            capability=filters.get("capability"),
            since=filters.get("since"),
            invocation_id=filters.get("invocation_id"),
            client_reference_id=filters.get("client_reference_id"),
            limit=min(filters.get("limit", 50), 1000),
        )

        return {
            "entries": entries,
            "count": len(entries),
            "root_principal": root_principal,
            "capability_filter": filters.get("capability"),
            "since_filter": filters.get("since"),
        }

    async def get_checkpoints(self, limit: int = 10) -> dict[str, Any]:
        """Return recent checkpoints."""
        limit = min(limit, 100)
        rows = await self._storage.get_checkpoints(limit)

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

    async def get_checkpoint(
        self,
        checkpoint_id: str,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Return a checkpoint by ID, optionally with proofs."""
        row = await self._storage.get_checkpoint_by_id(checkpoint_id)
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
            tree = await self._rebuild_merkle_to(last_seq)
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
            old_row = await self._storage.get_checkpoint_by_id(consistency_from)
            if old_row:
                old_rng = old_row.get("range", {})
                old_last = old_rng.get("last_sequence", old_row.get("last_sequence", 0))
                new_last = rng.get("last_sequence", row.get("last_sequence", 0))
                old_tree = await self._rebuild_merkle_to(old_last)
                new_tree = await self._rebuild_merkle_to(new_last)
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

    async def _log_audit(
        self,
        capability: str,
        token: DelegationToken,
        *,
        success: bool,
        failure_type: str | None,
        result_summary: dict[str, Any] | None,
        cost_actual: dict[str, Any] | None,
        cost_variance: dict[str, Any] | None,
        invocation_id: str | None = None,
        client_reference_id: str | None = None,
        stream_summary: dict[str, Any] | None = None,
    ) -> None:
        """Log an audit entry through the SDK's AuditLog."""
        chain = await self._engine.get_chain(token)
        await self._audit.log_entry({
            "capability": capability,
            "token_id": token.token_id,
            "root_principal": await self._engine.get_root_principal(token),
            "success": success,
            "failure_type": failure_type,
            "result_summary": result_summary,
            "cost_actual": cost_actual,
            "delegation_chain": [t.token_id for t in chain],
            "invocation_id": invocation_id,
            "client_reference_id": client_reference_id,
            "stream_summary": stream_summary,
        })

        self._entries_since_checkpoint += 1
        if self._checkpoint_policy and self._checkpoint_policy.should_checkpoint(
            self._entries_since_checkpoint
        ):
            await self._create_and_publish_checkpoint()

    async def _create_and_publish_checkpoint(self) -> None:
        """Create a checkpoint and publish to configured sinks."""
        try:
            snapshot = self._audit.get_merkle_snapshot()
            body, signature = create_checkpoint(
                merkle_snapshot=snapshot,
                service_id=self._service_id,
                previous_checkpoint=await self._get_last_checkpoint(),
                sign_fn=self._keys.sign_jws_detached_audit,
            )
            await self._storage.store_checkpoint(body, signature)
            for sink in self._sinks:
                sink.publish({"body": body, "signature": signature})
            self._entries_since_checkpoint = 0
            self._last_checkpoint_time = datetime.now(timezone.utc)
        except Exception:
            pass  # Checkpoint failures are non-fatal

    async def _get_last_checkpoint(self) -> dict[str, Any] | None:
        """Return the most recent checkpoint, or None."""
        rows = await self._storage.get_checkpoints(10000)
        return rows[-1] if rows else None

    async def _rebuild_merkle_to(self, sequence_number: int) -> MerkleTree:
        """Rebuild a Merkle tree from audit entries 1..sequence_number."""
        entries = await self._storage.get_audit_entries_range(1, sequence_number)
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
