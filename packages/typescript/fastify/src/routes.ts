import type { FastifyInstance, FastifyRequest, FastifyReply } from "fastify";
import type { ANIPService, Issuer } from "@anip-dev/service";
import { ANIPError } from "@anip-dev/service";
import { IssueApprovalGrantRequest, failureStatusCode } from "@anip-dev/core";

export async function mountAnip(
  app: FastifyInstance,
  service: ANIPService,
  opts?: { prefix?: string; healthEndpoint?: boolean },
): Promise<{ shutdown: () => Promise<void>; stop: () => void }> {
  const p = opts?.prefix ?? "";

  // --- Discovery & Identity ---
  app.get(`${p}/.well-known/anip`, async (req) => {
    const baseUrl = `${req.protocol}://${req.host}`;
    return service.getDiscovery({ baseUrl });
  });

  app.get(`${p}/.well-known/jwks.json`, async () => {
    return service.getJwks();
  });

  app.get(`${p}/anip/manifest`, async (_req, reply) => {
    const [bodyBytes, signature] = await service.getSignedManifest();
    return reply
      .header("Content-Type", "application/json")
      .header("X-ANIP-Signature", signature)
      .send(Buffer.from(bodyBytes));
  });

  // --- Tokens ---
  app.post(`${p}/anip/tokens`, { errorHandler: bodyErrorHandler(service, "bootstrap") }, async (req, reply) => {
    const issuer = await extractIssuer(req, service);
    if (!issuer) return authFailureTokenEndpoint(reply);
    if (!isJsonObject(req.body)) return sendFailure(reply, invalidParametersFailure(BODY_NOT_AN_OBJECT));
    try {
      const result = await service.issueTokenAs(issuer, req.body);
      return result;
    } catch (e) {
      if (e instanceof ANIPError) return errorResponse(reply, e);
      throw e;
    }
  });

  // --- Permissions ---
  app.post(`${p}/anip/permissions`, async (req, reply) => {
    const result = await resolveToken(req, service);
    if (result === null) return authFailureJwtEndpoint(reply);
    if (result instanceof ANIPError) return errorResponse(reply, result);
    const token = result;
    return service.discoverPermissions(token);
  });

  // --- Invoke ---
  app.post<{ Params: { capability: string } }>(
    `${p}/anip/invoke/:capability`,
    { errorHandler: bodyErrorHandler(service, "token") },
    async (req, reply) => {
      const authResult = await resolveToken(req, service);
      if (authResult === null) return authFailureJwtEndpoint(reply);
      if (authResult instanceof ANIPError) return errorResponse(reply, authResult);
      const token = authResult;
      const body = req.body;
      if (!isJsonObject(body)) return sendFailure(reply, invalidParametersFailure(BODY_NOT_AN_OBJECT));
      const params = (body.parameters as Record<string, unknown>) ?? body;
      const clientReferenceId = (body.client_reference_id as string) ?? null;
      const taskId = (body.task_id as string) ?? null;
      const parentInvocationId = (body.parent_invocation_id as string) ?? null;
      const upstreamService = (body.upstream_service as string) ?? null;
      const budget = (body.budget as Record<string, unknown>) ?? null;
      const requestedEffects = Array.isArray(body.requested_effects)
        ? body.requested_effects.map(String).filter((item) => item.trim().length > 0)
        : [];
      // v0.23: continuation invocations supply approval_grant. session_id for
      // session_bound grants is read from the signed token, never the body.
      const approvalGrant = (body.approval_grant as string) ?? null;
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
        const result = await service.invoke(req.params.capability, token, params, invokeOpts);
        if (!result.success) {
          const failure = result.failure as Record<string, unknown>;
          return reply.status(failureStatusCode(failure?.type as string)).send(result);
        }
        return result;
      }

      // Pre-validate streaming support (return JSON 400, not SSE)
      const decl = service.getCapabilityDeclaration(req.params.capability);
      const modes = (decl?.response_modes as string[]) ?? ["unary"];
      if (!modes.includes("streaming")) {
        const result = await service.invoke(req.params.capability, token, params, {
          ...invokeOpts,
          stream: true,
        });
        const failure = result.failure as Record<string, unknown>;
        return reply.status(failureStatusCode(failure?.type as string)).send(result);
      }

      // True streaming: reply.raw.write() as progress sink
      // Call hijack() first so Fastify knows we manage the response
      reply.hijack();
      reply.raw.writeHead(200, {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
      });

      const result = await service.invoke(req.params.capability, token, params, {
        ...invokeOpts,
        stream: true,
        progressSink: async (event) => {
          const eventData = { ...event, timestamp: new Date().toISOString() };
          reply.raw.write(`event: progress\ndata: ${JSON.stringify(eventData)}\n\n`);
        },
      });

      const ts = new Date().toISOString();
      const terminalType = result.success ? "completed" : "failed";
      const terminalData = {
        invocation_id: result.invocation_id,
        client_reference_id: result.client_reference_id,
        timestamp: ts,
        success: result.success,
        ...(result.success
          ? { result: result.result, cost_actual: result.cost_actual }
          : { failure: result.failure }),
        ...(result.stream_summary ? { stream_summary: result.stream_summary } : {}),
      };
      reply.raw.write(`event: ${terminalType}\ndata: ${JSON.stringify(terminalData)}\n\n`);
      reply.raw.end();
    },
  );

  // --- Graph ---
  app.get<{ Params: { capability: string } }>(
    `${p}/anip/graph/:capability`,
    async (req, reply) => {
      const graph = service.getCapabilityGraph(req.params.capability);
      if (!graph) {
        return sendFailure(reply, {
          success: false,
          failure: {
            type: "not_found",
            detail: `Capability '${req.params.capability}' not found`,
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
      return graph;
    },
  );

  // --- Approval Grants (v0.23 §4.9) ---
  // Validation order is security-relevant; see SPEC.md §4.9 line 1090:
  //   1. authn (already handled by resolveToken)
  //   2. parse body + schema-validate via IssueApprovalGrantRequest
  //   3. load ApprovalRequest
  //   4. check state (decided / expired) — BEFORE approver auth
  //   5. check approver authority against the loaded capability
  //   6. issueApprovalGrant (steps 6–11 of the spec)
  //
  // Fastify's content-type parser fails before the handler runs; the
  // route-level errorHandler maps that to canonical invalid_parameters JSON
  // after the credential check (see bodyErrorHandler).
  app.post(
    `${p}/anip/approval_grants`,
    { errorHandler: bodyErrorHandler(service, "token") },
    async (req, reply) => {
    const authResult = await resolveToken(req, service);
    if (authResult === null) return authFailureJwtEndpoint(reply);
    if (authResult instanceof ANIPError) return errorResponse(reply, authResult);
    const token = authResult;

    const parsed = IssueApprovalGrantRequest.safeParse(req.body);
    if (!parsed.success) {
      return sendFailure(
        reply,
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
      return sendFailure(reply, approvalRequestNotFoundFailure(approvalRequestId));
    }

    // SPEC.md §4.9 step 4: state check BEFORE approver authority.
    const status = approvalRequest.status as string;
    const expiresAt = approvalRequest.expires_at as string | undefined;
    if (status !== "pending") {
      return sendFailure(reply, approvalRequestAlreadyDecidedFailure(approvalRequestId, status));
    }
    if (expiresAt && expiresAt <= new Date().toISOString()) {
      return sendFailure(reply, approvalRequestExpiredFailure(approvalRequestId));
    }

    const targetCapability = approvalRequest.capability as string;
    const tokenScopes = token.scope ?? [];
    const acceptedScopes = new Set(["approver:*", `approver:${targetCapability}`]);
    if (!tokenScopes.some((s) => acceptedScopes.has(s))) {
      return sendFailure(reply, approverNotAuthorizedFailure(targetCapability));
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
      return grant;
    } catch (e) {
      if (e instanceof ANIPError) return errorResponse(reply, e);
      throw e;
    }
  });

  // --- Audit ---
  app.post(`${p}/anip/audit`, async (req, reply) => {
    const result = await resolveToken(req, service);
    if (result === null) return authFailureJwtEndpoint(reply);
    if (result instanceof ANIPError) return errorResponse(reply, result);
    const token = result;
    const query = req.query as Record<string, string>;
    const filters = {
      capability: query.capability ?? undefined,
      since: query.since ?? undefined,
      invocation_id: query.invocation_id ?? undefined,
      client_reference_id: query.client_reference_id ?? undefined,
      task_id: query.task_id ?? undefined,
      parent_invocation_id: query.parent_invocation_id ?? undefined,
      event_class: query.event_class ?? undefined,
      limit: parseInt(query.limit ?? "50", 10),
    };
    return await service.queryAudit(token, filters);
  });

  // --- Checkpoints ---
  app.get(`${p}/anip/checkpoints`, async (req) => {
    const query = req.query as Record<string, string>;
    const limit = parseInt(query.limit ?? "10", 10);
    return await service.getCheckpoints(limit);
  });

  app.get<{ Params: { id: string } }>(`${p}/anip/checkpoints/:id`, async (req, reply) => {
    const query = req.query as Record<string, string>;
    const options = {
      include_proof: query.include_proof === "true",
      leaf_index: query.leaf_index ?? undefined,
      consistency_from: query.consistency_from ?? undefined,
    };
    const result = await service.getCheckpoint(req.params.id, options);
    if (!result) return sendFailure(reply, {
      success: false,
      failure: {
        type: "not_found",
        detail: `Checkpoint ${req.params.id} not found`,
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
    return result;
  });

  // --- Health ---
  if (opts?.healthEndpoint) {
    app.get("/-/health", async (_request, reply) => {
      return reply.send(service.getHealth());
    });
  }

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
async function extractIssuer(req: FastifyRequest, service: ANIPService): Promise<Issuer | null> {
  const auth = req.headers.authorization ?? "";
  if (!auth.startsWith("Bearer ")) return null;
  return service.authenticateIssuer(auth.slice(7).trim());
}

async function resolveToken(req: FastifyRequest, service: ANIPService) {
  const auth = req.headers.authorization ?? "";
  if (!auth.startsWith("Bearer ")) return null;
  try {
    return await service.resolveBearerToken(auth.slice(7).trim());
  } catch (e) {
    if (e instanceof ANIPError) return e;
    throw e;
  }
}

const BODY_NOT_AN_OBJECT = "request body must be a JSON object";

function isJsonObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** Send a failure body with the HTTP status of its type (SPEC.md §6.3). */
function sendFailure(
  reply: FastifyReply,
  body: { success: boolean; failure: Record<string, unknown> & { type: string } },
) {
  return reply.status(failureStatusCode(body.failure.type)).send(body);
}

// Raised by Fastify's content-type parser before a route handler runs: the
// body is not JSON, is empty, or has a media type Fastify does not parse.
const BODY_PARSE_ERROR_CODES = new Set([
  "FST_ERR_CTP_INVALID_JSON_BODY",
  "FST_ERR_CTP_EMPTY_JSON_BODY",
  "FST_ERR_CTP_INVALID_MEDIA_TYPE",
]);

/**
 * Route-level error handler for the endpoints that read a JSON body.
 * SPEC.md §6.3 "HTTP Status Codes" and §4.9 step 2: a request body that is
 * not JSON is invalid_parameters (400), after the credential check the route
 * handler would have made first: without a credential the answer is 401.
 */
function bodyErrorHandler(service: ANIPService, credential: "bootstrap" | "token") {
  return async (err: any, req: FastifyRequest, reply: FastifyReply) => {
    if (!err || !BODY_PARSE_ERROR_CODES.has(err.code)) {
      // Not a body error: let Fastify's default error handling answer.
      return reply.send(err);
    }
    if (credential === "bootstrap") {
      const issuer = await extractIssuer(req, service);
      if (!issuer) return authFailureTokenEndpoint(reply);
    } else {
      const authResult = await resolveToken(req, service);
      if (authResult === null) return authFailureJwtEndpoint(reply);
      if (authResult instanceof ANIPError) return errorResponse(reply, authResult);
    }
    return sendFailure(
      reply,
      invalidParametersFailure(`request body must be JSON: ${err.message ?? "parse error"}`),
    );
  };
}

function authFailureTokenEndpoint(reply: FastifyReply) {
  return sendFailure(reply, {
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

function authFailureJwtEndpoint(reply: FastifyReply) {
  return sendFailure(reply, {
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

function errorResponse(reply: FastifyReply, error: ANIPError) {
  const status = failureStatusCode(error.errorType);
  const resolution = error.resolution ?? DEFAULT_RESOLUTIONS[error.errorType] ?? {
    action: "contact_service_owner",
    recovery_class: "terminal",
    requires: null,
    grantable_by: null,
    estimated_availability: null,
  };
  return reply.status(status).send({
    success: false,
    failure: {
      type: error.errorType,
      detail: error.detail,
      resolution,
      retry: error.retry,
    },
  });
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
