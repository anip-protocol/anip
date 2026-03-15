#!/usr/bin/env python3
"""Generate ANIP JSON Schema from the reference implementation's Pydantic models.

This script is a development tool — it generates a draft schema from the
reference implementation to bootstrap updates. The output should be reviewed
and edited to match SPEC.md before committing to schema/anip.schema.json.

The canonical schemas in schema/ are spec-owned, not implementation-derived.
This script helps keep them in sync but is not the source of truth.

Usage:
    cd examples/anip && source .venv/bin/activate
    python ../../schema/generate.py
"""

from __future__ import annotations

import json
from pathlib import Path

from anip_core import (
    ANIPFailure,
    ANIPManifest,
    AvailableCapability,
    CapabilityDeclaration,
    CostActual,
    DelegationToken,
    DeniedCapability,
    InvokeRequest,
    InvokeResponse,
    PermissionResponse,
    RestrictedCapability,
)


# The top-level types that external consumers need to validate against
SCHEMA_TYPES = {
    # Core protocol types
    "DelegationToken": DelegationToken,
    "CapabilityDeclaration": CapabilityDeclaration,
    "PermissionResponse": PermissionResponse,
    "ANIPFailure": ANIPFailure,
    # Invocation
    "InvokeRequest": InvokeRequest,
    "InvokeResponse": InvokeResponse,
    # Manifest
    "ANIPManifest": ANIPManifest,
    # Cost
    "CostActual": CostActual,
    # Permission components (for reference)
    "AvailableCapability": AvailableCapability,
    "RestrictedCapability": RestrictedCapability,
    "DeniedCapability": DeniedCapability,
}


def generate_schemas() -> dict:
    """Generate a combined JSON Schema document with all ANIP types."""
    schemas = {}
    all_defs = {}

    for name, model in SCHEMA_TYPES.items():
        schema = model.model_json_schema()
        # Extract $defs (shared sub-schemas) and merge them
        defs = schema.pop("$defs", {})
        all_defs.update(defs)
        schemas[name] = schema

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://anip.dev/schema/v0.4/anip.schema.json",
        "title": "ANIP — Agent-Native Interface Protocol",
        "description": (
            "Canonical JSON Schema for all ANIP v0.4 types as defined in SPEC.md. "
            "Use these schemas to validate ANIP documents, responses, and delegation tokens."
        ),
        "$defs": {**all_defs, **schemas},
    }


def main():
    schema = generate_schemas()
    output_path = Path(__file__).parent / "anip.schema.json"
    output_path.write_text(json.dumps(schema, indent=2) + "\n")
    print(f"Generated {output_path} ({len(SCHEMA_TYPES)} types)")

    # Also generate individual schema files for key types
    individual_dir = Path(__file__).parent / "types"
    individual_dir.mkdir(exist_ok=True)

    for name, model in SCHEMA_TYPES.items():
        schema = model.model_json_schema()
        path = individual_dir / f"{name}.json"
        path.write_text(json.dumps(schema, indent=2) + "\n")

    print(f"Generated {len(SCHEMA_TYPES)} individual schemas in {individual_dir}/")


if __name__ == "__main__":
    main()
