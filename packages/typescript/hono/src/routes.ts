import { Hono } from "hono";
import type { ContentfulStatusCode } from "hono/utils/http-status";
import type { ANIPService, Issuer } from "@anip-dev/service";
import { ANIPError } from "@anip-dev/service";
import { IssueApprovalGrantRequest, failureStatusCode } from "@anip-dev/core";

export async function mountAnip(
  app: Hono,
  service: ANIPService,
  opts?: { prefix?: string; healthEndpoint?: boolean },
): Promise<{ shutdown: () => Promise<void>; stop: () => void }> {
  const p = opts?.prefix ?? "";

  // --- Discovery & Identity ---
  app.get(`${p}/.well-known/anip`, (c) => {
    const baseUrl = new URL(c.req.url).origin;
    return c.json(service.getDiscovery({ baseUrl }));
  });

  app.get(`${p}/.well-known/jwks.json`, async (c) => {
    const jwks = await service.getJwks();
    return c.json(jwks);
  });

  app.get(`${p}/anip/manifest`, async (c) => {
    const [bodyBytes, signature] = await service.getSignedManifest();
    return new Response(new TextDecoder().decode(bodyBytes), {
      headers: {
        "Content-Type": "application/json",
        "X-ANIP-Signature": signature,
      },
    });
  });

  // --- Tokens ---
  app.post(`${p}/anip/tokens`, async (c) => {
    const issuer = await extractIssuer(c, service);
    if (!issuer) return authFailureTokenEndpoint(c);
    const body = await readJsonObject(c);
    if (typeof body === "string") return failureResponse(c, invalidParametersFailure(body));
    try {
      const result = await service.issueTokenAs(issuer, body);
      return c.json(result);
    } catch (e) {
      if (e instanceof ANIPError) return errorResponse(c, e);
      throw e;
    }
  });

  // --- Permissions ---
  app.post(`${p}/anip/permissions`, async (c) => {
    const result = await resolveToken(c, service);
    if (result === null) return authFailureJwtEndpoint(c);
    if (result instanceof ANIPError) return errorResponse(c, result);
    const token = result;
    return c.json(service.discoverPermissions(token));
  });

  // --- Invoke ---
  app.post(`${p}/anip/invoke/:capability`, async (c) => {
    const result = await resolveToken(c, service);
    if (result === null) return authFailureJwtEndpoint(c);
    if (result instanceof ANIPError) return errorResponse(c, result);
    const token = result;
    const capability = c.req.param("capability");
    const body = await readJsonObject(c);
    if (typeof body === "string") return failureResponse(c, invalidParametersFailure(body));
    const params = (body.parameters ?? body) as Record<string, unknown>;
    const clientReferenceId = (body.client_reference_id as string | undefined) ?? null;
    const taskId = (body.task_id as string | undefined) ?? null;
    const parentInvocationId = (body.parent_invocation_id as string | undefined) ?? null;
    const upstreamService = (body.upstream_service as string | undefined) ?? null;
    const budget = (body.budget as Record<string, unknown> | undefined) ?? null;
    const requestedEffects = Array.isArray(body.requested_effects)
      ? body.requested_effects
          .map((item: unknown) => String(item))
          .filter((item: string) => item.trim().length > 0)
      : [];
    // v0.23: continuation invocations supply approval_grant. session_id for
    // session_bound grants is read from the signed token, never the body.
    const approvalGrant = (body.approval_grant as string | undefined) ?? null;
    // One set of invocation options for the unary and the streaming call:
    // a streaming invocation goes through the same checks with the same
    // inputs (SPEC.md §6.3), plus `stream` and a progress sink.
    const invokeOpts = {
      clientReferenceId,
      taskId,
      parentInvocationId,
      upstreamService,
      budget,
      approvalGrant,
      requestedEffects,
    };

    if (!body.stream) {
      // Unary mode
      const result = await service.invoke(capability, token, params, invokeOpts);
      if (!result.success) {
        const failure = result.failure as Record<string, unknown>;
        return c.json(result, statusOf(failure?.type as string));
      }
      return c.json(result);
    }

    // Pre-validate streaming support (return JSON 400, not SSE)
    const decl = service.getCapabilityDeclaration(capability);
    const modes = (decl?.response_modes as string[]) ?? ["unary"];
    if (!modes.includes("streaming")) {
      const result = await service.invoke(capability, token, params, {
        ...invokeOpts,
        stream: true,
      });
      const failure = result.failure as Record<string, unknown>;
      return c.json(result, statusOf(failure?.type as string));
    }

    // True streaming: TransformStream bridges sink → Response body
    const { readable, writable } = new TransformStream();
    const writer = writable.getWriter();
    const encoder = new TextEncoder();

    (async () => {
      try {
        const result = await service.invoke(capability, token, params, {
          ...invokeOpts,
          stream: true,
          progressSink: async (event) => {
            const eventData = { ...event, timestamp: new Date().toISOString() };
            await writer.write(
              encoder.encode(`event: progress\ndata: ${JSON.stringify(eventData)}\n\n`),
            );
          },
        });

        const ts = new Date().toISOString();
        const terminalType = result.success ? "completed" : "failed";
        const terminalData: Record<string, unknown> = {
          invocation_id: result.invocation_id,
          client_reference_id: result.client_reference_id,
          timestamp: ts,
          success: result.success,
          ...(result.success
            ? { result: result.result, cost_actual: result.cost_actual }
            : { failure: result.failure }),
          ...(result.stream_summary ? { stream_summary: result.stream_summary } : {}),
        };
        await writer.write(
          encoder.encode(`event: ${terminalType}\ndata: ${JSON.stringify(terminalData)}\n\n`),
        );
        await writer.close();
      } catch (err) {
        const errorData = {
          timestamp: new Date().toISOString(),
          success: false,
          failure: { type: "internal_error", detail: "Internal error" },
        };
        await writer.write(
          encoder.encode(`event: failed\ndata: ${JSON.stringify(errorData)}\n\n`),
        );
        await writer.close();
      }
    })();

    return new Response(readable, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        Connection: "keep-alive",
      },
    });
  });

  // --- Graph ---
  app.get(`${p}/anip/graph/:capability`, async (c) => {
    const capability = c.req.param("capability");
    const graph = service.getCapabilityGraph(capability);
    if (!graph) {
      return failureResponse(c, {
        success: false,
        failure: {
          type: "not_found",
          detail: `Capability '${capability}' not found`,
          resolution: {
            action: "check_manifest",
            recovery_class: "revalidate_then_retry",
            requires: "Valid capability name from GET /anip/manifest",
            grantable_by: null,
            estimated_availability: null,
          },
          retry: false,
        },
      });
    }
    return c.json(graph);
  });

  // --- Approval Grants (v0.23 §4.9) ---
  // Validation order is security-relevant; see SPEC.md §4.9 line 1090:
  //   1. authn (already handled by resolveToken)
  //   2. parse body + schema-validate via IssueApprovalGrantRequest
  //   3. load ApprovalRequest
  //   4. check state (decided / expired) — BEFORE approver auth
  //   5. check approver authority against the loaded capability
  //   6. issueApprovalGrant (steps 6–11 of the spec)
  app.post(`${p}/anip/approval_grants`, async (c) => {
    const result = await resolveToken(c, service);
    if (result === null) return authFailureJwtEndpoint(c);
    if (result instanceof ANIPError) return errorResponse(c, result);
    const token = result;

    let rawBody: unknown;
    try {
      rawBody = await c.req.json();
    } catch {
      return failureResponse(c, invalidParametersFailure(BODY_NOT_JSON));
    }
    const parsed = IssueApprovalGrantRequest.safeParse(rawBody);
    if (!parsed.success) {
      return failureResponse(
        c,
        invalidParametersFailure(
          parsed.error.issues
            .map((i) => `${i.path.join(".")}: ${i.message}`)
            .join("; "),
        ),
      );
    }
    const { approval_request_id: approvalRequestId, grant_type: grantType } =
      parsed.data;

    const approvalRequest = await service.getApprovalRequest(approvalRequestId);
    if (approvalRequest === null) {
      return failureResponse(c, approvalRequestNotFoundFailure(approvalRequestId));
    }

    // SPEC.md §4.9 step 4: state check BEFORE approver authority. An
    // unauthorized token aimed at a decided/expired request must surface the
    // canonical state failure, not approver_not_authorized.
    const status = approvalRequest.status as string;
    const expiresAt = approvalRequest.expires_at as string | undefined;
    if (status !== "pending") {
      return failureResponse(c, approvalRequestAlreadyDecidedFailure(approvalRequestId, status));
    }
    if (expiresAt && expiresAt <= new Date().toISOString()) {
      return failureResponse(c, approvalRequestExpiredFailure(approvalRequestId));
    }

    // Approver authority check: token scope must contain approver:* OR
    // approver:<capability> for the request's capability.
    const targetCapability = approvalRequest.capability as string;
    const tokenScopes = token.scope ?? [];
    const acceptedScopes = new Set(["approver:*", `approver:${targetCapability}`]);
    if (!tokenScopes.some((s) => acceptedScopes.has(s))) {
      return failureResponse(c, approverNotAuthorizedFailure(targetCapability));
    }

    const approverPrincipal = {
      subject: token.subject,
      root_principal: token.root_principal,
    };
    try {
      const grant = await service.issueApprovalGrant(
        approvalRequestId,
        grantType,
        approverPrincipal,
        {
          expiresInSeconds: parsed.data.expires_in_seconds,
          maxUses: parsed.data.max_uses,
          sessionId: parsed.data.session_id,
        },
      );
      // SPEC.md §4.9: 200 response IS the signed ApprovalGrant — no wrapper.
      return c.json(grant);
    } catch (e) {
      if (e instanceof ANIPError) return errorResponse(c, e);
      throw e;
    }
  });

  // --- Audit ---
  app.post(`${p}/anip/audit`, async (c) => {
    const result = await resolveToken(c, service);
    if (result === null) return authFailureJwtEndpoint(c);
    if (result instanceof ANIPError) return errorResponse(c, result);
    const token = result;
    const url = new URL(c.req.url);
    const filters = {
      capability: url.searchParams.get("capability") ?? undefined,
      since: url.searchParams.get("since") ?? undefined,
      invocation_id: url.searchParams.get("invocation_id") ?? undefined,
      client_reference_id: url.searchParams.get("client_reference_id") ?? undefined,
      task_id: url.searchParams.get("task_id") ?? undefined,
      parent_invocation_id: url.searchParams.get("parent_invocation_id") ?? undefined,
      event_class: url.searchParams.get("event_class") ?? undefined,
      limit: parseInt(url.searchParams.get("limit") ?? "50", 10),
    };
    return c.json(await service.queryAudit(token, filters));
  });

  // --- Checkpoints ---
  app.get(`${p}/anip/checkpoints`, async (c) => {
    const url = new URL(c.req.url);
    const limit = parseInt(url.searchParams.get("limit") ?? "10", 10);
    return c.json(await service.getCheckpoints(limit));
  });

  app.get(`${p}/anip/checkpoints/:id`, async (c) => {
    const id = c.req.param("id");
    const url = new URL(c.req.url);
    const options = {
      include_proof: url.searchParams.get("include_proof") === "true",
      leaf_index: url.searchParams.get("leaf_index") ?? undefined,
      consistency_from: url.searchParams.get("consistency_from") ?? undefined,
    };
    const result = await service.getCheckpoint(id, options);
    if (!result) return failureResponse(c, {
      success: false,
      failure: {
        type: "not_found",
        detail: `Checkpoint ${id} not found`,
        resolution: {
          action: "revalidate_state",
          recovery_class: "revalidate_then_retry",
          requires: "GET /anip/checkpoints to find valid checkpoint IDs",
          grantable_by: null,
          estimated_availability: null,
        },
        retry: false,
      },
    });
    return c.json(result);
  });

  // --- Health ---
  if (opts?.healthEndpoint) {
    app.get("/-/health", (c) => c.json(service.getHealth()));
  }

  // --- Lifecycle ---
  await service.start();
  return {
    async shutdown() { await service.shutdown(); },
    stop() { service.stop(); },
  };
}

// --- Helpers ---

// The token endpoint accepts the bootstrap credential, or a delegation token
// issued by this service. A token authenticates as its holder, and the service
// refuses root issuance for such callers.
async function extractIssuer(c: any, service: ANIPService): Promise<Issuer | null> {
  const auth = c.req.header("authorization") ?? "";
  if (!auth.startsWith("Bearer ")) return null;
  return service.authenticateIssuer(auth.slice(7).trim());
}

async function resolveToken(c: any, service: ANIPService) {
  const auth = c.req.header("authorization") ?? "";
  if (!auth.startsWith("Bearer ")) return null;
  try {
    return await service.resolveBearerToken(auth.slice(7).trim());
  } catch (e) {
    if (e instanceof ANIPError) return e;
    throw e;
  }
}

/** The HTTP status of a failure type (SPEC.md §6.3 "HTTP Status Codes"). */
function statusOf(type?: string): ContentfulStatusCode {
  return failureStatusCode(type) as ContentfulStatusCode;
}

/** Answer with a failure body and the HTTP status of its type. */
function failureResponse(
  c: any,
  body: { success: boolean; failure: Record<string, unknown> & { type: string } },
) {
  return c.json(body, statusOf(body.failure.type));
}

const BODY_NOT_JSON = "request body must be JSON";
const BODY_NOT_AN_OBJECT = "request body must be a JSON object";

/**
 * Read the request body as a JSON object. Returns the detail of the
 * invalid_parameters failure when the body is not JSON or not an object.
 */
async function readJsonObject(c: any): Promise<Record<string, unknown> | string> {
  let body: unknown;
  try {
    body = await c.req.json();
  } catch {
    return BODY_NOT_JSON;
  }
  if (typeof body !== "object" || body === null || Array.isArray(body)) {
    return BODY_NOT_AN_OBJECT;
  }
  return body as Record<string, unknown>;
}

function authFailureTokenEndpoint(c: any) {
  return failureResponse(c, {
    success: false,
    failure: {
      type: "authentication_required",
      detail: "A valid API key is required to issue delegation tokens",
      resolution: {
        action: "provide_credentials",
        recovery_class: "retry_now",
        requires: "API key in Authorization header",
        grantable_by: null,
        estimated_availability: null,
      },
      retry: true,
    },
  });
}

function authFailureJwtEndpoint(c: any) {
  return failureResponse(c, {
    success: false,
    failure: {
      type: "authentication_required",
      detail: "A valid delegation token (JWT) is required in the Authorization header",
      resolution: {
        action: "request_new_delegation",
        recovery_class: "redelegation_then_retry",
        requires: "Bearer token from POST /anip/tokens",
        grantable_by: null,
        estimated_availability: null,
      },
      retry: true,
    },
  });
}

const DEFAULT_RESOLUTIONS: Record<string, Record<string, unknown>> = {
  invalid_token: {
    action: "request_new_delegation",
    recovery_class: "redelegation_then_retry",
    requires: "Valid JWT from POST /anip/tokens",
    grantable_by: null,
    estimated_availability: null,
  },
  scope_insufficient: {
    action: "request_broader_scope",
    recovery_class: "redelegation_then_retry",
    requires: "Token with required scope",
    grantable_by: null,
    estimated_availability: null,
  },
  unknown_capability: {
    action: "check_manifest",
    recovery_class: "revalidate_then_retry",
    requires: "Valid capability name from GET /anip/manifest",
    grantable_by: null,
    estimated_availability: null,
  },
  invalid_parameters: {
    action: "retry_now",
    recovery_class: "retry_now",
    requires: null,
    grantable_by: null,
    estimated_availability: null,
  },
};

function errorResponse(c: any, error: ANIPError) {
  const status = statusOf(error.errorType);
  const resolution = error.resolution ?? DEFAULT_RESOLUTIONS[error.errorType] ?? {
    action: "contact_service_owner",
    recovery_class: "terminal",
    requires: null,
    grantable_by: null,
    estimated_availability: null,
  };
  return c.json(
    {
      success: false,
      failure: {
        type: error.errorType,
        detail: error.detail,
        resolution,
        retry: error.retry,
      },
    },
    status,
  );
}

// --- Approval-grants endpoint failure shapes (v0.23 §4.9) ---

function invalidParametersFailure(detail: string) {
  return {
    success: false,
    failure: {
      type: "invalid_parameters",
      detail,
      resolution: {
        action: "retry_now",
        recovery_class: "retry_now",
        requires: null,
        grantable_by: null,
        estimated_availability: null,
      },
      retry: false,
    },
  };
}

function approvalRequestNotFoundFailure(approvalRequestId: string) {
  return {
    success: false,
    failure: {
      type: "approval_request_not_found",
      detail: `unknown approval_request_id=${JSON.stringify(approvalRequestId)}`,
      resolution: {
        action: "check_manifest",
        recovery_class: "revalidate_then_retry",
        requires: "Valid approval_request_id from a prior approval_required failure",
        grantable_by: null,
        estimated_availability: null,
      },
      retry: false,
    },
  };
}

function approvalRequestAlreadyDecidedFailure(
  approvalRequestId: string,
  status: string,
) {
  return {
    success: false,
    failure: {
      type: "approval_request_already_decided",
      detail: `approval_request_id=${JSON.stringify(approvalRequestId)} is in status=${JSON.stringify(status)}`,
      resolution: {
        action: "contact_service_owner",
        recovery_class: "terminal",
        requires: null,
        grantable_by: null,
        estimated_availability: null,
      },
      retry: false,
    },
  };
}

function approvalRequestExpiredFailure(approvalRequestId: string) {
  return {
    success: false,
    failure: {
      type: "approval_request_expired",
      detail: `approval_request_id=${JSON.stringify(approvalRequestId)} expired before issuance`,
      resolution: {
        action: "contact_service_owner",
        recovery_class: "terminal",
        requires: null,
        grantable_by: null,
        estimated_availability: null,
      },
      retry: false,
    },
  };
}

function approverNotAuthorizedFailure(targetCapability: string) {
  return {
    success: false,
    failure: {
      type: "approver_not_authorized",
      detail: `token lacks approver scope for capability ${JSON.stringify(targetCapability)}`,
      resolution: {
        action: "request_broader_scope",
        recovery_class: "redelegation_then_retry",
        requires: `scope += approver:${targetCapability}`,
        grantable_by: null,
        estimated_availability: null,
      },
      retry: false,
    },
  };
}
