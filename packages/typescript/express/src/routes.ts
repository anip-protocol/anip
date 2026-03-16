import express, { Router } from "express";
import type { Express, Request, Response } from "express";
import type { ANIPService } from "@anip/service";
import { ANIPError } from "@anip/service";

export function mountAnip(
  app: Express,
  service: ANIPService,
  opts?: { prefix?: string },
): { stop: () => void } {
  const router = Router();
  router.use(express.json());

  // --- Discovery & Identity ---
  router.get("/.well-known/anip", (_req, res) => {
    res.json(service.getDiscovery());
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
      if (!principal) { res.status(401).json({ error: "Authentication required" }); return; }
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
      const token = await resolveToken(req, service);
      if (!token) { res.status(401).json({ error: "Authentication required" }); return; }
      res.json(service.discoverPermissions(token));
    } catch (e) { next(e); }
  });

  // --- Invoke ---
  router.post("/anip/invoke/:capability", async (req, res, next) => {
    try {
      const token = await resolveToken(req, service);
      if (!token) { res.status(401).json({ error: "Authentication required" }); return; }
      const body = req.body;
      const params = body.parameters ?? body;
      const clientReferenceId = body.client_reference_id ?? null;
      const result = await service.invoke(req.params.capability, token, params, {
        clientReferenceId,
      });
      if (!result.success) {
        const failure = result.failure as Record<string, unknown>;
        res.status(failureStatus(failure?.type as string)).json(result);
        return;
      }
      res.json(result);
    } catch (e) { next(e); }
  });

  // --- Audit ---
  router.post("/anip/audit", async (req, res, next) => {
    try {
      const token = await resolveToken(req, service);
      if (!token) { res.status(401).json({ error: "Authentication required" }); return; }
      const filters = {
        capability: (req.query.capability as string) ?? undefined,
        since: (req.query.since as string) ?? undefined,
        invocation_id: (req.query.invocation_id as string) ?? undefined,
        client_reference_id: (req.query.client_reference_id as string) ?? undefined,
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
      if (!result) { res.status(404).json({ error: "Checkpoint not found" }); return; }
      res.json(result);
    } catch (e) { next(e); }
  });

  const prefix = opts?.prefix ?? "";
  if (prefix) {
    app.use(prefix, router);
  } else {
    app.use(router);
  }

  service.start();
  return { stop: () => service.stop() };
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

function errorResponse(res: Response, error: ANIPError) {
  const status = failureStatus(error.errorType);
  res.status(status).json({
    success: false,
    failure: { type: error.errorType, detail: error.detail },
  });
}
