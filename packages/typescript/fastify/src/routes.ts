import type { FastifyInstance, FastifyRequest, FastifyReply } from "fastify";
import type { ANIPService } from "@anip-dev/service";
import { ANIPError } from "@anip-dev/service";
import { IssueApprovalGrantRequest } from "@anip-dev/core";

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
  app.post(`${p}/anip/tokens`, async (req, reply) => {
    const principal = await extractPrincipal(req, service);
    if (!principal) return authFailureTokenEndpoint(reply);
    try {
      const result = await service.issueToken(principal, req.body as Record<string, unknown>);
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
    async (req, reply) => {
      const authResult = await resolveToken(req, service);
      if (authResult === null) return authFailureJwtEndpoint(reply);
      if (authResult instanceof ANIPError) return errorResponse(reply, authResult);
      const token = authResult;
      const body = req.body as Record<string, unknown>;
      const params = (body.parameters as Record<string, unknown>) ?? body;
      const clientReferenceId = (body.client_reference_id as string) ?? null;
      const taskId = (body.task_id as string) ?? null;
      const parentInvocationId = (body.parent_invocation_id as string) ?? null;
      const upstreamService = (body.upstream_service as string) ?? null;
      const budget = (body.budget as Record<string, unknown>) ?? null;
      // v0.23: continuation invocations supply approval_grant. session_id for
      // session_bound grants is read from the signed token, never the body.
      const approvalGrant = (body.approval_grant as string) ?? null;

      if (!body.stream) {
        // Unary mode — existing behavior
        const result = await service.invoke(req.params.capability, token, params, {
          clientReferenceId,
          taskId,
          parentInvocationId,
          upstreamService,
          budget,
          approvalGrant,
        });
        if (!result.success) {
          const failure = result.failure as Record<string, unknown>;
          return reply.status(failureStatus(failure?.type as string)).send(result);
        }
        return result;
      }

      // Pre-validate streaming support (return JSON 400, not SSE)
      const decl = service.getCapabilityDeclaration(req.params.capability);
      const modes = (decl?.response_modes as string[]) ?? ["unary"];
      if (!modes.includes("streaming")) {
        const result = await service.invoke(req.params.capability, token, params, {
          clientReferenceId, taskId, parentInvocationId, upstreamService, stream: true, budget,
          approvalGrant,
        });
        const failure = result.failure as Record<string, unknown>;
        return reply.status(failureStatus(failure?.type as string)).send(result);
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
        clientReferenceId,
        taskId,
        parentInvocationId,
        upstreamService,
        stream: true,
        budget,
        approvalGrant,
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
        return reply.status(404).send({
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
  app.post(`${p}/anip/approval_grants`, async (req, reply) => {
    const authResult = await resolveToken(req, service);
    if (authResult === null) return authFailureJwtEndpoint(reply);
    if (authResult instanceof ANIPError) return errorResponse(reply, authResult);
    const token = authResult;

    const parsed = IssueApprovalGrantRequest.safeParse(req.body);
    if (!parsed.success) {
      return reply.status(400).send(
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
      return reply
        .status(404)
        .send(approvalRequestNotFoundFailure(approvalRequestId));
    }

    // SPEC.md §4.9 step 4: state check BEFORE approver authority.
    const status = approvalRequest.status as string;
    const expiresAt = approvalRequest.expires_at as string | undefined;
    if (status !== "pending") {
      return reply
        .status(409)
        .send(approvalRequestAlreadyDecidedFailure(approvalRequestId, status));
    }
    if (expiresAt && expiresAt <= new Date().toISOString()) {
      return reply
        .status(409)
        .send(approvalRequestExpiredFailure(approvalRequestId));
    }

    const targetCapability = approvalRequest.capability as string;
    const tokenScopes = token.scope ?? [];
    const acceptedScopes = new Set(["approver:*", `approver:${targetCapability}`]);
    if (!tokenScopes.some((s) => acceptedScopes.has(s))) {
      return reply
        .status(403)
        .send(approverNotAuthorizedFailure(targetCapability));
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
    if (!result) return reply.status(404).send({
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

async function extractPrincipal(req: FastifyRequest, service: ANIPService): Promise<string | null> {
  const auth = req.headers.authorization ?? "";
  if (!auth.startsWith("Bearer ")) return null;
  return service.authenticateBearer(auth.slice(7).trim());
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

function failureStatus(type?: string): number {
  const mapping: Record<string, number> = {
    invalid_token: 401,
    token_expired: 401,
    scope_insufficient: 403,
    insufficient_authority: 403,
    budget_exceeded: 403,
    budget_currency_mismatch: 400,
    budget_not_enforceable: 400,
    binding_missing: 400,
    binding_stale: 400,
    control_requirement_unsatisfied: 403,
    purpose_mismatch: 403,
    unknown_capability: 404,
    not_found: 404,
    unavailable: 409,
    concurrent_lock: 409,
    internal_error: 500,
  };
  return mapping[type ?? ""] ?? 400;
}

function authFailureTokenEndpoint(reply: FastifyReply) {
  return reply.status(401).send({
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
  return reply.status(401).send({
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
};

function errorResponse(reply: FastifyReply, error: ANIPError) {
  const status = failureStatus(error.errorType);
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
