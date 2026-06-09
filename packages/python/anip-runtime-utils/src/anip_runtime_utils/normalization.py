"""Deterministic parameter-normalization helpers for agent runtimes."""

from __future__ import annotations

import re
from typing import Any


def semantic_key(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def normalize_by_allowed_values(
    value: Any,
    allowed_values: list[Any],
    default: Any = None,
) -> tuple[Any, dict[str, Any] | None]:
    if value is None:
        if default is not None:
            return default, {"reason": "default_applied", "from": None, "to": default}
        return value, None

    raw = str(value).strip()
    if not raw:
        if default is not None:
            return default, {"reason": "default_applied", "from": value, "to": default}
        return value, None

    normalized_raw = semantic_key(raw)
    canonical_allowed: list[tuple[Any, str]] = [(candidate, semantic_key(candidate)) for candidate in allowed_values]
    for candidate, candidate_key in canonical_allowed:
        if raw == str(candidate) or normalized_raw == candidate_key:
            if raw == str(candidate):
                return candidate, None
            return candidate, {"reason": "canonicalized_allowed_value", "from": value, "to": candidate}

    if len(allowed_values) == 1:
        candidate = allowed_values[0]
        return candidate, {"reason": "single_allowed_value", "from": value, "to": candidate}

    return value, None


def infer_allowed_value_from_history(allowed_values: list[Any], history: list[dict[str, str]] | None) -> Any | None:
    if not isinstance(history, list) or not history or not allowed_values:
        return None
    matched: list[Any] = []
    for candidate in allowed_values:
        candidate_key = semantic_key(candidate)
        if not candidate_key:
            continue
        for item in history:
            if str(item.get("role") or "").strip().lower() != "user":
                continue
            content_key = semantic_key(item.get("content"))
            if content_key and candidate_key in content_key:
                matched.append(candidate)
                break
    deduped: list[Any] = []
    for candidate in matched:
        if candidate not in deduped:
            deduped.append(candidate)
    if len(deduped) == 1:
        return deduped[0]
    return None


def apply_input_metadata_defaults_and_enums(
    parameters: dict[str, Any],
    metadata: dict[str, Any],
    history: list[dict[str, str]] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    normalized = dict(parameters)
    applied: list[dict[str, Any]] = []
    input_specs = metadata.get("input_specs") or []
    if not isinstance(input_specs, list):
        return normalized, applied

    for spec in input_specs:
        if not isinstance(spec, dict):
            continue
        name = spec.get("name")
        if not isinstance(name, str) or not name:
            continue
        allowed_values = spec.get("allowed_values")
        default = spec.get("default")
        carried_forward = (
            infer_allowed_value_from_history(allowed_values, history)
            if isinstance(allowed_values, list) and allowed_values
            else None
        )
        if name not in normalized and carried_forward is not None:
            normalized[name] = carried_forward
            applied.append({"field": name, "reason": "carried_forward_from_history", "from": None, "to": carried_forward})
            continue
        if name not in normalized and default is not None:
            normalized[name] = default
            applied.append({"field": name, "reason": "default_applied", "from": None, "to": default})
            continue
        if not isinstance(allowed_values, list) or not allowed_values or name not in normalized:
            continue
        normalized_value, change = normalize_by_allowed_values(normalized.get(name), allowed_values, default=default)
        normalized[name] = normalized_value
        if change:
            applied.append({"field": name, **change})

    return normalized, applied
