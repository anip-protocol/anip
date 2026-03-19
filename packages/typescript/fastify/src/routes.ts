import type { FastifyInstance, FastifyRequest, FastifyReply } from "fastify";
import type { ANIPService } from "@anip/service";
import { ANIPError } from "@anip/service";

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
    if (!principal) return reply.status(401).send({ error: "Authentication required" });
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
    const token = await resolveToken(req, service);
    if (!token) return reply.status(401).send({ error: "Authentication required" });
    return service.discoverPermissions(token);
  });

  // --- Invoke ---
  app.post<{ Params: { capability: string } }>(
    `${p}/anip/invoke/:capability`,
    async (req, reply) => {
      const token = await resolveToken(req, service);
      if (!token) return reply.status(401).send({ error: "Authentication required" });
      const body = req.body as Record<string, unknown>;
      const params = (body.parameters as Record<string, unknown>) ?? body;
      const clientReferenceId = (body.client_reference_id as string) ?? null;

      if (!body.stream) {
        // Unary mode — existing behavior
        const result = await service.invoke(req.params.capability, token, params, {
          clientReferenceId,
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
          clientReferenceId, stream: true,
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

  // --- Audit ---
  app.post(`${p}/anip/audit`, async (req, reply) => {
    const token = await resolveToken(req, service);
    if (!token) return reply.status(401).send({ error: "Authentication required" });
    const query = req.query as Record<string, string>;
    const filters = {
      capability: query.capability ?? undefined,
      since: query.since ?? undefined,
      invocation_id: query.invocation_id ?? undefined,
      client_reference_id: query.client_reference_id ?? undefined,
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
    if (!result) return reply.status(404).send({ error: "Checkpoint not found" });
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
  } catch {
    return null;
  }
}

function failureStatus(type?: string): number {
  const mapping: Record<string, number> = {
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

function errorResponse(reply: FastifyReply, error: ANIPError) {
  const status = failureStatus(error.errorType);
  return reply.status(status).send({
    success: false,
    failure: { type: error.errorType, detail: error.detail },
  });
}
