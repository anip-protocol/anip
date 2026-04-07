"""ANIP service runtime — the main developer-facing class."""
from __future__ import annotations

import asyncio
import inspect
import json
import os
import re
import socket
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Literal

from anip_core import (
    ANIPFailure,
    ANIPManifest,
    AnchoringPosture,
    AuditPosture,
    Budget,
    CapabilityDeclaration,
    ConcurrentBranches,
    CostCertainty,
    DEFAULT_PROFILE,
    DelegationToken,
    DiscoveryPosture,
    FailureDisclosure,
    PermissionResponse,
    PROTOCOL_VERSION,
    ResponseMode,
    ServiceIdentity,
    TrustPosture,
    AnchoringPolicy,
)


# ---------------------------------------------------------------------------
# Budget / binding / control helpers
# ---------------------------------------------------------------------------

def _parse_iso8601_duration(duration_str: str) -> timedelta:
    """Parse an ISO 8601 duration string like PT15M, PT5M, PT1H30M, PT30S."""
    pattern = r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?'
    match = re.match(pattern, duration_str)
    if not match:
        return timedelta()
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return timedelta(hours=hours, minutes=minutes, seconds=seconds)


def _resolve_bound_price(decl: CapabilityDeclaration, params: dict) -> float | None:
    """Extract bound price from params using capability's binding declarations."""
    for binding in decl.requires_binding:
        if binding.field in params and params[binding.field] is not None:
            bound_value = params[binding.field]
            if isinstance(bound_value, dict) and "price" in bound_value:
                return float(bound_value["price"])
    return None


def _resolve_binding_age(binding_value: Any, now: float | None = None) -> timedelta | None:
    """Determine age of a binding value. Returns None if age cannot be determined."""
    if now is None:
        now = time.time()
    # Try to extract timestamp from binding value
    if isinstance(binding_value, dict) and "issued_at" in binding_value:
        return timedelta(seconds=now - binding_value["issued_at"])
    if isinstance(binding_value, str):
        # Try to extract unix timestamp from format like "qt-hexhex-1234567890"
        parts = binding_value.rsplit("-", 1)
        if len(parts) == 2:
            try:
                ts = int(parts[-1])
                if ts > 1000000000:  # sanity check for unix timestamp
                    return timedelta(seconds=now - ts)
            except (ValueError, OverflowError):
                pass
    return None
from anip_crypto import KeyManager
from anip_server import (
    AuditLog,
    CheckpointPolicy,
    CheckpointScheduler,
    DelegationEngine,
    InMemoryStorage,
    MerkleTree,
    RetentionEnforcer,
    SQLiteStorage,
    StorageBackend,
    build_manifest,
    discover_permissions,
    reconstruct_and_create_checkpoint,
    CheckpointSink,
)

from .aggregation import AggregatedEntry, AuditAggregator
from .classification import classify_event
from .disclosure import resolve_disclosure_level
from .hooks import ANIPHooks, HealthReport
from .redaction import redact_failure
from .retention import RetentionPolicy
from .storage_redaction import storage_redact_entry
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
        authenticate: Callable[[str], str | None | Awaitable[str | None]] | None = None,
        retention_policy: RetentionPolicy | None = None,
        disclosure_level: Literal["full", "reduced", "redacted", "policy"] = "full",
        disclosure_policy: dict[str, str] | None = None,
        aggregation_window: int | None = None,
        exclusive_ttl: int = 60,
        hooks: ANIPHooks | None = None,
    ) -> None:
        self._service_id = service_id
        self._disclosure_level: Literal["full", "reduced", "redacted", "policy"] = disclosure_level
        self._disclosure_policy = disclosure_policy
        self._hooks = hooks or ANIPHooks()
        self._log_hooks = self._hooks.logging
        self._metrics_hooks = self._hooks.metrics
        self._tracing_hooks = self._hooks.tracing

        # --- Bootstrap authentication ---
        self._authenticate = authenticate

        # --- Retention policy (v0.8) ---
        self._retention_policy = retention_policy or RetentionPolicy()

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
                self._storage = InMemoryStorage()
            elif storage.startswith("postgres"):
                from anip_server.postgres import PostgresStorage
                self._storage = PostgresStorage(storage)
            elif storage.startswith("sqlite:///"):
                db_path = storage[len("sqlite:///"):]
                self._storage = SQLiteStorage(db_path)
            else:
                raise ValueError(f"Unknown storage string: {storage!r}. Use 'sqlite:///path', ':memory:', or 'postgres://...'.")
        else:
            self._storage = storage

        # --- Keys ---
        self._keys = KeyManager(key_path)

        # --- Delegation engine ---
        self._exclusive_ttl = exclusive_ttl
        self._engine = DelegationEngine(self._storage, service_id=service_id, exclusive_ttl=exclusive_ttl)

        # --- Audit log ---
        signer = audit_signer or self._keys.sign_audit_entry
        self._audit = AuditLog(self._storage, signer=signer)

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
                    uri = getattr(s, "uri", None)
                    if uri:
                        sink_uris.append(uri)
                    else:
                        directory = getattr(s, "directory", None)
                        if directory:
                            sink_uris.append(f"file://{directory}")
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
        self._last_checkpoint_at: str | None = None  # Updated only when a checkpoint is actually published

        if trust_level == "anchored" and checkpoint_policy:
            self._scheduler = CheckpointScheduler(
                interval_seconds=checkpoint_policy.interval_seconds or 60,
                create_fn=self._leader_checkpoint_tick,
                on_error=self._on_checkpoint_error,
            )

        # --- Retention enforcer (v0.8) ---
        # In cluster mode (Postgres), audit retention is disabled because
        # cumulative checkpoint reconstruction requires all entries from entry 1.
        _skip_retention = hasattr(self._storage, 'initialize')  # PostgresStorage marker
        self._retention_enforcer = RetentionEnforcer(
            self._storage,
            interval_seconds=60,
            skip_audit_retention=_skip_retention,
            on_sweep=self._on_retention_sweep,
            on_error=self._on_retention_error,
        )

        # --- Audit aggregation (v0.9) ---
        if aggregation_window is not None:
            self._aggregator: AuditAggregator | None = AuditAggregator(window_seconds=aggregation_window)
            self._aggregation_window = aggregation_window
        else:
            self._aggregator = None
            self._aggregation_window = None
        self._flush_task: asyncio.Task[None] | None = None

    # --- Public domain-level operations ---

    def get_discovery(self, *, base_url: str | None = None) -> dict[str, Any]:
        """Return lightweight discovery document per SPEC.md §6.1."""
        caps_summary = {}
        for name, cap in self._capabilities.items():
            decl = cap.declaration
            caps_summary[name] = {
                "description": decl.description,
                "side_effect": decl.side_effect.type.value if decl.side_effect else None,
                "minimum_scope": decl.minimum_scope,
                "financial": decl.cost is not None and decl.cost.financial is not None,
                "contract": decl.contract_version,
            }

        # Build posture from existing service state (v0.7)
        anchoring_src = self._manifest.trust.anchoring if self._manifest.trust else None
        is_anchored = self._trust_level in ("anchored", "attested")
        failure_disc = FailureDisclosure(
            detail_level=self._disclosure_level,
            caller_classes=list(self._disclosure_policy.keys()) if self._disclosure_level == "policy" and self._disclosure_policy else None,
        )
        posture = DiscoveryPosture(
            audit=AuditPosture(
                retention=self._retention_policy.default_retention or "P90D",
                retention_enforced=self._retention_enforcer.is_running and not getattr(self._retention_enforcer, '_skip_audit_retention', False),
            ),
            failure_disclosure=failure_disc,
            anchoring=AnchoringPosture(
                enabled=is_anchored,
                cadence=anchoring_src.cadence if anchoring_src else None,
                max_lag=anchoring_src.max_lag if anchoring_src else None,
                proofs_available=is_anchored and self._checkpoint_policy is not None,
            ),
        )

        doc: dict[str, Any] = {
            "protocol": PROTOCOL_VERSION,
            "compliance": "anip-compliant",
            "profile": {**DEFAULT_PROFILE},
            "auth": {
                "delegation_token_required": True,
                "supported_formats": ["anip-v1"],
                "minimum_scope_for_discovery": "none",
            },
            "capabilities": caps_summary,
            "trust_level": self._trust_level,
            "posture": posture.model_dump(),
            "endpoints": {
                "manifest": "/anip/manifest",
                "permissions": "/anip/permissions",
                "invoke": "/anip/invoke/{capability}",
                "tokens": "/anip/tokens",
                "audit": "/anip/audit",
                "checkpoints": "/anip/checkpoints",
                "jwks": "/.well-known/jwks.json",
            },
        }

        if base_url is not None:
            doc["base_url"] = base_url

        return {"anip_discovery": doc}

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
        # Try bootstrap auth (API keys, external auth).
        # Supports both sync and async hooks: if the hook returns a coroutine,
        # we await it; otherwise we use the value directly.
        if self._authenticate:
            result = self._authenticate(bearer_value)
            if inspect.isawaitable(result):
                principal = await result
            else:
                from typing import cast
                principal = cast("str | None", result)
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

        # Parse budget from request if present
        budget_data = request.get("budget")
        budget: Budget | None = None
        if budget_data is not None:
            if isinstance(budget_data, Budget):
                budget = budget_data
            elif isinstance(budget_data, dict):
                budget = Budget(**budget_data)

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

            capability: str = request.get("capability", "")
            result = await self._engine.delegate(
                parent_token=parent,
                subject=request.get("subject", authenticated_principal),
                scope=request.get("scope", []),
                capability=capability,
                purpose_parameters=request.get("purpose_parameters"),
                ttl_hours=ttl_hours,
                budget=budget,
            )
        else:
            # Root token
            capability: str = request.get("capability", "")
            result = await self._engine.issue_root_token(
                authenticated_principal=authenticated_principal,
                subject=request.get("subject", authenticated_principal),
                scope=request.get("scope", []),
                capability=capability,
                purpose_parameters=request.get("purpose_parameters"),
                ttl_hours=ttl_hours,
                budget=budget,
            )

        # Check for delegation failure (ANIPFailure is a Pydantic model)
        if isinstance(result, ANIPFailure):
            raise ANIPError(result.type, result.detail)

        token, token_id = result

        # Apply caller_class from request and persist the update
        caller_class = request.get("caller_class")
        if caller_class is not None:
            token = token.model_copy(update={"caller_class": caller_class})
            await self._engine.register_token(token)

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
        if token.caller_class is not None:
            claims["anip:caller_class"] = token.caller_class

        jwt_str = self._keys.sign_jwt(claims)

        response = {
            "issued": True,
            "token_id": token_id,
            "token": jwt_str,
            "expires": expires.isoformat(),
        }

        # Echo budget in issuance response if present
        if token.constraints and token.constraints.budget:
            response["budget"] = token.constraints.budget.model_dump()

        return response

    async def issue_capability_token(
        self,
        principal: str,
        capability: str,
        scope: list[str],
        *,
        purpose_parameters: dict[str, Any] | None = None,
        ttl_hours: int = 2,
        budget: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Issue a root token pre-bound to a specific capability.

        ``scope`` must be explicitly provided -- capability names and scope
        strings are different things (e.g. capability ``evaluate_service_design``
        may need scope ``studio.workbench.evaluate_service_design``).

        This helper covers **root issuance only**.  For delegation flows
        (``parent_token``, non-default ``subject``, ``caller_class``), use
        :meth:`issue_token` directly until ``parent_token`` semantics are
        resolved across runtimes (deferred to v0.21).
        """
        request: dict[str, Any] = {
            "subject": principal,
            "capability": capability,
            "scope": scope,
            "ttl_hours": ttl_hours,
        }
        if purpose_parameters is not None:
            request["purpose_parameters"] = purpose_parameters
        if budget is not None:
            request["budget"] = budget
        return await self.issue_token(principal, request)

    async def issue_delegated_capability_token(
        self,
        principal: str,
        parent_token: str,
        capability: str,
        scope: list[str],
        subject: str,
        *,
        caller_class: str | None = None,
        purpose_parameters: dict[str, Any] | None = None,
        ttl_hours: int = 2,
        budget: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Issue a delegated token from an existing parent token.

        This is the delegated counterpart to :meth:`issue_capability_token`.
        ``parent_token`` is a token ID (not a JWT) -- the service looks up
        the parent by ID in storage.  ``scope`` must be explicitly provided.
        """
        request: dict[str, Any] = {
            "subject": subject,
            "capability": capability,
            "scope": scope,
            "parent_token": parent_token,
            "ttl_hours": ttl_hours,
        }
        if caller_class is not None:
            request["caller_class"] = caller_class
        if purpose_parameters is not None:
            request["purpose_parameters"] = purpose_parameters
        if budget is not None:
            request["budget"] = budget
        return await self.issue_token(principal, request)

    def discover_permissions(self, token: DelegationToken) -> PermissionResponse:
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
        task_id: str | None = None,
        parent_invocation_id: str | None = None,
        upstream_service: str | None = None,
        stream: bool = False,
        budget: dict[str, Any] | None = None,
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
        invoke_start = time.monotonic()

        # Start root tracing span
        root_span = None
        if self._tracing_hooks and self._tracing_hooks.start_span:
            try:
                root_span = self._tracing_hooks.start_span({
                    "name": "anip.invoke",
                    "attributes": {"capability": capability_name},
                })
            except Exception:
                root_span = None
        _invoke_span_ended = False
        try:
            return await self._invoke_body(
                capability_name, token, params,
                client_reference_id=client_reference_id,
                task_id=task_id,
                parent_invocation_id=parent_invocation_id,
                upstream_service=upstream_service,
                stream=stream,
                budget=budget,
                _progress_sink=_progress_sink,
                invocation_id=invocation_id,
                invoke_start=invoke_start,
                root_span=root_span,
            )
        except Exception as e:
            _invoke_span_ended = True
            if self._tracing_hooks and self._tracing_hooks.end_span and root_span is not None:
                try:
                    self._tracing_hooks.end_span({
                        "span": root_span,
                        "status": "error",
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                    })
                except Exception:
                    pass
            raise
        finally:
            if not _invoke_span_ended and self._tracing_hooks and self._tracing_hooks.end_span and root_span is not None:
                try:
                    self._tracing_hooks.end_span({"span": root_span, "status": "ok"})
                except Exception:
                    pass

    async def _invoke_body(
        self,
        capability_name: str,
        token: DelegationToken,
        params: dict[str, Any],
        *,
        client_reference_id: str | None,
        task_id: str | None,
        parent_invocation_id: str | None,
        upstream_service: str | None,
        stream: bool,
        budget: dict[str, Any] | None,
        _progress_sink: Callable[[dict[str, Any]], Awaitable[None]] | None,
        invocation_id: str,
        invoke_start: float,
        root_span: Any,
    ) -> dict[str, Any]:

        # Resolve effective disclosure level for this caller
        effective_level = resolve_disclosure_level(
            self._disclosure_level,
            token_claims={"anip:caller_class": token.caller_class, "scope": token.scope} if token else None,
            disclosure_policy=self._disclosure_policy,
        )

        # task_id precedence: token purpose.task_id is authoritative
        token_task_id = getattr(token.purpose, 'task_id', None) if token.purpose else None
        if token_task_id and task_id and task_id != token_task_id:
            _duration_ms = int((time.monotonic() - invoke_start) * 1000)
            return {
                "success": False,
                "failure": {
                    "type": "purpose_mismatch",
                    "detail": f"Request task_id '{task_id}' does not match token purpose task_id '{token_task_id}'",
                    "resolution": {"action": "revalidate_state", "recovery_class": "revalidate_then_retry", "requires": "matching task_id or omit from request"},
                    "retry": False,
                },
                "invocation_id": invocation_id,
                "client_reference_id": client_reference_id,
                "task_id": task_id,
                "parent_invocation_id": parent_invocation_id,
                "upstream_service": upstream_service,
            }
        effective_task_id = task_id or token_task_id

        # 1. Check capability exists
        if capability_name not in self._capabilities:
            _duration_ms = int((time.monotonic() - invoke_start) * 1000)
            if self._log_hooks and self._log_hooks.on_invocation_end:
                self._safe_hook(self._log_hooks.on_invocation_end, {
                    "capability": capability_name,
                    "invocation_id": invocation_id,
                    "success": False,
                    "failure_type": "unknown_capability",
                    "duration_ms": _duration_ms,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            if self._metrics_hooks and self._metrics_hooks.on_invocation_duration:
                self._safe_hook(self._metrics_hooks.on_invocation_duration, {"capability": capability_name, "duration_ms": _duration_ms, "success": False})
            return {
                "success": False,
                "failure": redact_failure({
                    "type": "unknown_capability",
                    "detail": f"Capability '{capability_name}' not found",
                    "resolution": {"action": "check_manifest", "recovery_class": "revalidate_then_retry"},
                }, effective_level),
                "invocation_id": invocation_id,
                "client_reference_id": client_reference_id,
                "task_id": effective_task_id,
                "parent_invocation_id": parent_invocation_id,
                "upstream_service": upstream_service,
            }

        cap = self._capabilities[capability_name]
        decl = cap.declaration

        # Check streaming support
        if stream:
            response_modes = [m.value if hasattr(m, 'value') else m for m in (decl.response_modes or ["unary"])]  # noqa: E501  # pyright: ignore[reportAttributeAccessIssue]
            if "streaming" not in response_modes:
                _duration_ms = int((time.monotonic() - invoke_start) * 1000)
                if self._log_hooks and self._log_hooks.on_invocation_end:
                    self._safe_hook(self._log_hooks.on_invocation_end, {
                        "capability": capability_name,
                        "invocation_id": invocation_id,
                        "success": False,
                        "failure_type": "streaming_not_supported",
                        "duration_ms": _duration_ms,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                if self._metrics_hooks and self._metrics_hooks.on_invocation_duration:
                    self._safe_hook(self._metrics_hooks.on_invocation_duration, {"capability": capability_name, "duration_ms": _duration_ms, "success": False})
                return {
                    "success": False,
                    "failure": redact_failure({
                        "type": "streaming_not_supported",
                        "detail": f"Capability '{capability_name}' does not support streaming",
                        "resolution": {"action": "check_manifest", "recovery_class": "revalidate_then_retry"},
                    }, effective_level),
                    "invocation_id": invocation_id,
                    "client_reference_id": client_reference_id,
                    "task_id": effective_task_id,
                    "parent_invocation_id": parent_invocation_id,
                    "upstream_service": upstream_service,
                }

        # 2. Validate delegation
        min_scope = decl.minimum_scope or []
        validation_result = await self._with_span(
            "anip.delegation.validate", {"capability": capability_name}, root_span,
            lambda: self._engine.validate_delegation(token, min_scope, capability_name),
        )

        # Check for validation failure (ANIPFailure is a Pydantic model)
        if isinstance(validation_result, ANIPFailure):
            failure = {
                "type": validation_result.type,
                "detail": validation_result.detail,
                "resolution": validation_result.resolution.model_dump() if hasattr(validation_result.resolution, "model_dump") else validation_result.resolution,
            }
            if self._log_hooks and self._log_hooks.on_delegation_failure:
                self._safe_hook(self._log_hooks.on_delegation_failure, {
                    "reason": failure["type"],
                    "token_id": token.token_id if token else None,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            if self._metrics_hooks and self._metrics_hooks.on_delegation_denied:
                self._safe_hook(self._metrics_hooks.on_delegation_denied, {"reason": failure["type"]})
            _side_effect_type = decl.side_effect.type.value if decl.side_effect else None
            _event_class = classify_event(_side_effect_type, False, failure["type"])
            _retention_tier = self._retention_policy.resolve_tier(_event_class)
            _expires_at = self._retention_policy.compute_expires_at(_retention_tier)
            await self._log_audit(
                capability_name, token, success=False,
                failure_type=failure["type"], result_summary=None,
                cost_actual=None, cost_variance=None,
                invocation_id=invocation_id, client_reference_id=client_reference_id,
                task_id=effective_task_id, parent_invocation_id=parent_invocation_id,
                upstream_service=upstream_service,
                event_class=_event_class, retention_tier=_retention_tier, expires_at=_expires_at,
                parent_span=root_span,
            )
            _deleg_duration_ms = int((time.monotonic() - invoke_start) * 1000)
            if self._log_hooks and self._log_hooks.on_invocation_end:
                self._safe_hook(self._log_hooks.on_invocation_end, {
                    "capability": capability_name,
                    "invocation_id": invocation_id,
                    "success": False,
                    "failure_type": failure["type"],
                    "duration_ms": _deleg_duration_ms,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            if self._metrics_hooks and self._metrics_hooks.on_invocation_duration:
                self._safe_hook(self._metrics_hooks.on_invocation_duration, {"capability": capability_name, "duration_ms": _deleg_duration_ms, "success": False})
            return {
                "success": False,
                "failure": redact_failure(failure, effective_level),
                "invocation_id": invocation_id,
                "client_reference_id": client_reference_id,
                "task_id": effective_task_id,
                "parent_invocation_id": parent_invocation_id,
                "upstream_service": upstream_service,
            }

        # Use the resolved/stored token from validation
        resolved_token = validation_result

        # --- Budget, binding, and control requirement enforcement (v0.14) ---

        # Parse invocation-level budget hint if present
        request_budget = None
        if budget:
            request_budget = Budget(currency=budget["currency"], max_amount=budget["max_amount"])

        # Determine effective budget (token is ceiling, invocation hint can only narrow)
        effective_budget: Budget | None = None
        if resolved_token.constraints and resolved_token.constraints.budget:
            effective_budget = resolved_token.constraints.budget
            if request_budget is not None:
                if request_budget.currency != effective_budget.currency:
                    return {
                        "success": False,
                        "failure": redact_failure({
                            "type": "budget_currency_mismatch",
                            "detail": f"Invocation budget is in {request_budget.currency} but token budget is in {effective_budget.currency}",
                            "resolution": {"action": "request_matching_currency_delegation", "recovery_class": "redelegation_then_retry"},
                        }, effective_level),
                        "invocation_id": invocation_id,
                        "client_reference_id": client_reference_id,
                        "task_id": effective_task_id,
                        "parent_invocation_id": parent_invocation_id,
                        "upstream_service": upstream_service,
                    }
                effective_budget = Budget(
                    currency=effective_budget.currency,
                    max_amount=min(effective_budget.max_amount, request_budget.max_amount),
                )
        elif request_budget is not None:
            effective_budget = request_budget

        # Budget enforcement against declared cost
        check_amount: float | None = None
        if effective_budget:
            if decl.cost and decl.cost.financial:
                if decl.cost.financial.currency != effective_budget.currency:
                    return {
                        "success": False,
                        "failure": redact_failure({
                            "type": "budget_currency_mismatch",
                            "detail": f"Token budget is in {effective_budget.currency} but capability cost is in {decl.cost.financial.currency}",
                            "resolution": {"action": "request_matching_currency_delegation", "recovery_class": "redelegation_then_retry"},
                        }, effective_level),
                        "invocation_id": invocation_id,
                        "client_reference_id": client_reference_id,
                        "task_id": effective_task_id,
                        "parent_invocation_id": parent_invocation_id,
                        "upstream_service": upstream_service,
                    }

                if decl.cost.certainty == CostCertainty.FIXED:
                    check_amount = decl.cost.financial.amount
                elif decl.cost.certainty == CostCertainty.ESTIMATED:
                    if decl.requires_binding:
                        bound_price = _resolve_bound_price(decl, params)
                        if bound_price is not None:
                            check_amount = bound_price
                        else:
                            # Binding exists but no resolvable price — budget cannot be enforced.
                            # If the binding field is missing entirely, binding_missing will also fire below,
                            # but we must not silently skip budget enforcement when the field IS present
                            # but doesn't carry a concrete price.
                            return {
                                "success": False,
                                "failure": redact_failure({
                                    "type": "budget_not_enforceable",
                                    "detail": f"Capability {decl.name} has estimated cost with requires_binding but the provided binding does not carry a resolvable price",
                                    "resolution": {"action": "obtain_binding", "recovery_class": "refresh_then_retry", "requires": "binding value must include a 'price' field or the service must resolve binding to a concrete price"},
                                    "retry": False,
                                }, effective_level),
                                "invocation_id": invocation_id,
                                "client_reference_id": client_reference_id,
                                "task_id": effective_task_id,
                                "parent_invocation_id": parent_invocation_id,
                                "upstream_service": upstream_service,
                            }
                    else:
                        return {
                            "success": False,
                            "failure": redact_failure({
                                "type": "budget_not_enforceable",
                                "detail": f"Capability {decl.name} has estimated cost but no requires_binding — budget cannot be enforced",
                                "resolution": {"action": "escalate_to_root_principal", "recovery_class": "terminal"},
                            }, effective_level),
                            "invocation_id": invocation_id,
                            "client_reference_id": client_reference_id,
                            "task_id": effective_task_id,
                            "parent_invocation_id": parent_invocation_id,
                            "upstream_service": upstream_service,
                        }
                elif decl.cost.certainty == CostCertainty.DYNAMIC:
                    check_amount = decl.cost.financial.upper_bound

                if check_amount is not None and check_amount > effective_budget.max_amount:
                    return {
                        "success": False,
                        "failure": redact_failure({
                            "type": "budget_exceeded",
                            "detail": f"Cost ${check_amount} exceeds budget ${effective_budget.max_amount}",
                            "resolution": {"action": "request_budget_increase", "recovery_class": "redelegation_then_retry"},
                        }, effective_level),
                        "budget_context": {
                            "budget_max": effective_budget.max_amount,
                            "budget_currency": effective_budget.currency,
                            "cost_check_amount": check_amount,
                            "cost_certainty": decl.cost.certainty.value,
                            "cost_actual": None,
                            "within_budget": False,
                        },
                        "invocation_id": invocation_id,
                        "client_reference_id": client_reference_id,
                        "task_id": effective_task_id,
                        "parent_invocation_id": parent_invocation_id,
                        "upstream_service": upstream_service,
                    }

        # Binding enforcement
        for binding in decl.requires_binding:
            if binding.field not in params or params[binding.field] is None:
                return {
                    "success": False,
                    "failure": redact_failure({
                        "type": "binding_missing",
                        "detail": f"Capability {decl.name} requires '{binding.field}' (type: {binding.type})",
                        "resolution": {
                            "action": "obtain_binding",
                            "recovery_class": "refresh_then_retry",
                            "requires": f"invoke {binding.source_capability or 'source capability'} to obtain a {binding.field}",
                        },
                    }, effective_level),
                    "invocation_id": invocation_id,
                    "client_reference_id": client_reference_id,
                    "task_id": effective_task_id,
                    "parent_invocation_id": parent_invocation_id,
                    "upstream_service": upstream_service,
                }
            if binding.max_age:
                age = _resolve_binding_age(params[binding.field])
                if age is not None and age > _parse_iso8601_duration(binding.max_age):
                    return {
                        "success": False,
                        "failure": redact_failure({
                            "type": "binding_stale",
                            "detail": f"Binding '{binding.field}' has exceeded max_age of {binding.max_age}",
                            "resolution": {
                                "action": "refresh_binding",
                                "recovery_class": "refresh_then_retry",
                                "requires": f"invoke {binding.source_capability or 'source capability'} again for a fresh {binding.field}",
                            },
                        }, effective_level),
                        "invocation_id": invocation_id,
                        "client_reference_id": client_reference_id,
                        "task_id": effective_task_id,
                        "parent_invocation_id": parent_invocation_id,
                        "upstream_service": upstream_service,
                    }

        # Control requirement enforcement (reject only — no warn in v0.14).
        # NOTE: The stronger_delegation_required check below is defence-in-depth.
        # Purpose validation in the delegation engine (purpose.capability != invoked
        # capability -> purpose_mismatch) fires before this loop, making the
        # stronger_delegation_required branch unreachable through normal invoke.
        for req in decl.control_requirements:
            satisfied = True
            if req.type == "cost_ceiling":
                satisfied = effective_budget is not None
            elif req.type == "stronger_delegation_required":
                satisfied = (
                    hasattr(resolved_token, 'purpose')
                    and resolved_token.purpose
                    and resolved_token.purpose.capability == decl.name
                )

            if not satisfied:
                return {
                    "success": False,
                    "failure": redact_failure({
                        "type": "control_requirement_unsatisfied",
                        "detail": f"Capability {decl.name} requires {req.type}",
                        "unsatisfied_requirements": [req.type],
                        "resolution": {"action": "request_capability_binding", "recovery_class": "redelegation_then_retry"},
                    }, effective_level),
                    "invocation_id": invocation_id,
                    "client_reference_id": client_reference_id,
                    "task_id": effective_task_id,
                    "parent_invocation_id": parent_invocation_id,
                    "upstream_service": upstream_service,
                }

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
                    if self._metrics_hooks and self._metrics_hooks.on_streaming_delivery_failure:
                        self._safe_hook(self._metrics_hooks.on_streaming_delivery_failure, {"capability": capability_name})

        # Pre-compute audit context for budget and binding (available to all audit calls below)
        _audit_budget_base: dict[str, Any] | None = None
        if effective_budget:
            _audit_budget_base = {
                "budget_max": effective_budget.max_amount,
                "budget_currency": effective_budget.currency,
                "cost_check_amount": check_amount,
                "cost_certainty": decl.cost.certainty.value if decl.cost else None,
                "cost_actual": None,
                "within_budget": False,
            }

        _audit_binding_base: dict[str, Any] | None = None
        if decl.requires_binding:
            _audit_binding_base = {
                "bindings_required": [b.field for b in decl.requires_binding],
                "bindings_provided": [b.field for b in decl.requires_binding if b.field in params],
            }

        # 3. Build invocation context
        chain = await self._engine.get_chain(resolved_token)
        root_principal = await self._engine.get_root_principal(resolved_token)
        ctx = InvocationContext(
            token=resolved_token,
            root_principal=root_principal,
            subject=resolved_token.subject,
            scopes=resolved_token.scope or [],
            delegation_chain=[t.token_id for t in chain],
            invocation_id=invocation_id,
            client_reference_id=client_reference_id,
            _progress_sink=_internal_progress_sink if stream else None,
        )

        if self._log_hooks and self._log_hooks.on_invocation_start:
            self._safe_hook(self._log_hooks.on_invocation_start, {
                "capability": capability_name,
                "invocation_id": invocation_id,
                "client_reference_id": client_reference_id,
                "root_principal": root_principal,
                "subject": resolved_token.subject,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        # 4. Acquire lock if configured
        locked = False
        if cap.exclusive_lock:
            lock_result = await self._engine.acquire_exclusive_lock(resolved_token)
            if lock_result is not None:
                _side_effect_type = decl.side_effect.type.value if decl.side_effect else None
                _event_class = classify_event(_side_effect_type, False, "concurrent_lock")
                _retention_tier = self._retention_policy.resolve_tier(_event_class)
                _expires_at = self._retention_policy.compute_expires_at(_retention_tier)
                await self._log_audit(
                    capability_name, resolved_token, success=False,
                    failure_type="concurrent_lock",
                    result_summary=None, cost_actual=None, cost_variance=None,
                    invocation_id=invocation_id, client_reference_id=client_reference_id,
                    task_id=effective_task_id, parent_invocation_id=parent_invocation_id,
                    upstream_service=upstream_service,
                    event_class=_event_class, retention_tier=_retention_tier, expires_at=_expires_at,
                    parent_span=root_span,
                    budget_context=_audit_budget_base,
                    binding_context=_audit_binding_base,
                )
                _lock_duration_ms = int((time.monotonic() - invoke_start) * 1000)
                if self._log_hooks and self._log_hooks.on_invocation_end:
                    self._safe_hook(self._log_hooks.on_invocation_end, {
                        "capability": capability_name,
                        "invocation_id": invocation_id,
                        "success": False,
                        "failure_type": "concurrent_lock",
                        "duration_ms": _lock_duration_ms,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                if self._metrics_hooks and self._metrics_hooks.on_invocation_duration:
                    self._safe_hook(self._metrics_hooks.on_invocation_duration, {"capability": capability_name, "duration_ms": _lock_duration_ms, "success": False})
                return {
                    "success": False,
                    "failure": redact_failure({"type": lock_result.type, "detail": lock_result.detail}, effective_level),
                    "invocation_id": invocation_id,
                    "client_reference_id": client_reference_id,
                    "task_id": effective_task_id,
                    "parent_invocation_id": parent_invocation_id,
                    "upstream_service": upstream_service,
                }
            locked = True

        try:
            # 5. Call handler (supports both sync and async handlers)
            try:
                async def _run_handler() -> Any:
                    r = cap.handler(ctx, params)
                    if inspect.isawaitable(r):
                        r = await r
                    return r

                async def _handler_with_heartbeat():
                    return await self._run_with_exclusive_heartbeat(
                        resolved_token, _run_handler()
                    )

                result = await self._with_span(
                    "anip.handler.execute", {"capability": capability_name}, root_span,
                    _handler_with_heartbeat,
                )
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
                _side_effect_type = decl.side_effect.type.value if decl.side_effect else None
                _event_class = classify_event(_side_effect_type, False, e.error_type)
                _retention_tier = self._retention_policy.resolve_tier(_event_class)
                _expires_at = self._retention_policy.compute_expires_at(_retention_tier)
                await self._log_audit(
                    capability_name, resolved_token, success=False,
                    failure_type=e.error_type,
                    result_summary={"detail": e.detail},
                    cost_actual=None, cost_variance=None,
                    invocation_id=invocation_id, client_reference_id=client_reference_id,
                    task_id=effective_task_id, parent_invocation_id=parent_invocation_id,
                    upstream_service=upstream_service,
                    stream_summary=fail_stream_summary,
                    event_class=_event_class, retention_tier=_retention_tier, expires_at=_expires_at,
                    parent_span=root_span,
                    budget_context=_audit_budget_base,
                    binding_context=_audit_binding_base,
                )
                if stream and fail_stream_summary and self._log_hooks and self._log_hooks.on_streaming_summary:
                    self._safe_hook(self._log_hooks.on_streaming_summary, {
                        "invocation_id": invocation_id,
                        "capability": capability_name,
                        "events_emitted": events_emitted,
                        "events_delivered": events_delivered,
                        "client_disconnected": client_disconnected,
                        "duration_ms": int((time.monotonic() - stream_start) * 1000),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                _anip_err_duration_ms = int((time.monotonic() - invoke_start) * 1000)
                if self._log_hooks and self._log_hooks.on_invocation_end:
                    self._safe_hook(self._log_hooks.on_invocation_end, {
                        "capability": capability_name,
                        "invocation_id": invocation_id,
                        "success": False,
                        "failure_type": e.error_type,
                        "duration_ms": _anip_err_duration_ms,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                if self._metrics_hooks and self._metrics_hooks.on_invocation_duration:
                    self._safe_hook(self._metrics_hooks.on_invocation_duration, {"capability": capability_name, "duration_ms": _anip_err_duration_ms, "success": False})
                _fail_dict: dict[str, Any] = {"type": e.error_type, "detail": e.detail}
                if e.resolution is not None:
                    _fail_dict["resolution"] = e.resolution
                fail_response: dict[str, Any] = {
                    "success": False,
                    "failure": redact_failure(_fail_dict, effective_level),
                    "invocation_id": invocation_id,
                    "client_reference_id": client_reference_id,
                    "task_id": effective_task_id,
                    "parent_invocation_id": parent_invocation_id,
                    "upstream_service": upstream_service,
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
                _side_effect_type = decl.side_effect.type.value if decl.side_effect else None
                _event_class = classify_event(_side_effect_type, False, "internal_error")
                _retention_tier = self._retention_policy.resolve_tier(_event_class)
                _expires_at = self._retention_policy.compute_expires_at(_retention_tier)
                await self._log_audit(
                    capability_name, resolved_token, success=False,
                    failure_type="internal_error",
                    result_summary=None, cost_actual=None, cost_variance=None,
                    invocation_id=invocation_id, client_reference_id=client_reference_id,
                    task_id=effective_task_id, parent_invocation_id=parent_invocation_id,
                    upstream_service=upstream_service,
                    stream_summary=fail_stream_summary_exc,
                    event_class=_event_class, retention_tier=_retention_tier, expires_at=_expires_at,
                    parent_span=root_span,
                    budget_context=_audit_budget_base,
                    binding_context=_audit_binding_base,
                )
                if stream and fail_stream_summary_exc and self._log_hooks and self._log_hooks.on_streaming_summary:
                    self._safe_hook(self._log_hooks.on_streaming_summary, {
                        "invocation_id": invocation_id,
                        "capability": capability_name,
                        "events_emitted": events_emitted,
                        "events_delivered": events_delivered,
                        "client_disconnected": client_disconnected,
                        "duration_ms": int((time.monotonic() - stream_start) * 1000),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                _internal_err_duration_ms = int((time.monotonic() - invoke_start) * 1000)
                if self._log_hooks and self._log_hooks.on_invocation_end:
                    self._safe_hook(self._log_hooks.on_invocation_end, {
                        "capability": capability_name,
                        "invocation_id": invocation_id,
                        "success": False,
                        "failure_type": "internal_error",
                        "duration_ms": _internal_err_duration_ms,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                if self._metrics_hooks and self._metrics_hooks.on_invocation_duration:
                    self._safe_hook(self._metrics_hooks.on_invocation_duration, {"capability": capability_name, "duration_ms": _internal_err_duration_ms, "success": False})
                fail_response_exc: dict[str, Any] = {
                    "success": False,
                    "failure": redact_failure({"type": "internal_error", "detail": "Internal error"}, effective_level),
                    "invocation_id": invocation_id,
                    "client_reference_id": client_reference_id,
                    "task_id": effective_task_id,
                    "parent_invocation_id": parent_invocation_id,
                    "upstream_service": upstream_service,
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
                    "events_delivered": events_delivered,
                    "duration_ms": int((time.monotonic() - stream_start) * 1000),
                    "client_disconnected": client_disconnected,
                }

            # 8. Log audit (success)
            _side_effect_type = decl.side_effect.type.value if decl.side_effect else None
            _event_class = classify_event(_side_effect_type, True, None)
            _retention_tier = self._retention_policy.resolve_tier(_event_class)
            _expires_at = self._retention_policy.compute_expires_at(_retention_tier)

            # Build success budget_context (add cost_actual and within_budget)
            _success_budget_ctx: dict[str, Any] | None = None
            if _audit_budget_base:
                _cost_actual_amount = None
                if cost_actual:
                    _ca_fin = cost_actual.get("financial", {})
                    _cost_actual_amount = _ca_fin.get("amount") if isinstance(_ca_fin, dict) else None
                _success_budget_ctx = {**_audit_budget_base, "cost_actual": _cost_actual_amount, "within_budget": True}

            await self._log_audit(
                capability_name, resolved_token, success=True,
                failure_type=None,
                result_summary=self._summarize_result(result),
                cost_actual=cost_actual,
                cost_variance=cost_variance,
                invocation_id=invocation_id, client_reference_id=client_reference_id,
                task_id=effective_task_id, parent_invocation_id=parent_invocation_id,
                upstream_service=upstream_service,
                stream_summary=stream_summary,
                event_class=_event_class, retention_tier=_retention_tier, expires_at=_expires_at,
                parent_span=root_span,
                budget_context=_success_budget_ctx,
                binding_context=_audit_binding_base,
            )

            # 9. Fire streaming summary hook
            if stream and stream_summary and self._log_hooks and self._log_hooks.on_streaming_summary:
                self._safe_hook(self._log_hooks.on_streaming_summary, {
                    "invocation_id": invocation_id,
                    "capability": capability_name,
                    "events_emitted": events_emitted,
                    "events_delivered": events_delivered,
                    "client_disconnected": client_disconnected,
                    "duration_ms": int((time.monotonic() - stream_start) * 1000),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

            # 10. Fire invocation end hook (success)
            _success_duration_ms = int((time.monotonic() - invoke_start) * 1000)
            if self._log_hooks and self._log_hooks.on_invocation_end:
                self._safe_hook(self._log_hooks.on_invocation_end, {
                    "capability": capability_name,
                    "invocation_id": invocation_id,
                    "success": True,
                    "failure_type": None,
                    "duration_ms": _success_duration_ms,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            if self._metrics_hooks and self._metrics_hooks.on_invocation_duration:
                self._safe_hook(self._metrics_hooks.on_invocation_duration, {"capability": capability_name, "duration_ms": _success_duration_ms, "success": True})

            # 11. Build response
            response: dict[str, Any] = {
                "success": True,
                "result": result,
                "invocation_id": invocation_id,
                "client_reference_id": client_reference_id,
                "task_id": effective_task_id,
                "parent_invocation_id": parent_invocation_id,
                "upstream_service": upstream_service,
            }
            if cost_actual:
                response["cost_actual"] = cost_actual

            if stream_summary:
                response["stream_summary"] = stream_summary

            # Budget context in response (v0.14)
            if effective_budget:
                cost_actual_amount = None
                if cost_actual:
                    cost_actual_financial = cost_actual.get("financial", {})
                    cost_actual_amount = cost_actual_financial.get("amount") if isinstance(cost_actual_financial, dict) else None
                response["budget_context"] = {
                    "budget_max": effective_budget.max_amount,
                    "budget_currency": effective_budget.currency,
                    "cost_check_amount": check_amount,
                    "cost_certainty": decl.cost.certainty.value if decl.cost else None,
                    "cost_actual": cost_actual_amount,
                    "within_budget": True,
                }

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
            task_id=filters.get("task_id"),
            parent_invocation_id=filters.get("parent_invocation_id"),
            event_class=filters.get("event_class"),
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

        # Compute expires_hint from earliest expiry in the checkpoint's range
        first_seq = rng.get("first_sequence", row.get("first_sequence"))
        last_seq = rng.get("last_sequence", row.get("last_sequence"))
        if first_seq is not None and last_seq is not None:
            expires_hint = await self._storage.get_earliest_expiry_in_range(
                int(first_seq), int(last_seq)
            )
            if expires_hint is not None:
                result["expires_hint"] = expires_hint

        options = options or {}

        # Inclusion proof
        if options.get("include_proof") and options.get("leaf_index") is not None:
            leaf_index = int(options["leaf_index"])
            last_seq = rng.get("last_sequence", row.get("last_sequence", 0))
            _proof_start = time.monotonic()
            try:
                async def _gen_inclusion_proof():
                    tree = await self._rebuild_merkle_to(last_seq)
                    try:
                        proof = tree.inclusion_proof(leaf_index)
                        result["inclusion_proof"] = {
                            "leaf_index": leaf_index,
                            "path": proof,
                            "merkle_root": tree.root,
                            "leaf_count": tree.leaf_count,
                        }
                        if self._metrics_hooks and self._metrics_hooks.on_proof_generated:
                            self._safe_hook(self._metrics_hooks.on_proof_generated, {"duration_ms": int((time.monotonic() - _proof_start) * 1000)})
                    except (IndexError, ValueError):
                        if self._metrics_hooks and self._metrics_hooks.on_proof_unavailable:
                            self._safe_hook(self._metrics_hooks.on_proof_unavailable, {"reason": "leaf_index_out_of_range"})

                await self._with_span("anip.proof.generate", {"checkpoint_id": checkpoint_id}, None, _gen_inclusion_proof)
            except ValueError:
                result["proof_unavailable"] = "audit_entries_expired"
                if self._metrics_hooks and self._metrics_hooks.on_proof_unavailable:
                    self._safe_hook(self._metrics_hooks.on_proof_unavailable, {"reason": "audit_entries_expired"})

        # Consistency proof
        consistency_from = options.get("consistency_from")
        if consistency_from:
            old_row = await self._storage.get_checkpoint_by_id(consistency_from)
            if old_row:
                old_rng = old_row.get("range", {})
                old_last = old_rng.get("last_sequence", old_row.get("last_sequence", 0))
                new_last = rng.get("last_sequence", row.get("last_sequence", 0))
                _cons_proof_start = time.monotonic()
                try:
                    async def _gen_consistency_proof():
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
                            if self._metrics_hooks and self._metrics_hooks.on_proof_generated:
                                self._safe_hook(self._metrics_hooks.on_proof_generated, {"duration_ms": int((time.monotonic() - _cons_proof_start) * 1000)})
                        except (IndexError, ValueError):
                            if self._metrics_hooks and self._metrics_hooks.on_proof_unavailable:
                                self._safe_hook(self._metrics_hooks.on_proof_unavailable, {"reason": "consistency_proof_failed"})

                    await self._with_span("anip.proof.generate", {"checkpoint_id": checkpoint_id}, None, _gen_consistency_proof)
                except ValueError:
                    result["proof_unavailable"] = "audit_entries_expired"
                    if self._metrics_hooks and self._metrics_hooks.on_proof_unavailable:
                        self._safe_hook(self._metrics_hooks.on_proof_unavailable, {"reason": "audit_entries_expired"})

        return result

    def get_health(self) -> HealthReport:
        """Return a cached snapshot of runtime health."""
        storage_type = (
            "postgres" if hasattr(self._storage, "initialize") else
            "sqlite" if isinstance(self._storage, SQLiteStorage) else
            "memory"
        )

        checkpoint_health = None
        if self._scheduler:
            lag_seconds = None
            if self._scheduler.last_run_at:
                last_run = datetime.fromisoformat(self._scheduler.last_run_at)
                lag_seconds = int((datetime.now(timezone.utc) - last_run).total_seconds())
            checkpoint_health = {
                "healthy": self._scheduler.last_error is None,
                "last_run_at": self._scheduler.last_run_at,
                "lag_seconds": lag_seconds,
            }

        retention_health = {
            "healthy": self._retention_enforcer.is_running and self._retention_enforcer.last_error is None,
            "last_run_at": self._retention_enforcer.last_run_at,
            "last_deleted_count": self._retention_enforcer.last_deleted_count,
        }

        aggregation_health = None
        if self._aggregator:
            aggregation_health = {"pending_windows": self._aggregator.get_pending_count()}

        status: str = "healthy"
        if checkpoint_health and not checkpoint_health["healthy"]:
            status = "degraded"
        if not retention_health["healthy"]:
            status = "degraded"

        return HealthReport(
            status=status,
            storage={"type": storage_type},
            checkpoint=checkpoint_health,
            retention=retention_health,
            aggregation=aggregation_health,
        )

    async def start(self) -> None:
        """Start background services (checkpoint scheduler, retention enforcer, aggregation flush).

        Must be called from within a running event loop.  For PostgresStorage
        this also initialises the connection pool and schema.
        """
        initializer = getattr(self._storage, 'initialize', None)
        if initializer:
            await initializer()

        if self._scheduler:
            self._scheduler.start()
        self._retention_enforcer.start()

        if self._aggregator is not None and self._aggregation_window is not None:
            async def _periodic_flush() -> None:
                try:
                    while True:
                        await asyncio.sleep(self._aggregation_window)  # type: ignore[arg-type]
                        try:
                            await self._flush_aggregator()
                        except Exception as e:
                            if self._hooks.diagnostics and self._hooks.diagnostics.on_background_error:
                                try:
                                    self._hooks.diagnostics.on_background_error({
                                        "source": "aggregation",
                                        "error": str(e),
                                        "timestamp": datetime.now(timezone.utc).isoformat(),
                                    })
                                except Exception:
                                    pass
                except asyncio.CancelledError:
                    pass

            self._flush_task = asyncio.get_event_loop().create_task(_periodic_flush())

    def stop(self) -> None:
        """Stop background services (sync, no persistence)."""
        if self._scheduler:
            self._scheduler.stop()
        self._retention_enforcer.stop()
        if self._flush_task is not None:
            self._flush_task.cancel()
            self._flush_task = None

    async def shutdown(self) -> None:
        """Flush remaining aggregated events, stop background services, close storage."""
        if self._aggregator is not None:
            await self._flush_aggregator()
        closer = getattr(self._storage, 'close', None)
        if closer:
            await closer()

    async def _flush_aggregator(self) -> None:
        """Flush closed aggregation windows and persist each result."""
        if self._aggregator is None:
            return
        aggregator = self._aggregator

        async def _do_flush():
            results = aggregator.flush(datetime.now(timezone.utc))
            entries_flushed = 0
            for item in results:
                if isinstance(item, AggregatedEntry):
                    entry = storage_redact_entry(item.to_audit_dict())
                else:
                    entry = storage_redact_entry(item)
                await self._audit.log_entry(entry)
                entries_flushed += 1
            if self._log_hooks and self._log_hooks.on_aggregation_flush:
                self._safe_hook(self._log_hooks.on_aggregation_flush, {
                    "window_count": len(results),
                    "entries_flushed": entries_flushed,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            if self._metrics_hooks and self._metrics_hooks.on_aggregation_flushed:
                self._safe_hook(self._metrics_hooks.on_aggregation_flushed, {"window_count": len(results)})

        await self._with_span("anip.aggregation.flush", {}, None, _do_flush)

    # --- Background hook callbacks ---

    def _on_retention_sweep(self, deleted_count: int, duration_ms: float) -> None:
        if self._log_hooks and self._log_hooks.on_retention_sweep:
            self._safe_hook(self._log_hooks.on_retention_sweep, {
                "deleted_count": deleted_count,
                "duration_ms": duration_ms,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        if self._metrics_hooks and self._metrics_hooks.on_retention_deleted:
            self._safe_hook(self._metrics_hooks.on_retention_deleted, {"count": deleted_count})

    def _on_retention_error(self, error: str) -> None:
        if self._hooks.diagnostics and self._hooks.diagnostics.on_background_error:
            try:
                self._hooks.diagnostics.on_background_error({
                    "source": "retention",
                    "error": error,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            except Exception:
                pass

    def _on_checkpoint_error(self, error: str) -> None:
        if self._hooks.diagnostics and self._hooks.diagnostics.on_background_error:
            try:
                self._hooks.diagnostics.on_background_error({
                    "source": "checkpoint",
                    "error": error,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            except Exception:
                pass

    # --- Internal helpers ---

    def _safe_hook(self, fn: Any, payload: Any) -> None:
        """Call a hook callback, swallowing any exception.

        Hooks are optional instrumentation and must never affect correctness.
        """
        try:
            fn(payload)
        except Exception:
            pass

    async def _with_span(self, name: str, attrs: dict, parent_span: Any, fn):
        """Run fn() inside a tracing span. No-op when tracing hooks are absent."""
        if not self._tracing_hooks or not self._tracing_hooks.start_span:
            return await fn()
        try:
            span = self._tracing_hooks.start_span({"name": name, "attributes": attrs, "parent_span": parent_span})
        except Exception:
            return await fn()
        try:
            result = await fn()
            if self._tracing_hooks.end_span:
                try:
                    self._tracing_hooks.end_span({"span": span, "status": "ok"})
                except Exception:
                    pass
            return result
        except Exception as e:
            if self._tracing_hooks.end_span:
                try:
                    self._tracing_hooks.end_span({"span": span, "status": "error", "error_type": type(e).__name__, "error_message": str(e)})
                except Exception:
                    pass
            raise

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
        task_id: str | None = None,
        parent_invocation_id: str | None = None,
        upstream_service: str | None = None,
        stream_summary: dict[str, Any] | None = None,
        event_class: str | None = None,
        retention_tier: str | None = None,
        expires_at: str | None = None,
        parent_span: Any = None,
        budget_context: dict[str, Any] | None = None,
        binding_context: dict[str, Any] | None = None,
    ) -> None:
        """Log an audit entry through the SDK's AuditLog.

        When the aggregator is enabled and the event_class is
        ``malformed_or_spam``, the event is routed through the aggregator
        instead of being persisted immediately.
        """
        chain = await self._engine.get_chain(token)
        entry_data = {
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
            "task_id": task_id,
            "parent_invocation_id": parent_invocation_id,
            "upstream_service": upstream_service,
            "stream_summary": stream_summary,
            "event_class": event_class,
            "retention_tier": retention_tier,
            "expires_at": expires_at,
            "budget_context": budget_context,
            "binding_context": binding_context,
        }

        # Apply storage-side redaction (after classification, before persistence)
        entry_data = storage_redact_entry(entry_data)

        # Route low-value denials through the aggregator when enabled
        if self._aggregator is not None and event_class == "malformed_or_spam":
            entry_data["timestamp"] = datetime.now(timezone.utc).isoformat()
            self._aggregator.submit(entry_data)
            return

        async def _do_audit():
            _audit_start = time.monotonic()
            try:
                stored = await self._audit.log_entry(entry_data)
            except Exception:
                _audit_duration_ms = int((time.monotonic() - _audit_start) * 1000)
                if self._metrics_hooks and self._metrics_hooks.on_audit_append_duration:
                    self._safe_hook(self._metrics_hooks.on_audit_append_duration, {"duration_ms": _audit_duration_ms, "success": False})
                raise
            _audit_duration_ms = int((time.monotonic() - _audit_start) * 1000)
            if self._metrics_hooks and self._metrics_hooks.on_audit_append_duration:
                self._safe_hook(self._metrics_hooks.on_audit_append_duration, {"duration_ms": _audit_duration_ms, "success": True})
            if self._log_hooks and self._log_hooks.on_audit_append:
                self._safe_hook(self._log_hooks.on_audit_append, {
                    "sequence_number": stored.get("sequence_number", 0),
                    "capability": capability,
                    "invocation_id": invocation_id,
                    "success": success,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

        await self._with_span("anip.audit.append", {"capability": capability}, parent_span, _do_audit)

    async def _leader_checkpoint_tick(self) -> None:
        """One tick of the checkpoint scheduler.

        Attempts leader election; if this replica wins it reconstructs the
        Merkle tree from storage and creates a new checkpoint.
        """
        holder = self._get_holder_id()
        acquired = await self._storage.try_acquire_leader("checkpoint", holder, 120)
        if not acquired:
            return  # Another replica is leader this tick
        try:
            async def _do_checkpoint():
                result = await reconstruct_and_create_checkpoint(
                    storage=self._storage,
                    service_id=self._service_id,
                    sign_fn=self._keys.sign_jws_detached_audit if self._keys else None,
                )
                if result is not None:
                    body, signature = result
                    await self._storage.store_checkpoint(body, signature)
                    for sink in self._sinks:
                        sink.publish({"body": body, "signature": signature})
                    if self._log_hooks and self._log_hooks.on_checkpoint_created:
                        self._safe_hook(self._log_hooks.on_checkpoint_created, {
                            "checkpoint_id": body.get("checkpoint_id", ""),
                            "entry_count": body.get("entry_count", 0),
                            "merkle_root": body.get("merkle_root", ""),
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })
                    if self._metrics_hooks and self._metrics_hooks.on_checkpoint_created:
                        # Lag = time since previous checkpoint *publication* (not scheduler tick).
                        now = datetime.now(timezone.utc)
                        if self._last_checkpoint_at:
                            try:
                                lag_seconds = int((now - datetime.fromisoformat(self._last_checkpoint_at)).total_seconds())
                            except (ValueError, TypeError):
                                lag_seconds = 0
                        else:
                            lag_seconds = 0
                        self._safe_hook(self._metrics_hooks.on_checkpoint_created, {"lag_seconds": lag_seconds})
                    self._last_checkpoint_at = datetime.now(timezone.utc).isoformat()

            await self._with_span("anip.checkpoint.create", {}, None, _do_checkpoint)
        except Exception as e:
            if self._metrics_hooks and self._metrics_hooks.on_checkpoint_failed:
                self._safe_hook(self._metrics_hooks.on_checkpoint_failed, {"error": str(e)})
            raise
        finally:
            await self._storage.release_leader("checkpoint", holder)

    def _get_holder_id(self) -> str:
        """Return a unique holder identifier for this process."""
        return f"{socket.gethostname()}:{os.getpid()}"

    async def _run_with_exclusive_heartbeat(
        self,
        token: DelegationToken,
        handler_coro: Any,
    ) -> Any:
        """Run a handler coroutine while periodically renewing the exclusive lease.

        For long-running invocations under ``ConcurrentBranches.EXCLUSIVE``,
        this keeps the lease alive so that no other replica steals it while
        the handler is still executing.
        """
        if (
            not token.constraints
            or token.constraints.concurrent_branches != ConcurrentBranches.EXCLUSIVE
        ):
            return await handler_coro

        root = await self._engine.get_root_principal(token)
        key = f"exclusive:{self._service_id}:{root}"
        holder = self._get_holder_id()
        interval = self._exclusive_ttl / 2

        async def renew_loop() -> None:
            while True:
                await asyncio.sleep(interval)
                await self._storage.try_acquire_exclusive(key, holder, self._exclusive_ttl)

        renewal_task = asyncio.create_task(renew_loop())
        try:
            return await handler_coro
        finally:
            renewal_task.cancel()

    async def _rebuild_merkle_to(self, sequence_number: int) -> MerkleTree:
        """Rebuild a Merkle tree from audit entries 1..sequence_number."""
        entries = await self._storage.get_audit_entries_range(1, sequence_number)
        if len(entries) < sequence_number:
            raise ValueError(
                f"Cannot rebuild proof: audit entries have been deleted by retention enforcement. "
                f"Expected {sequence_number} entries, found {len(entries)}."
            )
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
