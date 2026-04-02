# ANIP v0.19: Cross-Service Handoff Hints — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add advisory cross-service relationship hints to capability declarations — `ServiceCapabilityRef` type and a `cross_service` block with `handoff_to`, `refresh_via`, `verify_via`, `followup_via` arrays.

**Architecture:** One new type (`ServiceCapabilityRef`: `{service, capability}`) and one new optional block (`cross_service`) on `CapabilityDeclaration` with four optional arrays. All advisory, no enforcement. `service` identifier SHOULD match `upstream_service` from v0.18. Manifest-level only — no invoke-time or audit changes.

**Tech Stack:** Python, TypeScript, Go, Java, C# runtimes + JSON Schema + SPEC.md + Vue (Studio)

**Spec:** `docs/proposals/v0.19-phase4-slice2-cross-service-handoff-spec-draft.md`

---

## File Structure

```
# Spec and Schema
SPEC.md                                                        # MODIFY: §4.1 add ServiceCapabilityRef + cross_service block
schema/anip.schema.json                                        # MODIFY: add ServiceCapabilityRef def + cross_service object on CapabilityDeclaration

# Python
packages/python/anip-core/src/anip_core/models.py              # MODIFY: add ServiceCapabilityRef model + CrossServiceHints model + cross_service field on CapabilityDeclaration

# TypeScript
packages/typescript/core/src/models.ts                          # MODIFY: add ServiceCapabilityRef + CrossServiceHints Zod schemas + cross_service on CapabilityDeclaration

# Go
packages/go/core/models.go                                     # MODIFY: add ServiceCapabilityRef + CrossServiceHints structs + CrossService field on CapabilityDeclaration

# Java
packages/java/anip-core/src/main/java/dev/anip/core/ServiceCapabilityRef.java  # CREATE
packages/java/anip-core/src/main/java/dev/anip/core/CrossServiceHints.java      # CREATE
packages/java/anip-core/src/main/java/dev/anip/core/CapabilityDeclaration.java  # MODIFY: add crossService field

# C#
packages/csharp/src/Anip.Core/ServiceCapabilityRef.cs          # CREATE
packages/csharp/src/Anip.Core/CrossServiceHints.cs              # CREATE
packages/csharp/src/Anip.Core/CapabilityDeclaration.cs          # MODIFY: add CrossService property

# Showcase
examples/showcase/travel/capabilities.py                        # MODIFY: add cross_service hints to search_flights + book_flight

# Studio
studio/src/components/CapabilityCard.vue                        # MODIFY: display cross_service hints

# Conformance
conformance/test_cross_service_hints.py                         # CREATE: validate cross_service schema shape in manifest

# Website
website/docs/protocol/capabilities.md                           # MODIFY: add cross-service handoff hints section
website/docs/protocol/reference.md                              # MODIFY: add cross_service to CapabilityDeclaration field table
website/docs/protocol/lineage.md                                # MODIFY: reference cross_service hints from cross-service continuity section
website/docs/feature-map.md                                     # MODIFY: add v0.19 entries
website/docs/releases/version-history.md                        # MODIFY: add v0.19 entry
website/docs/releases/what-ships-today.md                       # MODIFY: add v0.19 entry
```

---

## Task 1: Spec and Schema

**Files:**
- Modify: `SPEC.md`
- Modify: `schema/anip.schema.json`

- [ ] **Step 1: Update SPEC.md §4.1**

Add after the Advisory Composition Hints (v0.17) section:

1. `ServiceCapabilityRef` type definition: `{service: string, capability: string}` with identity alignment note (SHOULD match `upstream_service`)
2. `cross_service` block on CapabilityDeclaration with field table (4 optional arrays)
3. Advisory nature + normative guidance for each field (`handoff_to`, `refresh_via`, `verify_via`, `followup_via`)
4. Examples (travel handoff, cross-service refresh, deployment verification, order follow-up)
5. Note that same-manifest `refresh_via`/`verify_via` from v0.17 are unchanged

- [ ] **Step 2: Update JSON Schema**

Add `ServiceCapabilityRef` to `$defs`:
```json
"ServiceCapabilityRef": {
  "type": "object",
  "properties": {
    "service": {"type": "string"},
    "capability": {"type": "string"}
  },
  "required": ["service", "capability"]
}
```

Add `cross_service` to CapabilityDeclaration:
```json
"cross_service": {
  "type": "object",
  "properties": {
    "handoff_to": {"type": "array", "items": {"$ref": "#/$defs/ServiceCapabilityRef"}, "default": []},
    "refresh_via": {"type": "array", "items": {"$ref": "#/$defs/ServiceCapabilityRef"}, "default": []},
    "verify_via": {"type": "array", "items": {"$ref": "#/$defs/ServiceCapabilityRef"}, "default": []},
    "followup_via": {"type": "array", "items": {"$ref": "#/$defs/ServiceCapabilityRef"}, "default": []}
  },
  "default": null
}
```

- [ ] **Step 3: Commit**

```bash
git add SPEC.md schema/anip.schema.json
git commit -m "spec: add ServiceCapabilityRef and cross_service handoff hints (v0.19)"
```

---

## Task 2: All 5 Runtimes

**Files:** See file structure above.

- [ ] **Step 1: Python**

In `models.py`, add:
```python
class ServiceCapabilityRef(BaseModel):
    service: str
    capability: str

class CrossServiceHints(BaseModel):
    handoff_to: list[ServiceCapabilityRef] = Field(default_factory=list)
    refresh_via: list[ServiceCapabilityRef] = Field(default_factory=list)
    verify_via: list[ServiceCapabilityRef] = Field(default_factory=list)
    followup_via: list[ServiceCapabilityRef] = Field(default_factory=list)
```

Add to CapabilityDeclaration: `cross_service: CrossServiceHints | None = None`

Export from `__init__.py`.

- [ ] **Step 2: TypeScript**

In `models.ts`, add Zod schemas:
```typescript
export const ServiceCapabilityRef = z.object({
  service: z.string(),
  capability: z.string(),
});

export const CrossServiceHints = z.object({
  handoff_to: z.array(ServiceCapabilityRef).default([]),
  refresh_via: z.array(ServiceCapabilityRef).default([]),
  verify_via: z.array(ServiceCapabilityRef).default([]),
  followup_via: z.array(ServiceCapabilityRef).default([]),
});
```

Add to CapabilityDeclaration: `cross_service: CrossServiceHints.nullable().default(null)`

- [ ] **Step 3: Go**

In `models.go`, add:
```go
type ServiceCapabilityRef struct {
    Service    string `json:"service"`
    Capability string `json:"capability"`
}

type CrossServiceHints struct {
    HandoffTo  []ServiceCapabilityRef `json:"handoff_to,omitempty"`
    RefreshVia []ServiceCapabilityRef `json:"refresh_via,omitempty"`
    VerifyVia  []ServiceCapabilityRef `json:"verify_via,omitempty"`
    FollowupVia []ServiceCapabilityRef `json:"followup_via,omitempty"`
}
```

Add to CapabilityDeclaration: `CrossService *CrossServiceHints \`json:"cross_service,omitempty"\``

- [ ] **Step 4: Java**

Create `ServiceCapabilityRef.java` and `CrossServiceHints.java`. Add `CrossServiceHints crossService` to CapabilityDeclaration with getter. Update constructors.

- [ ] **Step 5: C#**

Create `ServiceCapabilityRef.cs` and `CrossServiceHints.cs`. Add `CrossServiceHints? CrossService` property to CapabilityDeclaration.

- [ ] **Step 6: Run tests**

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
git commit -m "feat: add ServiceCapabilityRef and cross_service to CapabilityDeclaration across all runtimes (v0.19)"
```

---

## Task 3: Showcase Apps

**Files:**
- Modify: `examples/showcase/travel/capabilities.py`

- [ ] **Step 1: Add cross_service hints to travel capabilities**

Read the file. Add to `search_flights`:
```python
cross_service=CrossServiceHints(
    handoff_to=[ServiceCapabilityRef(service="travel-booking", capability="book_flight")],
)
```

Add to `book_flight`:
```python
cross_service=CrossServiceHints(
    refresh_via=[ServiceCapabilityRef(service="travel-search", capability="search_flights")],
)
```

Note: the travel showcase is a single service, so these are illustrative — showing what the hints would look like if search and booking were separate services.

- [ ] **Step 2: Commit**

```bash
git add examples/
git commit -m "feat(showcase): add cross_service handoff hints to travel example (v0.19)"
```

---

## Task 4: Conformance Suite

**Files:**
- Create: `conformance/test_cross_service_hints.py`

- [ ] **Step 1: Write conformance tests**

- `test_cross_service_block_in_manifest` — fetch `/anip/manifest`, if any capability has `cross_service`, verify it's an object with the expected keys
- `test_service_capability_ref_shape` — every entry in `handoff_to`/`refresh_via`/`verify_via`/`followup_via` must have `service` (string) and `capability` (string)
- `test_cross_service_optional` — capabilities without `cross_service` are valid (field is optional)

Skip gracefully if no capabilities declare `cross_service`.

- [ ] **Step 2: Commit**

```bash
git add conformance/
git commit -m "test: add cross-service handoff hints conformance tests (v0.19)"
```

---

## Task 5: Studio UI

**Files:**
- Modify: `studio/src/components/CapabilityCard.vue`

- [ ] **Step 1: Display cross_service hints**

When a capability has `cross_service`, display each non-empty array as a section with `service:capability` badges. Use distinct colors per relationship type (e.g., handoff=blue, refresh=green, verify=amber, followup=purple).

- [ ] **Step 2: Build and sync**

```bash
cd /Users/samirski/Development/ANIP/studio && npm run build && cd .. && bash studio/sync.sh
```

- [ ] **Step 3: Commit**

```bash
git add studio/ packages/*/studio/
git commit -m "feat(studio): display cross_service handoff hints in capability cards (v0.19)"
```

---

## Task 6: Website Documentation

**Files:**
- Modify: `website/docs/protocol/capabilities.md`
- Modify: `website/docs/protocol/reference.md`
- Modify: `website/docs/protocol/lineage.md`
- Modify: `website/docs/feature-map.md`
- Modify: `website/docs/releases/version-history.md`
- Modify: `website/docs/releases/what-ships-today.md`

- [ ] **Step 1: Update capabilities page**

Add "Cross-service handoff hints (v0.19)" section with:
- `ServiceCapabilityRef` type description + identity alignment note
- `cross_service` block with 4 field descriptions
- Advisory nature + normative guidance
- Examples
- Relationship to v0.17 same-manifest hints

- [ ] **Step 2: Update reference page**

Add `cross_service` to CapabilityDeclaration field table. Add `ServiceCapabilityRef` type description.

- [ ] **Step 3: Update lineage page**

Add brief reference from the v0.18 cross-service continuity section to the v0.19 handoff hints.

- [ ] **Step 4: Update feature map + version history + what-ships-today**

- [ ] **Step 5: Commit**

```bash
git add website/
git commit -m "docs(website): add cross-service handoff hints documentation (v0.19)"
```

---

## Task 7: Version Bump

- [ ] **Step 1: Bump to anip/0.19**

Update all 5 runtime constants + constant-verification tests + model defaults + SPEC.md title + schema `$id` + website version references (`0.18.0` → `0.19.0`).

- [ ] **Step 2: Commit**

```bash
git add SPEC.md schema/ packages/ website/
git commit -m "chore: bump protocol version to anip/0.19"
```
