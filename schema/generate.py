#!/usr/bin/env python3
"""Generate ANIP JSON Schema from Pydantic models.

This script exports the canonical JSON Schema for all ANIP types.
Run it whenever the models change to keep the schema in sync.

Usage:
    cd examples/anip && source .venv/bin/activate
    python ../../schema/generate.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add the examples package to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "examples" / "anip"))

from anip_server.primitives.models import (
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
        "$id": "https://anip.dev/schema/v0.1/anip.schema.json",
        "title": "ANIP — Agent-Native Interface Protocol",
        "description": (
            "JSON Schema for all ANIP v0.1 types. Generated from "
            "Pydantic models in examples/anip/anip_server/primitives/models.py. "
            "Use these schemas to validate ANIP documents and responses."
        ),
        "version": "0.1.0",
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
