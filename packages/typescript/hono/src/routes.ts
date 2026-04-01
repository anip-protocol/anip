import { Hono } from "hono";
import type { ContentfulStatusCode } from "hono/utils/http-status";
import type { ANIPService } from "@anip-dev/service";
import { ANIPError } from "@anip-dev/service";

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
    const principal = await extractPrincipal(c, service);
    if (!principal) return authFailureTokenEndpoint(c);
    const body = await c.req.json();
    try {
      const result = await service.issueToken(principal, body);
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
    const body = await c.req.json();
    const params = body.parameters ?? body;
    const clientReferenceId = body.client_reference_id ?? null;
    const taskId = body.task_id ?? null;
    const parentInvocationId = body.parent_invocation_id ?? null;
    const budget = body.budget ?? null;

    if (!body.stream) {
      // Unary mode — existing behavior
      const result = await service.invoke(capability, token, params, {
        clientReferenceId,
        taskId,
        parentInvocationId,
        budget,
      });
      if (!result.success) {
        const failure = result.failure as Record<string, unknown>;
        return c.json(result, failureStatus(failure?.type as string));
      }
      return c.json(result);
    }

    // Pre-validate streaming support (return JSON 400, not SSE)
    const decl = service.getCapabilityDeclaration(capability);
    const modes = (decl?.response_modes as string[]) ?? ["unary"];
    if (!modes.includes("streaming")) {
      const result = await service.invoke(capability, token, params, {
        clientReferenceId,
        taskId,
        parentInvocationId,
        stream: true,
        budget,
      });
      const failure = result.failure as Record<string, unknown>;
      return c.json(result, failureStatus(failure?.type as string));
    }

    // True streaming: TransformStream bridges sink → Response body
    const { readable, writable } = new TransformStream();
    const writer = writable.getWriter();
    const encoder = new TextEncoder();

    (async () => {
      try {
        const result = await service.invoke(capability, token, params, {
          clientReferenceId,
          taskId,
          parentInvocationId,
          stream: true,
          budget,
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
    if (!result) return c.json({
      success: false,
      failure: {
        type: "not_found",
        detail: `Checkpoint ${id} not found`,
        resolution: {
          action: "list_checkpoints",
          recovery_class: "revalidate_then_retry",
          requires: "GET /anip/checkpoints to find valid checkpoint IDs",
          grantable_by: null,
          estimated_availability: null,
        },
        retry: false,
      },
    }, 404);
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

async function extractPrincipal(c: any, service: ANIPService): Promise<string | null> {
  const auth = c.req.header("authorization") ?? "";
  if (!auth.startsWith("Bearer ")) return null;
  return service.authenticateBearer(auth.slice(7).trim());
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

function failureStatus(type?: string): ContentfulStatusCode {
  const mapping: Record<string, ContentfulStatusCode> = {
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

function authFailureTokenEndpoint(c: any) {
  return c.json({
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
  }, 401);
}

function authFailureJwtEndpoint(c: any) {
  return c.json({
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
  }, 401);
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

function errorResponse(c: any, error: ANIPError) {
  const status = failureStatus(error.errorType);
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
