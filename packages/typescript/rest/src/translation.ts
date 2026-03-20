/**
 * ANIP → REST translation layer.
 *
 * Generates OpenAPI 3.1 specs and route mappings from ANIP capabilities.
 */

const TYPE_MAP: Record<string, string> = {
  string: "string",
  integer: "integer",
  number: "number",
  boolean: "boolean",
  date: "string",
  airport_code: "string",
};

export interface RouteOverride {
  path: string;
  method: string;
}

export interface RESTRoute {
  capabilityName: string;
  path: string;
  method: string; // "GET" or "POST"
  declaration: Record<string, unknown>;
}

/**
 * Generate REST routes from service capabilities.
 * Default: GET for read side_effect, POST for everything else.
 * Route overrides allow custom paths and methods.
 */
export function generateRoutes(
  capabilities: Record<string, Record<string, unknown>>,
  overrides?: Record<string, RouteOverride>,
): RESTRoute[] {
  const routes: RESTRoute[] = [];
  for (const [name, decl] of Object.entries(capabilities)) {
    const override = overrides?.[name];
    const se = decl.side_effect as Record<string, unknown> | string;
    const seType = typeof se === "string" ? se : (se as any)?.type ?? "read";

    routes.push({
      capabilityName: name,
      path: override?.path ?? `/api/${name}`,
      method: (override?.method ?? (seType === "read" ? "GET" : "POST")).toUpperCase(),
      declaration: decl,
    });
  }
  return routes;
}

/**
 * Build OpenAPI 3.1 query parameters from capability inputs (for GET routes).
 */
function buildQueryParameters(decl: Record<string, unknown>): Record<string, unknown>[] {
  const inputs = (decl.inputs ?? []) as Array<Record<string, unknown>>;
  return inputs.map((inp) => ({
    name: inp.name,
    in: "query",
    required: inp.required !== false,
    schema: {
      type: TYPE_MAP[(inp.type as string) ?? "string"] ?? "string",
      ...(inp.type === "date" ? { format: "date" } : {}),
      ...(inp.default != null ? { default: inp.default } : {}),
    },
    description: inp.description ?? "",
  }));
}

/**
 * Build OpenAPI 3.1 request body from capability inputs (for POST routes).
 */
function buildRequestBody(decl: Record<string, unknown>): Record<string, unknown> {
  const inputs = (decl.inputs ?? []) as Array<Record<string, unknown>>;
  const properties: Record<string, unknown> = {};
  const required: string[] = [];
  for (const inp of inputs) {
    properties[inp.name as string] = {
      type: TYPE_MAP[(inp.type as string) ?? "string"] ?? "string",
      ...(inp.type === "date" ? { format: "date" } : {}),
      description: inp.description ?? "",
    };
    if (inp.required !== false) required.push(inp.name as string);
  }
  return {
    required: true,
    content: {
      "application/json": {
        schema: { type: "object", properties, ...(required.length > 0 ? { required } : {}) },
      },
    },
  };
}

/**
 * Generate a complete OpenAPI 3.1 spec from routes.
 */
export function generateOpenAPISpec(
  serviceId: string,
  routes: RESTRoute[],
): Record<string, unknown> {
  const paths: Record<string, unknown> = {};
  for (const route of routes) {
    const method = route.method.toLowerCase();
    const se = route.declaration.side_effect as Record<string, unknown> | string;
    const seType = typeof se === "string" ? se : (se as any)?.type ?? "read";
    const minScope = (route.declaration.minimum_scope ?? []) as string[];
    const financial = !!(route.declaration.cost as any)?.financial;

    const operation: Record<string, unknown> = {
      summary: route.declaration.description as string,
      operationId: route.capabilityName,
      responses: {
        "200": { description: "Success", content: { "application/json": { schema: { $ref: "#/components/schemas/ANIPResponse" } } } },
        "401": { description: "Authentication required" },
        "403": { description: "Authorization failed" },
        "404": { description: "Unknown capability" },
      },
      "x-anip-side-effect": seType,
      "x-anip-minimum-scope": minScope,
      "x-anip-financial": financial,
    };

    if (method === "get") {
      operation.parameters = buildQueryParameters(route.declaration);
    } else {
      operation.requestBody = buildRequestBody(route.declaration);
    }

    paths[route.path] = { [method]: operation };
  }

  return {
    openapi: "3.1.0",
    info: { title: `ANIP REST — ${serviceId}`, version: "1.0" },
    paths,
    components: {
      schemas: {
        ANIPResponse: {
          type: "object",
          properties: {
            success: { type: "boolean" },
            result: { type: "object" },
            invocation_id: { type: "string" },
            failure: { $ref: "#/components/schemas/ANIPFailure" },
          },
        },
        ANIPFailure: {
          type: "object",
          properties: {
            type: { type: "string" },
            detail: { type: "string" },
            resolution: { type: "object" },
            retry: { type: "boolean" },
          },
        },
      },
      securitySchemes: {
        bearer: { type: "http", scheme: "bearer", bearerFormat: "JWT" },
      },
    },
    security: [{ bearer: [] }],
  };
}
