import express, { Router } from "express";
import type { Express, Request, Response } from "express";
import type { ANIPService } from "@anip-dev/service";
import { ANIPError } from "@anip-dev/service";

export async function mountAnip(
  app: Express,
  service: ANIPService,
  opts?: { prefix?: string; healthEndpoint?: boolean },
): Promise<{ shutdown: () => Promise<void>; stop: () => void }> {
  const router = Router();
  router.use(express.json());

  // --- Discovery & Identity ---
  router.get("/.well-known/anip", (req, res) => {
    const baseUrl = `${req.protocol}://${req.get("host")}`;
    res.json(service.getDiscovery({ baseUrl }));
  });

  router.get("/.well-known/jwks.json", async (_req, res, next) => {
    try {
      const jwks = await service.getJwks();
      res.json(jwks);
    } catch (e) { next(e); }
  });

  router.get("/anip/manifest", async (_req, res, next) => {
    try {
      const [bodyBytes, signature] = await service.getSignedManifest();
      res.set("Content-Type", "application/json");
      res.set("X-ANIP-Signature", signature);
      res.send(Buffer.from(bodyBytes));
    } catch (e) { next(e); }
  });

  // --- Tokens ---
  router.post("/anip/tokens", async (req, res, next) => {
    try {
      const principal = await extractPrincipal(req, service);
      if (!principal) { authFailureTokenEndpoint(res); return; }
      const result = await service.issueToken(principal, req.body);
      res.json(result);
    } catch (e) {
      if (e instanceof ANIPError) { errorResponse(res, e); return; }
      next(e);
    }
  });

  // --- Permissions ---
  router.post("/anip/permissions", async (req, res, next) => {
    try {
      const result = await resolveToken(req, service);
      if (result === null) { authFailureJwtEndpoint(res); return; }
      if (result instanceof ANIPError) { errorResponse(res, result); return; }
      const token = result;
      res.json(service.discoverPermissions(token));
    } catch (e) { next(e); }
  });

  // --- Invoke ---
  router.post("/anip/invoke/:capability", async (req, res, next) => {
    try {
      const authResult = await resolveToken(req, service);
      if (authResult === null) { authFailureJwtEndpoint(res); return; }
      if (authResult instanceof ANIPError) { errorResponse(res, authResult); return; }
      const token = authResult;
      const body = req.body;
      const params = body.parameters ?? body;
      const clientReferenceId = body.client_reference_id ?? null;
      const taskId = body.task_id ?? null;
      const parentInvocationId = body.parent_invocation_id ?? null;
      const upstreamService = body.upstream_service ?? null;
      const budget = body.budget ?? null;
      // v0.23: continuation invocations supply approval_grant. session_id for
      // session_bound grants is read from the signed token, never the body.
      const approvalGrant = body.approval_grant ?? null;

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
          res.status(failureStatus(failure?.type as string)).json(result);
          return;
        }
        res.json(result);
        return;
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
        res.status(failureStatus(failure?.type as string)).json(result);
        return;
      }

      // True streaming: res.write() as progress sink
      res.writeHead(200, {
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
          res.write(`event: progress\ndata: ${JSON.stringify(eventData)}\n\n`);
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
      res.write(`event: ${terminalType}\ndata: ${JSON.stringify(terminalData)}\n\n`);
      res.end();
    } catch (e) { next(e); }
  });

  // --- Graph ---
  router.get("/anip/graph/:capability", async (req, res, _next) => {
    const graph = service.getCapabilityGraph(req.params.capability);
    if (!graph) {
      res.status(404).json({
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
      return;
    }
    res.json(graph);
  });

  // --- Approval Grants (v0.23 §4.9) ---
  router.post("/anip/approval_grants", async (req, res, next) => {
    try {
      const authResult = await resolveToken(req, service);
      if (authResult === null) { authFailureJwtEndpoint(res); return; }
      if (authResult instanceof ANIPError) { errorResponse(res, authResult); return; }
      const token = authResult;

      const body = req.body ?? {};
      const approvalRequestId = body.approval_request_id as string | undefined;
      const grantType = body.grant_type as
        | "one_time"
        | "session_bound"
        | undefined;
      if (!approvalRequestId || !grantType) {
        res.status(400).json({
          success: false,
          failure: {
            type: "invalid_request",
            detail: "Missing approval_request_id or grant_type",
            resolution: {
              action: "fix_request_body",
              recovery_class: "revalidate_then_retry",
              requires: "Both approval_request_id and grant_type fields",
              grantable_by: null,
              estimated_availability: null,
            },
            retry: false,
          },
        });
        return;
      }

      const approvalRequest = await service.getApprovalRequest(approvalRequestId);
      if (approvalRequest === null) {
        res.status(404).json({
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
        });
        return;
      }

      const targetCapability = approvalRequest.capability as string;
      const tokenScopes = token.scope ?? [];
      const acceptedScopes = new Set(["approver:*", `approver:${targetCapability}`]);
      if (!tokenScopes.some((s) => acceptedScopes.has(s))) {
        res.status(403).json({
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
        });
        return;
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
            expiresInSeconds: body.expires_in_seconds as number | undefined,
            maxUses: body.max_uses as number | undefined,
            sessionId: body.session_id as string | undefined,
          },
        );
        // SPEC.md §4.9: 200 response IS the signed ApprovalGrant — no wrapper.
        res.json(grant);
      } catch (e) {
        if (e instanceof ANIPError) { errorResponse(res, e); return; }
        throw e;
      }
    } catch (e) { next(e); }
  });

  // --- Audit ---
  router.post("/anip/audit", async (req, res, next) => {
    try {
      const result = await resolveToken(req, service);
      if (result === null) { authFailureJwtEndpoint(res); return; }
      if (result instanceof ANIPError) { errorResponse(res, result); return; }
      const token = result;
      const filters = {
        capability: (req.query.capability as string) ?? undefined,
        since: (req.query.since as string) ?? undefined,
        invocation_id: (req.query.invocation_id as string) ?? undefined,
        client_reference_id: (req.query.client_reference_id as string) ?? undefined,
        task_id: (req.query.task_id as string) ?? undefined,
        parent_invocation_id: (req.query.parent_invocation_id as string) ?? undefined,
        event_class: (req.query.event_class as string) ?? undefined,
        limit: parseInt((req.query.limit as string) ?? "50", 10),
      };
      res.json(await service.queryAudit(token, filters));
    } catch (e) { next(e); }
  });

  // --- Checkpoints ---
  router.get("/anip/checkpoints", async (req, res, next) => {
    try {
      const limit = parseInt((req.query.limit as string) ?? "10", 10);
      res.json(await service.getCheckpoints(limit));
    } catch (e) { next(e); }
  });

  router.get("/anip/checkpoints/:id", async (req, res, next) => {
    try {
      const options = {
        include_proof: req.query.include_proof === "true",
        leaf_index: (req.query.leaf_index as string) ?? undefined,
        consistency_from: (req.query.consistency_from as string) ?? undefined,
      };
      const result = await service.getCheckpoint(req.params.id, options);
      if (!result) {
        res.status(404).json({
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
        return;
      }
      res.json(result);
    } catch (e) { next(e); }
  });

  const prefix = opts?.prefix ?? "";
  if (prefix) {
    app.use(prefix, router);
  } else {
    app.use(router);
  }

  // --- Health ---
  if (opts?.healthEndpoint) {
    app.get("/-/health", (_req, res) => {
      res.json(service.getHealth());
    });
  }

  await service.start();
  return {
    async shutdown() { await service.shutdown(); },
    stop() { service.stop(); },
  };
}

// --- Helpers ---

async function extractPrincipal(req: Request, service: ANIPService): Promise<string | null> {
  const auth = req.headers.authorization ?? "";
  if (!auth.startsWith("Bearer ")) return null;
  return service.authenticateBearer(auth.slice(7).trim());
}

async function resolveToken(req: Request, service: ANIPService) {
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

function authFailureTokenEndpoint(res: Response) {
  res.status(401).json({
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

function authFailureJwtEndpoint(res: Response) {
  res.status(401).json({
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

function errorResponse(res: Response, error: ANIPError) {
  const status = failureStatus(error.errorType);
  const resolution = error.resolution ?? DEFAULT_RESOLUTIONS[error.errorType] ?? {
    action: "contact_service_owner",
    recovery_class: "terminal",
    requires: null,
    grantable_by: null,
    estimated_availability: null,
  };
  res.status(status).json({
    success: false,
    failure: {
      type: error.errorType,
      detail: error.detail,
      resolution,
      retry: error.retry,
    },
  });
}
