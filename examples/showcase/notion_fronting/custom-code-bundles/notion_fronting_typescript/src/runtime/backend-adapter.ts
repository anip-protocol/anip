import type { BackendInvocationPlan, GeneratedCapabilityRuntimeMetadata } from "../generated/runtime-target.js";

export type GeneratedBackendInvocationContext = {
  rootPrincipal?: string;
  approvalGrant?: string | null;
};

export interface GeneratedBackendAdapter {
  execute(capability: GeneratedCapabilityRuntimeMetadata, plan: BackendInvocationPlan, adapterInput: Record<string, unknown>, context: GeneratedBackendInvocationContext): Promise<Record<string, unknown>>;
}

function token(): string | null {
  const value = process.env.NOTION_TOKEN?.trim() ?? "";
  return value || null;
}

function apiBase(): string {
  return (process.env.NOTION_API_BASE?.trim() || "https://api.notion.com/v1").replace(/\/+$/, "");
}

function notionVersion(): string {
  return process.env.NOTION_VERSION?.trim() || "2026-03-11";
}

function csvEnv(name: string): Set<string> {
  return new Set((process.env[name] ?? "").split(",").map((item) => item.trim().toLowerCase()).filter(Boolean));
}

function scopeAllowed(scope: string): boolean {
  const key = scope.trim().toLowerCase();
  const blocked = csvEnv("ANIP_NOTION_BLOCKED_WORKSPACES");
  const allowed = csvEnv("ANIP_NOTION_ALLOWED_WORKSPACES");
  return !blocked.has(key) && (allowed.size === 0 || allowed.has(key));
}

function idAllowed(value: string, envName: string): boolean {
  const allowed = csvEnv(envName);
  return allowed.size === 0 || allowed.has(value.trim().toLowerCase());
}

function configuredDataSourceId(): string {
  return (process.env.NOTION_DATA_SOURCE_ID?.trim() || process.env.ANIP_NOTION_DATA_SOURCE_ID?.trim() || "");
}

function boundedLimit(value: unknown, defaultValue = 20, maximum = 50): number {
  const parsed = Number.parseInt(String(value ?? ""), 10);
  const limit = Number.isFinite(parsed) ? parsed : defaultValue;
  return Math.max(1, Math.min(limit, maximum));
}

function mutationEnabled(context: GeneratedBackendInvocationContext): boolean {
  return process.env.ANIP_NOTION_ALLOW_MUTATION === "true" && Boolean(context?.approvalGrant);
}

function text(value: unknown): string {
  return String(value ?? "").trim();
}

function richText(value: string): Array<Record<string, unknown>> {
  return [{ type: "text", text: { content: value.slice(0, 1900) } }];
}

function result(capability: GeneratedCapabilityRuntimeMetadata, plan: BackendInvocationPlan, status: string, extra: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    execution_status: status,
    capability_id: capability.capability_id,
    selected_backend: plan.selected_binding,
    semantic_input: plan.semantic_input,
    backend_input_contract: plan.backend_input_contract,
    ...extra,
  };
}

function restricted(capability: GeneratedCapabilityRuntimeMetadata, plan: BackendInvocationPlan, reason: string): Record<string, unknown> {
  return result(capability, plan, "restricted", { reason });
}

async function notion(method: string, path: string, body?: Record<string, unknown>): Promise<Record<string, unknown>> {
  const notionToken = token();
  if (!notionToken) return { error: "missing_notion_token" };
  try {
    const response = await fetch(`${apiBase()}${path}`, {
      method,
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${notionToken}`,
        "Content-Type": "application/json",
        "Notion-Version": notionVersion(),
        "User-Agent": "anip-notion-fronting-showcase",
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const raw = await response.text();
    const payload = raw ? JSON.parse(raw) as Record<string, unknown> : {};
    if (!response.ok) return { error: "notion_http_error", status: response.status, detail: payload };
    return payload;
  } catch (error) {
    return { error: "notion_connection_error", detail: String(error) };
  }
}

function titleFromPage(page: Record<string, unknown>): string {
  const properties = page.properties as Record<string, Record<string, unknown>> | undefined;
  for (const value of Object.values(properties ?? {})) {
    if (value.type === "title") {
      const title = (value.title ?? []) as Array<Record<string, unknown>>;
      return title.map((part) => text(part.plain_text)).join("").trim();
    }
  }
  return "";
}

function summarizeObject(item: Record<string, unknown>): Record<string, unknown> {
  const title = item.object === "page" ? titleFromPage(item) : Array.isArray(item.title) ? (item.title as Array<Record<string, unknown>>).map((part) => text(part.plain_text)).join("") : text(item.title);
  return {
    id: item.id,
    object: item.object,
    title: title || item.url || item.id,
    url: item.url,
    created_time: item.created_time,
    last_edited_time: item.last_edited_time,
  };
}

function writePreview(capability: GeneratedCapabilityRuntimeMetadata, plan: BackendInvocationPlan, action: string, body: Record<string, unknown>, metadata: Record<string, unknown>): Record<string, unknown> {
  return result(capability, plan, "prepared", {
    approval_required: true,
    mutation_performed: false,
    notion_action: action,
    notion_metadata: metadata,
    notion_request: { operation: action, body },
    note: "Prepared a Notion API payload. No Notion mutation was performed.",
  });
}

export function createDefaultBackendAdapter(): GeneratedBackendAdapter {
  return {
    async execute(capability, plan, adapterInput, context) {
      if (plan.unresolved_required_backend_inputs.length > 0) {
        return result(capability, plan, "backend_input_incomplete", { unresolved_required_backend_inputs: plan.unresolved_required_backend_inputs });
      }
      if (!token()) return result(capability, plan, "backend_error", { notion_error: { error: "missing_notion_token" } });

      switch (capability.capability_id) {
        case "notion.workspace.search_context": {
          const workspaceScope = text(adapterInput.workspace_scope);
          if (!scopeAllowed(workspaceScope)) return restricted(capability, plan, "Workspace scope is outside the configured ANIP policy.");
          const limit = boundedLimit(adapterInput.limit);
          const response = await notion("POST", "/search", { query: text(adapterInput.query), page_size: limit });
          if (response.error) return result(capability, plan, "backend_error", { notion_error: response });
          const items = ((response.results ?? []) as Record<string, unknown>[]).slice(0, limit).map(summarizeObject);
          return result(capability, plan, "completed", { notion_query: adapterInput.query, result: { workspace_scope: workspaceScope, items, count: items.length } });
        }
        case "notion.database.query_context": {
          const databaseId = text(adapterInput.database_id);
          if (!idAllowed(databaseId, "ANIP_NOTION_ALLOWED_DATABASES")) return restricted(capability, plan, "Database is outside the configured ANIP policy.");
          const limit = boundedLimit(adapterInput.limit);
          let dataSourceId = configuredDataSourceId();
          if (dataSourceId && !idAllowed(dataSourceId, "ANIP_NOTION_ALLOWED_DATA_SOURCES")) return restricted(capability, plan, "Data source is outside the configured ANIP policy.");
          if (!dataSourceId) {
            const database = await notion("GET", `/databases/${encodeURIComponent(databaseId)}`);
            if (database.error) return result(capability, plan, "backend_error", { notion_error: database });
            const dataSources = (database.data_sources ?? []) as Array<Record<string, unknown>>;
            dataSourceId = text(dataSources[0]?.id);
          }
          const response = dataSourceId
            ? await notion("POST", `/data_sources/${encodeURIComponent(dataSourceId)}/query`, { page_size: limit })
            : await notion("POST", `/databases/${encodeURIComponent(databaseId)}/query`, { page_size: limit });
          if (response.error) return result(capability, plan, "backend_error", { notion_error: response });
          const items = ((response.results ?? []) as Record<string, unknown>[]).slice(0, limit).map(summarizeObject);
          return result(capability, plan, "completed", { result: { database_id: databaseId, data_source_id: dataSourceId, items, count: items.length } });
        }
        case "notion.page.create.prepare": {
          const parentId = text(adapterInput.parent_id);
          if (!idAllowed(parentId, "ANIP_NOTION_ALLOWED_PARENTS")) return restricted(capability, plan, "Parent page/database is outside the configured ANIP policy.");
          const body = {
            parent: { page_id: parentId },
            properties: { title: { title: richText(text(adapterInput.title)) } },
            children: [{ object: "block", type: "paragraph", paragraph: { rich_text: richText(text(adapterInput.content_summary)) } }],
          };
          const preview = writePreview(capability, plan, "pages.create", body, { parent_id: parentId });
          if (!mutationEnabled(context)) return preview;
          const created = await notion("POST", "/pages", body);
          if (created.error) return { ...preview, execution_status: "backend_error", notion_error: created };
          return { ...preview, execution_status: "completed", approval_required: false, mutation_performed: true, created_page: summarizeObject(created) };
        }
        case "notion.page.update.prepare": {
          const pageId = text(adapterInput.page_id);
          if (!idAllowed(pageId, "ANIP_NOTION_ALLOWED_PAGES")) return restricted(capability, plan, "Page is outside the configured ANIP policy.");
          return writePreview(capability, plan, "pages.update.preview", { archived: false, change_summary: text(adapterInput.change_summary), content_patch: text(adapterInput.content_patch) }, { page_id: pageId });
        }
        case "notion.comment.prepare": {
          const pageId = text(adapterInput.page_id);
          if (!idAllowed(pageId, "ANIP_NOTION_ALLOWED_PAGES")) return restricted(capability, plan, "Page is outside the configured ANIP policy.");
          const body = { parent: { page_id: pageId }, rich_text: richText(`[${text(adapterInput.comment_purpose)}] ${text(adapterInput.context)}`.trim()) };
          const preview = writePreview(capability, plan, "comments.create", body, { page_id: pageId });
          if (!mutationEnabled(context)) return preview;
          const created = await notion("POST", "/comments", body);
          if (created.error) return { ...preview, execution_status: "backend_error", notion_error: created };
          return { ...preview, execution_status: "completed", approval_required: false, mutation_performed: true, created_comment: created };
        }
        default:
          return result(capability, plan, "backend_execution_stub", { note: "No Notion custom handler is registered for this capability." });
      }
    },
  };
}

export const backendAdapter = createDefaultBackendAdapter();
