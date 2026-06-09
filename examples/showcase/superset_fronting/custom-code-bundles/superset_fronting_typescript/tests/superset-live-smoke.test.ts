import { describe, expect, it } from "vitest";
import { backendAdapter } from "../src/runtime/backend-adapter.js";
import { generatedCapabilityMetadata, type BackendInvocationPlan, type GeneratedCapabilityRuntimeMetadata } from "../src/generated/runtime-target.js";

const configured = Boolean(process.env.SUPERSET_BASE_URL && (process.env.SUPERSET_ACCESS_TOKEN || (process.env.SUPERSET_USERNAME && process.env.SUPERSET_PASSWORD)));

function capability(id: string): GeneratedCapabilityRuntimeMetadata {
  const found = generatedCapabilityMetadata.find((item) => item.capability_id === id);
  if (!found) throw new Error(`Missing capability ${id}`);
  return found;
}

function plan(parameters: Record<string, unknown>): BackendInvocationPlan {
  return {
    selected_binding: { backend_kind: "native_api" },
    semantic_input: parameters,
    adapter_input: parameters,
    backend_input_contract: { mode: "explicit", required: [], optional: [] },
    unresolved_required_backend_inputs: [],
  };
}

describe.skipIf(!configured)("Superset live backend adapter", () => {
  it("executes bounded discovery and prepares governed previews without mutation", async () => {
    const workspaceScope = process.env.SUPERSET_WORKSPACE_SCOPE ?? "local";
    process.env.ANIP_SUPERSET_ALLOWED_WORKSPACES ??= workspaceScope;

    const discoveryParams = { workspace_scope: workspaceScope, query: "birth", limit: 5 };
    const discovery = await backendAdapter.execute(capability("superset.analytics.discover_context"), plan(discoveryParams), discoveryParams, {});
    expect(discovery.execution_status).toBe("completed");
    expect((discovery.result as Record<string, unknown>).count).toBeGreaterThanOrEqual(0);

    const chartParams = { dataset_ref: "1", metric: "count", visualization_type: "bar", title: "ANIP TypeScript preview chart" };
    const chart = await backendAdapter.execute(capability("superset.chart.preview.create"), plan(chartParams), chartParams, {});
    expect(chart.execution_status).toBe("prepared");
    expect(chart.approval_required).toBe(true);
    expect(chart.mutation_performed).toBe(false);
    expect(((chart.superset_request as Record<string, unknown>).body as Record<string, unknown>).save_chart).toBe(false);

    const datasetParams = { database_ref: "1", dataset_purpose: "ANIP smoke", query_intent: "Count records by category" };
    const dataset = await backendAdapter.execute(capability("superset.dataset.draft.prepare"), plan(datasetParams), datasetParams, {});
    expect(dataset.execution_status).toBe("prepared");
    expect(dataset.mutation_performed).toBe(false);
    expect(((dataset.superset_request as Record<string, unknown>).body as Record<string, unknown>).raw_sql_accepted).toBe(false);
  });
});
