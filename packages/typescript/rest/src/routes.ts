/**
 * ANIP REST bindings — mount RESTful API endpoints on a Hono app.
 */
import type { Hono } from "hono";
import type { ANIPService } from "@anip/service";
import { ANIPError } from "@anip/service";
import {
  generateRoutes,
  generateOpenAPISpec,
  type RouteOverride,
} from "./translation.js";

export type { RouteOverride } from "./translation.js";

export interface RestMountOptions {
  /** Custom route paths/methods per capability. */
  routes?: Record<string, RouteOverride>;
  /** Prefix for all REST routes. Default: none. */
  prefix?: string;
}

const FAILURE_STATUS: Record<string, number> = {
  authentication_required: 401,
  invalid_token: 401,
  scope_insufficient: 403,
  budget_exceeded: 403,
  purpose_mismatch: 403,
  unknown_capability: 404,
  invalid_parameters: 400,
  unavailable: 409,
  internal_error: 500,
};

/**
 * Resolve auth from Authorization header.
 *
 * Order matters: try JWT first, then API key. authenticateBearer()
 * also accepts valid JWTs internally, so calling it first would
 * misidentify a caller-supplied JWT as an API key and issue a
 * synthetic token, losing the original delegation chain.
 */
async function resolveAuth(
  authHeader: string | undefined,
  service: ANIPService,
  capabilityName: string,
  adapterSubject: string,
) {
  if (!authHeader || !authHeader.startsWith("Bearer ")) {
    return null;
  }
  const bearer = authHeader.slice(7).trim();

  // Try as JWT first — preserves original delegation chain
  let jwtError: ANIPError | null = null;
  try {
    return await service.resolveBearerToken(bearer);
  } catch (e) {
    if (!(e instanceof ANIPError)) throw e;
    jwtError = e; // Stash the structured error
  }

  // Try as API key — only if JWT failed
  const principal = await service.authenticateBearer(bearer);
  if (principal) {
    // This is a real API key — issue synthetic token
    const capDecl = service.getCapabilityDeclaration(capabilityName);
    const minScope = (capDecl?.minimum_scope as string[]) ?? [];
    const tokenResult = await service.issueToken(principal, {
      subject: adapterSubject,
      scope: minScope.length > 0 ? minScope : ["*"],
      capability: capabilityName,
      purpose_parameters: { source: "rest" },
    });
    const jwt = tokenResult.token as string;
    return await service.resolveBearerToken(jwt);
  }

  // Neither JWT nor API key — surface the original JWT error if we had one,
  // so the caller gets invalid_token/token_expired instead of generic 401
  if (jwtError) throw jwtError;
  return null;
}

/**
 * Convert query string values to appropriate types based on capability inputs.
 */
function convertQueryParams(
  query: Record<string, string>,
  decl: Record<string, unknown>,
): Record<string, unknown> {
  const inputs = (decl.inputs ?? []) as Array<Record<string, unknown>>;
  const typeMap = new Map(inputs.map((i) => [i.name as string, i.type as string]));
  const result: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(query)) {
    const type = typeMap.get(key);
    if (type === "integer") result[key] = parseInt(value, 10);
    else if (type === "number") result[key] = parseFloat(value);
    else if (type === "boolean") result[key] = value === "true";
    else result[key] = value;
  }
  return result;
}

/**
 * Mount RESTful API endpoints on a Hono app.
 *
 * Does NOT own service lifecycle — the caller (or mountAnip) is
 * responsible for calling service.start() before and service.shutdown()
 * after. This avoids double-starting when multiple mount functions
 * share the same ANIPService.
 */
export async function mountAnipRest(
  app: Hono,
  service: ANIPService,
  opts?: RestMountOptions,
): Promise<void> {
  const prefix = opts?.prefix ?? "";

  // Build routes from manifest
  const manifest = service.getManifest();
  const capabilities: Record<string, Record<string, unknown>> = {};
  for (const name of Object.keys(manifest.capabilities)) {
    const decl = service.getCapabilityDeclaration(name);
    if (decl) capabilities[name] = decl;
  }
  const routes = generateRoutes(capabilities, opts?.routes);
  const serviceIdentity = (manifest as any).service_identity;
  const serviceId = serviceIdentity?.id ?? "anip-service";
  const openApiSpec = generateOpenAPISpec(serviceId, routes);

  // Register OpenAPI endpoints under /rest/ to avoid framework collisions
  app.get(`${prefix}/rest/openapi.json`, (c) => c.json(openApiSpec));
  app.get(`${prefix}/rest/docs`, (c) => {
    return c.html(`<!DOCTYPE html>
<html><head><title>ANIP REST API</title>
<link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist/swagger-ui.css">
</head><body>
<div id="swagger-ui"></div>
<script src="https://unpkg.com/swagger-ui-dist/swagger-ui-bundle.js"></script>
<script>SwaggerUIBundle({ url: "${prefix}/rest/openapi.json", dom_id: "#swagger-ui" });</script>
</body></html>`);
  });

  // Register capability routes
  for (const route of routes) {
    const handler = async (c: any) => {
      const authHeader = c.req.header("authorization");
      let token;
      try {
        token = await resolveAuth(authHeader, service, route.capabilityName, "adapter:anip-rest");
      } catch (e) {
        if (e instanceof ANIPError) {
          const status = FAILURE_STATUS[e.errorType] ?? 400;
          return c.json({
            success: false,
            failure: { type: e.errorType, detail: e.detail, resolution: e.resolution, retry: e.retry },
          }, status);
        }
        throw e;
      }

      if (!token) {
        return c.json({
          success: false,
          failure: {
            type: "authentication_required",
            detail: "Authorization header with Bearer token or API key required",
            resolution: { action: "provide_credentials", requires: "Bearer token or API key" },
            retry: true,
          },
        }, 401);
      }

      // Extract parameters
      let params: Record<string, unknown>;
      if (route.method === "GET") {
        const query = Object.fromEntries(new URL(c.req.url).searchParams);
        params = convertQueryParams(query, route.declaration);
      } else {
        const body = await c.req.json();
        params = body.parameters ?? body;
      }

      const clientReferenceId = c.req.header("x-client-reference-id") ?? undefined;

      try {
        const result = await service.invoke(route.capabilityName, token, params, {
          clientReferenceId,
        });
        return c.json(result);
      } catch (e) {
        if (e instanceof ANIPError) {
          const status = FAILURE_STATUS[e.errorType] ?? 400;
          return c.json({
            success: false,
            failure: { type: e.errorType, detail: e.detail, resolution: e.resolution, retry: e.retry },
          }, status);
        }
        throw e;
      }
    };

    if (route.method === "GET") {
      app.get(`${prefix}${route.path}`, handler);
    } else {
      app.post(`${prefix}${route.path}`, handler);
    }
  }
}
