# ANIP v0.17: Advisory Composition Hints — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two optional advisory fields (`refresh_via`, `verify_via`) to CapabilityDeclaration — simple capability-name arrays that tell agents where to refresh stale state and how to verify side effects.

**Architecture:** Two optional `string[]` fields on CapabilityDeclaration, same-manifest only. No enforcement, no ordering, no new failure types. Fields appear in the manifest and are displayed in Studio. Conformance validates that referenced capabilities exist in the same manifest.

**Tech Stack:** Python, TypeScript, Go, Java, C# runtimes + JSON Schema + SPEC.md + Vue (Studio)

**Spec:** `docs/proposals/v0.17-phase3-slice2-advisory-composition-spec-draft.md`

---

## File Structure

```
# Spec and Schema
SPEC.md                                                        # MODIFY: §4.1 add refresh_via + verify_via to CapabilityDeclaration
schema/anip.schema.json                                        # MODIFY: add 2 optional string array fields to CapabilityDeclaration

# Python
packages/python/anip-core/src/anip_core/models.py              # MODIFY: add refresh_via + verify_via to CapabilityDeclaration

# TypeScript
packages/typescript/core/src/models.ts                          # MODIFY: add to Zod schema

# Go
packages/go/core/models.go                                     # MODIFY: add to CapabilityDeclaration struct

# Java
packages/java/anip-core/src/main/java/dev/anip/core/CapabilityDeclaration.java  # MODIFY: add fields

# C#
packages/csharp/src/Anip.Core/CapabilityDeclaration.cs          # MODIFY: add fields

# Showcase
examples/showcase/travel/capabilities.py                        # MODIFY: add refresh_via to book_flight
examples/showcase/devops/capabilities.py                        # MODIFY: add verify_via to scale_replicas, deploy-like capabilities

# Studio
studio/src/components/CapabilityCard.vue                        # MODIFY: display refresh_via + verify_via

# Conformance
conformance/test_composition_hints.py                           # CREATE: validate referenced capabilities exist in manifest

# Website
website/docs/protocol/capabilities.md                           # MODIFY: add refresh_via + verify_via docs
website/docs/feature-map.md                                     # MODIFY: add v0.17 entries
website/docs/releases/version-history.md                        # MODIFY: add v0.17 entry
```

---

## Task 1: Spec and Schema

**Files:**
- Modify: `SPEC.md`
- Modify: `schema/anip.schema.json`

- [ ] **Step 1: Update SPEC.md §4.1 (Capability Declaration)**

Add `refresh_via` and `verify_via` to the capability declaration fields table. Add descriptions, examples, and the advisory nature note. Add same-manifest scope rule. Add examples showing travel (refresh_via) and devops (verify_via) usage.

- [ ] **Step 2: Update JSON Schema**

Add two optional fields to the CapabilityDeclaration schema:
```json
"refresh_via": {
  "type": "array",
  "items": {"type": "string"},
  "default": [],
  "description": "Capability names (same manifest) that can refresh prerequisites or stale state"
},
"verify_via": {
  "type": "array",
  "items": {"type": "string"},
  "default": [],
  "description": "Capability names (same manifest) that can verify this capability's side effects"
}
```

- [ ] **Step 3: Commit**

```bash
git add SPEC.md schema/anip.schema.json
git commit -m "spec: add refresh_via and verify_via advisory composition hints (v0.17)"
```

---

## Task 2: All 5 Runtimes

**Files:**
- Modify: `packages/python/anip-core/src/anip_core/models.py`
- Modify: `packages/typescript/core/src/models.ts`
- Modify: `packages/go/core/models.go`
- Modify: `packages/java/anip-core/src/main/java/dev/anip/core/CapabilityDeclaration.java`
- Modify: `packages/csharp/src/Anip.Core/CapabilityDeclaration.cs`

- [ ] **Step 1: Python**

Add to CapabilityDeclaration in `models.py`:
```python
refresh_via: list[str] = Field(default_factory=list)
verify_via: list[str] = Field(default_factory=list)
```

- [ ] **Step 2: TypeScript**

Add to CapabilityDeclaration Zod schema in `models.ts`:
```typescript
refresh_via: z.array(z.string()).default([]),
verify_via: z.array(z.string()).default([]),
```

- [ ] **Step 3: Go**

Add to CapabilityDeclaration struct in `models.go`:
```go
RefreshVia []string `json:"refresh_via,omitempty"`
VerifyVia  []string `json:"verify_via,omitempty"`
```

- [ ] **Step 4: Java**

Add to CapabilityDeclaration in `CapabilityDeclaration.java`:
```java
private List<String> refreshVia;
private List<String> verifyVia;
```
With getters. Update constructors to default to empty lists if not provided.

- [ ] **Step 5: C#**

Add to CapabilityDeclaration in `CapabilityDeclaration.cs`:
```csharp
public List<string>? RefreshVia { get; set; }
public List<string>? VerifyVia { get; set; }
```

- [ ] **Step 6: Run tests across all runtimes**

```bash
cd /Users/samirski/Development/ANIP && python3 -m pytest packages/python/anip-core/tests/ -x -q 2>&1 | tail -5
cd /Users/samirski/Development/ANIP/packages/typescript && npx vitest run core/tests/ 2>&1 | tail -5
cd /Users/samirski/Development/ANIP/packages/go && go test ./core/ 2>&1 | tail -5
cd /Users/samirski/Development/ANIP/packages/java && mvn test -pl anip-core -q 2>&1 | tail -5
cd /Users/samirski/Development/ANIP/packages/csharp && dotnet test test/Anip.Core.Tests/ --verbosity minimal 2>&1 | tail -5
```

- [ ] **Step 7: Commit**

```bash
git add packages/
git commit -m "feat: add refresh_via and verify_via to CapabilityDeclaration across all runtimes (v0.17)"
```

---

## Task 3: Showcase Apps

**Files:**
- Modify: `examples/showcase/travel/capabilities.py`
- Modify: `examples/showcase/devops/capabilities.py`

- [ ] **Step 1: Add refresh_via to travel book_flight**

Read `capabilities.py`. Add `refresh_via=["search_flights"]` to the `book_flight` capability declaration.

- [ ] **Step 2: Add verify_via to devops capabilities**

Read devops `capabilities.py`. Add `verify_via` to capabilities with irreversible side effects (e.g., `scale_replicas` → `verify_via=["get_service_status"]` or similar read capability in the same manifest). Check what read capabilities exist and use appropriate names.

- [ ] **Step 3: Commit**

```bash
git add examples/showcase/
git commit -m "feat(showcase): add refresh_via and verify_via hints to travel + devops examples (v0.17)"
```

---

## Task 4: Conformance Suite

**Files:**
- Create: `conformance/test_composition_hints.py`

- [ ] **Step 1: Write conformance tests**

- `test_composition_hints_roundtrip_through_manifest` — fetch `/anip/manifest`, find a capability that declares `refresh_via` or `verify_via`, verify the fields are present in the HTTP response (not just in the model — proves the manifest serialization layer exposes them)
- `test_refresh_via_references_exist_in_manifest` — if a capability declares `refresh_via`, every referenced capability MUST exist in the same manifest
- `test_verify_via_references_exist_in_manifest` — same for `verify_via`
- `test_refresh_via_is_string_array` — `refresh_via` values are strings (capability names)
- `test_verify_via_is_string_array` — same for `verify_via`

Tests should skip gracefully if no capabilities declare these fields.

- [ ] **Step 2: Commit**

```bash
git add conformance/
git commit -m "test: add composition hints conformance tests (v0.17)"
```

---

## Task 5: Studio UI

**Files:**
- Modify: `studio/src/components/CapabilityCard.vue`

- [ ] **Step 1: Display refresh_via and verify_via in capability cards**

Read CapabilityCard.vue. Add sections for `refresh_via` and `verify_via` when present (non-empty arrays). Display as simple lists of capability name links/badges, similar to how `requires` is displayed.

- [ ] **Step 2: Build and sync**

```bash
cd /Users/samirski/Development/ANIP/studio && npm run build && cd .. && bash studio/sync.sh
```

- [ ] **Step 3: Commit**

```bash
git add studio/ packages/*/studio/
git commit -m "feat(studio): display refresh_via and verify_via in capability cards (v0.17)"
```

---

## Task 6: Website Documentation

**Files:**
- Modify: `website/docs/protocol/capabilities.md`
- Modify: `website/docs/protocol/reference.md`
- Modify: `website/docs/feature-map.md`
- Modify: `website/docs/releases/version-history.md`

- [ ] **Step 1: Update capabilities page**

Add section on advisory composition hints with:
- `refresh_via` and `verify_via` field descriptions
- Same-manifest scope rule
- Advisory nature note
- Examples (travel refresh, devops verify)

- [ ] **Step 2: Update reference page**

Add `refresh_via` and `verify_via` to the CapabilityDeclaration field table in `website/docs/protocol/reference.md`.

- [ ] **Step 3: Update feature map + version history**

Add v0.17 entries.

- [ ] **Step 4: Commit**

```bash
git add website/
git commit -m "docs(website): add refresh_via and verify_via documentation (v0.17)"
```

---

## Task 7: Version Bump

- [ ] **Step 1: Bump to anip/0.17**

Update all 5 runtime constants + constant-verification tests + model defaults + SPEC.md title + schema `$id` + website version references (`0.16.0` → `0.17.0`). Add v0.17 entry to version history.

- [ ] **Step 2: Commit**

```bash
git add SPEC.md schema/ packages/ website/
git commit -m "chore: bump protocol version to anip/0.17"
```
