import { describe, expect, it } from "vitest";
import type { InvocationContext } from "@anip-dev/service";
import { backendAdapter } from "../src/runtime/backend-adapter.js";
import { generatedCapabilities } from "../src/generated/capabilities.js";
import { generatedCapabilityMetadata, type BackendInvocationPlan, type GeneratedCapabilityRuntimeMetadata } from "../src/generated/runtime-target.js";

const configured = Boolean(process.env.NOTION_TOKEN && process.env.NOTION_WORKSPACE_SCOPE && process.env.NOTION_PARENT_PAGE_ID && process.env.NOTION_DATABASE_ID);

function capability(id: string): GeneratedCapabilityRuntimeMetadata {
  const found = generatedCapabilityMetadata.find((item) => item.capability_id === id);
  if (!found) throw new Error(`Missing capability ${id}`);
  return found;
}

function plan(parameters: Record<string, unknown>): BackendInvocationPlan {
  return {
    selected_binding: null,
    semantic_input: parameters,
    adapter_input: parameters,
    backend_input_contract: { mode: "explicit", required: [], optional: [] },
    unresolved_required_backend_inputs: [],
  };
}

describe.sequential("Notion backend adapter", () => {
  it("returns a bounded missing-token backend error", async () => {
    const oldToken = process.env.NOTION_TOKEN;
    let result: Record<string, unknown>;
    try {
      delete process.env.NOTION_TOKEN;
      result = await backendAdapter.execute(capability("notion.workspace.search_context"), plan({ workspace_scope: "demo", query: "ANIP" }), { workspace_scope: "demo", query: "ANIP" }, {});
    } finally {
      if (oldToken === undefined) {
        delete process.env.NOTION_TOKEN;
      } else {
        process.env.NOTION_TOKEN = oldToken;
      }
    }
    expect(result.execution_status).toBe("backend_error");
    expect((result.notion_error as Record<string, unknown>).error).toBe("missing_notion_token");
  });
});

describe.skipIf(!configured).sequential("Notion live backend adapter", () => {
  it("executes bounded reads and prepares governed previews without mutation", async () => {
    const workspaceScope = process.env.NOTION_WORKSPACE_SCOPE!;
    const parentPageId = process.env.NOTION_PARENT_PAGE_ID!;
    const databaseId = process.env.NOTION_DATABASE_ID!;
    process.env.ANIP_NOTION_ALLOWED_WORKSPACES ??= workspaceScope;
    process.env.ANIP_NOTION_ALLOWED_PARENTS ??= parentPageId;
    process.env.ANIP_NOTION_ALLOWED_PAGES ??= parentPageId;
    process.env.ANIP_NOTION_ALLOWED_DATABASES ??= databaseId;

    const search = await backendAdapter.execute(capability("notion.workspace.search_context"), plan({ workspace_scope: workspaceScope, query: "ANIP", limit: 5 }), { workspace_scope: workspaceScope, query: "ANIP", limit: 5 }, {});
    expect(search.execution_status).toBe("completed");

    const query = await backendAdapter.execute(capability("notion.database.query_context"), plan({ database_id: databaseId, limit: 5 }), { database_id: databaseId, limit: 5 }, {});
    expect(query.execution_status).toBe("completed");

    const create = await backendAdapter.execute(capability("notion.page.create.prepare"), plan({ parent_id: parentPageId, title: "ANIP Notion TypeScript preview", content_summary: "Preview only" }), { parent_id: parentPageId, title: "ANIP Notion TypeScript preview", content_summary: "Preview only" }, {});
    expect(create.execution_status).toBe("prepared");
    expect(create.mutation_performed).toBe(false);

    const update = await backendAdapter.execute(capability("notion.page.update.prepare"), plan({ page_id: parentPageId, change_summary: "Preview only", content_patch: "No write" }), { page_id: parentPageId, change_summary: "Preview only", content_patch: "No write" }, {});
    expect(update.execution_status).toBe("prepared");
    expect(update.mutation_performed).toBe(false);

    const comment = await backendAdapter.execute(capability("notion.comment.prepare"), plan({ page_id: parentPageId, comment_purpose: "smoke-test", context: "Preview only" }), { page_id: parentPageId, comment_purpose: "smoke-test", context: "Preview only" }, {});
    expect(comment.execution_status).toBe("prepared");
    expect(comment.mutation_performed).toBe(false);
  });

  it("routes approved page creation through the generated handler", async () => {
    const parentPageId = process.env.NOTION_PARENT_PAGE_ID!;
    process.env.ANIP_NOTION_ALLOWED_PARENTS ??= parentPageId;
    const capabilityDef = generatedCapabilities.find((item) => item.declaration.name === "notion.page.create.prepare");
    expect(capabilityDef).toBeTruthy();
    const parameters = {
      parent_id: parentPageId,
      title: `ANIP approved Notion TypeScript page at ${Date.now()}`,
      content_summary: "Created by explicit ANIP Notion TypeScript generated-handler smoke.",
    };

    const preview = await capabilityDef!.handler(testContext(null), { ...parameters, request_execution_approval: true });
    expect(preview.execution_status).toBe("prepared");
    expect(preview.mutation_performed).toBe(false);

    if (process.env.ANIP_NOTION_ALLOW_MUTATION === "true") {
      const created = await capabilityDef!.handler(testContext("grant_live_typescript_notion_smoke"), parameters);
      expect(created.execution_status).toBe("completed");
      expect(created.mutation_performed).toBe(true);
      expect((created.created_page as Record<string, unknown>).id).toBeTruthy();
    }
  });
});

function testContext(approvalGrant: string | null): InvocationContext {
  return {
    token: {} as InvocationContext["token"],
    rootPrincipal: "human:local-dev|actor_id=notion_fronting_consumer",
    subject: "agent:notion-live-smoke",
    scopes: ["notion.page.create.prepare"],
    delegationChain: [],
    invocationId: "inv-test",
    clientReferenceId: null,
    taskId: null,
    parentInvocationId: null,
    upstreamService: null,
    approvalGrant,
    setCostActual: () => {},
    emitProgress: async () => {},
  };
}
