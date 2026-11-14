import { describe, expect, it } from "vitest";
import type { InvocationContext } from "@anip-dev/service";
import { backendAdapter } from "../src/runtime/backend-adapter.js";
import { generatedCapabilities } from "../src/generated/capabilities.js";
import { generatedCapabilityMetadata, type BackendInvocationPlan, type GeneratedCapabilityRuntimeMetadata } from "../src/generated/runtime-target.js";

const configured = Boolean(process.env.GITHUB_TOKEN && process.env.GITHUB_OWNER && process.env.GITHUB_REPO);

// Principals the 0.2.0 runtime policy bindings select.
const DRAFTER = "human:local-dev|actor_id=release_notes_drafter";
const ISSUE_REQUESTER = "human:local-dev|actor_id=issue_requester";
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

    // release_notes_drafter may prepare issues: without a grant it gets a preview.
    const preview = await capabilityDef!.handler(testContext(DRAFTER, null), parameters);
    expect(preview.execution_status).toBe("prepared");
    expect(preview.mutation_performed).toBe(false);

    // issue_requester's binding requires approval: no grant, no adapter call.
    await expect(capabilityDef!.handler(testContext(ISSUE_REQUESTER, null), parameters)).rejects.toMatchObject({
      errorType: "approval_required",
    });

    if (process.env.ANIP_GITHUB_ALLOW_MUTATION === "true") {
      // The runtime sets approvalGrant only after validating the grant.
      const created = await capabilityDef!.handler(testContext(ISSUE_REQUESTER, "grant_live_typescript_github_smoke"), parameters);
      expect(created.execution_status).toBe("completed");
      expect(created.mutation_performed).toBe(true);
      expect((created.created_issue as Record<string, unknown>).number).toBeTruthy();
    }
  });
});

describe("GitHub generated handler policy", () => {
  // The generated policy refuses a principal no binding selects before the
  // backend adapter runs, so this needs no GitHub credentials.
  it("refuses principals no binding selects", async () => {
    const capabilityDef = generatedCapabilities.find((item) => item.declaration.name === "github.issue.prepare");
    expect(capabilityDef).toBeTruthy();
    const parameters = { owner: "anip-smoke", repo: "sandbox", title: "Refused", body: "Never reaches GitHub." };
    for (const principal of ["human:local-dev", "human:local-dev|actor_id=github_fronting_consumer"]) {
      await expect(capabilityDef!.handler(testContext(principal, "grant_live_typescript_github_smoke"), parameters)).rejects.toMatchObject({
        errorType: "denied",
        detail: NO_BINDING_DETAIL,
      });
    }
  });
});

function repoParams(): { owner: string; repo: string } {
  return { owner: process.env.GITHUB_OWNER!, repo: process.env.GITHUB_REPO! };
}

function testContext(rootPrincipal: string, approvalGrant: string | null): InvocationContext {
  return {
    token: {} as InvocationContext["token"],
    rootPrincipal,
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
