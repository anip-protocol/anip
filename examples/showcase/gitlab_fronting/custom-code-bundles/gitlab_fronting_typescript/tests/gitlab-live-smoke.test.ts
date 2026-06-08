import { describe, expect, it } from "vitest";
import type { InvocationContext } from "@anip-dev/service";
import { backendAdapter } from "../src/runtime/backend-adapter.js";
import { generatedCapabilities } from "../src/generated/capabilities.js";
import { generatedCapabilityMetadata, type BackendInvocationPlan, type GeneratedCapabilityRuntimeMetadata } from "../src/generated/runtime-target.js";

const configured = Boolean(process.env.GITLAB_TOKEN && projectParams().project_id);

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

describe.skipIf(!configured)("GitLab live backend adapter", () => {
  it("executes reads and prepares write-adjacent previews without mutation", async () => {
    const project = projectParams();
    process.env.ANIP_GITLAB_ALLOWED_PROJECTS ??= project.project_id;

    const search = await backendAdapter.execute(capability("gitlab.project.search_context"), plan({ ...project, query: "ANIP", limit: 5 }), { ...project, query: "ANIP", limit: 5 }, {});
    expect(search.execution_status).toBe("completed");

    const issue = await backendAdapter.execute(capability("gitlab.issue.prepare"), plan({ ...project, title: "ANIP GitLab TypeScript preview", body: "Preview only" }), { ...project, title: "ANIP GitLab TypeScript preview", body: "Preview only" }, {});
    expect(issue.execution_status).toBe("prepared");
    expect(issue.mutation_performed).toBe(false);

    const notes = await backendAdapter.execute(capability("gitlab.release_notes.prepare"), plan({ ...project, range: "HEAD", audience: "internal" }), { ...project, range: "HEAD", audience: "internal" }, {});
    expect(notes.execution_status).toBe("completed");
  });

  it("routes approved issue creation through the generated handler", async () => {
    const capabilityDef = generatedCapabilities.find((item) => item.declaration.name === "gitlab.issue.prepare");
    expect(capabilityDef).toBeTruthy();
    const project = projectParams();
    process.env.ANIP_GITLAB_ALLOWED_PROJECTS ??= project.project_id;
    const parameters = {
      ...project,
      title: `ANIP approved GitLab TypeScript issue at ${Date.now()}`,
      body: "Created by explicit ANIP GitLab TypeScript generated-handler smoke.",
    };

    const preview = await capabilityDef!.handler(testContext(null), { ...parameters, request_execution_approval: true });
    expect(preview.execution_status).toBe("prepared");
    expect(preview.mutation_performed).toBe(false);

    if (process.env.ANIP_GITLAB_ALLOW_MUTATION === "true") {
      const created = await capabilityDef!.handler(testContext("grant_live_typescript_gitlab_smoke"), parameters);
      expect(created.execution_status).toBe("completed");
      expect(created.mutation_performed).toBe(true);
      expect((created.created_issue as Record<string, unknown>).iid).toBeTruthy();
    }
  });
});

function projectParams(): { project_id: string; namespace?: string; project?: string } {
  const explicit = process.env.GITLAB_PROJECT_ID?.trim();
  if (explicit) {
    const [namespace, ...parts] = explicit.split("/");
    return { project_id: explicit, namespace, project: parts.join("/") || undefined };
  }
  const namespace = process.env.GITLAB_NAMESPACE?.trim();
  const project = process.env.GITLAB_PROJECT?.trim();
  return { project_id: namespace && project ? `${namespace}/${project}` : "", namespace, project };
}

function testContext(approvalGrant: string | null): InvocationContext {
  return {
    token: {} as InvocationContext["token"],
    rootPrincipal: "human:local-dev|actor_id=gitlab_fronting_consumer",
    subject: "agent:gitlab-live-smoke",
    scopes: ["gitlab.issue.prepare"],
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
