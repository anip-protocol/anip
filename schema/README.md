# ANIP JSON Schema

> Canonical JSON Schema for all ANIP v0.1 types. Use these to validate any ANIP implementation.

## Files

- `anip.schema.json` — combined schema with all types and shared definitions
- `types/` — individual schema files per type, for selective validation
- `discovery.schema.json` — schema for the `/.well-known/anip` discovery document
- `generate.py` — regenerate schemas from Pydantic models

## Types

| Schema | What It Validates | Spec Reference |
|--------|-------------------|----------------|
| `DelegationToken` | Delegation chain tokens | SPEC.md §4.3 |
| `CapabilityDeclaration` | Full capability metadata in manifest | SPEC.md §4.1 |
| `PermissionResponse` | Permission discovery responses | SPEC.md §4.4 |
| `ANIPFailure` | Structured error responses | SPEC.md §4.5 |
| `InvokeRequest` | Capability invocation requests | SPEC.md §6.2 |
| `InvokeResponse` | Capability invocation responses | SPEC.md §6.2 |
| `ANIPManifest` | Full service manifest | SPEC.md §6.2 |
| `CostActual` | Actual cost returned after invocation | SPEC.md §5.1 |
| `AvailableCapability` | Available capability in permission response | SPEC.md §4.4 |
| `RestrictedCapability` | Restricted capability in permission response | SPEC.md §4.4 |
| `DeniedCapability` | Denied capability in permission response | SPEC.md §4.4 |

## Usage

### Python (jsonschema)

```python
import json
from jsonschema import validate

with open("schema/anip.schema.json") as f:
    schema = json.load(f)

# Validate a delegation token
token = {"token_id": "tok_1", "issuer": "human:user", ...}
validate(token, schema["$defs"]["DelegationToken"])
```

### JavaScript/TypeScript

```typescript
import Ajv from "ajv";
import schema from "./schema/anip.schema.json";

const ajv = new Ajv();
const validate = ajv.compile(schema.$defs.DelegationToken);

const valid = validate(token);
if (!valid) console.error(validate.errors);
```

### CLI (ajv-cli)

```bash
npx ajv validate -s schema/types/DelegationToken.json -d token.json
```

## Regenerating

When the Pydantic models change, regenerate:

```bash
cd examples/anip && source .venv/bin/activate
python ../../schema/generate.py
```

The schemas are generated from `examples/anip/anip_server/primitives/models.py` — the single source of truth.
