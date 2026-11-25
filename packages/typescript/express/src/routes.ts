import express, { Router } from "express";
import type { Express, Request, Response } from "express";
import type { ANIPService, Issuer } from "@anip-dev/service";
import { ANIPError } from "@anip-dev/service";
import { IssueApprovalGrantRequest, failureStatusCode } from "@anip-dev/core";

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
      const issuer = await extractIssuer(req, service);
      if (!issuer) { authFailureTokenEndpoint(res); return; }
      if (!isJsonObject(req.body)) { sendFailure(res, invalidParametersFailure(BODY_NOT_AN_OBJECT)); return; }
      const result = await service.issueTokenAs(issuer, req.body);
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
      if (!isJsonObject(body)) { sendFailure(res, invalidParametersFailure(BODY_NOT_AN_OBJECT)); return; }
      const params = (body.parameters ?? body) as Record<string, unknown>;
      const clientReferenceId = (body.client_reference_id as string | undefined) ?? null;
      const taskId = (body.task_id as string | undefined) ?? null;
      const parentInvocationId = (body.parent_invocation_id as string | undefined) ?? null;
      const upstreamService = (body.upstream_service as string | undefined) ?? null;
      const budget = (body.budget as Record<string, unknown> | undefined) ?? null;
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
      };

      if (!body.stream) {
        // Unary mode
        const result = await service.invoke(req.params.capability, token, params, invokeOpts);
        if (!result.success) {
          const failure = result.failure as Record<string, unknown>;
          res.status(failureStatusCode(failure?.type as string)).json(result);
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
          ...invokeOpts,
          stream: true,
        });
        const failure = result.failure as Record<string, unknown>;
        res.status(failureStatusCode(failure?.type as string)).json(result);
        return;
      }

      // True streaming: res.write() as progress sink
      res.writeHead(200, {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
      });

      const result = await service.invoke(req.params.capability, token, params, {
        ...invokeOpts,
        stream: true,
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
      sendFailure(res, {
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
  // Validation order is security-relevant; see SPEC.md §4.9 line 1090:
  //   1. authn (already handled by resolveToken)
  //   2. parse body + schema-validate via IssueApprovalGrantRequest
  //   3. load ApprovalRequest
  //   4. check state (decided / expired) — BEFORE approver auth
  //   5. check approver authority against the loaded capability
  //   6. issueApprovalGrant (steps 6–11 of the spec)
  router.post("/anip/approval_grants", async (req, res, next) => {
    try {
      const authResult = await resolveToken(req, service);
      if (authResult === null) { authFailureJwtEndpoint(res); return; }
      if (authResult instanceof ANIPError) { errorResponse(res, authResult); return; }
      const token = authResult;

      const parsed = IssueApprovalGrantRequest.safeParse(req.body);
      if (!parsed.success) {
        sendFailure(
          res,
          invalidParametersFailure(
            parsed.error.issues
              .map((i) => `${i.path.join(".")}: ${i.message}`)
              .join("; "),
          ),
        );
        return;
      }
      const { approval_request_id: approvalRequestId, grant_type: grantType } =
        parsed.data;

      const approvalRequest = await service.getApprovalRequest(approvalRequestId);
      if (approvalRequest === null) {
        sendFailure(res, approvalRequestNotFoundFailure(approvalRequestId));
        return;
      }

      // SPEC.md §4.9 step 4: state check BEFORE approver authority.
      const status = approvalRequest.status as string;
      const expiresAt = approvalRequest.expires_at as string | undefined;
      if (status !== "pending") {
        sendFailure(res, approvalRequestAlreadyDecidedFailure(approvalRequestId, status));
        return;
      }
      if (expiresAt && expiresAt <= new Date().toISOString()) {
        sendFailure(res, approvalRequestExpiredFailure(approvalRequestId));
        return;
      }

      const targetCapability = approvalRequest.capability as string;
      const tokenScopes = token.scope ?? [];
      const acceptedScopes = new Set(["approver:*", `approver:${targetCapability}`]);
      if (!tokenScopes.some((s) => acceptedScopes.has(s))) {
        sendFailure(res, approverNotAuthorizedFailure(targetCapability));
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
            expiresInSeconds: parsed.data.expires_in_seconds,
            maxUses: parsed.data.max_uses,
            sessionId: parsed.data.session_id,
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
        sendFailure(res, {
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

  // SPEC.md §6.3 "HTTP Status Codes" and §4.9 step 2: a request body that is
  // not JSON is invalid_parameters at the invoke, tokens and approval_grants
  // endpoints, not the framework default. express.json() raises SyntaxError
  // with type "entity.parse.failed" before the route handler runs, so the
  // mapping happens here, after the credential check the handler would have
  // made first: without a credential the answer is still 401.
  router.use(async (err: any, req: Request, res: Response, next: any) => {
    if (!err || err.type !== "entity.parse.failed" || req.method !== "POST") {
      next(err);
      return;
    }
    try {
      if (req.path === "/anip/tokens") {
        const issuer = await extractIssuer(req, service);
        if (!issuer) { authFailureTokenEndpoint(res); return; }
      } else if (req.path === "/anip/approval_grants" || req.path.startsWith("/anip/invoke/")) {
        const authResult = await resolveToken(req, service);
        if (authResult === null) { authFailureJwtEndpoint(res); return; }
        if (authResult instanceof ANIPError) { errorResponse(res, authResult); return; }
      } else {
        next(err);
        return;
      }
      sendFailure(
        res,
        invalidParametersFailure(`request body must be JSON: ${err.message ?? "parse error"}`),
      );
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

// The token endpoint accepts the bootstrap credential, or a delegation token
// issued by this service. A token authenticates as its holder, and the service
// refuses root issuance for such callers.
async function extractIssuer(req: Request, service: ANIPService): Promise<Issuer | null> {
  const auth = req.headers.authorization ?? "";
  if (!auth.startsWith("Bearer ")) return null;
  return service.authenticateIssuer(auth.slice(7).trim());
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

const BODY_NOT_AN_OBJECT = "request body must be a JSON object";

function isJsonObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** Send a failure body with the HTTP status of its type (SPEC.md §6.3). */
function sendFailure(
  res: Response,
  body: { success: boolean; failure: Record<string, unknown> & { type: string } },
) {
  res.status(failureStatusCode(body.failure.type)).json(body);
}

function authFailureTokenEndpoint(res: Response) {
  sendFailure(res, {
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
  sendFailure(res, {
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

function errorResponse(res: Response, error: ANIPError) {
  const status = failureStatusCode(error.errorType);
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
