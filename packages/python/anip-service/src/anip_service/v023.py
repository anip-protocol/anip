"""v0.23 — Capability composition and approval grants runtime.

This module is the canonical location for:
- composition declaration validation (registration time)
- composition execution (sequential step runner with empty-result + failure policies)
- digest helpers (SHA-256 over canonical JSON)
- approval grant signing helpers and validation order primitives

The :class:`anip_service.service.ANIPService` wires these into the invoke
pipeline. Keeping this module separate keeps the v0.22 service.py changes
small and reviewable.

See SPEC.md §4.6, §4.7, §4.8, §4.9.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable

from anip_core import (
    Composition,
    CompositionStep,
    CapabilityDeclaration,
)


# ---------------------------------------------------------------------------
# Digest + ID helpers
# ---------------------------------------------------------------------------


def canonical_json(value: Any) -> str:
    """Canonical JSON: sorted keys, no whitespace, UTF-8."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_digest(value: Any) -> str:
    """SHA-256 of canonical JSON, returned as ``sha256:<hex>``. v0.23 §4.7."""
    payload = canonical_json(value).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def new_approval_request_id() -> str:
    return f"apr_{uuid.uuid4().hex[:12]}"


def new_grant_id() -> str:
    return f"grant_{uuid.uuid4().hex[:12]}"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def utc_in_iso(seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


# ---------------------------------------------------------------------------
# Composition validation (registration time)
# ---------------------------------------------------------------------------


class CompositionValidationError(ValueError):
    """Raised when a composed capability declaration violates a v0.23 invariant."""


_JSONPATH_INPUT = re.compile(r"^\$\.input(?:\.[A-Za-z_][A-Za-z0-9_]*)+$")
_JSONPATH_STEP = re.compile(
    r"^\$\.steps\.(?P<step>[A-Za-z_][A-Za-z0-9_-]*)\.output(?:\.[A-Za-z_][A-Za-z0-9_]*)+$"
)


def _parse_step_ref(path: str) -> str | None:
    """Return the step id referenced by a JSONPath, or None if path is $.input.*."""
    if _JSONPATH_INPUT.match(path):
        return None
    m = _JSONPATH_STEP.match(path)
    if m is None:
        raise CompositionValidationError(
            f"composition_invalid_step: malformed JSONPath {path!r} "
            f"(must be $.input.* or $.steps.<id>.output.*)"
        )
    return m.group("step")


def validate_composition(
    parent_name: str,
    decl: CapabilityDeclaration,
    *,
    other_capabilities: dict[str, CapabilityDeclaration],
) -> None:
    """Enforce composition declaration invariants at registration time.

    Raises CompositionValidationError on any violation. See SPEC.md §4.6 and
    plan §6.1, §6.3, §6.4.
    """
    if decl.kind != "composed":
        return
    comp = decl.composition
    if comp is None:
        raise CompositionValidationError(
            f"composition_invalid_step: capability {parent_name!r} declares "
            f"kind='composed' but composition is missing"
        )

    # Authority boundary: only same_service in v0.23.
    if comp.authority_boundary != "same_service":
        raise CompositionValidationError(
            f"composition_unsupported_authority_boundary: "
            f"{comp.authority_boundary!r} is reserved in v0.23"
        )

    if not comp.steps:
        raise CompositionValidationError(
            f"composition_invalid_step: composition has no steps"
        )

    # Step IDs must be unique.
    step_ids = [s.id for s in comp.steps]
    if len(set(step_ids)) != len(step_ids):
        raise CompositionValidationError(
            f"composition_invalid_step: duplicate step ids in {step_ids}"
        )

    # At most one empty_result_source.
    sources = [s for s in comp.steps if s.empty_result_source]
    if len(sources) > 1:
        raise CompositionValidationError(
            "composition_invalid_step: at most one step may have "
            "empty_result_source=true"
        )
    source_step = sources[0] if sources else None

    # Step capabilities must exist (same_service) and must be kind=atomic.
    # Self-reference disallowed; composed-calling-composed disallowed.
    step_index = {s.id: i for i, s in enumerate(comp.steps)}
    for step in comp.steps:
        if step.capability == parent_name:
            raise CompositionValidationError(
                f"composition_invalid_step: step {step.id!r} self-references parent capability"
            )
        target = other_capabilities.get(step.capability)
        if target is None:
            raise CompositionValidationError(
                f"composition_unknown_capability: step {step.id!r} references "
                f"unknown capability {step.capability!r}"
            )
        if target.kind != "atomic":
            raise CompositionValidationError(
                f"composition_invalid_step: step {step.id!r} references "
                f"{step.capability!r} which is kind={target.kind!r}; "
                f"composed capabilities may only call kind='atomic' steps in v0.23"
            )

    # input_mapping references must resolve and be forward-only.
    for step_key, mapping in comp.input_mapping.items():
        if step_key not in step_index:
            raise CompositionValidationError(
                f"composition_invalid_step: input_mapping key {step_key!r} "
                f"is not a declared step id"
            )
        step_pos = step_index[step_key]
        for param, jp in mapping.items():
            ref = _parse_step_ref(jp)
            if ref is None:
                continue  # $.input.*
            if ref not in step_index:
                raise CompositionValidationError(
                    f"composition_invalid_step: input_mapping[{step_key!r}].{param} "
                    f"references unknown step {ref!r}"
                )
            if step_index[ref] >= step_pos:
                raise CompositionValidationError(
                    f"composition_invalid_step: input_mapping[{step_key!r}].{param} "
                    f"forward-references {ref!r} (forward-only references required)"
                )

    # output_mapping references must resolve to declared steps.
    for field, jp in comp.output_mapping.items():
        ref = _parse_step_ref(jp)
        if ref is None:
            continue  # $.input.* permitted in output_mapping
        if ref not in step_index:
            raise CompositionValidationError(
                f"composition_invalid_step: output_mapping[{field!r}] "
                f"references unknown step {ref!r}"
            )

    # empty_result_source step requires composition-level empty_result_policy.
    if source_step is not None and comp.empty_result_policy is None:
        raise CompositionValidationError(
            "composition_invalid_step: step has empty_result_source=true "
            "but composition has no empty_result_policy"
        )

    # empty_result_policy=return_success_no_results requires empty_result_output.
    if comp.empty_result_policy == "return_success_no_results":
        if comp.empty_result_output is None:
            raise CompositionValidationError(
                "composition_invalid_step: empty_result_policy="
                "'return_success_no_results' requires empty_result_output"
            )
        # empty_result_output may only reference $.input.* or $.steps.<source>.output.*.
        if source_step is None:
            raise CompositionValidationError(
                "composition_invalid_step: empty_result_output requires a step "
                "with empty_result_source=true"
            )
        for field, value in comp.empty_result_output.items():
            if isinstance(value, str) and value.startswith("$"):
                ref = _parse_step_ref(value)
                if ref is not None and ref != source_step.id:
                    raise CompositionValidationError(
                        f"composition_invalid_step: empty_result_output[{field!r}] "
                        f"references step {ref!r} but only the empty_result_source "
                        f"step {source_step.id!r} (or $.input.*) is allowed"
                    )
    elif comp.empty_result_policy in ("clarify", "deny") and comp.empty_result_output is not None:
        raise CompositionValidationError(
            "composition_invalid_step: empty_result_output is forbidden when "
            f"empty_result_policy={comp.empty_result_policy!r}"
        )


# ---------------------------------------------------------------------------
# Composition execution (runtime)
# ---------------------------------------------------------------------------


def _resolve_jsonpath(
    path: str, *, parent_input: dict[str, Any], step_outputs: dict[str, dict[str, Any]]
) -> Any:
    """Resolve $.input.X or $.steps.<id>.output.Y. Raises KeyError on lookup miss."""
    if _JSONPATH_INPUT.match(path):
        keys = path.split(".")[2:]
        cur: Any = parent_input
        for k in keys:
            cur = cur[k]
        return cur
    m = _JSONPATH_STEP.match(path)
    if m is None:
        raise ValueError(f"malformed JSONPath at runtime: {path!r}")
    step = m.group("step")
    keys = path.split(".")[4:]  # skip $.steps.<id>.output
    cur = step_outputs[step]
    for k in keys:
        cur = cur[k]
    return cur


def _is_empty(value: Any) -> bool:
    """Empty-source detection. Empty list/dict/string or None counts as empty."""
    if value is None:
        return True
    if isinstance(value, (list, dict, str)):
        return len(value) == 0
    return False


async def execute_composition(
    parent_name: str,
    decl: CapabilityDeclaration,
    parent_input: dict[str, Any],
    *,
    invoke_step: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    """Run a composed capability's steps and return the parent response.

    ``invoke_step`` is supplied by the service runtime — it invokes a child
    capability with the same authority/audit lineage as the parent.

    Raises ANIPError on policy-driven failures (empty result with clarify/deny,
    child failure propagation, etc.).
    """
    from .types import ANIPError  # local import to avoid cycle

    comp = decl.composition
    assert comp is not None  # validated at registration

    source_step = next((s for s in comp.steps if s.empty_result_source), None)
    step_outputs: dict[str, dict[str, Any]] = {}

    for step in comp.steps:
        # Resolve this step's inputs.
        mapping = comp.input_mapping.get(step.id, {})
        step_input: dict[str, Any] = {}
        for param, jp in mapping.items():
            try:
                step_input[param] = _resolve_jsonpath(
                    jp, parent_input=parent_input, step_outputs=step_outputs
                )
            except (KeyError, ValueError):
                # Missing reference at runtime → treat as null.
                step_input[param] = None

        # Invoke the child.
        result = await invoke_step(step.capability, step_input)
        if not result.get("success", False):
            # Child failure: apply failure_policy.
            failure = result.get("failure") or {}
            failure_type = failure.get("type", "unknown")
            outcome = _failure_outcome(failure_type, comp.failure_policy)
            if outcome == "fail_parent":
                raise ANIPError(
                    failure_type,
                    f"child step {step.id!r} ({step.capability}) failed: {failure.get('detail', '')}",
                    resolution=failure.get("resolution"),
                )
            # propagate (default)
            raise ANIPError(
                failure_type,
                failure.get("detail", "child step failed"),
                resolution=failure.get("resolution"),
                approval_required=failure.get("approval_required"),
            )

        step_outputs[step.id] = result.get("result") or {}

        # Empty-result detection happens immediately after the source step.
        if step is source_step and _is_empty_for_step(step, step_outputs[step.id], comp):
            return _build_empty_result_response(comp, parent_input, step_outputs[step.id])

    # All steps complete → resolve normal output_mapping.
    return _build_output(comp.output_mapping, parent_input=parent_input, step_outputs=step_outputs)


def _failure_outcome(failure_type: str, policy) -> str:
    """Map a child failure_type to the configured outcome."""
    if failure_type == "approval_required":
        return policy.child_approval_required
    if failure_type in ("scope_insufficient", "denied", "non_delegable_action"):
        return policy.child_denial
    if failure_type in (
        "binding_missing",
        "binding_stale",
        "control_requirement_unsatisfied",
        "purpose_mismatch",
        "invalid_parameters",
    ):
        return policy.child_clarification
    return policy.child_error


def _is_empty_for_step(step: CompositionStep, output: dict[str, Any], comp: Composition) -> bool:
    """Determine if a step's primary output is empty.

    Uses ``empty_result_path`` if declared; otherwise looks for the first key
    referenced by a downstream step or returned by output_mapping.
    """
    if not output:
        return True
    if step.empty_result_path is not None:
        try:
            keys = step.empty_result_path.split(".")
            # empty_result_path is scoped to this step's output, so $-prefix optional
            keys = [k for k in keys if k not in ("$", "")]
            cur: Any = output
            for k in keys:
                cur = cur[k]
            return _is_empty(cur)
        except KeyError:
            return True
    # Fallback: any list-typed value in the output is treated as the primary.
    for v in output.values():
        if isinstance(v, list):
            return len(v) == 0
    # Otherwise: empty if dict has no values.
    return all(_is_empty(v) for v in output.values())


def _build_empty_result_response(
    comp: Composition, parent_input: dict[str, Any], source_output: dict[str, Any]
) -> dict[str, Any]:
    """Build the response for the return_success_no_results / clarify / deny branches."""
    from .types import ANIPError

    if comp.empty_result_policy == "clarify":
        raise ANIPError(
            "composition_empty_result_clarification_required",
            "selection step returned no results; clarification required",
        )
    if comp.empty_result_policy == "deny":
        raise ANIPError(
            "composition_empty_result_denied",
            "selection step returned no results; policy denies an empty answer",
        )
    # return_success_no_results — use empty_result_output exclusively.
    out: dict[str, Any] = {}
    assert comp.empty_result_output is not None
    for field, value in comp.empty_result_output.items():
        if isinstance(value, str) and value.startswith("$"):
            try:
                out[field] = _resolve_empty_ref(value, parent_input, source_output)
            except (KeyError, ValueError):
                out[field] = None
        else:
            # Literal value.
            out[field] = value
    return out


def _resolve_empty_ref(
    path: str, parent_input: dict[str, Any], source_output: dict[str, Any]
) -> Any:
    """Like _resolve_jsonpath but accepts only $.input.* or $.steps.<source>.output.*."""
    if _JSONPATH_INPUT.match(path):
        keys = path.split(".")[2:]
        cur: Any = parent_input
        for k in keys:
            cur = cur[k]
        return cur
    m = _JSONPATH_STEP.match(path)
    if m is None:
        raise ValueError(f"malformed JSONPath: {path!r}")
    keys = path.split(".")[4:]
    cur = source_output
    for k in keys:
        cur = cur[k]
    return cur


def _build_output(
    mapping: dict[str, str], *, parent_input: dict[str, Any], step_outputs: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for field, jp in mapping.items():
        try:
            out[field] = _resolve_jsonpath(jp, parent_input=parent_input, step_outputs=step_outputs)
        except (KeyError, ValueError):
            out[field] = None
    return out


# ---------------------------------------------------------------------------
# Approval grants — signing + validation
# ---------------------------------------------------------------------------


def sign_grant(grant: dict[str, Any], *, key_manager: Any) -> str:
    """Compute the grant signature.

    The signature covers all stored fields except ``signature`` and ``use_count``.
    Uses the same ES256 detached-JWS manifest signing path. v0.23. See SPEC.md §4.8.
    """
    from anip_crypto.jws import sign_jws_detached

    payload = {k: v for k, v in grant.items() if k not in ("signature", "use_count")}
    canon = canonical_json(payload).encode("utf-8")
    return sign_jws_detached(key_manager, canon)


def verify_grant_signature(grant: dict[str, Any], *, key_manager: Any) -> bool:
    """Verify a grant's signature. Returns True if valid."""
    from anip_crypto.jws import verify_jws_detached

    payload = {k: v for k, v in grant.items() if k not in ("signature", "use_count")}
    canon = canonical_json(payload).encode("utf-8")
    try:
        verify_jws_detached(key_manager, grant["signature"], canon)
        return True
    except Exception:
        return False


def grant_scope_subset_of_token(grant_scope: list[str], token_scope: list[str]) -> bool:
    """Per SPEC.md §4.8 'Scope Subset Rule': forall s in grant.scope: s in token.scope."""
    return all(s in token_scope for s in grant_scope)


# ---------------------------------------------------------------------------
# v0.23 failure types (canonical names — also live in constants.py)
# ---------------------------------------------------------------------------


FAILURE_GRANT_NOT_FOUND = "grant_not_found"
FAILURE_GRANT_EXPIRED = "grant_expired"
FAILURE_GRANT_CONSUMED = "grant_consumed"
FAILURE_GRANT_CAPABILITY_MISMATCH = "grant_capability_mismatch"
FAILURE_GRANT_SCOPE_MISMATCH = "grant_scope_mismatch"
FAILURE_GRANT_PARAM_DRIFT = "grant_param_drift"
FAILURE_GRANT_SESSION_INVALID = "grant_session_invalid"

FAILURE_APPROVAL_REQUEST_NOT_FOUND = "approval_request_not_found"
FAILURE_APPROVAL_REQUEST_ALREADY_DECIDED = "approval_request_already_decided"
FAILURE_APPROVAL_REQUEST_EXPIRED = "approval_request_expired"
FAILURE_APPROVER_NOT_AUTHORIZED = "approver_not_authorized"
FAILURE_GRANT_TYPE_NOT_ALLOWED_BY_POLICY = "grant_type_not_allowed_by_policy"

FAILURE_COMPOSITION_INVALID_STEP = "composition_invalid_step"
FAILURE_COMPOSITION_UNKNOWN_CAPABILITY = "composition_unknown_capability"
FAILURE_COMPOSITION_UNSUPPORTED_AUTHORITY_BOUNDARY = "composition_unsupported_authority_boundary"
FAILURE_COMPOSITION_EMPTY_RESULT_CLARIFICATION_REQUIRED = (
    "composition_empty_result_clarification_required"
)
FAILURE_COMPOSITION_EMPTY_RESULT_DENIED = "composition_empty_result_denied"


# ---------------------------------------------------------------------------
# Storage-side validation gate (called from invoke for continuation)
# ---------------------------------------------------------------------------


async def validate_continuation_grant(
    *,
    storage,
    grant_id: str,
    capability: str,
    parameters: dict[str, Any],
    token_scope: list[str],
    token_session_id: str | None,
    key_manager: Any,
    now_iso: str,
) -> tuple[dict[str, Any] | None, str | None]:
    """Phase 7.3 read-side validation. Returns (grant, None) on success or
    (None, failure_type) on rejection. Atomic reservation is the caller's
    responsibility (see Phase 7.3 Phase B: storage.try_reserve_grant).
    """
    grant = await storage.get_grant(grant_id)
    if grant is None:
        return None, FAILURE_GRANT_NOT_FOUND
    if not verify_grant_signature(grant, key_manager=key_manager):
        return None, FAILURE_GRANT_NOT_FOUND  # don't leak existence
    if grant["expires_at"] <= now_iso:
        return None, FAILURE_GRANT_EXPIRED
    if grant["capability"] != capability:
        return None, FAILURE_GRANT_CAPABILITY_MISMATCH
    if not grant_scope_subset_of_token(grant["scope"], token_scope):
        return None, FAILURE_GRANT_SCOPE_MISMATCH
    submitted_digest = sha256_digest(parameters)
    if submitted_digest != grant["approved_parameters_digest"]:
        return None, FAILURE_GRANT_PARAM_DRIFT
    if grant["grant_type"] == "session_bound":
        if token_session_id != grant.get("session_id"):
            return None, FAILURE_GRANT_SESSION_INVALID
    return grant, None
