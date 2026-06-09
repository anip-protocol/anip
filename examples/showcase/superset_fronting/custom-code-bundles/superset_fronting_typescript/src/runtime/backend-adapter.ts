import type { BackendInvocationPlan, GeneratedCapabilityRuntimeMetadata } from "../generated/runtime-target.js";

export type GeneratedBackendInvocationContext = {
  rootPrincipal?: string;
  approvalGrant?: string | null;
};

export interface GeneratedBackendAdapter {
  execute(capability: GeneratedCapabilityRuntimeMetadata, plan: BackendInvocationPlan, adapterInput: Record<string, unknown>, context: GeneratedBackendInvocationContext): Promise<Record<string, unknown>>;
}

const baseUrl = () => (process.env.SUPERSET_BASE_URL ?? "http://127.0.0.1:18088").replace(/\/$/, "");

function csvEnv(name: string): Set<string> {
  return new Set((process.env[name] ?? "").split(",").map((item) => item.trim().toLowerCase()).filter(Boolean));
}

function scopeAllowed(scope: string): boolean {
  const key = scope.trim().toLowerCase();
  const blocked = csvEnv("ANIP_SUPERSET_BLOCKED_WORKSPACES");
  const allowed = csvEnv("ANIP_SUPERSET_ALLOWED_WORKSPACES");
  return !blocked.has(key) && (allowed.size === 0 || allowed.has(key));
}

function datasetAllowed(datasetRef: string): boolean {
  const allowed = csvEnv("ANIP_SUPERSET_ALLOWED_DATASETS");
  return allowed.size === 0 || allowed.has(datasetRef.trim().toLowerCase());
}

function boundedLimit(value: unknown, fallback = 20, maximum = 100): number {
  const parsed = Number.parseInt(String(value ?? ""), 10);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.max(1, Math.min(parsed, maximum));
}

async function requestJson(method: string, path: string, token: string | null, body?: Record<string, unknown>): Promise<Record<string, unknown>> {
  try {
    const response = await fetch(`${baseUrl()}${path}`, {
      method,
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        "User-Agent": "anip-superset-fronting-showcase",
      },
      body: body ? JSON.stringify(body) : undefined,
    });
    const text = await response.text();
    const payload = text ? JSON.parse(text) as Record<string, unknown> : {};
    if (!response.ok) return { error: "superset_http_error", status: response.status, detail: payload };
    return payload;
  } catch (error) {
    return { error: "superset_connection_error", detail: String(error) };
  }
}

async function accessToken(): Promise<string | null> {
  const direct = (process.env.SUPERSET_ACCESS_TOKEN ?? "").trim();
  if (direct) return direct;
  const username = (process.env.SUPERSET_USERNAME ?? "").trim();
  const password = (process.env.SUPERSET_PASSWORD ?? "").trim();
  if (!username || !password) return null;
  const response = await requestJson("POST", "/api/v1/security/login", null, {
    username,
    password,
    provider: process.env.SUPERSET_AUTH_PROVIDER ?? "db",
    refresh: true,
  });
  return typeof response.access_token === "string" ? response.access_token : null;
}

function metadata(capability: GeneratedCapabilityRuntimeMetadata, plan: BackendInvocationPlan): Record<string, unknown> {
  return {
    capability_id: capability.capability_id,
    selected_backend: plan.selected_binding,
    semantic_input: plan.semantic_input,
    backend_input_contract: plan.backend_input_contract,
  };
}

function restricted(capability: GeneratedCapabilityRuntimeMetadata, plan: BackendInvocationPlan, reason: string): Record<string, unknown> {
  return { execution_status: "restricted", ...metadata(capability, plan), reason };
}

function backendError(capability: GeneratedCapabilityRuntimeMetadata, plan: BackendInvocationPlan, supersetError: unknown): Record<string, unknown> {
  return { execution_status: "backend_error", ...metadata(capability, plan), superset_error: supersetError };
}

function listResult(response: Record<string, unknown>): Record<string, unknown>[] {
  const raw = response.result;
  if (Array.isArray(raw)) return raw as Record<string, unknown>[];
  if (raw && typeof raw === "object") {
    const object = raw as Record<string, unknown>;
    if (Array.isArray(object.data)) return object.data as Record<string, unknown>[];
    if (Array.isArray(object.result)) return object.result as Record<string, unknown>[];
  }
  return [];
}

function writePreview(capability: GeneratedCapabilityRuntimeMetadata, plan: BackendInvocationPlan, action: string, body: Record<string, unknown>, supersetMetadata: Record<string, unknown>): Record<string, unknown> {
  return {
    execution_status: "prepared",
    ...metadata(capability, plan),
    approval_required: true,
    mutation_performed: false,
    superset_action: action,
    superset_metadata: supersetMetadata,
    superset_request: { operation: action, body },
    note: "Prepared a governed Superset analytics request. No Superset mutation was performed.",
  };
}

export function createDefaultBackendAdapter(): GeneratedBackendAdapter {
  return {
    async execute(capability, plan, adapterInput, context) {
      if (plan.unresolved_required_backend_inputs.length > 0) {
        return {
          execution_status: "backend_input_incomplete",
          capability_id: capability.capability_id,
          backend_input_contract: plan.backend_input_contract,
          unresolved_required_backend_inputs: plan.unresolved_required_backend_inputs,
          note: "Generated host is runnable, but backend-only inputs still require extension completion.",
        };
      }
      const token = await accessToken();
      if (!token) return backendError(capability, plan, { error: "missing_superset_credentials" });
      switch (capability.capability_id) {
        case "superset.analytics.discover_context": {
          const workspaceScope = String(adapterInput.workspace_scope ?? "").trim();
          if (!scopeAllowed(workspaceScope)) return restricted(capability, plan, "Workspace scope is outside the configured ANIP policy.");
          const query = String(adapterInput.query ?? "").trim().toLowerCase();
          const limit = boundedLimit(adapterInput.limit, 20, 50);
          const assetType = String(adapterInput.asset_type ?? "").trim();
          let endpoints: Array<[string, string]> = [["dataset", "/api/v1/dataset/"], ["chart", "/api/v1/chart/"], ["dashboard", "/api/v1/dashboard/"]];
          if (assetType) endpoints = endpoints.filter(([kind]) => kind === assetType);
          const items: Record<string, unknown>[] = [];
          for (const [kind, endpoint] of endpoints) {
            const response = await requestJson("GET", `${endpoint}?page_size=${limit}`, token);
            if (response.error) return backendError(capability, plan, response);
            for (const item of listResult(response)) {
              const title = String(item.table_name ?? item.slice_name ?? item.dashboard_title ?? item.name ?? item.id ?? "");
              if (query && !title.toLowerCase().includes(query)) continue;
              items.push({ asset_type: kind, id: item.id, title, url: item.url });
              if (items.length >= limit) break;
            }
            if (items.length >= limit) break;
          }
          return { execution_status: "completed", ...metadata(capability, plan), result: { workspace_scope: workspaceScope, items, count: items.length } };
        }
        case "superset.analytics.answer_question": {
          const datasetRef = String(adapterInput.dataset_ref ?? "").trim();
          if (!datasetAllowed(datasetRef)) return restricted(capability, plan, "Dataset is outside the configured ANIP policy.");
          return {
            execution_status: "completed",
            ...metadata(capability, plan),
            mutation_performed: false,
            result: {
              question: adapterInput.question,
              dataset_ref: datasetRef,
              metric: adapterInput.metric,
              dimension: adapterInput.dimension,
              time_window: adapterInput.time_window,
              answer: "Governed analytics answer placeholder. The service owns SQL generation and execution policy.",
              raw_sql_disclosed: false,
            },
          };
        }
        case "superset.chart.preview.create": {
          const datasetRef = String(adapterInput.dataset_ref ?? "").trim();
          if (!datasetAllowed(datasetRef)) return restricted(capability, plan, "Dataset is outside the configured ANIP policy.");
          const body = {
            dataset_ref: datasetRef,
            metric: adapterInput.metric,
            dimension: adapterInput.dimension,
            visualization_type: adapterInput.visualization_type,
            title: adapterInput.title ?? `${String(adapterInput.metric ?? "")} by ${String(adapterInput.dimension ?? "time")}`,
            save_chart: false,
          };
          return writePreview(capability, plan, "chart.preview", body, { dataset_ref: datasetRef });
        }
        case "superset.chart.publish.request": {
          const preview = writePreview(capability, plan, "chart.publish", {
            chart_preview_ref: adapterInput.chart_preview_ref,
            dashboard_scope: adapterInput.dashboard_scope,
            reason: adapterInput.reason,
            title: adapterInput.title,
          }, { dashboard_scope: adapterInput.dashboard_scope });
          if (process.env.ANIP_SUPERSET_ALLOW_MUTATION === "true" && context.approvalGrant) {
            return { ...preview, execution_status: "completed", approval_required: false, mutation_performed: false, note: "Approved publish request recorded. Concrete chart save is intentionally left to deployment-specific Superset adapter code." };
          }
          return preview;
        }
        case "superset.dashboard.draft.prepare":
          return writePreview(capability, plan, "dashboard.draft", {
            dashboard_scope: adapterInput.dashboard_scope,
            objective: adapterInput.objective,
            chart_refs: adapterInput.chart_refs ?? [],
            layout_hint: adapterInput.layout_hint,
            audience: adapterInput.audience,
          }, { dashboard_scope: adapterInput.dashboard_scope });
        case "superset.dataset.draft.prepare": {
          const preview = writePreview(capability, plan, "dataset.draft", {
            database_ref: adapterInput.database_ref,
            dataset_purpose: adapterInput.dataset_purpose,
            query_intent: adapterInput.query_intent,
            source_tables: adapterInput.source_tables ?? [],
            metrics: adapterInput.metrics ?? [],
            raw_sql_accepted: false,
          }, { database_ref: adapterInput.database_ref });
          if (process.env.ANIP_SUPERSET_ALLOW_MUTATION === "true" && context.approvalGrant) {
            return { ...preview, execution_status: "completed", approval_required: false, mutation_performed: false, note: "Approved dataset draft recorded. Raw SQL generation remains deployment-owned." };
          }
          return preview;
        }
        default:
          return { execution_status: "backend_execution_stub", ...metadata(capability, plan), note: "No Superset custom handler is registered for this capability." };
      }
    },
  };
}

export const backendAdapter = createDefaultBackendAdapter();
