import { describe, expect, it } from "vitest";
import type { InvocationContext } from "@anip-dev/service";
import { backendAdapter } from "../src/runtime/backend-adapter.js";
import { generatedCapabilities } from "../src/generated/capabilities.js";
import { generatedCapabilityMetadata, type BackendInvocationPlan, type GeneratedCapabilityRuntimeMetadata } from "../src/generated/runtime-target.js";

const configured = Boolean(process.env.NOTION_TOKEN && process.env.NOTION_WORKSPACE_SCOPE && process.env.NOTION_PARENT_PAGE_ID && process.env.NOTION_DATABASE_ID);

// Principals the 0.2.0 runtime policy bindings select.
const REVIEWER = "human:local-dev|actor_id=notion_governance_reviewer";
const REQUESTER = "human:local-dev|actor_id=governed_notion_requester";
const NO_BINDING_DETAIL = "No runtime policy binding matches the current actor for this capability.";

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

    // notion_governance_reviewer may create pages: without a grant it gets a preview.
    const preview = await capabilityDef!.handler(testContext(REVIEWER, null), parameters);
    expect(preview.execution_status).toBe("prepared");
    expect(preview.mutation_performed).toBe(false);

    // governed_notion_requester's binding requires approval: no grant, no adapter call.
    await expect(capabilityDef!.handler(testContext(REQUESTER, null), parameters)).rejects.toMatchObject({
      errorType: "approval_required",
    });

    if (process.env.ANIP_NOTION_ALLOW_MUTATION === "true") {
      // The runtime sets approvalGrant only after validating the grant.
      const created = await capabilityDef!.handler(testContext(REQUESTER, "grant_live_typescript_notion_smoke"), parameters);
      expect(created.execution_status).toBe("completed");
      expect(created.mutation_performed).toBe(true);
      expect((created.created_page as Record<string, unknown>).id).toBeTruthy();
    }
  });
});

describe("Notion generated handler policy", () => {
  // The generated policy refuses a principal no binding selects before the
  // backend adapter runs, so this needs no Notion credentials.
  it("refuses principals no binding selects", async () => {
    const capabilityDef = generatedCapabilities.find((item) => item.declaration.name === "notion.page.create.prepare");
    expect(capabilityDef).toBeTruthy();
    const parameters = { parent_id: "11111111-1111-4111-8111-111111111111", title: "Refused", content_summary: "Never reaches Notion." };
    for (const principal of ["human:local-dev", "human:local-dev|actor_id=notion_fronting_consumer"]) {
      await expect(capabilityDef!.handler(testContext(principal, "grant_live_typescript_notion_smoke"), parameters)).rejects.toMatchObject({
        errorType: "denied",
        detail: NO_BINDING_DETAIL,
      });
    }
  });
});

function testContext(rootPrincipal: string, approvalGrant: string | null): InvocationContext {
  return {
    token: {} as InvocationContext["token"],
    rootPrincipal,
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
