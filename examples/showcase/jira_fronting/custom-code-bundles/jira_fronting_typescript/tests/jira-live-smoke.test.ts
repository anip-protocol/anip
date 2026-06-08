import { describe, expect, it } from "vitest";
import { backendAdapter } from "../src/runtime/backend-adapter.js";
import { generatedCapabilityMetadata, type BackendInvocationPlan, type GeneratedCapabilityRuntimeMetadata } from "../src/generated/runtime-target.js";

const configured = Boolean(process.env.JIRA_BASE_URL && process.env.JIRA_EMAIL && process.env.JIRA_API_TOKEN);

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

async function jiraGet(path: string, query: Record<string, string> = {}): Promise<Record<string, unknown>> {
  const url = new URL(`${process.env.JIRA_BASE_URL!.replace(/\/+$/, "")}${path}`);
  for (const [key, value] of Object.entries(query)) url.searchParams.set(key, value);
  const response = await fetch(url, {
    headers: {
      Accept: "application/json",
      Authorization: `Basic ${Buffer.from(`${process.env.JIRA_EMAIL}:${process.env.JIRA_API_TOKEN}`).toString("base64")}`,
    },
  });
  expect(response.ok).toBe(true);
  return await response.json() as Record<string, unknown>;
}

describe.skipIf(!configured)("Jira live backend adapter", () => {
  it("executes bounded reads and prepares governed previews without mutation", async () => {
    const projects = ((await jiraGet("/rest/api/3/project/search", { maxResults: "1" })).values ?? []) as Record<string, unknown>[];
    expect(projects.length).toBeGreaterThan(0);
    const projectKey = String(projects[0].key);
    const issues = ((await jiraGet("/rest/api/3/search/jql", { jql: `project = ${projectKey} ORDER BY updated DESC`, maxResults: "2", fields: "summary,status,issuetype,project" })).issues ?? []) as Record<string, unknown>[];
    expect(issues.length).toBeGreaterThan(0);
    const issueKey = String(issues[0].key);
    const secondIssueKey = String((issues[1] ?? issues[0]).key);

    const search = await backendAdapter.execute(capability("jira.backlog.search_context"), plan({ project_key: projectKey, query: "test", limit: 5 }), { project_key: projectKey, query: "test", limit: 5 }, {});
    expect(search.execution_status).toBe("completed");

    const issue = await backendAdapter.execute(capability("jira.issue.get_context"), plan({ issue_key: issueKey, include_comments: true }), { issue_key: issueKey, include_comments: true }, {});
    expect(issue.execution_status).toBe("completed");

    const previews: Array<[string, Record<string, unknown>]> = [
      ["jira.incident_bug.prepare", { project_key: projectKey, summary: "ANIP smoke bug", description: "Preview only", severity: "sev3", labels: ["anip-smoke"] }],
      ["jira.story.prepare", { project_key: projectKey, summary: "ANIP smoke story", acceptance_criteria: ["Given ANIP", "Then no mutation"], priority: "medium" }],
      ["jira.subtask.prepare", { parent_issue_key: issueKey, summary: "ANIP smoke subtask", description: "Preview only" }],
      ["jira.customer_escalation.comment.prepare", { issue_key: issueKey, comment_purpose: "triage_update", context: "Preview only", visibility: "internal" }],
      ["jira.workflow_transition.request", { issue_key: issueKey, target_status: "To Do", reason: "Preview only", comment: "Preview only" }],
      ["jira.sprint_move.request", { issue_keys: [issueKey], target_sprint: "preview-sprint", reason: "Preview only" }],
      ["jira.assignee_change.request", { issue_key: issueKey, assignee_ref: "preview-account-id", reason: "Preview only" }],
      ["jira.issue_link.request", { source_issue_key: issueKey, target_issue_key: secondIssueKey, link_type: "Relates", reason: "Preview only" }],
    ];
    for (const [id, parameters] of previews) {
      const result = await backendAdapter.execute(capability(id), plan(parameters), parameters, {});
      expect(result.execution_status).toBe("prepared");
      expect(result.mutation_performed).toBe(false);
    }
  });
});
