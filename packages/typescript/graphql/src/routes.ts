/**
 * ANIP GraphQL bindings — mount a GraphQL endpoint on a Hono app.
 */
import { buildSchema, graphql } from "graphql";
import type { Hono } from "hono";
import type { ANIPService } from "@anip/service";
import { ANIPError } from "@anip/service";
import {
  generateSchema,
  buildGraphQLResponse,
  toCamelCase,
  toSnakeCase,
} from "./translation.js";

export interface GraphQLMountOptions {
  /** URL path for the GraphQL endpoint. Default: "/graphql" */
  path?: string;
  /** URL prefix. Default: none. */
  prefix?: string;
}

/**
 * Resolve auth — JWT first, then API key.
 * See REST plan for rationale on ordering.
 */
async function resolveAuth(
  authHeader: string | undefined,
  service: ANIPService,
  capabilityName: string,
) {
  if (!authHeader || !authHeader.startsWith("Bearer ")) return null;
  const bearer = authHeader.slice(7).trim();

  // Try as JWT first — preserves original delegation chain
  let jwtError: ANIPError | null = null;
  try {
    return await service.resolveBearerToken(bearer);
  } catch (e) {
    if (!(e instanceof ANIPError)) throw e;
    jwtError = e;
  }

  // Try as API key — only if JWT failed
  const principal = await service.authenticateBearer(bearer);
  if (principal) {
    const capDecl = service.getCapabilityDeclaration(capabilityName);
    const minScope = (capDecl?.minimum_scope as string[]) ?? [];
    const tokenResult = await service.issueToken(principal, {
      subject: "adapter:anip-graphql",
      scope: minScope.length > 0 ? minScope : ["*"],
      capability: capabilityName,
      purpose_parameters: { source: "graphql" },
    });
    return await service.resolveBearerToken(tokenResult.token as string);
  }

  // Surface the original JWT error (invalid_token, token_expired, etc.)
  if (jwtError) throw jwtError;
  return null;
}

/**
 * Mount a GraphQL endpoint on a Hono app.
 *
 * Does NOT own service lifecycle — the caller (or mountAnip) is
 * responsible for start/shutdown.
 */
export async function mountAnipGraphQL(
  app: Hono,
  service: ANIPService,
  opts?: GraphQLMountOptions,
): Promise<void> {
  const gqlPath = opts?.path ?? "/graphql";
  const prefix = opts?.prefix ?? "";
  const fullPath = `${prefix}${gqlPath}`;

  // Build capabilities map
  const manifest = service.getManifest();
  const capabilities: Record<string, Record<string, unknown>> = {};
  for (const name of Object.keys(manifest.capabilities)) {
    const decl = service.getCapabilityDeclaration(name);
    if (decl) capabilities[name] = decl;
  }

  // Generate and build schema
  const schemaSdl = generateSchema(capabilities);
  const schema = buildSchema(schemaSdl);

  // Build resolvers: camelCase field name → ANIP invoke
  const resolvers: Record<string, (args: Record<string, unknown>, creds: any) => Promise<Record<string, unknown>>> = {};
  for (const name of Object.keys(capabilities)) {
    const camelName = toCamelCase(name);
    resolvers[camelName] = async (args, creds) => {
      // Convert camelCase args back to snake_case for ANIP
      const snakeArgs: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(args)) {
        snakeArgs[toSnakeCase(k)] = v;
      }

      let token;
      try {
        token = await resolveAuth(creds?.authHeader, service, name);
      } catch (e) {
        if (e instanceof ANIPError) {
          return buildGraphQLResponse({
            success: false,
            failure: { type: e.errorType, detail: e.detail, resolution: e.resolution, retry: e.retry },
          });
        }
        throw e;
      }

      if (!token) {
        return buildGraphQLResponse({
          success: false,
          failure: {
            type: "authentication_required",
            detail: "Authorization header required",
            resolution: { action: "provide_credentials" },
            retry: true,
          },
        });
      }

      try {
        const result = await service.invoke(name, token, snakeArgs);
        return buildGraphQLResponse(result);
      } catch (e) {
        if (e instanceof ANIPError) {
          return buildGraphQLResponse({
            success: false,
            failure: { type: e.errorType, detail: e.detail, resolution: e.resolution, retry: e.retry },
          });
        }
        throw e;
      }
    };
  }

  // POST /graphql — execute query/mutation
  app.post(fullPath, async (c) => {
    const body = await c.req.json() as {
      query: string;
      variables?: Record<string, unknown>;
      operationName?: string;
    };

    const authHeader = c.req.header("authorization");

    // Wrap resolvers to inject auth context
    const rootValue: Record<string, (args: Record<string, unknown>) => Promise<Record<string, unknown>>> = {};
    for (const [name, resolver] of Object.entries(resolvers)) {
      rootValue[name] = (args) => resolver(args, { authHeader });
    }

    const result = await graphql({
      schema,
      source: body.query,
      rootValue,
      variableValues: body.variables,
      operationName: body.operationName,
    });

    return c.json(result);
  });

  // GET /graphql — simple playground
  app.get(fullPath, (c) => {
    return c.html(`<!DOCTYPE html>
<html><head><title>ANIP GraphQL</title></head><body>
<h2>ANIP GraphQL Playground</h2>
<textarea id="q" rows="10" cols="60">{ }</textarea><br>
<button onclick="run()">Run</button><pre id="r"></pre>
<script>
async function run() {
  const r = await fetch("${fullPath}", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({query: document.getElementById("q").value})
  });
  document.getElementById("r").textContent = JSON.stringify(await r.json(), null, 2);
}
</script></body></html>`);
  });

  // GET /schema.graphql — raw SDL
  app.get(`${prefix}/schema.graphql`, (c) => {
    return c.text(schemaSdl);
  });
}
