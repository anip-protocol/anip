import type { BackendInvocationPlan, GeneratedCapabilityRuntimeMetadata } from "../generated/runtime-target.js";

export type GeneratedBackendInvocationContext = {
  rootPrincipal?: string;
};

export interface GeneratedBackendAdapter {
  execute(capability: GeneratedCapabilityRuntimeMetadata, plan: BackendInvocationPlan, adapterInput: Record<string, unknown>, context: GeneratedBackendInvocationContext): Promise<Record<string, unknown>>;
}

type JiraConfig = {
  baseUrl: string;
  email: string;
  token: string;
};

function jiraConfig(): JiraConfig | null {
  const baseUrl = (process.env.JIRA_BASE_URL ?? "").replace(/\/+$/, "");
  const email = process.env.JIRA_EMAIL ?? "";
  const token = process.env.JIRA_API_TOKEN ?? "";
  if (!baseUrl || !email || !token) return null;
  return { baseUrl, email, token };
}

function authHeaders(config: JiraConfig): Record<string, string> {
  return {
    Accept: "application/json",
    Authorization: `Basic ${Buffer.from(`${config.email}:${config.token}`).toString("base64")}`,
  };
}

async function jiraJson(config: JiraConfig, method: string, path: string, query?: Record<string, string>, body?: Record<string, unknown>): Promise<Record<string, unknown>> {
  const url = new URL(`${config.baseUrl}${path}`);
  for (const [key, value] of Object.entries(query ?? {})) url.searchParams.set(key, value);
  const response = await fetch(url, {
    method,
    headers: body ? { ...authHeaders(config), "Content-Type": "application/json" } : authHeaders(config),
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await response.text();
  const payload = text ? JSON.parse(text) as Record<string, unknown> : {};
  if (!response.ok) return { error: "jira_http_error", status: response.status, detail: payload };
  return payload;
}

function boundedLimit(value: unknown, defaultValue = 25, maximum = 50): number {
  const parsed = Number.parseInt(String(value ?? ""), 10);
  const limit = Number.isFinite(parsed) ? parsed : defaultValue;
  return Math.max(1, Math.min(limit, maximum));
}

function safeJqlValue(value: unknown): string {
  return String(value ?? "").trim().replace(/\\/g, "\\\\").replace(/"/g, '\\"');
}

function listValue(value: unknown): string[] {
  const raw = Array.isArray(value) ? value : typeof value === "string" && value.trim() ? value.split(",") : [];
  const result: string[] = [];
  for (const item of raw) {
    const text = String(item).trim();
    if (text && !result.includes(text)) result.push(text);
  }
  return result;
}

function safeLabel(value: unknown): string {
  return String(value ?? "").trim().toLowerCase().replace(/[^a-z0-9_.-]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 255);
}

function labels(value: unknown): string[] {
  return listValue(value).map(safeLabel).filter(Boolean);
}

function adfDoc(text: unknown): Record<string, unknown> {
  return {
    type: "doc",
    version: 1,
    content: [{ type: "paragraph", content: [{ type: "text", text: String(text ?? "").trim() }] }],
  };
}

function plainTextFromAdf(value: unknown): string {
  const parts: string[] = [];
  const walk = (node: unknown): void => {
    if (Array.isArray(node)) {
      for (const child of node) walk(child);
      return;
    }
    if (!node || typeof node !== "object") return;
    const record = node as Record<string, unknown>;
    if (record.type === "text" && typeof record.text === "string") parts.push(record.text);
    walk(record.content);
  };
  walk(value);
  return parts.map((part) => part.trim()).filter(Boolean).join(" ");
}

function issueSummary(issue: Record<string, unknown>): Record<string, unknown> {
  const fields = (issue.fields ?? {}) as Record<string, unknown>;
  return {
    key: issue.key,
    summary: fields.summary,
    status: (fields.status as Record<string, unknown> | undefined)?.name,
    issue_type: (fields.issuetype as Record<string, unknown> | undefined)?.name,
    project_key: (fields.project as Record<string, unknown> | undefined)?.key,
    assignee: (fields.assignee as Record<string, unknown> | undefined)?.displayName,
    priority: (fields.priority as Record<string, unknown> | undefined)?.name,
  };
}

function issueQueryJql(projectKey: string, queryText: string): string {
  let jql = `project = "${safeJqlValue(projectKey)}"`;
  if (queryText) jql += ` AND text ~ "${safeJqlValue(queryText)}"`;
  return `${jql} ORDER BY updated DESC`;
}

async function searchIssues(config: JiraConfig, jql: string, limit: number, fields: string): Promise<Record<string, unknown>> {
  return jiraJson(config, "GET", "/rest/api/3/search/jql", { jql, maxResults: String(limit), fields });
}

function priorityForSeverity(value: unknown): string {
  const severity = String(value ?? "").toLowerCase();
  if (severity === "sev1" || severity === "sev2") return "High";
  if (severity === "sev4") return "Low";
  return "Medium";
}

function previewResult(capability: GeneratedCapabilityRuntimeMetadata, plan: BackendInvocationPlan, action: string, request: Record<string, unknown>, metadata: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    execution_status: "prepared",
    capability_id: capability.capability_id,
    selected_backend: plan.selected_binding,
    semantic_input: plan.semantic_input,
    approval_required: capability.operation_type === "approval_gated" || capability.execution_posture === "prepare_only",
    mutation_performed: false,
    jira_action: action,
    jira_request_preview: request,
    jira_metadata: metadata,
    note: "Prepared a governed Jira request preview. No Jira mutation was performed.",
  };
}

function backendError(capability: GeneratedCapabilityRuntimeMetadata, plan: BackendInvocationPlan, payload: Record<string, unknown>): Record<string, unknown> {
  return { execution_status: "backend_error", capability_id: capability.capability_id, selected_backend: plan.selected_binding, semantic_input: plan.semantic_input, jira_error: payload };
}

export function createDefaultBackendAdapter(): GeneratedBackendAdapter {
  return {
    async execute(capability, plan, adapterInput, _context) {
      if (plan.unresolved_required_backend_inputs.length > 0) {
        return { execution_status: "backend_input_incomplete", capability_id: capability.capability_id, backend_input_contract: plan.backend_input_contract, unresolved_required_backend_inputs: plan.unresolved_required_backend_inputs };
      }
      const config = jiraConfig();
      const params = adapterInput;
      switch (capability.capability_id) {
        case "jira.backlog.search_context": {
          const projectKey = String(params.project_key ?? "").trim();
          const queryText = String(params.query ?? "").trim();
          let jql = issueQueryJql(projectKey, queryText);
          if (params.issue_type) jql += ` AND issuetype = "${safeJqlValue(params.issue_type)}"`;
          if (params.status) jql += ` AND status = "${safeJqlValue(params.status)}"`;
          if (!config) return { execution_status: "backend_not_configured", capability_id: capability.capability_id, selected_backend: plan.selected_binding, semantic_input: plan.semantic_input, jql_preview: jql };
          const payload = await searchIssues(config, jql, boundedLimit(params.limit), "summary,status,issuetype,project,assignee,priority");
          if (payload.error) return backendError(capability, plan, payload);
          const issues = ((payload.issues as Record<string, unknown>[] | undefined) ?? []).map(issueSummary);
          return { execution_status: "completed", capability_id: capability.capability_id, selected_backend: plan.selected_binding, semantic_input: plan.semantic_input, jql, result: { issues, count: issues.length, is_last: payload.isLast } };
        }
        case "jira.issue.get_context": {
          const issueKey = String(params.issue_key ?? "").trim();
          if (!config) return { execution_status: "backend_not_configured", capability_id: capability.capability_id, selected_backend: plan.selected_binding, semantic_input: plan.semantic_input, path_preview: `/rest/api/3/issue/${issueKey}` };
          const payload = await jiraJson(config, "GET", `/rest/api/3/issue/${encodeURIComponent(issueKey)}`, { fields: "summary,status,issuetype,project,assignee,priority,description" });
          if (payload.error) return backendError(capability, plan, payload);
          const result = issueSummary(payload);
          const description = (payload.fields as Record<string, unknown> | undefined)?.description;
          if (description) result.description_excerpt = plainTextFromAdf(description).slice(0, 500);
          if (String(params.include_comments ?? "").toLowerCase() === "true") {
            const comments = await jiraJson(config, "GET", `/rest/api/3/issue/${encodeURIComponent(issueKey)}/comment`, { maxResults: "5" });
            if (!comments.error) result.comments = ((comments.comments as Record<string, unknown>[] | undefined) ?? []).map((comment) => ({
              author: (comment.author as Record<string, unknown> | undefined)?.displayName,
              body_excerpt: plainTextFromAdf(comment.body).slice(0, 500),
              created: comment.created,
            }));
          }
          return { execution_status: "completed", capability_id: capability.capability_id, selected_backend: plan.selected_binding, semantic_input: plan.semantic_input, result };
        }
        case "jira.release_notes.prepare": {
          const projectKey = String(params.project_key ?? "").trim();
          const releaseRef = String(params.release_ref ?? "").trim();
          const audience = String(params.audience ?? "internal").trim();
          let jql = releaseRef.toLowerCase() === "unversioned" ? `project = "${safeJqlValue(projectKey)}" AND fixVersion is EMPTY` : `project = "${safeJqlValue(projectKey)}" AND fixVersion = "${safeJqlValue(releaseRef)}"`;
          if (params.issue_query) jql += ` AND text ~ "${safeJqlValue(params.issue_query)}"`;
          jql += " ORDER BY priority DESC, updated DESC";
          let issues: Record<string, unknown>[] = [];
          if (config) {
            const payload = await searchIssues(config, jql, boundedLimit(params.limit, 20, 50), "summary,status,issuetype,project");
            if (payload.error) return backendError(capability, plan, payload);
            issues = ((payload.issues as Record<string, unknown>[] | undefined) ?? []).map(issueSummary);
          }
          const draft = issues.length ? [`Release ${releaseRef} notes for ${audience}`, "", ...issues.map((issue) => `- ${issue.key}: ${issue.summary} (${issue.status})`)].join("\n") : `Release ${releaseRef} notes for ${audience}\n\nNo matching Jira issues were returned for the bounded query.`;
          return { execution_status: "prepared", capability_id: capability.capability_id, selected_backend: plan.selected_binding, semantic_input: plan.semantic_input, jql, result: { audience, issue_count: issues.length, issues, draft }, note: "Prepared release notes only. No Jira mutation or publication was performed." };
        }
        case "jira.incident_bug.prepare":
        case "jira.story.prepare": {
          const issueTypeName = capability.capability_id === "jira.incident_bug.prepare" ? "Bug" : "Story";
          const fields: Record<string, unknown> = { project: { key: params.project_key }, issuetype: { name: issueTypeName }, summary: String(params.summary ?? "").trim() };
          if (capability.capability_id === "jira.incident_bug.prepare") {
            fields.description = adfDoc(params.description);
            fields.priority = { name: priorityForSeverity(params.severity) };
          } else {
            fields.description = adfDoc(`Acceptance criteria:\n${params.acceptance_criteria ?? ""}`);
            if (params.priority) fields.priority = { name: String(params.priority).replace(/^./, (ch) => ch.toUpperCase()) };
          }
          const labelValues = labels(params.labels);
          if (labelValues.length) fields.labels = labelValues;
          return previewResult(capability, plan, "create_issue", { method: "POST", path: "/rest/api/3/issue", body: { fields } }, { project_key: params.project_key, requested_issue_type: issueTypeName });
        }
        case "jira.subtask.prepare": {
          const parentIssueKey = String(params.parent_issue_key ?? "").trim();
          const fields: Record<string, unknown> = { parent: { key: parentIssueKey }, issuetype: { name: "Sub-task" }, summary: String(params.summary ?? "").trim(), description: adfDoc(params.description) };
          if (config) {
            const parent = await jiraJson(config, "GET", `/rest/api/3/issue/${encodeURIComponent(parentIssueKey)}`, { fields: "project" });
            const projectKey = ((parent.fields as Record<string, unknown> | undefined)?.project as Record<string, unknown> | undefined)?.key;
            if (projectKey) fields.project = { key: projectKey };
            if (parent.id) fields.parent = { id: parent.id };
          }
          return previewResult(capability, plan, "create_subtask", { method: "POST", path: "/rest/api/3/issue", body: { fields } }, { parent_issue_key: parentIssueKey });
        }
        case "jira.customer_escalation.comment.prepare":
          return previewResult(capability, plan, "add_comment", { method: "POST", path: `/rest/api/3/issue/${params.issue_key}/comment`, body: { body: adfDoc(`[${params.comment_purpose}] ${params.context ?? ""}`), visibility: params.visibility ?? "internal" } }, { issue_key: params.issue_key, visibility: params.visibility ?? "internal", comment_purpose: params.comment_purpose });
        case "jira.workflow_transition.request":
          return previewResult(capability, plan, "transition_issue", { method: "POST", path: `/rest/api/3/issue/${params.issue_key}/transitions`, body: { transition: { id: params.target_status }, ...(params.comment ? { update: { comment: [{ add: { body: adfDoc(params.comment) } }] } } : {}) } }, { issue_key: params.issue_key, target_status: params.target_status });
        case "jira.sprint_move.request":
          return previewResult(capability, plan, "move_issues_to_sprint", { method: "POST", path: `/rest/agile/1.0/sprint/${params.target_sprint}/issue`, body: { issues: listValue(params.issue_keys) } }, { issue_keys: listValue(params.issue_keys), target_sprint: params.target_sprint });
        case "jira.assignee_change.request":
          return previewResult(capability, plan, "assign_issue", { method: "PUT", path: `/rest/api/3/issue/${params.issue_key}/assignee`, body: { accountId: params.assignee_ref } }, { issue_key: params.issue_key, assignee_ref: params.assignee_ref });
        case "jira.issue_link.request":
          return previewResult(capability, plan, "link_issues", { method: "POST", path: "/rest/api/3/issueLink", body: { type: { name: params.link_type }, inwardIssue: { key: params.source_issue_key }, outwardIssue: { key: params.target_issue_key }, comment: { body: adfDoc(params.reason) } } }, { requested_link_type: params.link_type });
        default:
          return { execution_status: "backend_execution_stub", capability_id: capability.capability_id, selected_backend: plan.selected_binding, semantic_input: plan.semantic_input, backend_input_contract: plan.backend_input_contract, note: "No Jira custom handler is registered for this capability." };
      }
    },
  };
}

export const backendAdapter = createDefaultBackendAdapter();
