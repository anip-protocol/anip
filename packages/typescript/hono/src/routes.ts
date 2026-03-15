import { Hono } from "hono";
import type { ContentfulStatusCode } from "hono/utils/http-status";
import type { ANIPService } from "@anip/service";
import { ANIPError } from "@anip/service";

export function mountAnip(
  app: Hono,
  service: ANIPService,
  opts?: { prefix?: string },
): { stop: () => void } {
  const p = opts?.prefix ?? "";

  // --- Discovery & Identity ---
  app.get(`${p}/.well-known/anip`, (c) => c.json(service.getDiscovery()));

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
    if (!principal) return c.json({ error: "Authentication required" }, 401);
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
    const token = await resolveToken(c, service);
    if (!token) return c.json({ error: "Authentication required" }, 401);
    return c.json(service.discoverPermissions(token));
  });

  // --- Invoke ---
  app.post(`${p}/anip/invoke/:capability`, async (c) => {
    const token = await resolveToken(c, service);
    if (!token) return c.json({ error: "Authentication required" }, 401);
    const capability = c.req.param("capability");
    const body = await c.req.json();
    const params = body.parameters ?? body;
    const clientReferenceId = body.client_reference_id ?? null;
    const result = await service.invoke(capability, token, params, {
      clientReferenceId,
    });
    if (!result.success) {
      const failure = result.failure as Record<string, unknown>;
      return c.json(result, failureStatus(failure?.type as string));
    }
    return c.json(result);
  });

  // --- Audit ---
  app.post(`${p}/anip/audit`, async (c) => {
    const token = await resolveToken(c, service);
    if (!token) return c.json({ error: "Authentication required" }, 401);
    const url = new URL(c.req.url);
    const filters = {
      capability: url.searchParams.get("capability") ?? undefined,
      since: url.searchParams.get("since") ?? undefined,
      invocation_id: url.searchParams.get("invocation_id") ?? undefined,
      client_reference_id: url.searchParams.get("client_reference_id") ?? undefined,
      limit: parseInt(url.searchParams.get("limit") ?? "50", 10),
    };
    return c.json(service.queryAudit(token, filters));
  });

  // --- Checkpoints ---
  app.get(`${p}/anip/checkpoints`, (c) => {
    const url = new URL(c.req.url);
    const limit = parseInt(url.searchParams.get("limit") ?? "10", 10);
    return c.json(service.getCheckpoints(limit));
  });

  app.get(`${p}/anip/checkpoints/:id`, (c) => {
    const id = c.req.param("id");
    const url = new URL(c.req.url);
    const options = {
      include_proof: url.searchParams.get("include_proof") === "true",
      leaf_index: url.searchParams.get("leaf_index") ?? undefined,
      consistency_from: url.searchParams.get("consistency_from") ?? undefined,
    };
    const result = service.getCheckpoint(id, options);
    if (!result) return c.json({ error: "Checkpoint not found" }, 404);
    return c.json(result);
  });

  // --- Lifecycle ---
  service.start();
  return { stop: () => service.stop() };
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
  } catch {
    return null;
  }
}

function failureStatus(type?: string): ContentfulStatusCode {
  const mapping: Record<string, ContentfulStatusCode> = {
    invalid_token: 401,
    token_expired: 401,
    scope_insufficient: 403,
    insufficient_authority: 403,
    purpose_mismatch: 403,
    unknown_capability: 404,
    not_found: 404,
    unavailable: 409,
    concurrent_lock: 409,
    internal_error: 500,
  };
  return mapping[type ?? ""] ?? 400;
}

function errorResponse(c: any, error: ANIPError) {
  const status = failureStatus(error.errorType);
  return c.json(
    { success: false, failure: { type: error.errorType, detail: error.detail } },
    status,
  );
}
