import { describe, expect, it } from "vitest";
import type { InvocationContext } from "@anip-dev/service";
import { backendAdapter } from "../src/runtime/backend-adapter.js";
import { generatedCapabilities } from "../src/generated/capabilities.js";
import { generatedCapabilityMetadata, type BackendInvocationPlan, type GeneratedCapabilityRuntimeMetadata } from "../src/generated/runtime-target.js";

const configured = Boolean(process.env.GITHUB_TOKEN && process.env.GITHUB_OWNER && process.env.GITHUB_REPO);

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

describe.skipIf(!configured)("GitHub live backend adapter", () => {
  it("executes reads and prepares write-adjacent previews without mutation", async () => {
    const repo = repoParams();
    process.env.ANIP_GITHUB_ALLOWED_REPOS ??= `${repo.owner}/${repo.repo}`;

    const search = await backendAdapter.execute(capability("github.repo.search_context"), plan({ ...repo, query: "is:issue", limit: 5 }), { ...repo, query: "is:issue", limit: 5 }, {});
    expect(search.execution_status).toBe("completed");

    const issue = await backendAdapter.execute(capability("github.issue.prepare"), plan({ ...repo, title: "ANIP GitHub TypeScript preview", body: "Preview only" }), { ...repo, title: "ANIP GitHub TypeScript preview", body: "Preview only" }, {});
    expect(issue.execution_status).toBe("prepared");
    expect(issue.mutation_performed).toBe(false);

    const notes = await backendAdapter.execute(capability("github.release_notes.prepare"), plan({ ...repo, range: "HEAD", audience: "internal" }), { ...repo, range: "HEAD", audience: "internal" }, {});
    expect(notes.execution_status).toBe("completed");
  });

  it("routes approved issue creation through the generated handler", async () => {
    const capabilityDef = generatedCapabilities.find((item) => item.declaration.name === "github.issue.prepare");
    expect(capabilityDef).toBeTruthy();
    const repo = repoParams();
    process.env.ANIP_GITHUB_ALLOWED_REPOS ??= `${repo.owner}/${repo.repo}`;
    const parameters = {
      ...repo,
      title: `ANIP approved GitHub TypeScript issue at ${Date.now()}`,
      body: "Created by explicit ANIP GitHub TypeScript generated-handler smoke.",
    };

    const preview = await capabilityDef!.handler(testContext(null), { ...parameters, request_execution_approval: true });
    expect(preview.execution_status).toBe("prepared");
    expect(preview.mutation_performed).toBe(false);

    if (process.env.ANIP_GITHUB_ALLOW_MUTATION === "true") {
      const created = await capabilityDef!.handler(testContext("grant_live_typescript_github_smoke"), parameters);
      expect(created.execution_status).toBe("completed");
      expect(created.mutation_performed).toBe(true);
      expect((created.created_issue as Record<string, unknown>).number).toBeTruthy();
    }
  });
});

function repoParams(): { owner: string; repo: string } {
  return { owner: process.env.GITHUB_OWNER!, repo: process.env.GITHUB_REPO! };
}

function testContext(approvalGrant: string | null): InvocationContext {
  return {
    token: {} as InvocationContext["token"],
    rootPrincipal: "human:local-dev|actor_id=github_fronting_consumer",
    subject: "agent:github-live-smoke",
    scopes: ["github.issue.prepare"],
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
