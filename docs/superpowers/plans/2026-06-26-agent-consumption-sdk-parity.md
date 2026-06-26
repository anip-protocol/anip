# Agent Consumption SDK Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add contract-derived agent-consumption runtime-utils helper parity across TypeScript, Go, Java, and C# using shared golden fixtures.

**Architecture:** Python `anip-runtime-utils` remains the temporary behavioral reference, but shared JSON fixtures become the parity contract. Each non-Python SDK gets a small language-native helper surface that implements the same deterministic behavior without GTM-specific terms or LLM calls.

**Tech Stack:** Python pytest, TypeScript Vitest, Go testing, Java JUnit/Maven, C# xUnit/dotnet test, shared JSON fixtures.

---

## File Structure

- Create `packages/agent-consumption-fixtures/capability-selection.json`: shared neutral fixture cases.
- Modify `packages/python/anip-runtime-utils/tests/test_agent_consumption.py`: add fixture-driven parity test.
- Create `packages/typescript/runtime-utils/package.json`, `tsconfig.json`, `src/index.ts`, `tests/agent-consumption.test.ts`.
- Modify `packages/typescript/package.json`: add `runtime-utils` workspace.
- Create `packages/go/runtimeutils/agent_consumption.go`, `agent_consumption_test.go`.
- Create `packages/java/anip-runtime-utils/pom.xml`, `src/main/java/dev/anip/runtimeutils/AgentConsumption.java`, `src/test/java/dev/anip/runtimeutils/AgentConsumptionTest.java`.
- Modify `packages/java/pom.xml`: add `anip-runtime-utils` module.
- Create `packages/csharp/src/Anip.RuntimeUtils/Anip.RuntimeUtils.csproj`, `AgentConsumption.cs`.
- Create `packages/csharp/test/Anip.RuntimeUtils.Tests/Anip.RuntimeUtils.Tests.csproj`, `AgentConsumptionTests.cs`.
- Modify `packages/csharp/Anip.sln`: add runtime-utils project and tests using `dotnet sln add`.
- Create `packages/typescript/runtime-utils/README.md`, `packages/go/runtimeutils/README.md`, `packages/java/anip-runtime-utils/README.md`, and `packages/csharp/src/Anip.RuntimeUtils/README.md`.

---

### Task 1: Add Shared Golden Fixtures and Python Parity Test

**Files:**
- Create: `packages/agent-consumption-fixtures/capability-selection.json`
- Modify: `packages/python/anip-runtime-utils/tests/test_agent_consumption.py`

- [ ] **Step 1: Write the shared fixture**

Create `packages/agent-consumption-fixtures/capability-selection.json`:

```json
{
  "schema_version": "anip-agent-consumption-fixtures/v1",
  "cases": [
    {
      "id": "stronger_same_effect_clarifies_missing_target",
      "conversation": "Draft a notification for the selected customer cohort.",
      "selected_capability": "records.single_notification_draft",
      "expected_capability": "records.cohort_notification_draft",
      "expected_missing_inputs": ["cohort_ref"],
      "expected_unsupported_effects": [],
      "metadata": {
        "records.single_notification_draft": {
          "capability_id": "records.single_notification_draft",
          "description": "Draft a notification for one explicit record.",
          "business_effects": {
            "produces": ["content.draft"],
            "does_not_produce": ["external_dispatch", "system.mutation"]
          },
          "input_specs": [
            {
              "name": "record_ref",
              "type": "string",
              "required": true,
              "semantic_type": "record_reference",
              "resolution": {"mode": "explicit_only", "on_missing": "clarify"}
            }
          ],
          "app_profile": {
            "capability_framing": "Draft content for a single explicitly selected record.",
            "input_meanings": {},
            "app_boundaries": {"unsupported_effects": ["external_dispatch", "system.mutation"]}
          }
        },
        "records.cohort_notification_draft": {
          "capability_id": "records.cohort_notification_draft",
          "description": "Draft a notification after selecting from a bounded cohort.",
          "business_effects": {
            "produces": ["content.draft"],
            "does_not_produce": ["external_dispatch", "system.mutation"]
          },
          "input_specs": [
            {
              "name": "cohort_ref",
              "type": "string",
              "required": true,
              "allowed_values": ["renewal_risk", "expansion_ready"],
              "semantic_type": "cohort_reference",
              "resolution": {"mode": "closed_values", "on_missing": "clarify", "on_ambiguous": "clarify"}
            }
          ],
          "app_profile": {
            "capability_framing": "Select from a bounded cohort and draft notification content.",
            "input_meanings": {
              "cohort_ref": {
                "renewal_risk": "renewal risk customer cohort",
                "expansion_ready": "expansion ready customer cohort"
              }
            },
            "app_boundaries": {"unsupported_effects": ["external_dispatch", "system.mutation"]}
          }
        }
      }
    },
    {
      "id": "unsupported_external_dispatch_detected",
      "conversation": "Draft the notification and send it immediately.",
      "selected_capability": "records.single_notification_draft",
      "expected_capability": "records.single_notification_draft",
      "expected_missing_inputs": ["record_ref"],
      "expected_unsupported_effects": ["external_dispatch"],
      "metadata": {
        "records.single_notification_draft": {
          "capability_id": "records.single_notification_draft",
          "description": "Draft a notification for one explicit record.",
          "business_effects": {
            "produces": ["content.draft"],
            "does_not_produce": ["external_dispatch", "system.mutation"]
          },
          "input_specs": [
            {
              "name": "record_ref",
              "type": "string",
              "required": true,
              "semantic_type": "record_reference",
              "resolution": {"mode": "explicit_only", "on_missing": "clarify"}
            }
          ],
          "app_profile": {
            "capability_framing": "Draft content for a single explicitly selected record.",
            "app_boundaries": {"unsupported_effects": ["external_dispatch", "system.mutation"]}
          }
        }
      }
    }
  ]
}
```

- [ ] **Step 2: Add failing Python fixture parity test**

Append to `packages/python/anip-runtime-utils/tests/test_agent_consumption.py`:

```python
def test_shared_agent_consumption_fixtures():
    fixture_path = Path(__file__).resolve().parents[4] / "agent-consumption-fixtures" / "capability-selection.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

    for case in fixture["cases"]:
        metadata = case["metadata"]
        selected = case["selected_capability"]
        conversation = case["conversation"]
        chosen = assistant_service.select_consumable_capability(conversation, selected, metadata)
        assert chosen == case["expected_capability"], case["id"]
        assert sorted(missing_required_input_names(conversation, metadata[chosen])) == sorted(case["expected_missing_inputs"]), case["id"]
        assert sorted(requested_unsupported_effects(conversation, metadata[selected])) == sorted(case["expected_unsupported_effects"]), case["id"]
```

Add `import json` and `from pathlib import Path` at the top of the file.

- [ ] **Step 3: Run test and verify it fails for missing helper wiring or import mismatch**

Run:

```bash
PYTHONPATH=packages/python/anip-runtime-utils/src ./.venv/bin/pytest packages/python/anip-runtime-utils/tests/test_agent_consumption.py::test_shared_agent_consumption_fixtures -q
```

Expected before implementation cleanup: FAIL if helper names/imports differ.

- [ ] **Step 4: Make Python fixture test pass without changing helper behavior**

Use existing functions from `anip_runtime_utils.agent_consumption`. Do not add GTM-specific logic.

- [ ] **Step 5: Run Python runtime-utils tests**

Run:

```bash
PYTHONPATH=packages/python/anip-runtime-utils/src ./.venv/bin/pytest packages/python/anip-runtime-utils/tests -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add packages/agent-consumption-fixtures packages/python/anip-runtime-utils/tests/test_agent_consumption.py
git commit -m "test: add shared agent consumption fixtures"
```

---

### Task 2: Add TypeScript Runtime Utils Package

**Files:**
- Create: `packages/typescript/runtime-utils/package.json`
- Create: `packages/typescript/runtime-utils/tsconfig.json`
- Create: `packages/typescript/runtime-utils/src/index.ts`
- Create: `packages/typescript/runtime-utils/tests/agent-consumption.test.ts`
- Modify: `packages/typescript/package.json`

- [ ] **Step 1: Add package scaffold**

Create `packages/typescript/runtime-utils/package.json`:

```json
{
  "name": "@anip-dev/runtime-utils",
  "version": "0.25.0",
  "description": "ANIP agent-consumption helper utilities",
  "type": "module",
  "engines": {"node": ">=20"},
  "main": "dist/index.js",
  "types": "dist/index.d.ts",
  "scripts": {
    "build": "tsc",
    "test": "vitest run"
  },
  "devDependencies": {
    "typescript": "^5.5.0",
    "vitest": "^4.1.0"
  },
  "license": "Apache-2.0",
  "repository": {
    "type": "git",
    "url": "https://github.com/anip-protocol/anip.git",
    "directory": "packages/typescript/runtime-utils"
  },
  "publishConfig": {"access": "public"},
  "files": ["dist", "README.md"]
}
```

Create `packages/typescript/runtime-utils/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ES2022",
    "moduleResolution": "Bundler",
    "declaration": true,
    "declarationMap": true,
    "sourceMap": true,
    "outDir": "dist",
    "rootDir": "src",
    "strict": true,
    "skipLibCheck": true
  },
  "include": ["src/**/*.ts"]
}
```

Add `"runtime-utils"` to `packages/typescript/package.json` workspaces.

- [ ] **Step 2: Write failing Vitest fixture test**

Create `packages/typescript/runtime-utils/tests/agent-consumption.test.ts`:

```ts
import { describe, expect, test } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import {
  detectUnsupportedEffects,
  missingRequiredInputNames,
  selectConsumableCapability
} from "../src/index.js";

const fixture = JSON.parse(
  readFileSync(resolve(__dirname, "../../../agent-consumption-fixtures/capability-selection.json"), "utf8")
);

describe("shared agent-consumption fixtures", () => {
  for (const item of fixture.cases) {
    test(item.id, () => {
      const metadata = item.metadata;
      const chosen = selectConsumableCapability(item.conversation, item.selected_capability, metadata);
      expect(chosen).toBe(item.expected_capability);
      expect(missingRequiredInputNames(item.conversation, metadata[chosen]).sort()).toEqual([...item.expected_missing_inputs].sort());
      expect(detectUnsupportedEffects(item.conversation, metadata[item.selected_capability]).sort()).toEqual([...item.expected_unsupported_effects].sort());
    });
  }
});
```

- [ ] **Step 3: Run test and verify it fails**

Run:

```bash
cd packages/typescript/runtime-utils && npm test
```

Expected: FAIL because `src/index.ts` helpers do not exist.

- [ ] **Step 4: Implement minimal TypeScript helpers**

Create `packages/typescript/runtime-utils/src/index.ts` with exported functions:

```ts
export type CapabilityMetadata = Record<string, any>;

export function semanticTextKey(value: unknown): string {
  return String(value ?? "").toLowerCase().replace(/[^a-z0-9]+/g, "");
}

export function textTokens(value: unknown): Set<string> {
  return new Set(String(value ?? "").toLowerCase().match(/[a-z0-9]+/g) ?? []);
}

export function missingRequiredInputNames(conversation: string, metadata: CapabilityMetadata): string[] {
  const tokens = textTokens(conversation);
  const missing: string[] = [];
  for (const spec of metadata.input_specs ?? []) {
    if (!spec?.required || !spec.name) continue;
    const values = [...(spec.allowed_values ?? []), ...Object.keys(metadata.app_profile?.input_meanings?.[spec.name] ?? {})];
    const grounded = values.some((value) => tokens.has(String(value).toLowerCase()) || semanticTextKey(conversation).includes(semanticTextKey(value)));
    if (!grounded) missing.push(String(spec.name));
  }
  return missing;
}

export function detectUnsupportedEffects(conversation: string, metadata: CapabilityMetadata): string[] {
  const lower = conversation.toLowerCase();
  const unsupported = new Set<string>(metadata.app_profile?.app_boundaries?.unsupported_effects ?? metadata.business_effects?.does_not_produce ?? []);
  const found: string[] = [];
  if (unsupported.has("external_dispatch") && /\b(send|dispatch|publish|deliver)\b/.test(lower)) found.push("external_dispatch");
  if (unsupported.has("system.mutation") && /\b(update|delete|apply|write|mutate|change)\b/.test(lower)) found.push("system.mutation");
  if (unsupported.has("raw_data_export") && /\b(raw|export|dump|underlying)\b/.test(lower)) found.push("raw_data_export");
  return [...new Set(found)].sort();
}

export function capabilityMatchScore(conversation: string, capabilityId: string, metadata: CapabilityMetadata): number {
  const source = textTokens(conversation);
  const target = textTokens([
    capabilityId,
    metadata.description,
    metadata.app_profile?.capability_framing,
    Object.keys(metadata.app_profile?.input_meanings ?? {}).join(" "),
    JSON.stringify(metadata.app_profile?.input_meanings ?? {})
  ].join(" "));
  if (source.size === 0 || target.size === 0) return 0;
  const overlap = [...source].filter((token) => target.has(token)).length;
  return overlap / source.size;
}

export function selectConsumableCapability(conversation: string, selectedCapability: string, metadata: Record<string, CapabilityMetadata>): string {
  const selected = metadata[selectedCapability];
  if (!selected) return selectedCapability;
  const selectedProduces = new Set(selected.business_effects?.produces ?? []);
  let best = selectedCapability;
  let bestScore = capabilityMatchScore(conversation, selectedCapability, selected);
  for (const [capabilityId, candidate] of Object.entries(metadata)) {
    const candidateProduces = new Set(candidate.business_effects?.produces ?? []);
    const sameEffect = [...candidateProduces].some((effect) => selectedProduces.has(effect));
    if (!sameEffect) continue;
    const score = capabilityMatchScore(conversation, capabilityId, candidate);
    if (score > bestScore + 0.08) {
      best = capabilityId;
      bestScore = score;
    }
  }
  return best;
}
```

- [ ] **Step 5: Run TypeScript tests**

Run:

```bash
cd packages/typescript/runtime-utils && npm test && npm run build
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/typescript/package.json packages/typescript/runtime-utils
git commit -m "feat(ts): add runtime utils agent consumption helpers"
```

---

### Task 3: Add Go Runtime Utils Package

**Files:**
- Create: `packages/go/runtimeutils/agent_consumption.go`
- Create: `packages/go/runtimeutils/agent_consumption_test.go`

- [ ] **Step 1: Write failing Go fixture test**

Create `packages/go/runtimeutils/agent_consumption_test.go` with a fixture loader that reads `../../agent-consumption-fixtures/capability-selection.json` and asserts `SelectConsumableCapability`, `MissingRequiredInputNames`, and `DetectUnsupportedEffects`.

Run:

```bash
cd packages/go && go test ./runtimeutils
```

Expected: FAIL because package does not exist.

- [ ] **Step 2: Implement minimal Go helpers**

Create `packages/go/runtimeutils/agent_consumption.go` with:

```go
package runtimeutils

import (
	"regexp"
	"sort"
	"strings"
)

var tokenPattern = regexp.MustCompile(`[a-z0-9]+`)

type CapabilityMetadata map[string]any

func SemanticTextKey(value string) string {
	return regexp.MustCompile(`[^a-z0-9]+`).ReplaceAllString(strings.ToLower(value), "")
}

func TextTokens(value string) map[string]bool {
	out := map[string]bool{}
	for _, token := range tokenPattern.FindAllString(strings.ToLower(value), -1) {
		out[token] = true
	}
	return out
}
```

Implement the exported functions with the same signatures used by the test:

```go
func MissingRequiredInputNames(conversation string, metadata CapabilityMetadata) []string
func DetectUnsupportedEffects(conversation string, metadata CapabilityMetadata) []string
func CapabilityMatchScore(conversation string, capabilityID string, metadata CapabilityMetadata) float64
func SelectConsumableCapability(conversation string, selectedCapability string, metadata map[string]CapabilityMetadata) string
```

The Go implementation should use only values from `metadata`, generic tokenization, and canonical effect terms.

- [ ] **Step 3: Run Go tests**

Run:

```bash
cd packages/go && go test ./runtimeutils
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add packages/go/runtimeutils
git commit -m "feat(go): add runtime utils agent consumption helpers"
```

---

### Task 4: Add Java Runtime Utils Module

**Files:**
- Create: `packages/java/anip-runtime-utils/pom.xml`
- Create: `packages/java/anip-runtime-utils/src/main/java/dev/anip/runtimeutils/AgentConsumption.java`
- Create: `packages/java/anip-runtime-utils/src/test/java/dev/anip/runtimeutils/AgentConsumptionTest.java`
- Modify: `packages/java/pom.xml`

- [ ] **Step 1: Add Maven module and failing test**

Add `<module>anip-runtime-utils</module>` to `packages/java/pom.xml`.

Create a JUnit test that reads `../../agent-consumption-fixtures/capability-selection.json` through Jackson and calls:

```java
AgentConsumption.selectConsumableCapability(conversation, selectedCapability, metadata);
AgentConsumption.missingRequiredInputNames(conversation, metadata.get(chosen));
AgentConsumption.detectUnsupportedEffects(conversation, metadata.get(selectedCapability));
```

Run:

```bash
cd packages/java && mvn -pl anip-runtime-utils test
```

Expected: FAIL because `AgentConsumption` does not exist.

- [ ] **Step 2: Implement Java helpers**

Create `AgentConsumption.java` with these static methods:

```java
package dev.anip.runtimeutils;

import java.util.*;
import java.util.regex.Pattern;

public final class AgentConsumption {
  private AgentConsumption() {}

  public static String semanticTextKey(Object value) {
    return String.valueOf(value == null ? "" : value).toLowerCase(Locale.ROOT).replaceAll("[^a-z0-9]+", "");
  }

  public static List<String> missingRequiredInputNames(String conversation, Map<String, Object> metadata) {
    return List.of();
  }

  public static List<String> detectUnsupportedEffects(String conversation, Map<String, Object> metadata) {
    return List.of();
  }

  public static double capabilityMatchScore(String conversation, String capabilityId, Map<String, Object> metadata) {
    return 0.0;
  }

  public static String selectConsumableCapability(String conversation, String selectedCapability, Map<String, Map<String, Object>> metadata) {
    return selectedCapability;
  }
}
```

Replace the initial method bodies in the same task with fixture-passing logic before running the green test.

- [ ] **Step 3: Run Java tests**

Run:

```bash
cd packages/java && mvn -pl anip-runtime-utils test
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add packages/java/pom.xml packages/java/anip-runtime-utils
git commit -m "feat(java): add runtime utils agent consumption helpers"
```

---

### Task 5: Add C# Runtime Utils Project

**Files:**
- Create: `packages/csharp/src/Anip.RuntimeUtils/Anip.RuntimeUtils.csproj`
- Create: `packages/csharp/src/Anip.RuntimeUtils/AgentConsumption.cs`
- Create: `packages/csharp/test/Anip.RuntimeUtils.Tests/Anip.RuntimeUtils.Tests.csproj`
- Create: `packages/csharp/test/Anip.RuntimeUtils.Tests/AgentConsumptionTests.cs`
- Modify: `packages/csharp/Anip.sln`

- [ ] **Step 1: Add project and failing test**

Create `Anip.RuntimeUtils.csproj` targeting the same target framework as existing SDK packages.

Create xUnit test that reads `../../../agent-consumption-fixtures/capability-selection.json` using `System.Text.Json` and calls:

```csharp
AgentConsumption.SelectConsumableCapability(conversation, selectedCapability, metadata);
AgentConsumption.MissingRequiredInputNames(conversation, metadata[chosen]);
AgentConsumption.DetectUnsupportedEffects(conversation, metadata[selectedCapability]);
```

Run:

```bash
cd packages/csharp && dotnet test test/Anip.RuntimeUtils.Tests/Anip.RuntimeUtils.Tests.csproj
```

Expected: FAIL because implementation does not exist.

- [ ] **Step 2: Implement C# helpers**

Create `AgentConsumption.cs` with static helper methods:

```csharp
namespace Anip.RuntimeUtils;

public static class AgentConsumption
{
    public static string SemanticTextKey(object? value)
    {
        var raw = Convert.ToString(value)?.ToLowerInvariant() ?? "";
        return System.Text.RegularExpressions.Regex.Replace(raw, "[^a-z0-9]+", "");
    }
}
```

Add methods for tokenization, required input detection, unsupported effect detection, match scoring, and consumable capability selection.

- [ ] **Step 3: Add projects to solution**

Run:

```bash
cd packages/csharp
dotnet sln Anip.sln add src/Anip.RuntimeUtils/Anip.RuntimeUtils.csproj
dotnet sln Anip.sln add test/Anip.RuntimeUtils.Tests/Anip.RuntimeUtils.Tests.csproj
```

- [ ] **Step 4: Run C# tests**

Run:

```bash
cd packages/csharp && dotnet test test/Anip.RuntimeUtils.Tests/Anip.RuntimeUtils.Tests.csproj
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/csharp/Anip.sln packages/csharp/src/Anip.RuntimeUtils packages/csharp/test/Anip.RuntimeUtils.Tests
git commit -m "feat(csharp): add runtime utils agent consumption helpers"
```

---

### Task 6: Documentation and Release Wiring

**Files:**
- Modify: `packages/python/anip-runtime-utils/README.md`
- Create: `packages/typescript/runtime-utils/README.md`
- Create: `packages/go/runtimeutils/README.md`
- Create: `packages/java/anip-runtime-utils/README.md`
- Create: `packages/csharp/src/Anip.RuntimeUtils/README.md`
- Inspect release scripts/workflows for explicit package lists and update those lists when they omit the new runtime-utils packages.

- [ ] **Step 1: Document trust-boundary positioning**

Each README must include:

```markdown
These helpers assist consuming agents with routing, compact prompt construction, and contract-derived preflight checks. They are not the trust boundary. The authoritative policy decision remains the ANIP service invocation result.
```

- [ ] **Step 2: Verify no GTM terms in shared helper implementations**

Run:

```bash
rg -n "gtm|pipeline|outreach|enrichment|q2|account|cohort" packages/typescript/runtime-utils packages/go/runtimeutils packages/java/anip-runtime-utils packages/csharp/src/Anip.RuntimeUtils
```

Expected: no matches in implementation files. Fixture references in tests may mention neutral terms such as `cohort` only when they come from `packages/agent-consumption-fixtures/capability-selection.json`.

- [ ] **Step 3: Run package tests**

Run:

```bash
PYTHONPATH=packages/python/anip-runtime-utils/src ./.venv/bin/pytest packages/python/anip-runtime-utils/tests -q
cd packages/typescript/runtime-utils && npm test && npm run build
cd packages/go && go test ./runtimeutils
cd packages/java && mvn -pl anip-runtime-utils test
cd packages/csharp && dotnet test test/Anip.RuntimeUtils.Tests/Anip.RuntimeUtils.Tests.csproj
```

Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add packages/*/*runtime* packages/go/runtimeutils packages/agent-consumption-fixtures
git commit -m "docs: document runtime utils parity packages"
```

---

## Final Verification

- [ ] Run targeted parity tests for all five languages.
- [ ] Run existing generator tests touched by package discovery, if release wiring changed.
- [ ] Confirm `git status --short` is clean.
- [ ] Summarize package names and test results before opening a PR.

## Self-Review Notes

- Spec coverage: tasks cover shared fixtures, Python parity, TS, Go, Java, C#, docs, and release wiring checks.
- Scope control: the plan does not port GTM behavior and does not modify generated services.
- TDD path: each language starts with a failing fixture test before implementation.
