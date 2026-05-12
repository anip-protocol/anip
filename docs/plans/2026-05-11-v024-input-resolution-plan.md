# ANIP v0.24 — Input Resolution Metadata Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bump ANIP to `anip/0.24` adding **input resolution metadata** — a portable, protocol-visible declaration on each capability input that says how a value should be resolved (closed enum, backend-resolved reference, app-selected, actor-policy-derived, explicit-only, clarify-on-miss). Plus the adjacent typed substrate fields (`semantic_type`, `entity_reference`, `allowed_values`, `catalog_ref`, `input_meanings`) that resolution depends on.

**Scope:** Main-only. Contract + core support: SPEC §4.10, JSON schema, `PROTOCOL_VERSION` bumped to `anip/0.24`, `CapabilityInput` extended in all 5 runtimes (Python pydantic, TypeScript zod, Go, Java, C# records), conformance fixtures + tests, docs + package version bumps to `0.24.0`. Pure additive — v0.23 manifests parse unchanged.

**Out of scope (deliberately not in this plan):**
- Studio UI editing for the new fields
- Generator pass-through (emitting `resolution` into service-definition / agent-consumption artifacts)
- Runtime consumption (e.g. honoring `resolution.mode` in any agent runtime)
- Registry display + signature tests
- Verifier behavior expansion (e.g. closed-values open-text rejection at the verifier layer)
- Wiring `ValidateCapabilityInput` / `CapabilityInput.validate(...)` / `CapabilityInput.Validate(...)` into Go/Java/C# manifest/service-definition load paths so cross-field validation auto-fires on every load (Python and TS auto-fire today via Pydantic / zod hooks — D1.7 has the detail). This PR ships model-level validators; auto-firing the static-typed runtimes' validators on load is a separate plan.

These will be handled in separate plans once the relevant consumer code is on main. This plan ships only the portable contract.

**Architecture:** Pure additive protocol bump. Extend `CapabilityInput` with optional fields:
1. `resolution: InputResolution | null` — the new v0.24 block (`mode` + `resolver_ref` + `on_missing` + `on_ambiguous` + `on_unresolved`).
2. Adjacent typed hint fields the resolution block depends on: `semantic_type`, `entity_reference`, `allowed_values`, `catalog_ref`, `input_meanings`.

Validation is layered (see Decision 1.7 for detail): enum membership and `resolution.mode` presence are rejected at the decode/model-validation layer by every runtime — at decode in Python/TS/Go/Java (via Pydantic, zod, custom `UnmarshalJSON`, `@JsonCreator` + record constructor), and at the `Validate(...)` step in C# where `Mode` is typed nullable and `Validate(...)` rejects null. The two cross-field rules (`closed_values` requires `allowed_values`; `on_missing=use_default` requires non-null `default`) are model-level validators in all 5 runtimes — auto-fired in Python/TS, callable in Go/Java/C# (see D1.7 auto-invoke asymmetry) — not JSON Schema rules. All new fields are optional. v0.23 manifests parse unchanged.

**Tech Stack:** All 5 runtimes (Python pydantic, TypeScript zod, Go structs, Java POJO classes, C# records). JSON Schema draft 2020-12. Conformance tests in `conformance/` (Python pytest).

**Design doc:** `/Users/samirski/Development/codex/2026-05-11-anip-v024-input-resolution-design-for-claude-code.md`

**Prior pattern:** `/Users/samirski/Development/ANIP/docs/plans/2026-04-25-v023-composition-and-approval-grants-plan.md` — same shape (decisions → spec → schema → constants → 5 runtimes → conformance → docs).

**Branch:** `feat/anip-v024-input-resolution` (from `main`).

---

## Decisions Block — Lock Normative Choices Before Touching Code

**Decision 1.1 — Field name and shape on `CapabilityInput`.**
Use `resolution: InputResolution | null` (snake_case in JSON / wire format; runtime-idiomatic in code: Python `resolution`, TS `resolution`, Go `Resolution *InputResolution \`json:"resolution,omitempty"\``, Java `getResolution()`, C# `Resolution` with `[JsonPropertyName("resolution")]`).

**Decision 1.2 — Additional v0.24 hint fields on `CapabilityInput`.**
Add all the following as optional. These are the typed substrate the `resolution` block depends on:
- `semantic_type: string | null` — free-form string slug naming the domain category (e.g. `"cohort_reference"`, `"scope_reference"`, `"business_category"`). Not enum-constrained at the protocol layer.
- `entity_reference: boolean` — defaults `false`. Marks the input as a reference to a domain entity (vs a literal value).
- `allowed_values: list[string] | null` — closed enum candidates when `resolution.mode == "closed_values"`.
- `catalog_ref: string | null` — string identifier for a reviewed catalog (e.g. `"gtm.account_catalog"`). A single string identifier; named `catalog_ref` (not `reference_catalog`) to leave room for a future plural map of values without naming collision.
- `input_meanings: list[InputMeaning] | null` — labeled reviewed alternatives. Each entry: `{ label: string, value: string, description: string }`.

**Decision 1.3 — Resolution mode enum (closed set).**
Exactly these seven values:
- `closed_values`
- `backend_resolved`
- `app_selected`
- `actor_policy`
- `actor_policy_or_explicit`
- `explicit_only`
- `clarify`

Schema enums reject unknown values via the underlying validator's natural enum check.

**Decision 1.4 — Failure behavior enums (closed set).**
Exactly these seven values for each of `on_missing`, `on_ambiguous`, `on_unresolved`:
- `clarify`
- `use_default`
- `use_actor_scope`
- `app_select_or_clarify`
- `deny`
- `deny_or_clarify`
- `omit`

Same rejection mechanism as mode: enum check at the schema layer.

**Decision 1.5 — Resolver reference shape (inside `InputResolution`).**
`resolver_ref: string | null` — free-form dotted identifier (`gtm.cohort_catalog`, `jira.issue_catalog`). The protocol does NOT validate it as a capability ID, does NOT resolve it, does NOT require it to map to anything in the manifest. It is metadata for the service implementer.

**Decision 1.6 — Required fields on `InputResolution`.**
Only `mode` is required. `resolver_ref`, `on_missing`, `on_ambiguous`, `on_unresolved` are all optional.

**Decision 1.7 — Validation layering.**
Two layers, with explicit responsibilities:

- **Decode / model-validation layer rejection** (fails loudly when given invalid input): unknown values for `resolution.mode`, `resolution.on_missing`, `resolution.on_ambiguous`, `resolution.on_unresolved`. Also `resolution.mode == null` (missing required field). Mechanism per runtime:
  - Python: Pydantic enum validators run at `model_validate(...)`; invalid input raises `ValidationError` synchronously.
  - TypeScript: zod `z.enum(...)` rejects at `parse()`.
  - Go: custom `UnmarshalJSON` on `ResolutionMode`, `ResolutionBehavior`, and `InputResolution` so `json.Unmarshal` itself fails (without `UnmarshalJSON`, Go's plain string typing would silently accept anything).
  - Java: `@JsonCreator` on each enum (Jackson throws `IllegalArgumentException` on unknown values during `readValue`) + null-check in `InputResolution`'s canonical constructor.
  - C#: `JsonConverter` on each enum throws `JsonException` on unknown values during deserialization. `Mode` is typed nullable (`ResolutionMode?`) so missing-mode deserialises to `null`; `CapabilityInput.Validate(...)` then rejects null `Mode` as part of the cross-field check. C# is the one runtime where the missing-mode rejection lives in `Validate(...)` rather than at decode — see the asymmetry note below.

- **Cross-field validation** (separate validator step in each runtime; NOT in JSON Schema): two hard rules:
  - If `resolution.mode == "closed_values"` → `allowed_values` MUST be non-empty.
  - If `resolution.on_missing == "use_default"` → the input's `default` field MUST be non-null.

Cross-field rules live in model-level validators (`ValidateCapabilityInput` in Go; pydantic `@model_validator` in Python; zod `.superRefine` in TS; static `validate(...)` methods in Java/C#) because expressing the `default: any non-null literal` constraint cleanly across all JSON Schema validators is impractical. The JSON Schema in `schema/types/CapabilityDeclaration.json` enforces shape + enum membership only.

**Auto-invoke asymmetry (documented, not fixed in this PR).** Python and TypeScript invoke cross-field validation automatically as part of the standard parsing entry point (`model_validate(...)` runs `@model_validator(mode="after")`; `parse(...)` runs `.superRefine(...)`). Go, Java, and C# expose cross-field validation as a separate explicit call (`ValidateCapabilityInput(...)`, `CapabilityInput.validate(...)`, `CapabilityInput.Validate(...)`) that callers must invoke. This PR ships the **model-level validators only**. Wiring these validators into existing manifest/service-definition load paths so they run automatically on every load is a follow-up — out of scope for this PR.

The "SHOULD" preferences (`backend_resolved` SHOULD have `resolver_ref`; `actor_policy` SHOULD have `entity_reference=false`) are dropped from parse validation — these are advisory and would belong in a future verifier, not a parser.

Tests assert that invalid input is rejected, not any specific error string.

**Decision 1.8 — Backward compatibility for v0.23 manifests.**
Manifests with `version: "anip/0.23"` MUST continue to parse. Loaders MUST treat missing `resolution` blocks as `null`. Manifests declaring `version: "anip/0.24"` MAY include the new fields but are not required to.

**Decision 1.9 — Version-string handling.**
`PROTOCOL_VERSION` constants bump to `"anip/0.24"`. Manifest loaders accept both `anip/0.23` and `anip/0.24` (purely additive change). Tests reference the `PROTOCOL_VERSION` constant per the repo's existing convention.

**Decision 1.10 — PR strategy.**
Single PR on `main` covering Phases 1–11 (spec + schema + 5 runtime models + conformance + docs + version bumps). Matches v0.22 and v0.23 patterns where the contract bump was one atomic change.

---

## File Structure

**Modified:**
- `SPEC.md` — add §4.10 "Input Resolution Metadata"; bump version references.
- `schema/types/CapabilityDeclaration.json` — add `InputResolution`, `InputMeaning` `$defs`; extend `CapabilityInput`.
- `schema/anip.schema.json` — regenerate or mirror.
- `packages/python/anip-core/src/anip_core/constants.py` — bump `PROTOCOL_VERSION`.
- `packages/python/anip-core/src/anip_core/models.py` — add enums + models; extend `CapabilityInput`.
- `packages/python/anip-core/src/anip_core/__init__.py` — export new symbols.
- `packages/typescript/core/src/constants.ts` — bump version.
- `packages/typescript/core/src/models.ts` — add zod schemas; extend `CapabilityInput`.
- `packages/typescript/core/src/index.ts` — export new types (if not via barrel).
- `packages/go/core/constants.go` — bump version.
- `packages/go/core/models.go` — add structs + validator; extend `CapabilityInput`.
- `packages/go/core/models_test.go` — bump version assertion.
- `packages/java/anip-core/src/main/java/dev/anip/core/Constants.java` — bump version.
- `packages/java/anip-core/src/main/java/dev/anip/core/CapabilityInput.java` — add fields.
- `packages/csharp/src/Anip.Core/Constants.cs` — bump version.
- `packages/csharp/src/Anip.Core/CapabilityInput.cs` — add properties + `Validate` method.
- `README.md`, `schema/README.md`, `website/docs/releases/version-history.md`, `website/docs/releases/what-ships-today.md`, version-bumps `0.23.0` → `0.24.0` across docs and package manifests (`pyproject.toml`, `package.json`, `pom.xml`, `Directory.Build.props`/`.csproj`).

**Created:**
- `packages/java/anip-core/src/main/java/dev/anip/core/InputResolution.java`
- `packages/java/anip-core/src/main/java/dev/anip/core/InputMeaning.java`
- `packages/java/anip-core/src/main/java/dev/anip/core/ResolutionMode.java`
- `packages/java/anip-core/src/main/java/dev/anip/core/ResolutionBehavior.java`
- `packages/csharp/src/Anip.Core/InputResolution.cs`
- `packages/csharp/src/Anip.Core/InputMeaning.cs`
- `packages/csharp/src/Anip.Core/ResolutionMode.cs`
- `packages/csharp/src/Anip.Core/ResolutionBehavior.cs`
- `packages/python/anip-core/tests/test_input_resolution.py`
- `packages/typescript/core/tests/input-resolution.test.ts`
- `packages/go/core/input_resolution_test.go`
- `packages/java/anip-core/src/test/java/dev/anip/core/InputResolutionTest.java`
- `packages/csharp/src/Anip.Core.Tests/InputResolutionTests.cs`
- `conformance/samples/v024_input_resolution_examples.json`
- `conformance/test_input_resolution.py`

---

## Phase 1 — Spec

### Task 1: Add §4.10 Input Resolution Metadata to SPEC.md

**Files:**
- Modify: `SPEC.md`.

- [ ] **Step 1: Locate insertion point**

```bash
grep -n "^### 4\.\|^## 5\\." /Users/samirski/Development/ANIP/SPEC.md
```
Identify the §4 subsection list and pick the slot for §4.10 (after the last existing §4.x subsection, before §5).

- [ ] **Step 2: Draft §4.10 section text**

Section content:

- One-paragraph motivation: input resolution is the seam between caller-provided values and service-side validation. Declaring it explicitly stops downstream runtimes from inferring resolution from input names or types.
- Subsection: `InputResolution` object shape (table: `mode`, `resolver_ref`, `on_missing`, `on_ambiguous`, `on_unresolved`).
- Subsection: Resolution mode table (seven values × one-line meaning each — copy from design doc §"Proposed Resolution Modes").
- Subsection: Failure behavior table (seven values × one-line meaning each — copy from design doc §"Proposed Failure Behaviors").
- Subsection: `resolver_ref` semantics — string identifier, not a capability ID, not validated at protocol layer.
- Subsection: Adjacent hint fields — `semantic_type`, `entity_reference`, `allowed_values`, `catalog_ref`, `input_meanings` — each with one-line meaning.
- Subsection: Validation layering — enum membership and `resolution.mode` presence are rejected at the decode/model-validation layer; the two cross-field rules (`closed_values` requires `allowed_values`; `on_missing=use_default` requires non-null `default`) are model-level validation, not JSON Schema rules. Quote D1.7's two-layer split verbatim, including the auto-invoke asymmetry note for Python/TS vs Go/Java/C#.
- Subsection: Backward compatibility — v0.23 manifests parse unchanged; missing `resolution` → null.

- [ ] **Step 3: Insert §4.10**

Use Edit to add the section after the last existing §4.x. Confirm rendering once by reading the file around the new section.

- [ ] **Step 4: Bump version-bearing references**

```bash
grep -n "anip/0\\.23\\|\"0\\.23\"\\|v0\\.23" /Users/samirski/Development/ANIP/SPEC.md | head -20
```
Update mentions of the current protocol version to `anip/0.24` / `v0.24`. Leave historical references untouched.

- [ ] **Step 5: Commit**

```bash
git add SPEC.md
git commit -m "spec(v0.24): add §4.10 Input Resolution Metadata"
```

---

## Phase 2 — JSON Schema

### Task 2: Add InputResolution + InputMeaning $defs; extend CapabilityInput

**Files:**
- Modify: `schema/types/CapabilityDeclaration.json` — extend `$defs` and `CapabilityInput`.
- Modify (or regenerate): `schema/anip.schema.json`.

- [ ] **Step 1: Confirm $defs location**

```bash
grep -n "\"\\$defs\"\\|\"CapabilityInput\"" /Users/samirski/Development/ANIP/schema/types/CapabilityDeclaration.json
```

- [ ] **Step 2: Add `InputMeaning` and `InputResolution` $defs**

Insert into `$defs`:

```json
"InputMeaning": {
  "properties": {
    "label": { "type": "string", "title": "Label" },
    "value": { "type": "string", "title": "Value" },
    "description": { "type": "string", "default": "", "title": "Description" }
  },
  "required": ["label", "value"],
  "title": "InputMeaning",
  "type": "object"
},
"InputResolution": {
  "properties": {
    "mode": {
      "enum": ["closed_values", "backend_resolved", "app_selected", "actor_policy", "actor_policy_or_explicit", "explicit_only", "clarify"],
      "title": "Mode",
      "type": "string"
    },
    "resolver_ref": {
      "anyOf": [{ "type": "string" }, { "type": "null" }],
      "default": null,
      "title": "Resolver Ref"
    },
    "on_missing": {
      "anyOf": [
        { "enum": ["clarify", "use_default", "use_actor_scope", "app_select_or_clarify", "deny", "deny_or_clarify", "omit"], "type": "string" },
        { "type": "null" }
      ],
      "default": null,
      "title": "On Missing"
    },
    "on_ambiguous": {
      "anyOf": [
        { "enum": ["clarify", "use_default", "use_actor_scope", "app_select_or_clarify", "deny", "deny_or_clarify", "omit"], "type": "string" },
        { "type": "null" }
      ],
      "default": null,
      "title": "On Ambiguous"
    },
    "on_unresolved": {
      "anyOf": [
        { "enum": ["clarify", "use_default", "use_actor_scope", "app_select_or_clarify", "deny", "deny_or_clarify", "omit"], "type": "string" },
        { "type": "null" }
      ],
      "default": null,
      "title": "On Unresolved"
    }
  },
  "required": ["mode"],
  "title": "InputResolution",
  "type": "object"
}
```

- [ ] **Step 3: Extend `CapabilityInput` properties**

Add to the `CapabilityInput` $def's `properties`:

```json
"semantic_type": {
  "anyOf": [{ "type": "string" }, { "type": "null" }],
  "default": null,
  "title": "Semantic Type"
},
"entity_reference": {
  "default": false,
  "title": "Entity Reference",
  "type": "boolean"
},
"allowed_values": {
  "anyOf": [
    { "items": { "type": "string" }, "type": "array" },
    { "type": "null" }
  ],
  "default": null,
  "title": "Allowed Values"
},
"catalog_ref": {
  "anyOf": [{ "type": "string" }, { "type": "null" }],
  "default": null,
  "title": "Catalog Ref"
},
"input_meanings": {
  "anyOf": [
    { "items": { "$ref": "#/$defs/InputMeaning" }, "type": "array" },
    { "type": "null" }
  ],
  "default": null,
  "title": "Input Meanings"
},
"resolution": {
  "anyOf": [{ "$ref": "#/$defs/InputResolution" }, { "type": "null" }],
  "default": null
}
```

`required` stays `["name", "type"]`.

- [ ] **Step 4: Mirror in top-level schema**

If `schema/anip.schema.json` is generated by `schema/generate.py`:
```bash
cd /Users/samirski/Development/ANIP && python schema/generate.py
```
Otherwise hand-mirror the same edits.

- [ ] **Step 5: Commit**

```bash
git add schema/
git commit -m "schema(v0.24): add InputResolution + InputMeaning; extend CapabilityInput"
```

---

## Phase 3 — Constants Bump (All 5 Runtimes)

### Task 3: Bump PROTOCOL_VERSION

**Files:**
- Modify: `packages/python/anip-core/src/anip_core/constants.py:3`
- Modify: `packages/typescript/core/src/constants.ts:1`
- Modify: `packages/go/core/constants.go:40`
- Modify: `packages/java/anip-core/src/main/java/dev/anip/core/Constants.java:14`
- Modify: `packages/csharp/src/Anip.Core/Constants.cs:5`
- Modify: `packages/go/core/models_test.go:289` (literal-string assertion)

- [ ] **Step 1: Python**
Edit `packages/python/anip-core/src/anip_core/constants.py`: `PROTOCOL_VERSION = "anip/0.23"` → `PROTOCOL_VERSION = "anip/0.24"`.

- [ ] **Step 2: TypeScript**
Edit `packages/typescript/core/src/constants.ts`: `export const PROTOCOL_VERSION = "anip/0.23";` → `"anip/0.24"`.

- [ ] **Step 3: Go**
Edit `packages/go/core/constants.go`: `const ProtocolVersion = "anip/0.23"` → `"anip/0.24"`.

- [ ] **Step 4: Go test**
Edit `packages/go/core/models_test.go` (around line 289): both occurrences `"anip/0.23"` → `"anip/0.24"`.

- [ ] **Step 5: Java**
Edit `packages/java/anip-core/src/main/java/dev/anip/core/Constants.java`: `public static final String PROTOCOL_VERSION = "anip/0.23";` → `"anip/0.24"`.

- [ ] **Step 6: C#**
Edit `packages/csharp/src/Anip.Core/Constants.cs`: `public const string ProtocolVersion = "anip/0.23";` → `"anip/0.24"`.

- [ ] **Step 7: Audit residual hardcoded version strings**

The Phase 3 file list above is the primary set, but several other files in the repo carry the literal `"anip/0.23"` (tests, manifest defaults, sample app code). The following grep is the source of truth — every match outside historical/archive paths must flip to `"anip/0.24"`:

```bash
grep -rn "\"anip/0\\.23\"" /Users/samirski/Development/ANIP/packages/ /Users/samirski/Development/ANIP/studio/ /Users/samirski/Development/ANIP/examples/ /Users/samirski/Development/ANIP/conformance/
```

Non-exhaustive list of files known to carry literal version strings (the grep will catch the canonical set):
- `packages/java/anip-core/src/test/java/dev/anip/core/ConstantsTest.java` — pinning test for `PROTOCOL_VERSION`.
- `packages/typescript/core/src/models.ts` — `ANIPManifest.protocol` default literal, if present.
- `packages/csharp/src/Anip.Core.Tests/ConstantsTests.cs` — equivalent pinning test if it exists.
- Any Vue/Angular sample test under `packages/typescript/studio/`, `packages/python/anip-studio/`, or examples that assert the protocol version literal.

Per repo memory `feedback_version_constants.md`: tests must use the `PROTOCOL_VERSION` constant, not hardcoded strings — for any test that hardcodes the literal solely for assertion convenience, refactor to import the constant. Tests that pin the constant's *value* (e.g. `ConstantsTest`) keep the literal because their job is to fail if the constant ever drifts unexpectedly — bump those literals in-place.

- [ ] **Step 8: Run unit tests across all 5 runtimes**

```bash
cd /Users/samirski/Development/ANIP/packages/python && pytest anip-core/tests/ -x -q 2>&1 | tail -20
cd /Users/samirski/Development/ANIP/packages/typescript/core && npm test 2>&1 | tail -20
cd /Users/samirski/Development/ANIP/packages/go/core && go test ./... 2>&1 | tail -20
cd /Users/samirski/Development/ANIP/packages/java && mvn -pl anip-core test -q 2>&1 | tail -30
cd /Users/samirski/Development/ANIP/packages/csharp && dotnet test src/Anip.Core.Tests 2>&1 | tail -20
```
Expected: all PASS.

- [ ] **Step 9: Commit**

```bash
git add packages/
git commit -m "core(v0.24): bump PROTOCOL_VERSION to anip/0.24 across all 5 runtimes"
```

---

## Phase 4 — Python Model

### Task 4: Add Python InputResolution + InputMeaning; extend CapabilityInput

**Files:**
- Modify: `packages/python/anip-core/src/anip_core/models.py` (insert before line 136 `class CapabilityInput`).
- Modify: `packages/python/anip-core/src/anip_core/__init__.py`.
- Test: `packages/python/anip-core/tests/test_input_resolution.py` (NEW).

- [ ] **Step 1: Write the failing test**

Create `packages/python/anip-core/tests/test_input_resolution.py`:

```python
"""v0.24 input resolution metadata — parse and round-trip."""
import pytest
from anip_core.models import (
    CapabilityInput,
    InputResolution,
    InputMeaning,
    ResolutionMode,
    ResolutionBehavior,
)
from pydantic import ValidationError


def test_minimal_input_no_resolution_block():
    """v0.23-compatible input parses unchanged."""
    inp = CapabilityInput(name="quarter", type="string")
    assert inp.resolution is None
    assert inp.semantic_type is None
    assert inp.entity_reference is False
    assert inp.allowed_values is None
    assert inp.catalog_ref is None
    assert inp.input_meanings is None


def test_closed_values_resolution():
    inp = CapabilityInput(
        name="forecast_mode",
        type="string",
        required=False,
        default="risk_adjusted",
        allowed_values=["risk_adjusted", "likely", "best_case"],
        semantic_type="business_category",
        resolution=InputResolution(
            mode=ResolutionMode.CLOSED_VALUES,
            on_missing=ResolutionBehavior.USE_DEFAULT,
            on_ambiguous=ResolutionBehavior.CLARIFY,
        ),
    )
    assert inp.resolution.mode == ResolutionMode.CLOSED_VALUES


def test_backend_resolved_resolution():
    inp = CapabilityInput(
        name="cohort_ref",
        type="string",
        required=True,
        semantic_type="cohort_reference",
        entity_reference=True,
        catalog_ref="gtm.cohort_catalog",
        resolution=InputResolution(
            mode=ResolutionMode.BACKEND_RESOLVED,
            resolver_ref="gtm.cohort_catalog",
            on_missing=ResolutionBehavior.CLARIFY,
        ),
    )
    assert inp.resolution.resolver_ref == "gtm.cohort_catalog"
    assert inp.catalog_ref == "gtm.cohort_catalog"
    assert inp.entity_reference is True


def test_actor_policy_or_explicit_resolution():
    inp = CapabilityInput(
        name="owner_scope",
        type="string",
        required=False,
        semantic_type="scope_reference",
        resolution=InputResolution(
            mode=ResolutionMode.ACTOR_POLICY_OR_EXPLICIT,
            on_missing=ResolutionBehavior.USE_ACTOR_SCOPE,
            on_unresolved=ResolutionBehavior.DENY_OR_CLARIFY,
        ),
    )
    assert inp.resolution.mode == ResolutionMode.ACTOR_POLICY_OR_EXPLICIT


def test_input_meanings():
    inp = CapabilityInput(
        name="priority",
        type="string",
        input_meanings=[
            InputMeaning(label="High", value="P0", description="critical"),
            InputMeaning(label="Medium", value="P1"),
        ],
    )
    assert len(inp.input_meanings) == 2
    assert inp.input_meanings[1].description == ""  # default


def test_unknown_mode_rejected():
    """Schema-level enum rejection (no specific error string assertion)."""
    with pytest.raises(ValidationError):
        InputResolution(mode="not_a_real_mode")


def test_unknown_behavior_rejected():
    with pytest.raises(ValidationError):
        InputResolution(mode=ResolutionMode.CLARIFY, on_missing="not_real")


def test_missing_mode_rejected():
    """resolution.mode is required; {} body must fail decode."""
    with pytest.raises(ValidationError):
        InputResolution.model_validate({})


def test_closed_values_without_allowed_values_rejected():
    """D1.7 hard cross-field rule."""
    with pytest.raises(ValidationError):
        CapabilityInput(
            name="x",
            type="string",
            resolution=InputResolution(mode=ResolutionMode.CLOSED_VALUES),
        )


def test_use_default_without_default_rejected():
    """D1.7 hard cross-field rule."""
    with pytest.raises(ValidationError):
        CapabilityInput(
            name="x",
            type="string",
            default=None,
            resolution=InputResolution(
                mode=ResolutionMode.CLARIFY,
                on_missing=ResolutionBehavior.USE_DEFAULT,
            ),
        )


def test_round_trip_json():
    inp = CapabilityInput(
        name="cohort_ref",
        type="string",
        semantic_type="cohort_reference",
        entity_reference=True,
        catalog_ref="gtm.cohort_catalog",
        resolution=InputResolution(
            mode=ResolutionMode.BACKEND_RESOLVED,
            resolver_ref="gtm.cohort_catalog",
            on_missing=ResolutionBehavior.CLARIFY,
        ),
    )
    raw = inp.model_dump_json()
    parsed = CapabilityInput.model_validate_json(raw)
    assert parsed == inp


def test_v023_manifest_still_parses():
    v023_json = {"name": "q", "type": "string", "required": True}
    inp = CapabilityInput.model_validate(v023_json)
    assert inp.resolution is None
    assert inp.semantic_type is None
    assert inp.catalog_ref is None
```

- [ ] **Step 2: Run tests — expect FAIL (ImportError)**

```bash
cd /Users/samirski/Development/ANIP/packages/python && pytest anip-core/tests/test_input_resolution.py -v 2>&1 | tail -25
```

- [ ] **Step 3: Add enums + models in `models.py`**

Edit `packages/python/anip-core/src/anip_core/models.py`. Confirm `from pydantic import BaseModel, model_validator` is imported (add `model_validator` if missing). Insert before `class CapabilityInput` (line 136):

```python
class ResolutionMode(str, Enum):
    CLOSED_VALUES = "closed_values"
    BACKEND_RESOLVED = "backend_resolved"
    APP_SELECTED = "app_selected"
    ACTOR_POLICY = "actor_policy"
    ACTOR_POLICY_OR_EXPLICIT = "actor_policy_or_explicit"
    EXPLICIT_ONLY = "explicit_only"
    CLARIFY = "clarify"


class ResolutionBehavior(str, Enum):
    CLARIFY = "clarify"
    USE_DEFAULT = "use_default"
    USE_ACTOR_SCOPE = "use_actor_scope"
    APP_SELECT_OR_CLARIFY = "app_select_or_clarify"
    DENY = "deny"
    DENY_OR_CLARIFY = "deny_or_clarify"
    OMIT = "omit"


class InputResolution(BaseModel):
    mode: ResolutionMode
    resolver_ref: str | None = None
    on_missing: ResolutionBehavior | None = None
    on_ambiguous: ResolutionBehavior | None = None
    on_unresolved: ResolutionBehavior | None = None


class InputMeaning(BaseModel):
    label: str
    value: str
    description: str = ""
```

- [ ] **Step 4: Extend `CapabilityInput`**

Replace the existing class:

```python
class CapabilityInput(BaseModel):
    name: str
    type: str
    required: bool = True
    default: Any = None
    description: str = ""
    semantic_type: str | None = None
    entity_reference: bool = False
    allowed_values: list[str] | None = None
    catalog_ref: str | None = None
    input_meanings: list[InputMeaning] | None = None
    resolution: InputResolution | None = None

    @model_validator(mode="after")
    def _validate_resolution_cross_fields(self) -> "CapabilityInput":
        if self.resolution is None:
            return self
        if self.resolution.mode == ResolutionMode.CLOSED_VALUES and not self.allowed_values:
            raise ValueError("closed_values requires non-empty allowed_values")
        if self.resolution.on_missing == ResolutionBehavior.USE_DEFAULT and self.default is None:
            raise ValueError("on_missing=use_default requires a non-null default")
        return self
```

- [ ] **Step 5: Export from `__init__.py`**

Add `InputResolution`, `InputMeaning`, `ResolutionMode`, `ResolutionBehavior` to the imports from `.models` and to `__all__`.

- [ ] **Step 6: Run tests — expect PASS**

```bash
cd /Users/samirski/Development/ANIP/packages/python && pytest anip-core/tests/test_input_resolution.py -v 2>&1 | tail -25
```
Expected: 10/10 PASS.

- [ ] **Step 7: Full anip-core suite**

```bash
cd /Users/samirski/Development/ANIP/packages/python && pytest anip-core/tests/ -x -q 2>&1 | tail -10
```

- [ ] **Step 8: Commit**

```bash
git add packages/python/anip-core/
git commit -m "python(v0.24): add InputResolution, InputMeaning models; extend CapabilityInput"
```

---

## Phase 5 — TypeScript Model

### Task 5: Add TS zod schemas; extend CapabilityInput

**Files:**
- Modify: `packages/typescript/core/src/models.ts` (around line 80).
- Modify: `packages/typescript/core/src/index.ts` (if not using barrel export).
- Test: `packages/typescript/core/tests/input-resolution.test.ts` (NEW).

- [ ] **Step 1: Read current shape**

```bash
sed -n '75,95p' /Users/samirski/Development/ANIP/packages/typescript/core/src/models.ts
```

- [ ] **Step 2: Write the failing test**

Create `packages/typescript/core/tests/input-resolution.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { CapabilityInput, InputResolution, InputMeaning, ResolutionMode, ResolutionBehavior } from "../src/models";

describe("v0.24 input resolution", () => {
  it("parses minimal v0.23-shaped input unchanged", () => {
    const inp = CapabilityInput.parse({ name: "q", type: "string" });
    expect(inp.resolution).toBeNull();
    expect(inp.semantic_type).toBeNull();
    expect(inp.catalog_ref).toBeNull();
    expect(inp.entity_reference).toBe(false);
  });

  it("parses closed_values resolution", () => {
    const inp = CapabilityInput.parse({
      name: "forecast_mode",
      type: "string",
      required: false,
      default: "risk_adjusted",
      allowed_values: ["risk_adjusted", "likely", "best_case"],
      semantic_type: "business_category",
      resolution: { mode: "closed_values", on_missing: "use_default", on_ambiguous: "clarify" },
    });
    expect(inp.resolution?.mode).toBe("closed_values");
  });

  it("parses backend_resolved resolution with catalog_ref", () => {
    const inp = CapabilityInput.parse({
      name: "cohort_ref",
      type: "string",
      semantic_type: "cohort_reference",
      entity_reference: true,
      catalog_ref: "gtm.cohort_catalog",
      resolution: { mode: "backend_resolved", resolver_ref: "gtm.cohort_catalog", on_missing: "clarify" },
    });
    expect(inp.resolution?.resolver_ref).toBe("gtm.cohort_catalog");
    expect(inp.catalog_ref).toBe("gtm.cohort_catalog");
    expect(inp.entity_reference).toBe(true);
  });

  it("rejects unknown mode (schema-level)", () => {
    expect(() => InputResolution.parse({ mode: "not_real" })).toThrow();
  });

  it("rejects unknown behavior (schema-level)", () => {
    expect(() => InputResolution.parse({ mode: "clarify", on_missing: "bogus" })).toThrow();
  });

  it("rejects missing mode (required field)", () => {
    expect(() => InputResolution.parse({})).toThrow();
  });

  it("rejects closed_values without allowed_values", () => {
    expect(() => CapabilityInput.parse({
      name: "x",
      type: "string",
      resolution: { mode: "closed_values" },
    })).toThrow();
  });

  it("rejects use_default without default", () => {
    expect(() => CapabilityInput.parse({
      name: "x",
      type: "string",
      resolution: { mode: "clarify", on_missing: "use_default" },
    })).toThrow();
  });

  it("round-trips JSON", () => {
    const original = {
      name: "cohort_ref",
      type: "string",
      required: true,
      default: null,
      description: "",
      semantic_type: "cohort_reference",
      entity_reference: true,
      allowed_values: null,
      catalog_ref: "gtm.cohort_catalog",
      input_meanings: null,
      resolution: { mode: "backend_resolved", resolver_ref: "gtm.cohort_catalog", on_missing: "clarify", on_ambiguous: null, on_unresolved: null },
    };
    const parsed = CapabilityInput.parse(original);
    const serialized = JSON.parse(JSON.stringify(parsed));
    expect(serialized).toEqual(original);
  });
});
```

- [ ] **Step 3: Run — expect FAIL**

```bash
cd /Users/samirski/Development/ANIP/packages/typescript/core && npx vitest run tests/input-resolution.test.ts 2>&1 | tail -20
```

- [ ] **Step 4: Add zod schemas in `models.ts`**

Insert before the existing `CapabilityInput`:

```typescript
export const ResolutionMode = z.enum([
  "closed_values",
  "backend_resolved",
  "app_selected",
  "actor_policy",
  "actor_policy_or_explicit",
  "explicit_only",
  "clarify",
]);
export type ResolutionMode = z.infer<typeof ResolutionMode>;

export const ResolutionBehavior = z.enum([
  "clarify",
  "use_default",
  "use_actor_scope",
  "app_select_or_clarify",
  "deny",
  "deny_or_clarify",
  "omit",
]);
export type ResolutionBehavior = z.infer<typeof ResolutionBehavior>;

export const InputResolution = z.object({
  mode: ResolutionMode,
  resolver_ref: z.string().nullable().default(null),
  on_missing: ResolutionBehavior.nullable().default(null),
  on_ambiguous: ResolutionBehavior.nullable().default(null),
  on_unresolved: ResolutionBehavior.nullable().default(null),
});
export type InputResolution = z.infer<typeof InputResolution>;

export const InputMeaning = z.object({
  label: z.string(),
  value: z.string(),
  description: z.string().default(""),
});
export type InputMeaning = z.infer<typeof InputMeaning>;
```

- [ ] **Step 5: Replace `CapabilityInput`**

```typescript
export const CapabilityInput = z.object({
  name: z.string(),
  type: z.string(),
  required: z.boolean().default(true),
  default: z.any().default(null),
  description: z.string().default(""),
  semantic_type: z.string().nullable().default(null),
  entity_reference: z.boolean().default(false),
  allowed_values: z.array(z.string()).nullable().default(null),
  catalog_ref: z.string().nullable().default(null),
  input_meanings: z.array(InputMeaning).nullable().default(null),
  resolution: InputResolution.nullable().default(null),
}).superRefine((data, ctx) => {
  if (data.resolution === null) return;
  if (data.resolution.mode === "closed_values" && (!data.allowed_values || data.allowed_values.length === 0)) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, message: "closed_values requires non-empty allowed_values" });
  }
  if (data.resolution.on_missing === "use_default" && (data.default === null || data.default === undefined)) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, message: "on_missing=use_default requires a non-null default" });
  }
});
export type CapabilityInput = z.infer<typeof CapabilityInput>;
```

- [ ] **Step 6: Export from `index.ts`** if needed (verify barrel exports first).

- [ ] **Step 7: Run tests — expect PASS**

```bash
cd /Users/samirski/Development/ANIP/packages/typescript/core && npx vitest run tests/input-resolution.test.ts 2>&1 | tail -20
```

- [ ] **Step 8: Full TS suite**

```bash
cd /Users/samirski/Development/ANIP/packages/typescript/core && npm test 2>&1 | tail -20
```

- [ ] **Step 9: Commit**

```bash
git add packages/typescript/core/
git commit -m "typescript(v0.24): add InputResolution, InputMeaning schemas; extend CapabilityInput"
```

---

## Phase 6 — Go Model

### Task 6: Add Go types + validator; extend CapabilityInput

**Files:**
- Modify: `packages/go/core/models.go`.
- Test: `packages/go/core/input_resolution_test.go` (NEW).

- [ ] **Step 1: Inspect current shape**

```bash
sed -n '100,115p' /Users/samirski/Development/ANIP/packages/go/core/models.go
```

- [ ] **Step 2: Write the failing test**

Create `packages/go/core/input_resolution_test.go`:

```go
package core

import (
	"encoding/json"
	"strings"
	"testing"
)

func TestInputResolution_MinimalUnchanged(t *testing.T) {
	// Note on `required` defaulting: Python/TS/Java/C# default missing
	// `required` to true via their respective serializer hooks; Go's plain
	// json.Unmarshal sets bool fields to false when absent. That pre-existing
	// asymmetry is not introduced or fixed by v0.24; do not assert on
	// inp.Required here.
	raw := `{"name":"q","type":"string"}`
	var inp CapabilityInput
	if err := json.Unmarshal([]byte(raw), &inp); err != nil {
		t.Fatalf("v0.23-shaped input should parse: %v", err)
	}
	if inp.Resolution != nil {
		t.Errorf("expected nil Resolution")
	}
	if inp.EntityReference {
		t.Errorf("expected entity_reference=false default")
	}
	if inp.CatalogRef != nil {
		t.Errorf("expected nil CatalogRef")
	}
}

func TestInputResolution_BackendResolved(t *testing.T) {
	raw := `{
		"name":"cohort_ref","type":"string","required":true,
		"semantic_type":"cohort_reference","entity_reference":true,"catalog_ref":"gtm.cohort_catalog",
		"resolution":{"mode":"backend_resolved","resolver_ref":"gtm.cohort_catalog","on_missing":"clarify"}
	}`
	var inp CapabilityInput
	if err := json.Unmarshal([]byte(raw), &inp); err != nil {
		t.Fatalf("parse: %v", err)
	}
	if err := ValidateCapabilityInput(&inp); err != nil {
		t.Fatalf("validate: %v", err)
	}
	if inp.Resolution.Mode != ResolutionModeBackendResolved {
		t.Errorf("mode = %q", inp.Resolution.Mode)
	}
	if *inp.CatalogRef != "gtm.cohort_catalog" {
		t.Errorf("catalog_ref = %q", *inp.CatalogRef)
	}
}

func TestInputResolution_UnknownModeRejectedAtDecode(t *testing.T) {
	// Decode itself must reject unknown enum strings — without UnmarshalJSON,
	// Go's plain string typing would silently accept "not_real".
	raw := `{"name":"x","type":"string","resolution":{"mode":"not_real"}}`
	var inp CapabilityInput
	if err := json.Unmarshal([]byte(raw), &inp); err == nil {
		t.Errorf("expected decode error for unknown mode, got nil")
	}
}

func TestInputResolution_UnknownBehaviorRejectedAtDecode(t *testing.T) {
	raw := `{"name":"x","type":"string","resolution":{"mode":"clarify","on_missing":"bogus"}}`
	var inp CapabilityInput
	if err := json.Unmarshal([]byte(raw), &inp); err == nil {
		t.Errorf("expected decode error for unknown behavior, got nil")
	}
}

func TestInputResolution_MissingModeRejectedAtDecode(t *testing.T) {
	// resolution.mode is required by the contract; missing it must fail decode.
	raw := `{"name":"x","type":"string","resolution":{}}`
	var inp CapabilityInput
	if err := json.Unmarshal([]byte(raw), &inp); err == nil {
		t.Errorf("expected decode error for missing resolution.mode, got nil")
	}
}

func TestInputResolution_ClosedValuesRequiresAllowedValues(t *testing.T) {
	raw := `{"name":"x","type":"string","resolution":{"mode":"closed_values"}}`
	var inp CapabilityInput
	_ = json.Unmarshal([]byte(raw), &inp)
	err := ValidateCapabilityInput(&inp)
	if err == nil || !strings.Contains(strings.ToLower(err.Error()), "allowed_values") {
		t.Errorf("expected allowed_values error, got %v", err)
	}
}

func TestInputResolution_UseDefaultRequiresDefault(t *testing.T) {
	raw := `{"name":"x","type":"string","resolution":{"mode":"clarify","on_missing":"use_default"}}`
	var inp CapabilityInput
	_ = json.Unmarshal([]byte(raw), &inp)
	err := ValidateCapabilityInput(&inp)
	if err == nil || !strings.Contains(strings.ToLower(err.Error()), "default") {
		t.Errorf("expected default error, got %v", err)
	}
}

func TestInputResolution_RoundTrip(t *testing.T) {
	original := CapabilityInput{
		Name:            "cohort_ref",
		Type:            "string",
		Required:        true,
		SemanticType:    strPtr("cohort_reference"),
		EntityReference: true,
		CatalogRef:      strPtr("gtm.cohort_catalog"),
		Resolution: &InputResolution{
			Mode:        ResolutionModeBackendResolved,
			ResolverRef: strPtr("gtm.cohort_catalog"),
			OnMissing:   behaviorPtr(ResolutionBehaviorClarify),
		},
	}
	b, err := json.Marshal(original)
	if err != nil {
		t.Fatal(err)
	}
	var rt CapabilityInput
	if err := json.Unmarshal(b, &rt); err != nil {
		t.Fatal(err)
	}
	if rt.Resolution.Mode != original.Resolution.Mode {
		t.Errorf("mode lost in round-trip")
	}
	if *rt.CatalogRef != *original.CatalogRef {
		t.Errorf("catalog_ref lost")
	}
}

func strPtr(s string) *string                              { return &s }
func behaviorPtr(b ResolutionBehavior) *ResolutionBehavior { return &b }
```

- [ ] **Step 3: Run — expect FAIL**

```bash
cd /Users/samirski/Development/ANIP/packages/go/core && go test -run InputResolution -v 2>&1 | tail -20
```

- [ ] **Step 4: Add types and validator in `models.go`**

Insert (before `CapabilityInput`):

```go
type ResolutionMode string

const (
	ResolutionModeClosedValues          ResolutionMode = "closed_values"
	ResolutionModeBackendResolved       ResolutionMode = "backend_resolved"
	ResolutionModeAppSelected           ResolutionMode = "app_selected"
	ResolutionModeActorPolicy           ResolutionMode = "actor_policy"
	ResolutionModeActorPolicyOrExplicit ResolutionMode = "actor_policy_or_explicit"
	ResolutionModeExplicitOnly          ResolutionMode = "explicit_only"
	ResolutionModeClarify               ResolutionMode = "clarify"
)

type ResolutionBehavior string

const (
	ResolutionBehaviorClarify            ResolutionBehavior = "clarify"
	ResolutionBehaviorUseDefault         ResolutionBehavior = "use_default"
	ResolutionBehaviorUseActorScope      ResolutionBehavior = "use_actor_scope"
	ResolutionBehaviorAppSelectOrClarify ResolutionBehavior = "app_select_or_clarify"
	ResolutionBehaviorDeny               ResolutionBehavior = "deny"
	ResolutionBehaviorDenyOrClarify      ResolutionBehavior = "deny_or_clarify"
	ResolutionBehaviorOmit               ResolutionBehavior = "omit"
)

type InputResolution struct {
	Mode         ResolutionMode      `json:"mode"`
	ResolverRef  *string             `json:"resolver_ref,omitempty"`
	OnMissing    *ResolutionBehavior `json:"on_missing,omitempty"`
	OnAmbiguous  *ResolutionBehavior `json:"on_ambiguous,omitempty"`
	OnUnresolved *ResolutionBehavior `json:"on_unresolved,omitempty"`
}

type InputMeaning struct {
	Label       string `json:"label"`
	Value       string `json:"value"`
	Description string `json:"description,omitempty"`
}

// UnmarshalJSON for ResolutionMode rejects unknown enum strings at decode time.
func (m *ResolutionMode) UnmarshalJSON(data []byte) error {
	var s string
	if err := json.Unmarshal(data, &s); err != nil {
		return err
	}
	mode := ResolutionMode(s)
	if _, ok := validResolutionModes[mode]; !ok {
		return fmt.Errorf("invalid resolution.mode: %q", s)
	}
	*m = mode
	return nil
}

// UnmarshalJSON for ResolutionBehavior rejects unknown enum strings at decode time.
func (b *ResolutionBehavior) UnmarshalJSON(data []byte) error {
	var s string
	if err := json.Unmarshal(data, &s); err != nil {
		return err
	}
	behavior := ResolutionBehavior(s)
	if _, ok := validResolutionBehaviors[behavior]; !ok {
		return fmt.Errorf("invalid resolution behavior: %q", s)
	}
	*b = behavior
	return nil
}

// UnmarshalJSON for InputResolution enforces that `mode` is present.
// Without this, a JSON body of `{}` would silently produce a zero-value Mode.
// Use a flat raw struct (not an embedded alias) so there is no duplicate
// `json:"mode"` tag between the outer pointer and an inherited field.
func (r *InputResolution) UnmarshalJSON(data []byte) error {
	var raw struct {
		Mode         *ResolutionMode     `json:"mode"`
		ResolverRef  *string             `json:"resolver_ref,omitempty"`
		OnMissing    *ResolutionBehavior `json:"on_missing,omitempty"`
		OnAmbiguous  *ResolutionBehavior `json:"on_ambiguous,omitempty"`
		OnUnresolved *ResolutionBehavior `json:"on_unresolved,omitempty"`
	}
	if err := json.Unmarshal(data, &raw); err != nil {
		return err
	}
	if raw.Mode == nil {
		return fmt.Errorf("resolution.mode is required")
	}
	*r = InputResolution{
		Mode:         *raw.Mode,
		ResolverRef:  raw.ResolverRef,
		OnMissing:    raw.OnMissing,
		OnAmbiguous:  raw.OnAmbiguous,
		OnUnresolved: raw.OnUnresolved,
	}
	return nil
}
```

Place the `UnmarshalJSON` methods after the validResolutionModes / validResolutionBehaviors maps (defined below in the next sub-step) since they reference those maps. Reorder if needed so the maps appear before the methods.

Replace `CapabilityInput`:

```go
type CapabilityInput struct {
	Name            string           `json:"name"`
	Type            string           `json:"type"`
	Required        bool             `json:"required"`
	Default         any              `json:"default,omitempty"`
	Description     string           `json:"description,omitempty"`
	SemanticType    *string          `json:"semantic_type,omitempty"`
	EntityReference bool             `json:"entity_reference,omitempty"`
	AllowedValues   []string         `json:"allowed_values,omitempty"`
	CatalogRef      *string          `json:"catalog_ref,omitempty"`
	InputMeanings   []InputMeaning   `json:"input_meanings,omitempty"`
	Resolution      *InputResolution `json:"resolution,omitempty"`
}
```

Append validator:

```go
var validResolutionModes = map[ResolutionMode]struct{}{
	ResolutionModeClosedValues: {}, ResolutionModeBackendResolved: {}, ResolutionModeAppSelected: {},
	ResolutionModeActorPolicy: {}, ResolutionModeActorPolicyOrExplicit: {}, ResolutionModeExplicitOnly: {},
	ResolutionModeClarify: {},
}

var validResolutionBehaviors = map[ResolutionBehavior]struct{}{
	ResolutionBehaviorClarify: {}, ResolutionBehaviorUseDefault: {}, ResolutionBehaviorUseActorScope: {},
	ResolutionBehaviorAppSelectOrClarify: {}, ResolutionBehaviorDeny: {}, ResolutionBehaviorDenyOrClarify: {},
	ResolutionBehaviorOmit: {},
}

// ValidateCapabilityInput enforces cross-field rules. Enum validity and
// resolution.mode presence are enforced at decode time by UnmarshalJSON.
func ValidateCapabilityInput(inp *CapabilityInput) error {
	if inp.Resolution == nil {
		return nil
	}
	if inp.Resolution.Mode == ResolutionModeClosedValues && len(inp.AllowedValues) == 0 {
		return fmt.Errorf("closed_values requires non-empty allowed_values")
	}
	if inp.Resolution.OnMissing != nil && *inp.Resolution.OnMissing == ResolutionBehaviorUseDefault && inp.Default == nil {
		return fmt.Errorf("on_missing=use_default requires a non-null default")
	}
	return nil
}
```

Ensure `"fmt"` is imported.

- [ ] **Step 5: Run — expect PASS**

```bash
cd /Users/samirski/Development/ANIP/packages/go/core && go test -run InputResolution -v 2>&1 | tail -25
```

- [ ] **Step 6: Full Go suite**

```bash
cd /Users/samirski/Development/ANIP/packages/go && go test ./... 2>&1 | tail -20
```

- [ ] **Step 7: Commit**

```bash
git add packages/go/
git commit -m "go(v0.24): add InputResolution, InputMeaning; extend CapabilityInput + validator"
```

---

## Phase 7 — Java Model

### Task 7: Add Java types; extend CapabilityInput

**Files:**
- Create: `packages/java/anip-core/src/main/java/dev/anip/core/InputResolution.java`
- Create: `packages/java/anip-core/src/main/java/dev/anip/core/InputMeaning.java`
- Create: `packages/java/anip-core/src/main/java/dev/anip/core/ResolutionMode.java`
- Create: `packages/java/anip-core/src/main/java/dev/anip/core/ResolutionBehavior.java`
- Modify: `packages/java/anip-core/src/main/java/dev/anip/core/CapabilityInput.java`
- Test: `packages/java/anip-core/src/test/java/dev/anip/core/InputResolutionTest.java` (NEW).

- [ ] **Step 1: Read current `CapabilityInput.java`**

```bash
cat /Users/samirski/Development/ANIP/packages/java/anip-core/src/main/java/dev/anip/core/CapabilityInput.java
```

- [ ] **Step 2: Write the failing test**

Create `packages/java/anip-core/src/test/java/dev/anip/core/InputResolutionTest.java`:

```java
package dev.anip.core;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class InputResolutionTest {
    private final ObjectMapper M = new ObjectMapper();

    @Test
    void v023ShapedInputParsesUnchanged() throws Exception {
        String raw = "{\"name\":\"q\",\"type\":\"string\"}";
        CapabilityInput inp = M.readValue(raw, CapabilityInput.class);
        assertNull(inp.getResolution());
        assertFalse(inp.isEntityReference());
        assertNull(inp.getSemanticType());
        assertNull(inp.getCatalogRef());
    }

    @Test
    void backendResolvedParses() throws Exception {
        String raw = "{\"name\":\"cohort_ref\",\"type\":\"string\",\"required\":true," +
                "\"semantic_type\":\"cohort_reference\",\"entity_reference\":true,\"catalog_ref\":\"gtm.cohort_catalog\"," +
                "\"resolution\":{\"mode\":\"backend_resolved\",\"resolver_ref\":\"gtm.cohort_catalog\",\"on_missing\":\"clarify\"}}";
        CapabilityInput inp = M.readValue(raw, CapabilityInput.class);
        CapabilityInput.validate(inp);
        assertEquals(ResolutionMode.BACKEND_RESOLVED, inp.getResolution().mode());
        assertEquals("gtm.cohort_catalog", inp.getCatalogRef());
        assertTrue(inp.isEntityReference());
    }

    @Test
    void unknownModeRejected() throws Exception {
        String raw = "{\"name\":\"x\",\"type\":\"string\",\"resolution\":{\"mode\":\"not_real\"}}";
        assertThrows(Exception.class, () -> M.readValue(raw, CapabilityInput.class));
    }

    @Test
    void missingModeRejected() throws Exception {
        // {"resolution":{}} must fail because mode is required.
        String raw = "{\"name\":\"x\",\"type\":\"string\",\"resolution\":{}}";
        assertThrows(Exception.class, () -> M.readValue(raw, CapabilityInput.class));
    }

    @Test
    void closedValuesWithoutAllowedValuesRejected() throws Exception {
        String raw = "{\"name\":\"x\",\"type\":\"string\",\"resolution\":{\"mode\":\"closed_values\"}}";
        CapabilityInput inp = M.readValue(raw, CapabilityInput.class);
        assertThrows(IllegalArgumentException.class, () -> CapabilityInput.validate(inp));
    }

    @Test
    void useDefaultWithoutDefaultRejected() throws Exception {
        String raw = "{\"name\":\"x\",\"type\":\"string\",\"resolution\":{\"mode\":\"clarify\",\"on_missing\":\"use_default\"}}";
        CapabilityInput inp = M.readValue(raw, CapabilityInput.class);
        assertThrows(IllegalArgumentException.class, () -> CapabilityInput.validate(inp));
    }

    @Test
    void roundTrip() throws Exception {
        CapabilityInput inp = new CapabilityInput(
                "cohort_ref", "string", true, null, "",
                "cohort_reference", true, null, "gtm.cohort_catalog", null,
                new InputResolution(ResolutionMode.BACKEND_RESOLVED, "gtm.cohort_catalog",
                        ResolutionBehavior.CLARIFY, null, null)
        );
        String json = M.writeValueAsString(inp);
        CapabilityInput rt = M.readValue(json, CapabilityInput.class);
        assertEquals(inp.getResolution().mode(), rt.getResolution().mode());
        assertEquals(inp.getCatalogRef(), rt.getCatalogRef());
    }
}
```

- [ ] **Step 3: Run — expect FAIL (compile error)**

```bash
cd /Users/samirski/Development/ANIP/packages/java && mvn -pl anip-core test -Dtest=InputResolutionTest -q 2>&1 | tail -25
```

- [ ] **Step 4: Create `ResolutionMode.java`**

```java
package dev.anip.core;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;

public enum ResolutionMode {
    CLOSED_VALUES("closed_values"),
    BACKEND_RESOLVED("backend_resolved"),
    APP_SELECTED("app_selected"),
    ACTOR_POLICY("actor_policy"),
    ACTOR_POLICY_OR_EXPLICIT("actor_policy_or_explicit"),
    EXPLICIT_ONLY("explicit_only"),
    CLARIFY("clarify");

    private final String wire;
    ResolutionMode(String wire) { this.wire = wire; }

    @JsonValue
    public String wire() { return wire; }

    @JsonCreator
    public static ResolutionMode fromWire(String wire) {
        for (ResolutionMode m : values()) if (m.wire.equals(wire)) return m;
        throw new IllegalArgumentException("invalid resolution.mode: " + wire);
    }
}
```

- [ ] **Step 5: Create `ResolutionBehavior.java`**

```java
package dev.anip.core;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;

public enum ResolutionBehavior {
    CLARIFY("clarify"),
    USE_DEFAULT("use_default"),
    USE_ACTOR_SCOPE("use_actor_scope"),
    APP_SELECT_OR_CLARIFY("app_select_or_clarify"),
    DENY("deny"),
    DENY_OR_CLARIFY("deny_or_clarify"),
    OMIT("omit");

    private final String wire;
    ResolutionBehavior(String wire) { this.wire = wire; }

    @JsonValue
    public String wire() { return wire; }

    @JsonCreator
    public static ResolutionBehavior fromWire(String wire) {
        for (ResolutionBehavior b : values()) if (b.wire.equals(wire)) return b;
        throw new IllegalArgumentException("invalid resolution behavior: " + wire);
    }
}
```

- [ ] **Step 6: Create `InputResolution.java`**

```java
package dev.anip.core;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonProperty;

public record InputResolution(
        @JsonProperty("mode") ResolutionMode mode,
        @JsonProperty("resolver_ref") String resolverRef,
        @JsonProperty("on_missing") ResolutionBehavior onMissing,
        @JsonProperty("on_ambiguous") ResolutionBehavior onAmbiguous,
        @JsonProperty("on_unresolved") ResolutionBehavior onUnresolved
) {
    @JsonCreator
    public InputResolution {
        if (mode == null) {
            throw new IllegalArgumentException("resolution.mode is required");
        }
    }
}
```

- [ ] **Step 7: Create `InputMeaning.java`**

```java
package dev.anip.core;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonProperty;

public record InputMeaning(
        @JsonProperty("label") String label,
        @JsonProperty("value") String value,
        @JsonProperty("description") String description
) {
    @JsonCreator
    public InputMeaning {
        if (description == null) description = "";
    }
}
```

- [ ] **Step 8: Extend `CapabilityInput.java`**

After reading the existing file, replace its contents (preserve any extra `equals`/`hashCode`/`toString` methods the current file has — those are not shown here, copy them through and update them to include the new fields). Target shape:

```java
package dev.anip.core;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;

public class CapabilityInput {
    private final String name;
    private final String type;
    private final boolean required;
    private final Object defaultValue;
    private final String description;
    private final String semanticType;
    private final boolean entityReference;
    private final List<String> allowedValues;
    private final String catalogRef;
    private final List<InputMeaning> inputMeanings;
    private final InputResolution resolution;

    @JsonCreator
    public CapabilityInput(
            @JsonProperty("name") String name,
            @JsonProperty("type") String type,
            @JsonProperty("required") Boolean required,
            @JsonProperty("default") Object defaultValue,
            @JsonProperty("description") String description,
            @JsonProperty("semantic_type") String semanticType,
            @JsonProperty("entity_reference") Boolean entityReference,
            @JsonProperty("allowed_values") List<String> allowedValues,
            @JsonProperty("catalog_ref") String catalogRef,
            @JsonProperty("input_meanings") List<InputMeaning> inputMeanings,
            @JsonProperty("resolution") InputResolution resolution
    ) {
        this.name = name;
        this.type = type;
        this.required = required == null ? true : required;
        this.defaultValue = defaultValue;
        this.description = description == null ? "" : description;
        this.semanticType = semanticType;
        this.entityReference = entityReference != null && entityReference;
        this.allowedValues = allowedValues;
        this.catalogRef = catalogRef;
        this.inputMeanings = inputMeanings;
        this.resolution = resolution;
    }

    // Preserve existing convenience constructors used in source.
    public CapabilityInput(String name, String type, boolean required, Object defaultValue, String description) {
        this(name, type, required, defaultValue, description, null, false, null, null, null, null);
    }

    public CapabilityInput(String name, String type, boolean required, String description) {
        this(name, type, required, null, description, null, false, null, null, null, null);
    }

    @JsonProperty("name") public String getName() { return name; }
    @JsonProperty("type") public String getType() { return type; }
    @JsonProperty("required") public boolean isRequired() { return required; }
    // Keep getDefaultValue() — that is the existing Java-side API. Jackson maps
    // it to JSON "default" via @JsonProperty regardless of the method name.
    @JsonProperty("default") public Object getDefaultValue() { return defaultValue; }
    @JsonProperty("description") public String getDescription() { return description; }
    @JsonProperty("semantic_type") public String getSemanticType() { return semanticType; }
    @JsonProperty("entity_reference") public boolean isEntityReference() { return entityReference; }
    @JsonProperty("allowed_values") public List<String> getAllowedValues() { return allowedValues; }
    @JsonProperty("catalog_ref") public String getCatalogRef() { return catalogRef; }
    @JsonProperty("input_meanings") public List<InputMeaning> getInputMeanings() { return inputMeanings; }
    @JsonProperty("resolution") public InputResolution getResolution() { return resolution; }

    public static void validate(CapabilityInput inp) {
        if (inp.resolution == null) return;
        if (inp.resolution.mode() == ResolutionMode.CLOSED_VALUES
                && (inp.allowedValues == null || inp.allowedValues.isEmpty())) {
            throw new IllegalArgumentException("closed_values requires non-empty allowed_values");
        }
        if (inp.resolution.onMissing() == ResolutionBehavior.USE_DEFAULT && inp.defaultValue == null) {
            throw new IllegalArgumentException("on_missing=use_default requires a non-null default");
        }
    }
}
```

- [ ] **Step 9: Run test — expect PASS**

```bash
cd /Users/samirski/Development/ANIP/packages/java && mvn -pl anip-core test -Dtest=InputResolutionTest -q 2>&1 | tail -25
```

- [ ] **Step 10: Full anip-core suite**

```bash
cd /Users/samirski/Development/ANIP/packages/java && mvn -pl anip-core test -q 2>&1 | tail -20
```

- [ ] **Step 11: Build all java modules**

```bash
cd /Users/samirski/Development/ANIP/packages/java && mvn -DskipTests -q install 2>&1 | tail -10
```

- [ ] **Step 12: Commit**

```bash
git add packages/java/anip-core/
git commit -m "java(v0.24): add InputResolution, InputMeaning, enums; extend CapabilityInput"
```

---

## Phase 8 — C# Model

### Task 8: Add C# types; extend CapabilityInput

**Files:**
- Create: `packages/csharp/src/Anip.Core/InputResolution.cs`
- Create: `packages/csharp/src/Anip.Core/InputMeaning.cs`
- Create: `packages/csharp/src/Anip.Core/ResolutionMode.cs`
- Create: `packages/csharp/src/Anip.Core/ResolutionBehavior.cs`
- Modify: `packages/csharp/src/Anip.Core/CapabilityInput.cs`
- Test: `packages/csharp/src/Anip.Core.Tests/InputResolutionTests.cs` (NEW).

- [ ] **Step 1: Read current `CapabilityInput.cs`**

```bash
cat /Users/samirski/Development/ANIP/packages/csharp/src/Anip.Core/CapabilityInput.cs
```

- [ ] **Step 2: Write the failing test**

Create `packages/csharp/src/Anip.Core.Tests/InputResolutionTests.cs`:

```csharp
using System.Text.Json;
using Xunit;
using Anip.Core;

namespace Anip.Core.Tests;

public class InputResolutionTests
{
    private static readonly JsonSerializerOptions Opts = new() { PropertyNameCaseInsensitive = false };

    [Fact]
    public void V023ShapedInputParsesUnchanged()
    {
        var raw = @"{""name"":""q"",""type"":""string""}";
        var inp = JsonSerializer.Deserialize<CapabilityInput>(raw, Opts)!;
        Assert.Null(inp.Resolution);
        Assert.False(inp.EntityReference);
        Assert.Null(inp.CatalogRef);
    }

    [Fact]
    public void BackendResolvedParses()
    {
        var raw = @"{""name"":""cohort_ref"",""type"":""string"",""required"":true," +
                  @"""semantic_type"":""cohort_reference"",""entity_reference"":true,""catalog_ref"":""gtm.cohort_catalog""," +
                  @"""resolution"":{""mode"":""backend_resolved"",""resolver_ref"":""gtm.cohort_catalog"",""on_missing"":""clarify""}}";
        var inp = JsonSerializer.Deserialize<CapabilityInput>(raw, Opts)!;
        CapabilityInput.Validate(inp);
        Assert.Equal(ResolutionMode.BackendResolved, inp.Resolution!.Mode);
        Assert.Equal("gtm.cohort_catalog", inp.CatalogRef);
        Assert.True(inp.EntityReference);
    }

    [Fact]
    public void UnknownModeRejected()
    {
        var raw = @"{""name"":""x"",""type"":""string"",""resolution"":{""mode"":""not_real""}}";
        Assert.Throws<JsonException>(() => JsonSerializer.Deserialize<CapabilityInput>(raw, Opts));
    }

    [Fact]
    public void MissingModeRejectedAtValidate()
    {
        // {"resolution":{}} deserializes successfully with Mode==null;
        // Validate() must reject it.
        var raw = @"{""name"":""x"",""type"":""string"",""resolution"":{}}";
        var inp = JsonSerializer.Deserialize<CapabilityInput>(raw, Opts)!;
        Assert.Null(inp.Resolution!.Mode);
        Assert.Throws<ArgumentException>(() => CapabilityInput.Validate(inp));
    }

    [Fact]
    public void ClosedValuesWithoutAllowedValuesRejected()
    {
        var raw = @"{""name"":""x"",""type"":""string"",""resolution"":{""mode"":""closed_values""}}";
        var inp = JsonSerializer.Deserialize<CapabilityInput>(raw, Opts)!;
        Assert.Throws<ArgumentException>(() => CapabilityInput.Validate(inp));
    }

    [Fact]
    public void UseDefaultWithoutDefaultRejected()
    {
        var raw = @"{""name"":""x"",""type"":""string"",""resolution"":{""mode"":""clarify"",""on_missing"":""use_default""}}";
        var inp = JsonSerializer.Deserialize<CapabilityInput>(raw, Opts)!;
        Assert.Throws<ArgumentException>(() => CapabilityInput.Validate(inp));
    }

    [Fact]
    public void RoundTrip()
    {
        var inp = new CapabilityInput
        {
            Name = "cohort_ref",
            Type = "string",
            Required = true,
            SemanticType = "cohort_reference",
            EntityReference = true,
            CatalogRef = "gtm.cohort_catalog",
            Resolution = new InputResolution
            {
                Mode = ResolutionMode.BackendResolved,
                ResolverRef = "gtm.cohort_catalog",
                OnMissing = ResolutionBehavior.Clarify
            }
        };
        var json = JsonSerializer.Serialize(inp, Opts);
        var rt = JsonSerializer.Deserialize<CapabilityInput>(json, Opts)!;
        Assert.Equal(inp.Resolution.Mode, rt.Resolution!.Mode);
        Assert.Equal(inp.CatalogRef, rt.CatalogRef);
    }
}
```

- [ ] **Step 3: Run — expect FAIL**

```bash
cd /Users/samirski/Development/ANIP/packages/csharp && dotnet test src/Anip.Core.Tests --filter FullyQualifiedName~InputResolutionTests 2>&1 | tail -20
```

- [ ] **Step 4: Create `ResolutionMode.cs` (enum + JsonConverter)**

```csharp
using System.Text.Json;
using System.Text.Json.Serialization;

namespace Anip.Core;

[JsonConverter(typeof(ResolutionModeJsonConverter))]
public enum ResolutionMode
{
    ClosedValues,
    BackendResolved,
    AppSelected,
    ActorPolicy,
    ActorPolicyOrExplicit,
    ExplicitOnly,
    Clarify
}

public class ResolutionModeJsonConverter : JsonConverter<ResolutionMode>
{
    public override ResolutionMode Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options) =>
        reader.GetString() switch
        {
            "closed_values" => ResolutionMode.ClosedValues,
            "backend_resolved" => ResolutionMode.BackendResolved,
            "app_selected" => ResolutionMode.AppSelected,
            "actor_policy" => ResolutionMode.ActorPolicy,
            "actor_policy_or_explicit" => ResolutionMode.ActorPolicyOrExplicit,
            "explicit_only" => ResolutionMode.ExplicitOnly,
            "clarify" => ResolutionMode.Clarify,
            var s => throw new JsonException($"invalid resolution.mode: {s}")
        };

    public override void Write(Utf8JsonWriter writer, ResolutionMode value, JsonSerializerOptions options) =>
        writer.WriteStringValue(value switch
        {
            ResolutionMode.ClosedValues => "closed_values",
            ResolutionMode.BackendResolved => "backend_resolved",
            ResolutionMode.AppSelected => "app_selected",
            ResolutionMode.ActorPolicy => "actor_policy",
            ResolutionMode.ActorPolicyOrExplicit => "actor_policy_or_explicit",
            ResolutionMode.ExplicitOnly => "explicit_only",
            ResolutionMode.Clarify => "clarify",
            _ => throw new InvalidOperationException()
        });
}
```

- [ ] **Step 5: Create `ResolutionBehavior.cs`**

```csharp
using System.Text.Json;
using System.Text.Json.Serialization;

namespace Anip.Core;

[JsonConverter(typeof(ResolutionBehaviorJsonConverter))]
public enum ResolutionBehavior
{
    Clarify,
    UseDefault,
    UseActorScope,
    AppSelectOrClarify,
    Deny,
    DenyOrClarify,
    Omit
}

public class ResolutionBehaviorJsonConverter : JsonConverter<ResolutionBehavior>
{
    public override ResolutionBehavior Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options) =>
        reader.GetString() switch
        {
            "clarify" => ResolutionBehavior.Clarify,
            "use_default" => ResolutionBehavior.UseDefault,
            "use_actor_scope" => ResolutionBehavior.UseActorScope,
            "app_select_or_clarify" => ResolutionBehavior.AppSelectOrClarify,
            "deny" => ResolutionBehavior.Deny,
            "deny_or_clarify" => ResolutionBehavior.DenyOrClarify,
            "omit" => ResolutionBehavior.Omit,
            var s => throw new JsonException($"invalid resolution behavior: {s}")
        };

    public override void Write(Utf8JsonWriter writer, ResolutionBehavior value, JsonSerializerOptions options) =>
        writer.WriteStringValue(value switch
        {
            ResolutionBehavior.Clarify => "clarify",
            ResolutionBehavior.UseDefault => "use_default",
            ResolutionBehavior.UseActorScope => "use_actor_scope",
            ResolutionBehavior.AppSelectOrClarify => "app_select_or_clarify",
            ResolutionBehavior.Deny => "deny",
            ResolutionBehavior.DenyOrClarify => "deny_or_clarify",
            ResolutionBehavior.Omit => "omit",
            _ => throw new InvalidOperationException()
        });
}
```

- [ ] **Step 6: Create `InputResolution.cs` and `InputMeaning.cs`**

```csharp
// InputResolution.cs
using System.Text.Json.Serialization;

namespace Anip.Core;

public class InputResolution
{
    // Mode is required, but typed as nullable to distinguish "missing" from
    // "default enum value". Validate() rejects null mode at the cross-field check.
    [JsonPropertyName("mode")] public ResolutionMode? Mode { get; set; }
    [JsonPropertyName("resolver_ref")] public string? ResolverRef { get; set; }
    [JsonPropertyName("on_missing")] public ResolutionBehavior? OnMissing { get; set; }
    [JsonPropertyName("on_ambiguous")] public ResolutionBehavior? OnAmbiguous { get; set; }
    [JsonPropertyName("on_unresolved")] public ResolutionBehavior? OnUnresolved { get; set; }
}
```

```csharp
// InputMeaning.cs
using System.Text.Json.Serialization;

namespace Anip.Core;

public class InputMeaning
{
    [JsonPropertyName("label")] public string Label { get; set; } = "";
    [JsonPropertyName("value")] public string Value { get; set; } = "";
    [JsonPropertyName("description")] public string Description { get; set; } = "";
}
```

- [ ] **Step 7: Extend `CapabilityInput.cs`**

After reading current contents, add inside the class (under existing properties):

```csharp
[JsonPropertyName("semantic_type")] public string? SemanticType { get; set; }
[JsonPropertyName("entity_reference")] public bool EntityReference { get; set; }
[JsonPropertyName("allowed_values")] public List<string>? AllowedValues { get; set; }
[JsonPropertyName("catalog_ref")] public string? CatalogRef { get; set; }
[JsonPropertyName("input_meanings")] public List<InputMeaning>? InputMeanings { get; set; }
[JsonPropertyName("resolution")] public InputResolution? Resolution { get; set; }

public static void Validate(CapabilityInput inp)
{
    if (inp.Resolution == null) return;
    if (inp.Resolution.Mode == null)
    {
        throw new ArgumentException("resolution.mode is required");
    }
    if (inp.Resolution.Mode == ResolutionMode.ClosedValues
        && (inp.AllowedValues == null || inp.AllowedValues.Count == 0))
    {
        throw new ArgumentException("closed_values requires non-empty allowed_values");
    }
    if (inp.Resolution.OnMissing == ResolutionBehavior.UseDefault && inp.Default == null)
    {
        throw new ArgumentException("on_missing=use_default requires a non-null default");
    }
}
```

Add `using System.Collections.Generic;` and `using System;` if missing.

- [ ] **Step 8: Run — expect PASS**

```bash
cd /Users/samirski/Development/ANIP/packages/csharp && dotnet test src/Anip.Core.Tests --filter FullyQualifiedName~InputResolutionTests 2>&1 | tail -20
```

- [ ] **Step 9: Full solution build + tests**

```bash
cd /Users/samirski/Development/ANIP/packages/csharp && dotnet build 2>&1 | tail -10 && dotnet test 2>&1 | tail -15
```

- [ ] **Step 10: Commit**

```bash
git add packages/csharp/
git commit -m "csharp(v0.24): add InputResolution, InputMeaning, enums; extend CapabilityInput"
```

---

## Phase 9 — Reference Conformance (Python)

### Task 9: Shared fixture + Python reference test

This phase delivers a single canonical JSON fixture of valid/invalid input-resolution shapes plus a Python pytest harness that exercises it against the Python `CapabilityInput` model as the reference implementation. Each runtime's own test suite (Phases 4–8) already covers its native parsing.

If `conformance/conftest.py` exposes a subprocess harness for invoking the other four runtimes against shared fixtures, Step 5 below opts into it; otherwise the fixture stays Python-only for this plan, and a cross-runtime conformance harness is a separate follow-up.

**Files:**
- Create: `conformance/samples/v024_input_resolution_examples.json`.
- Create: `conformance/test_input_resolution.py`.

- [ ] **Step 1: Inspect conformance harness**

```bash
cat /Users/samirski/Development/ANIP/conformance/conftest.py 2>&1 | head -60
ls /Users/samirski/Development/ANIP/conformance/samples 2>&1 | head -10
```

- [ ] **Step 2: Create fixture**

Create `conformance/samples/v024_input_resolution_examples.json`:

```json
{
  "valid": [
    { "name": "minimal_v023_compat", "input": { "name": "quarter", "type": "string" } },
    {
      "name": "closed_values",
      "input": {
        "name": "forecast_mode", "type": "string", "required": false, "default": "risk_adjusted",
        "allowed_values": ["risk_adjusted", "likely", "best_case"],
        "semantic_type": "business_category",
        "resolution": { "mode": "closed_values", "on_missing": "use_default", "on_ambiguous": "clarify" }
      }
    },
    {
      "name": "backend_resolved",
      "input": {
        "name": "cohort_ref", "type": "string", "required": true,
        "semantic_type": "cohort_reference", "entity_reference": true, "catalog_ref": "gtm.cohort_catalog",
        "resolution": { "mode": "backend_resolved", "resolver_ref": "gtm.cohort_catalog", "on_missing": "clarify", "on_ambiguous": "clarify", "on_unresolved": "clarify" }
      }
    },
    {
      "name": "actor_policy_or_explicit",
      "input": {
        "name": "owner_scope", "type": "string", "required": false,
        "semantic_type": "scope_reference",
        "resolution": { "mode": "actor_policy_or_explicit", "resolver_ref": "gtm.scope_catalog", "on_missing": "use_actor_scope", "on_ambiguous": "clarify", "on_unresolved": "deny_or_clarify" }
      }
    },
    {
      "name": "app_selected",
      "input": {
        "name": "target_ref", "type": "string", "required": true,
        "semantic_type": "entity_reference", "entity_reference": true, "catalog_ref": "gtm.account_catalog",
        "resolution": { "mode": "app_selected", "resolver_ref": "gtm.account_catalog", "on_missing": "clarify", "on_ambiguous": "app_select_or_clarify" }
      }
    },
    {
      "name": "input_meanings_present",
      "input": {
        "name": "priority", "type": "string",
        "input_meanings": [
          { "label": "High", "value": "P0", "description": "critical" },
          { "label": "Medium", "value": "P1", "description": "" }
        ]
      }
    }
  ],
  "invalid": [
    { "name": "unknown_mode", "input": { "name": "x", "type": "string", "resolution": { "mode": "not_real" } } },
    { "name": "unknown_behavior", "input": { "name": "x", "type": "string", "resolution": { "mode": "clarify", "on_missing": "bogus" } } },
    { "name": "missing_mode", "input": { "name": "x", "type": "string", "resolution": {} } },
    { "name": "closed_values_without_allowed_values", "input": { "name": "x", "type": "string", "resolution": { "mode": "closed_values" } } },
    { "name": "use_default_without_default", "input": { "name": "x", "type": "string", "resolution": { "mode": "clarify", "on_missing": "use_default" } } }
  ]
}
```

Note: invalid cases do NOT pin a specific error string (per D1.7) — tests check that rejection happens, not what the error message says.

- [ ] **Step 3: Create Python conformance test**

Create `conformance/test_input_resolution.py`:

```python
"""v0.24 conformance — input resolution metadata parse + validate (Python reference)."""
import json
import pytest
from pathlib import Path
from anip_core.models import CapabilityInput
from pydantic import ValidationError

FIXTURE = Path(__file__).parent / "samples" / "v024_input_resolution_examples.json"
_DATA = json.loads(FIXTURE.read_text())


@pytest.mark.parametrize("case", _DATA["valid"], ids=lambda c: c["name"])
def test_valid_inputs_parse_and_round_trip(case):
    inp = CapabilityInput.model_validate(case["input"])
    raw = inp.model_dump_json()
    parsed = CapabilityInput.model_validate_json(raw)
    assert parsed == inp


@pytest.mark.parametrize("case", _DATA["invalid"], ids=lambda c: c["name"])
def test_invalid_inputs_rejected(case):
    with pytest.raises(ValidationError):
        CapabilityInput.model_validate(case["input"])
```

- [ ] **Step 4: Run — expect PASS**

```bash
cd /Users/samirski/Development/ANIP && pytest conformance/test_input_resolution.py -v 2>&1 | tail -20
```

- [ ] **Step 5: Cross-runtime parametrization — only if harness exists**

If `conformance/conftest.py` provides a way to invoke TS/Go/Java/C# parsers (look for subprocess fixtures), extend the test to parametrize the fixture cases across all 5 runtimes. If not, skip — runtime-level tests added in Phases 4–8 cover per-runtime parsing. Add a one-line comment in `test_input_resolution.py` stating which runtimes the fixture is exercised against ("Python only" if no harness; "all 5 runtimes" if extended).

- [ ] **Step 6: Commit**

```bash
git add conformance/
git commit -m "conformance(v0.24): reference fixture + python harness for input resolution"
```

---

## Phase 10 — Docs & Version Bumps

### Task 10: Update README, version-history, what-ships-today; bump package versions

**Files:** as listed in File Structure.

- [ ] **Step 1: Update README.md status**
Bump status header and any version examples to v0.24 / 0.24.0. Mention input resolution metadata in the protocol description.

- [ ] **Step 2: Update schema/README.md**
Bump "v0.23 types" → "v0.24 types"; list `InputResolution`, `InputMeaning`.

- [ ] **Step 3: Add v0.24 row to version-history.md**

```markdown
| **v0.24** | Input resolution metadata | Capability inputs declare a `resolution` block (`mode` + `resolver_ref` + `on_missing`/`on_ambiguous`/`on_unresolved`) so runtimes, generators, and agents have a portable contract for whether an input is closed-enum, backend-resolved, app-selected, actor-policy-derived, explicit-only, or clarify-on-miss. Adjacent typed hints (`semantic_type`, `entity_reference`, `allowed_values`, `catalog_ref`, `input_meanings`) give the resolution block its substrate. Pure additive — v0.23 manifests parse unchanged. |
```

Update §intro: "current version is **v0.24**".

- [ ] **Step 4: Update what-ships-today.md**
Add a v0.24 section matching the style of the existing v0.23 section.

- [ ] **Step 5: Bump version-string examples**

```bash
grep -rln "0\\.23\\.0" /Users/samirski/Development/ANIP/website/docs/ 2>&1 | head -20
```
Update where it describes the current package version.

- [ ] **Step 6: Bump package.json/pyproject.toml/pom.xml/csproj versions to `0.24.0`**

Files (per commit bd358c35 v0.23.0 bump) — non-exhaustive; the grep below is the source of truth:
- Each `packages/python/anip-*/pyproject.toml`
- Each `packages/typescript/*/package.json` (including any Vue/Angular sample packages)
- `packages/java/pom.xml` and child poms (`<version>` and `<anip.version>`)
- C#: `Directory.Build.props` or each `.csproj` `<Version>`
- `studio/package.json` if it carries a versioned dependency on an ANIP package
- Any sample manifests in `examples/` that pin the package version

Run:
```bash
grep -rn "0\\.23\\.0" packages/ studio/ examples/ 2>&1 | head -40
```
Walk each match. Update package-version pins to `0.24.0`. Leave historical references (changelog entries, archive paths, prior-version sample manifests intentionally pinned to 0.23.0) untouched. Re-run the grep after edits to confirm only intentional historical refs remain.

- [ ] **Step 7: Smoke-test all suites**

```bash
cd /Users/samirski/Development/ANIP && pytest conformance/ -x -q 2>&1 | tail -10
cd /Users/samirski/Development/ANIP/packages/python && pytest -x -q 2>&1 | tail -10
cd /Users/samirski/Development/ANIP/packages/typescript/core && npm test 2>&1 | tail -10
cd /Users/samirski/Development/ANIP/packages/go && go test ./... 2>&1 | tail -10
cd /Users/samirski/Development/ANIP/packages/java && mvn -DskipTests -q install 2>&1 | tail -5 && mvn -pl anip-core test -q 2>&1 | tail -10
cd /Users/samirski/Development/ANIP/packages/csharp && dotnet test 2>&1 | tail -10
```

- [ ] **Step 8: Commit**

```bash
git add README.md schema/README.md website/ packages/
git commit -m "docs(v0.24): version-history, what-ships-today, bump package versions to 0.24.0"
```

---

## Phase 11 — Open PR

### Task 11: Push branch and open PR

- [ ] **Step 1: Push**

```bash
git push -u origin feat/anip-v024-input-resolution
```

- [ ] **Step 2: Open PR against `main`**

```bash
gh pr create --base main --title "feat: ANIP v0.24 — input resolution metadata (contract)" --body "$(cat <<'EOF'
## Summary
- Adds `resolution` block (`mode` + `resolver_ref` + `on_missing`/`on_ambiguous`/`on_unresolved`) on `CapabilityInput`.
- Adds adjacent typed hint fields: `semantic_type`, `entity_reference`, `allowed_values`, `catalog_ref`, `input_meanings`.
- Bumps PROTOCOL_VERSION → `anip/0.24` across all 5 runtimes.
- Pure additive: v0.23 manifests parse unchanged.

## Out of scope (separate plans)
- Studio UI editing for resolution fields.
- Generator pass-through into emitted service definitions / agent-consumption artifacts.
- Runtime consumption (any agent runtime that honors `resolution.mode`).
- Registry display + package signature tests.
- Verifier behavior conformance.

## Test plan
- [ ] Python `pytest packages/python/anip-core/tests/test_input_resolution.py` passes
- [ ] TS `npx vitest run packages/typescript/core/tests/input-resolution.test.ts` passes
- [ ] Go `go test ./...` passes including `input_resolution_test.go`
- [ ] Java `mvn -pl anip-core test` passes including `InputResolutionTest`
- [ ] C# `dotnet test` passes including `InputResolutionTests`
- [ ] Conformance `pytest conformance/test_input_resolution.py` passes
- [ ] Package versions bumped to `0.24.0` across pyproject.toml / package.json / pom.xml / csproj

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-Review

**1. Spec coverage** against the design's 15-item Concrete Implementation Checklist:

| Design Item | Plan Coverage |
|---|---|
| 1. Spec section for input resolution | Phase 1 |
| 2. Bump spec version to 0.24 | Phase 1 + Phase 3 |
| 3. Schema fields for input resolution | Phase 2 |
| 4. Generator model fields (Go) | Phase 6 (Go core model only — generator pass-through deferred) |
| 5. Studio TypeScript model fields | Phase 5 (TS core model only — Studio UI deferred) |
| 6. Preserve fields through Studio serialization | Out of scope (separate plan) |
| 7. Studio UI editing/review support | Out of scope (separate plan) |
| 8. Assistant/operator prompt instructions | Out of scope (separate plan) |
| 9. Include metadata in generated service definition | Out of scope (separate plan) |
| 10. Include metadata in agent-consumption kit | Out of scope (separate plan) |
| 11. Runtime normalization honors resolution | Out of scope (separate plan) |
| 12. Regression tests for scope leakage | Out of scope (separate plan, downstream runtime) |
| 13. Generator tests proving metadata round-trips | Phase 9 covers core round-trip; generator-side tests are out of scope |
| 14. Registry display | Out of scope (separate plan) |
| 15. Package/signature tests for signed metadata | Out of scope (separate plan) |

This plan delivers the **portable contract** end-to-end across 5 runtimes. Downstream consumers (Studio, generators, runtimes, registry, verifier) can then build on a single source of truth landed on `main`.

**2. Placeholder scan.** No TBDs. Every step has actual code or an exact command + expected output.

**3. Type consistency.**
- `ResolutionMode` / `ResolutionBehavior` / `InputResolution` / `InputMeaning` consistent across all phases.
- Wire enum values identical across 5 runtimes (snake_case).
- `catalog_ref` used everywhere (not `reference_catalog`).
- No specific parse-error strings asserted in tests (per D1.7).

**4. YAGNI check.** Each new field has a concrete use in the contract:
- `resolution` — the primary feature.
- `semantic_type` — identifies domain category for downstream consumers.
- `entity_reference` — distinguishes literal vs reference inputs.
- `allowed_values` — required by `closed_values` mode (D1.7 enforces).
- `catalog_ref` — declarative pointer for service implementers.
- `input_meanings` — labeled reviewed alternatives.

No speculative additions.

---

## Execution Handoff

Plan complete and saved to `docs/plans/2026-05-11-v024-input-resolution-plan.md`. Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks.
2. **Inline Execution** — batch in this session with checkpoints.

Which approach?
