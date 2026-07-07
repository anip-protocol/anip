import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, test } from "vitest";
import {
  missingRequiredInputNames,
  requestedUnsupportedEffects,
  selectConsumableCapability,
  validateInvocationPlanForFallback,
} from "../src/index.js";

interface FixtureCase {
  id: string;
  conversation: string;
  selected_capability: string;
  expected_capability: string;
  expected_missing_inputs: string[];
  expected_unsupported_effects: string[];
  metadata: Record<string, unknown>;
}

const __dirname = dirname(fileURLToPath(import.meta.url));
const fixture = JSON.parse(
  readFileSync(
    resolve(__dirname, "../../../agent-consumption-fixtures/capability-selection.json"),
    "utf8",
  ),
) as { cases: FixtureCase[] };

describe("shared agent-consumption fixtures", () => {
  for (const item of fixture.cases) {
    test(item.id, () => {
      const chosen = selectConsumableCapability(
        item.conversation,
        item.selected_capability,
        item.metadata,
      );

      expect(chosen).toBe(item.expected_capability);
      expect(
        missingRequiredInputNames(item.conversation, item.metadata[chosen]).sort(),
      ).toEqual([...item.expected_missing_inputs].sort());
      expect(
        requestedUnsupportedEffects(
          item.conversation,
          item.metadata[item.selected_capability],
        ).sort(),
      ).toEqual([...item.expected_unsupported_effects].sort());
    });
  }
});

interface FallbackFixtureCase {
  id: string;
  conversation: string;
  plan: Record<string, unknown>;
  compact_candidate_ids?: string[];
  expected_reasons: string[];
  metadata: Record<string, unknown>;
}

const fallbackFixture = JSON.parse(
  readFileSync(
    resolve(__dirname, "../../../agent-consumption-fixtures/planner-fallback-validation.json"),
    "utf8",
  ),
) as { cases: FallbackFixtureCase[] };

describe("shared planner fallback validation fixtures", () => {
  for (const item of fallbackFixture.cases) {
    test(item.id, () => {
      expect(
        validateInvocationPlanForFallback(item.plan, item.conversation, item.metadata, {
          compactCandidateIds: item.compact_candidate_ids,
        }),
      ).toEqual(item.expected_reasons);
    });
  }
});
