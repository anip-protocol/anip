import type { BackendInvocationPlan, GeneratedCapabilityRuntimeMetadata } from "../generated/runtime-target.js";

export type GeneratedBackendInvocationContext = {
  rootPrincipal?: string;
  approvalGrant?: string | null;
};

export interface GeneratedBackendAdapter {
  execute(
    capability: GeneratedCapabilityRuntimeMetadata,
    plan: BackendInvocationPlan,
    adapterInput: Record<string, unknown>,
    context: GeneratedBackendInvocationContext,
  ): Promise<Record<string, unknown>>;
}

const gitlabToken = () => process.env.GITLAB_TOKEN?.trim() || null;
const apiBase = () => (process.env.GITLAB_API_BASE ?? "https://gitlab.com/api/v4").replace(/\/+$/, "");

function csvEnv(name: string): Set<string> {
  return new Set((process.env[name] ?? "").split(",").map((item) => item.trim().toLowerCase()).filter(Boolean));
}

function projectId(params: Record<string, unknown>): string {
  const explicit = String(params.project_id ?? "").trim();
  if (explicit) return explicit;
  const namespace = String(params.namespace ?? "").trim().replace(/^\/+|\/+$/g, "");
  const project = String(params.project ?? "").trim().replace(/^\/+|\/+$/g, "");
  return namespace && project ? `${namespace}/${project}` : "";
}

function projectAllowed(project: string): boolean {
  const key = project.toLowerCase();
  const blocked = csvEnv("ANIP_GITLAB_BLOCKED_PROJECTS");
  const allowed = csvEnv("ANIP_GITLAB_ALLOWED_PROJECTS");
  if (blocked.has(key)) return false;
  return allowed.size === 0 || allowed.has(key);
}

function limitValue(value: unknown, fallback = 20, max = 50): number {
  const parsed = Number.parseInt(String(value ?? ""), 10);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.max(1, Math.min(parsed, max));
}

function stringList(value: unknown): string[] {
  const raw = Array.isArray(value) ? value : typeof value === "string" && value.trim() ? value.split(",") : [];
  return Array.from(new Set(raw.map((item) => String(item).trim()).filter(Boolean)));
}

async function gitlabRequest(method: string, path: string, token: string, body?: Record<string, unknown>): Promise<Record<string, unknown> | Record<string, unknown>[]> {
  const response = await fetch(`${apiBase()}${path}`, {
    method,
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "PRIVATE-TOKEN": token,
      "User-Agent": "anip-gitlab-fronting-showcase",
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await response.text();
  const payload = text ? JSON.parse(text) as Record<string, unknown> | Record<string, unknown>[] : {};
  if (!response.ok) return { error: "gitlab_http_error", status: response.status, detail: payload };
  return payload;
}

function metadata(capability: GeneratedCapabilityRuntimeMetadata, plan: BackendInvocationPlan): Record<string, unknown> {
  return {
    capability_id: capability.capability_id,
    selected_backend: plan.selected_binding,
    semantic_input: plan.semantic_input,
  };
}

function restricted(capability: GeneratedCapabilityRuntimeMetadata, plan: BackendInvocationPlan, project: string): Record<string, unknown> {
  return {
    execution_status: "restricted",
    ...metadata(capability, plan),
    project_id: project,
    reason: "GitLab project is outside the configured ANIP project policy.",
  };
}

function mutationEnabled(context: GeneratedBackendInvocationContext): boolean {
  return process.env.ANIP_GITLAB_ALLOW_MUTATION === "true" && Boolean(context.approvalGrant);
}

function projectSummary(project: Record<string, unknown>): Record<string, unknown> {
  return {
    id: project.id,
    path_with_namespace: project.path_with_namespace,
    default_branch: project.default_branch,
    visibility: project.visibility,
    web_url: project.web_url,
  };
}

function preview(
  capability: GeneratedCapabilityRuntimeMetadata,
  plan: BackendInvocationPlan,
  action: string,
  path: string,
  body: Record<string, unknown>,
  project: Record<string, unknown>,
): Record<string, unknown> {
  return {
    execution_status: "prepared",
    ...metadata(capability, plan),
    approval_required: true,
    mutation_performed: false,
    gitlab_action: action,
    gitlab_metadata: projectSummary(project),
    gitlab_request: { method: "POST", path, body },
    note: "Prepared a GitLab request payload. No GitLab mutation was performed.",
  };
}

async function projectMetadata(
  capability: GeneratedCapabilityRuntimeMetadata,
  plan: BackendInvocationPlan,
  params: Record<string, unknown>,
  token: string,
): Promise<{ project: string; payload?: Record<string, unknown>; error?: Record<string, unknown> }> {
  const project = projectId(params);
  if (!projectAllowed(project)) return { project, error: restricted(capability, plan, project) };
  const payload = await gitlabRequest("GET", `/projects/${encodeURIComponent(project)}`, token);
  if (!Array.isArray(payload) && payload.error) return { project, error: { execution_status: "backend_error", ...metadata(capability, plan), gitlab_error: payload } };
  return { project, payload: payload as Record<string, unknown> };
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
      const token = gitlabToken();
      if (!token) return { execution_status: "backend_error", ...metadata(capability, plan), gitlab_error: { error: "missing_gitlab_token" } };
      if (capability.capability_id === "gitlab.project.search_context") return searchProjectContext(capability, plan, adapterInput, token);
      if (capability.capability_id === "gitlab.issue.prepare") return prepareOrCreateIssue(capability, plan, adapterInput, token, context);
      if (capability.capability_id === "gitlab.mr.comment.prepare") return prepareMergeRequestComment(capability, plan, adapterInput, token, context);
      if (capability.capability_id === "gitlab.pipeline.trigger.request") return preparePipelineTrigger(capability, plan, adapterInput, token);
      if (capability.capability_id === "gitlab.release_notes.prepare") return prepareReleaseNotes(capability, plan, adapterInput, token);
      return { execution_status: "backend_execution_stub", ...metadata(capability, plan) };
    },
  };
}

async function searchProjectContext(
  capability: GeneratedCapabilityRuntimeMetadata,
  plan: BackendInvocationPlan,
  params: Record<string, unknown>,
  token: string,
): Promise<Record<string, unknown>> {
  const project = projectId(params);
  if (!projectAllowed(project)) return restricted(capability, plan, project);
  const query = String(params.query ?? "").trim();
  const limit = limitValue(params.limit);
  const encoded = new URLSearchParams({ search: query, per_page: String(limit) });
  const issues = await gitlabRequest("GET", `/projects/${encodeURIComponent(project)}/issues?${encoded}`, token);
  const mergeRequests = await gitlabRequest("GET", `/projects/${encodeURIComponent(project)}/merge_requests?${encoded}`, token);
  if (!Array.isArray(issues) && issues.error) return { execution_status: "backend_error", ...metadata(capability, plan), gitlab_error: issues };
  if (!Array.isArray(mergeRequests) && mergeRequests.error) return { execution_status: "backend_error", ...metadata(capability, plan), gitlab_error: mergeRequests };
  const items = (issues as Record<string, unknown>[]).slice(0, limit).map((item) => ({
    kind: "issue",
    iid: item.iid,
    title: item.title,
    state: item.state,
    web_url: item.web_url,
  }));
  for (const item of (mergeRequests as Record<string, unknown>[]).slice(0, Math.max(0, limit - items.length))) {
    items.push({ kind: "merge_request", iid: item.iid, title: item.title, state: item.state, web_url: item.web_url });
  }
  return {
    execution_status: "completed",
    ...metadata(capability, plan),
    gitlab_query: query,
    result: { items, count: items.length, project_id: project },
  };
}

async function prepareOrCreateIssue(
  capability: GeneratedCapabilityRuntimeMetadata,
  plan: BackendInvocationPlan,
  params: Record<string, unknown>,
  token: string,
  context: GeneratedBackendInvocationContext,
): Promise<Record<string, unknown>> {
  const project = await projectMetadata(capability, plan, params, token);
  if (project.error) return project.error;
  const body: Record<string, unknown> = {
    title: String(params.title ?? "").trim(),
    description: String(params.body ?? params.description ?? "").trim(),
  };
  const labels = stringList(params.labels);
  if (labels.length) body.labels = labels.join(",");
  const prepared = preview(capability, plan, "issues.create", `/projects/${project.project}/issues`, body, project.payload!);
  if (!mutationEnabled(context)) return prepared;
  const created = await gitlabRequest("POST", `/projects/${encodeURIComponent(project.project)}/issues`, token, body);
  if (!Array.isArray(created) && created.error) return { ...prepared, execution_status: "backend_error", gitlab_error: created };
  const issue = created as Record<string, unknown>;
  return {
    ...prepared,
    execution_status: "completed",
    approval_required: false,
    mutation_performed: true,
    created_issue: { iid: issue.iid, web_url: issue.web_url, state: issue.state },
    note: "Created GitLab issue after the ANIP runtime validated and reserved an approval grant.",
  };
}

async function prepareMergeRequestComment(
  capability: GeneratedCapabilityRuntimeMetadata,
  plan: BackendInvocationPlan,
  params: Record<string, unknown>,
  token: string,
  context: GeneratedBackendInvocationContext,
): Promise<Record<string, unknown>> {
  const project = await projectMetadata(capability, plan, params, token);
  if (project.error) return project.error;
  const iid = String(params.merge_request_iid ?? "").trim();
  const mr = await gitlabRequest("GET", `/projects/${encodeURIComponent(project.project)}/merge_requests/${encodeURIComponent(iid)}`, token);
  if (!Array.isArray(mr) && mr.error) return { execution_status: "backend_error", ...metadata(capability, plan), gitlab_error: mr };
  const body = { body: `[${String(params.comment_purpose ?? "triage_update").trim()}] ${String(params.context ?? "").trim()}`.trim() };
  const prepared = preview(capability, plan, "merge_requests.createNote", `/projects/${project.project}/merge_requests/${iid}/notes`, body, project.payload!);
  prepared.merge_request = { iid: (mr as Record<string, unknown>).iid, title: (mr as Record<string, unknown>).title, state: (mr as Record<string, unknown>).state };
  if (!mutationEnabled(context)) return prepared;
  const posted = await gitlabRequest("POST", `/projects/${encodeURIComponent(project.project)}/merge_requests/${encodeURIComponent(iid)}/notes`, token, body);
  if (!Array.isArray(posted) && posted.error) return { ...prepared, execution_status: "backend_error", gitlab_error: posted };
  return { ...prepared, execution_status: "completed", approval_required: false, mutation_performed: true, posted_comment: { id: (posted as Record<string, unknown>).id } };
}

async function preparePipelineTrigger(
  capability: GeneratedCapabilityRuntimeMetadata,
  plan: BackendInvocationPlan,
  params: Record<string, unknown>,
  token: string,
): Promise<Record<string, unknown>> {
  const project = await projectMetadata(capability, plan, params, token);
  if (project.error) return project.error;
  const body = { ref: String(params.ref ?? "").trim(), variables: params.variables ?? {}, purpose: String(params.pipeline_purpose ?? "").trim() };
  return preview(capability, plan, "pipeline.trigger", `/projects/${project.project}/pipeline`, body, project.payload!);
}

async function prepareReleaseNotes(
  capability: GeneratedCapabilityRuntimeMetadata,
  plan: BackendInvocationPlan,
  params: Record<string, unknown>,
  token: string,
): Promise<Record<string, unknown>> {
  const project = await projectMetadata(capability, plan, params, token);
  if (project.error) return project.error;
  const range = String(params.range ?? "").trim();
  return {
    execution_status: "completed",
    ...metadata(capability, plan),
    mutation_performed: false,
    result: {
      title: `Release notes for ${project.payload!.path_with_namespace ?? project.project} ${range}`,
      audience: String(params.audience ?? "internal").trim(),
      project: projectSummary(project.payload!),
      range,
      sections: [
        { title: "Highlights", items: ["Review bounded GitLab context before publishing release notes."] },
        { title: "Governance", items: ["This capability drafts content only and does not create a GitLab release."] },
      ],
    },
  };
}

export const backendAdapter = createDefaultBackendAdapter();
