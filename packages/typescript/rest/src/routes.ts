/**
 * ANIP REST bindings — mount RESTful API endpoints on a Hono app.
 */
import type { Hono } from "hono";
import { failureStatusCode } from "@anip-dev/core";
import type { ANIPService } from "@anip-dev/service";
import { ANIPError } from "@anip-dev/service";
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

/** A request body that is not a JSON object (SPEC.md §6.3 "HTTP Status Codes"). */
function invalidBodyFailure(detail: string) {
  return {
    success: false,
    failure: {
      type: "invalid_parameters",
      detail,
      resolution: { action: "retry_now", recovery_class: "retry_now" },
      retry: false,
    },
  };
}

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

const JSON_NUMBER = /^-?(0|[1-9]\d*)(\.\d+)?([eE][+-]?\d+)?$/;

/**
 * Read a query string value as the JSON value its declared type calls for.
 * A value that cannot be read that way stays a string, and the service's
 * parameter validation (SPEC.md §6.3) refuses it by name.
 */
function convertQueryValue(value: string, type: string | undefined): unknown {
  switch (type) {
    case "integer":
    case "number":
      return JSON_NUMBER.test(value) ? Number(value) : value;
    case "boolean":
      return value === "true" ? true : value === "false" ? false : value;
    case "array":
    case "object":
      // The only way a query string can carry one: as JSON text.
      try {
        return JSON.parse(value);
      } catch {
        return value;
      }
    default:
      return value;
  }
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
    result[key] = convertQueryValue(value, typeMap.get(key));
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
          return c.json({
            success: false,
            failure: { type: e.errorType, detail: e.detail, resolution: e.resolution, retry: e.retry },
          }, failureStatusCode(e.errorType));
        }
        throw e;
      }

      if (!token) {
        return c.json({
          success: false,
          failure: {
            type: "authentication_required",
            detail: "Authorization header with Bearer token or API key required",
            resolution: { action: "provide_credentials", recovery_class: "retry_now", requires: "Bearer token or API key" },
            retry: true,
          },
        }, failureStatusCode("authentication_required"));
      }

      // Extract parameters
      let params: Record<string, unknown>;
      if (route.method === "GET") {
        const query = Object.fromEntries(new URL(c.req.url).searchParams);
        params = convertQueryParams(query, route.declaration);
      } else {
        let body: unknown;
        try {
          body = await c.req.json();
        } catch {
          return c.json(invalidBodyFailure("request body must be JSON"), failureStatusCode("invalid_parameters"));
        }
        if (typeof body !== "object" || body === null || Array.isArray(body)) {
          return c.json(
            invalidBodyFailure("request body must be a JSON object"),
            failureStatusCode("invalid_parameters"),
          );
        }
        const fields = body as Record<string, unknown>;
        params = (fields.parameters ?? fields) as Record<string, unknown>;
      }

      const clientReferenceId = c.req.header("x-client-reference-id") ?? undefined;
      const taskId = c.req.header("x-task-id") ?? undefined;
      const parentInvocationId = c.req.header("x-parent-invocation-id") ?? undefined;

      try {
        const result = await service.invoke(route.capabilityName, token, params, {
          clientReferenceId,
          taskId,
          parentInvocationId,
        });
        if (!result.success) {
          // The status of the failure type, as on the protocol endpoints.
          const failure = result.failure as Record<string, unknown> | undefined;
          return c.json(result, failureStatusCode(failure?.type as string | undefined));
        }
        return c.json(result);
      } catch (e) {
        if (e instanceof ANIPError) {
          return c.json({
            success: false,
            failure: { type: e.errorType, detail: e.detail, resolution: e.resolution, retry: e.retry },
          }, failureStatusCode(e.errorType));
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
