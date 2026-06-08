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

const githubToken = () => process.env.GITHUB_TOKEN?.trim() || null;

function csvEnv(name: string): Set<string> {
  return new Set((process.env[name] ?? "").split(",").map((item) => item.trim().toLowerCase()).filter(Boolean));
}

function repoAllowed(owner: string, repo: string): boolean {
  const key = `${owner}/${repo}`.toLowerCase();
  const blocked = csvEnv("ANIP_GITHUB_BLOCKED_REPOS");
  const allowed = csvEnv("ANIP_GITHUB_ALLOWED_REPOS");
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

async function githubRequest(method: string, path: string, token: string, body?: Record<string, unknown>): Promise<Record<string, unknown>> {
  const response = await fetch(`https://api.github.com${path}`, {
    method,
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      "User-Agent": "anip-github-fronting-showcase",
      "X-GitHub-Api-Version": "2022-11-28",
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await response.text();
  const payload = text ? JSON.parse(text) as Record<string, unknown> : {};
  if (!response.ok) return { error: "github_http_error", status: response.status, detail: payload };
  return payload;
}

function metadata(capability: GeneratedCapabilityRuntimeMetadata, plan: BackendInvocationPlan): Record<string, unknown> {
  return {
    capability_id: capability.capability_id,
    selected_backend: plan.selected_binding,
    semantic_input: plan.semantic_input,
  };
}

function restricted(capability: GeneratedCapabilityRuntimeMetadata, plan: BackendInvocationPlan, owner: string, repo: string): Record<string, unknown> {
  return {
    execution_status: "restricted",
    ...metadata(capability, plan),
    repository: { owner, repo },
    reason: "GitHub repository is outside the configured ANIP repository policy.",
  };
}

function mutationEnabled(context: GeneratedBackendInvocationContext): boolean {
  return process.env.ANIP_GITHUB_ALLOW_MUTATION === "true" && Boolean(context.approvalGrant);
}

function repoSummary(repoPayload: Record<string, unknown>): Record<string, unknown> {
  const owner = repoPayload.owner as Record<string, unknown> | undefined;
  return {
    owner: owner?.login,
    repo: repoPayload.name,
    default_branch: repoPayload.default_branch,
    private: repoPayload.private,
    html_url: repoPayload.html_url,
  };
}

function preview(
  capability: GeneratedCapabilityRuntimeMetadata,
  plan: BackendInvocationPlan,
  action: string,
  path: string,
  body: Record<string, unknown>,
  repoPayload: Record<string, unknown>,
): Record<string, unknown> {
  return {
    execution_status: "prepared",
    ...metadata(capability, plan),
    approval_required: true,
    mutation_performed: false,
    github_action: action,
    github_metadata: repoSummary(repoPayload),
    github_request: { method: "POST", path, body },
    note: "Prepared a GitHub request payload. No GitHub mutation was performed.",
  };
}

async function repoMetadata(
  capability: GeneratedCapabilityRuntimeMetadata,
  plan: BackendInvocationPlan,
  params: Record<string, unknown>,
  token: string,
): Promise<{ owner: string; repo: string; repoPayload?: Record<string, unknown>; error?: Record<string, unknown> }> {
  const owner = String(params.owner ?? "").trim();
  const repo = String(params.repo ?? "").trim();
  if (!repoAllowed(owner, repo)) return { owner, repo, error: restricted(capability, plan, owner, repo) };
  const repoPayload = await githubRequest("GET", `/repos/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}`, token);
  if (repoPayload.error) return { owner, repo, error: { execution_status: "backend_error", ...metadata(capability, plan), github_error: repoPayload } };
  return { owner, repo, repoPayload };
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
      const token = githubToken();
      if (!token) return { execution_status: "backend_error", ...metadata(capability, plan), github_error: { error: "missing_github_token" } };
      if (capability.capability_id === "github.repo.search_context") return searchRepositoryContext(capability, plan, adapterInput, token);
      if (capability.capability_id === "github.issue.prepare") return prepareOrCreateIssue(capability, plan, adapterInput, token, context);
      if (capability.capability_id === "github.pr.comment.prepare") return preparePullRequestComment(capability, plan, adapterInput, token, context);
      if (capability.capability_id === "github.workflow.dispatch.request") return prepareWorkflowDispatch(capability, plan, adapterInput, token, context);
      if (capability.capability_id === "github.release_notes.prepare") return prepareReleaseNotes(capability, plan, adapterInput, token);
      return { execution_status: "backend_execution_stub", ...metadata(capability, plan) };
    },
  };
}

async function searchRepositoryContext(
  capability: GeneratedCapabilityRuntimeMetadata,
  plan: BackendInvocationPlan,
  params: Record<string, unknown>,
  token: string,
): Promise<Record<string, unknown>> {
  const owner = String(params.owner ?? "").trim();
  const repo = String(params.repo ?? "").trim();
  if (!repoAllowed(owner, repo)) return restricted(capability, plan, owner, repo);
  const query = String(params.query ?? "").trim();
  const limit = limitValue(params.limit);
  const githubQuery = `repo:${owner}/${repo} ${query}`.trim();
  const payload = await githubRequest("GET", `/search/issues?${new URLSearchParams({ q: githubQuery, per_page: String(limit) })}`, token);
  if (payload.error) return { execution_status: "backend_error", ...metadata(capability, plan), github_error: payload };
  const items = ((payload.items ?? []) as Record<string, unknown>[]).slice(0, limit).map((item) => ({
    number: item.number,
    title: item.title,
    state: item.state,
    html_url: item.html_url,
    kind: item.pull_request ? "pull_request" : "issue",
  }));
  return {
    execution_status: "completed",
    ...metadata(capability, plan),
    github_query: githubQuery,
    result: { items, count: items.length, total_count: payload.total_count },
  };
}

async function prepareOrCreateIssue(
  capability: GeneratedCapabilityRuntimeMetadata,
  plan: BackendInvocationPlan,
  params: Record<string, unknown>,
  token: string,
  context: GeneratedBackendInvocationContext,
): Promise<Record<string, unknown>> {
  const repo = await repoMetadata(capability, plan, params, token);
  if (repo.error) return repo.error;
  const body: Record<string, unknown> = { title: String(params.title ?? "").trim(), body: String(params.body ?? "").trim() };
  const labels = stringList(params.labels);
  const assignees = stringList(params.assignees);
  if (labels.length) body.labels = labels;
  if (assignees.length) body.assignees = assignees;
  const prepared = preview(capability, plan, "issues.create", `/repos/${repo.owner}/${repo.repo}/issues`, body, repo.repoPayload!);
  if (!mutationEnabled(context)) return prepared;
  const created = await githubRequest("POST", `/repos/${encodeURIComponent(repo.owner)}/${encodeURIComponent(repo.repo)}/issues`, token, body);
  if (created.error) return { ...prepared, execution_status: "backend_error", github_error: created };
  return {
    ...prepared,
    execution_status: "completed",
    approval_required: false,
    mutation_performed: true,
    created_issue: { number: created.number, html_url: created.html_url, state: created.state },
    note: "Created GitHub issue after the ANIP runtime validated and reserved an approval grant.",
  };
}

async function preparePullRequestComment(
  capability: GeneratedCapabilityRuntimeMetadata,
  plan: BackendInvocationPlan,
  params: Record<string, unknown>,
  token: string,
  context: GeneratedBackendInvocationContext,
): Promise<Record<string, unknown>> {
  const repo = await repoMetadata(capability, plan, params, token);
  if (repo.error) return repo.error;
  const pullNumber = String(params.pull_number ?? "").trim();
  const pull = await githubRequest("GET", `/repos/${encodeURIComponent(repo.owner)}/${encodeURIComponent(repo.repo)}/pulls/${encodeURIComponent(pullNumber)}`, token);
  if (pull.error) return { execution_status: "backend_error", ...metadata(capability, plan), github_error: pull };
  const body = { body: `[${String(params.comment_purpose ?? "triage_update").trim()}] ${String(params.context ?? "").trim()}`.trim() };
  const prepared = preview(capability, plan, "issues.createComment", `/repos/${repo.owner}/${repo.repo}/issues/${pullNumber}/comments`, body, repo.repoPayload!);
  prepared.pull_request = { number: pull.number, title: pull.title, state: pull.state };
  if (!mutationEnabled(context)) return prepared;
  const posted = await githubRequest("POST", `/repos/${encodeURIComponent(repo.owner)}/${encodeURIComponent(repo.repo)}/issues/${encodeURIComponent(pullNumber)}/comments`, token, body);
  if (posted.error) return { ...prepared, execution_status: "backend_error", github_error: posted };
  return { ...prepared, execution_status: "completed", approval_required: false, mutation_performed: true, posted_comment: { id: posted.id, html_url: posted.html_url } };
}

async function prepareWorkflowDispatch(
  capability: GeneratedCapabilityRuntimeMetadata,
  plan: BackendInvocationPlan,
  params: Record<string, unknown>,
  token: string,
  context: GeneratedBackendInvocationContext,
): Promise<Record<string, unknown>> {
  const repo = await repoMetadata(capability, plan, params, token);
  if (repo.error) return repo.error;
  const workflowId = String(params.workflow_id ?? "").trim();
  const body = { ref: String(params.ref ?? "").trim(), inputs: params.inputs ?? {} };
  const prepared = preview(capability, plan, "actions.createWorkflowDispatch", `/repos/${repo.owner}/${repo.repo}/actions/workflows/${workflowId}/dispatches`, body, repo.repoPayload!);
  if (!mutationEnabled(context)) return prepared;
  const dispatched = await githubRequest("POST", `/repos/${encodeURIComponent(repo.owner)}/${encodeURIComponent(repo.repo)}/actions/workflows/${encodeURIComponent(workflowId)}/dispatches`, token, body);
  if (dispatched.error) return { ...prepared, execution_status: "backend_error", github_error: dispatched };
  return { ...prepared, execution_status: "completed", approval_required: false, mutation_performed: true, dispatched_workflow: { workflow_id: workflowId, ref: body.ref } };
}

async function prepareReleaseNotes(
  capability: GeneratedCapabilityRuntimeMetadata,
  plan: BackendInvocationPlan,
  params: Record<string, unknown>,
  token: string,
): Promise<Record<string, unknown>> {
  const repo = await repoMetadata(capability, plan, params, token);
  if (repo.error) return repo.error;
  return {
    execution_status: "completed",
    ...metadata(capability, plan),
    result: {
      title: `Release notes for ${repo.owner}/${repo.repo} ${String(params.range ?? "").trim()}`,
      audience: String(params.audience ?? "internal").trim(),
      repository: repoSummary(repo.repoPayload!),
      range: String(params.range ?? "").trim(),
      sections: [
        { title: "Highlights", items: ["Review bounded GitHub context before publishing release notes."] },
        { title: "Governance", items: ["This capability drafts content only and does not create a GitHub release."] },
      ],
    },
    mutation_performed: false,
  };
}

export const backendAdapter = createDefaultBackendAdapter();
