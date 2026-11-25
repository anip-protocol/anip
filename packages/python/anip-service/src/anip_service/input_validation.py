"""Validation of invocation parameters against declared inputs.

SPEC.md §6.3 "Parameter Validation": a required input that is absent or JSON
``null`` is missing, and a supplied value must be of the JSON type named by a
primitive declared type. Declared type names other than the six primitives
are not checked here; the handler validates them.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any, Iterable

# SPEC.md §6.3: the caller corrects the parameters against the manifest and
# sends a new request; nothing outside the request has to change.
INVALID_PARAMETERS_RESOLUTION: dict[str, Any] = {
    "action": "retry_now",
    "recovery_class": "retry_now",
    "requires": "parameters that match the capability's declared inputs",
}


def invalid_parameters_failure(detail: str, *, requires: str | None = None) -> dict[str, Any]:
    """An ``invalid_parameters`` failure object with its ``retry_now`` resolution."""
    resolution = dict(INVALID_PARAMETERS_RESOLUTION)
    if requires is not None:
        resolution["requires"] = requires
    return {
        "type": "invalid_parameters",
        "detail": detail,
        "resolution": resolution,
        "retry": False,
    }


def json_type_of(value: Any) -> str:
    """The JSON type of a parsed value, as §6.3 names it in a failure detail."""
    # bool is a subclass of int: a boolean is never a number.
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, str):
        return "string"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, Mapping):
        return "object"
    if isinstance(value, (list, tuple, set, frozenset)):
        return "array"
    if value is None:
        return "null"
    # Not a JSON value. Numeric-like types count as numbers, anything else
    # with attributes as an object.
    try:
        float(value)
    except (TypeError, ValueError):
        return "object"
    return "number"


def _is_integral(value: Any) -> bool:
    if isinstance(value, int):
        return True
    try:
        as_float = float(value)
    except (TypeError, ValueError, OverflowError):
        return False
    return math.isfinite(as_float) and as_float == math.floor(as_float)


def _declares_on_missing(declared_input: Any) -> bool:
    resolution = getattr(declared_input, "resolution", None)
    return getattr(resolution, "on_missing", None) is not None


_ACCEPTS = {
    "string": lambda received, value: received == "string",
    "integer": lambda received, value: received == "number" and _is_integral(value),
    "number": lambda received, value: received == "number",
    "boolean": lambda received, value: received == "boolean",
    "array": lambda received, value: received == "array",
    "object": lambda received, value: received == "object",
}


def check_declared_inputs(
    capability_name: str,
    inputs: Iterable[Any] | None,
    parameters: Mapping[str, Any] | None,
) -> str | None:
    """Check ``parameters`` as the caller sent them against declared ``inputs``.

    Returns the ``detail`` of the ``invalid_parameters`` failure, or ``None``
    when the parameters are acceptable. A required input that declares
    ``resolution.on_missing`` is not reported as missing; a value supplied
    for it is type-checked like any other. Defaults, ``allowed_values`` and the
    ``resolution`` block are not applied; undeclared parameters are ignored.
    """
    supplied: Mapping[str, Any] = parameters if parameters is not None else {}
    declared = list(inputs or [])

    def absent(name: str) -> bool:
        return name not in supplied or supplied[name] is None

    # An input that declares resolution.on_missing is left to the service's
    # on_missing path when it is absent, even when it is required (§4.10).
    missing = [
        i.name for i in declared
        if i.required and not _declares_on_missing(i) and absent(i.name)
    ]
    if missing:
        return f"{capability_name} is missing required input(s): " + ", ".join(missing)

    wrong: list[str] = []
    for declared_input in declared:
        if absent(declared_input.name):
            continue
        accepts = _ACCEPTS.get(declared_input.type)
        if accepts is None:
            continue
        value = supplied[declared_input.name]
        received = json_type_of(value)
        if not accepts(received, value):
            wrong.append(f"'{declared_input.name}' must be {declared_input.type}, got {received}")
    if wrong:
        return f"{capability_name} has invalid input(s): " + "; ".join(wrong)
    return None
