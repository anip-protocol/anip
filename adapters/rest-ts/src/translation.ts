/**
 * ANIP -> REST/OpenAPI translation layer.
 *
 * Converts ANIP capability declarations into REST routes and
 * generates an OpenAPI 3.1 specification with ANIP metadata
 * preserved as x-anip-* extensions.
 */

import type { ANIPCapability, ANIPService } from "./discovery.js";
import type { RouteOverride } from "./config.js";

// Map ANIP input types to JSON Schema types
const TYPE_MAP: Record<string, string> = {
  string: "string",
  integer: "integer",
  number: "number",
  boolean: "boolean",
  date: "string",
  airport_code: "string",
};

export interface RESTRoute {
  capabilityName: string;
  path: string;
  method: string; // "GET" or "POST"
  capability: ANIPCapability;
}

export function generateRoutes(
  service: ANIPService,
  routeOverrides?: Record<string, RouteOverride>
): Map<string, RESTRoute> {
  const routes = new Map<string, RESTRoute>();
  const overrides = routeOverrides ?? {};

  for (const [name, cap] of service.capabilities) {
    let path: string;
    let method: string;

    if (name in overrides) {
      path = overrides[name].path;
      method = overrides[name].method.toUpperCase();
    } else {
      path = `/api/${name}`;
      method = cap.sideEffect === "read" ? "GET" : "POST";
    }

    routes.set(name, {
      capabilityName: name,
      path,
      method,
      capability: cap,
    });
  }

  return routes;
}

export function generateOpenAPISpec(
  service: ANIPService,
  routes: Map<string, RESTRoute>
): Record<string, unknown> {
  const paths: Record<string, unknown> = {};

  for (const [name, route] of routes) {
    const operation = buildOperation(name, route);
    const methodKey = route.method.toLowerCase();
    paths[route.path] = { [methodKey]: operation };
  }

  return {
    openapi: "3.1.0",
    info: {
      title: `ANIP REST Adapter \u2014 ${service.baseUrl}`,
      version: service.compliance,
      description:
        "Auto-generated REST API from an ANIP service. " +
        "x-anip-* extensions preserve ANIP metadata.",
    },
    paths,
    components: {
      schemas: {
        ANIPResponse: {
          type: "object",
          properties: {
            success: { type: "boolean" },
            result: { type: "object" },
            failure: {
              type: "object",
              nullable: true,
              properties: {
                type: { type: "string" },
                detail: { type: "string" },
                retry: { type: "boolean" },
                resolution: {
                  type: "object",
                  properties: {
                    action: { type: "string" },
                    requires: { type: "string" },
                    grantable_by: { type: "string" },
                  },
                },
              },
            },
            cost_actual: {
              type: "object",
              nullable: true,
              properties: {
                financial: {
                  type: "object",
                  properties: {
                    amount: { type: "number" },
                    currency: { type: "string" },
                  },
                },
                variance_from_estimate: { type: "string" },
              },
            },
            warnings: {
              type: "array",
              items: { type: "string" },
            },
          },
          required: ["success"],
        },
      },
    },
  };
}

function buildOperation(
  name: string,
  route: RESTRoute
): Record<string, unknown> {
  const cap = route.capability;

  const operation: Record<string, unknown> = {
    operationId: name,
    summary: cap.description,
    tags: ["ANIP Capabilities"],
    "x-anip-side-effect": cap.sideEffect,
    "x-anip-minimum-scope": cap.minimumScope,
    "x-anip-financial": cap.financial,
    "x-anip-contract-version": cap.contractVersion,
  };

  if (cap.cost) {
    operation["x-anip-cost"] = cap.cost;
  }
  if (cap.requires && cap.requires.length > 0) {
    operation["x-anip-requires"] = cap.requires.map((r) =>
      typeof r === "object" && r !== null ? r.capability ?? r : r
    );
  }
  if (cap.rollbackWindow) {
    operation["x-anip-rollback-window"] = cap.rollbackWindow;
  }

  // Parameters / request body
  if (route.method === "GET") {
    operation.parameters = buildQueryParameters(cap);
  } else {
    operation.requestBody = buildRequestBody(cap);
  }

  // Responses
  operation.responses = {
    "200": {
      description: "Successful ANIP response",
      content: {
        "application/json": {
          schema: { $ref: "#/components/schemas/ANIPResponse" },
        },
      },
    },
    "400": { description: "Invalid parameters" },
    "401": { description: "Delegation expired or invalid" },
    "403": {
      description:
        "Insufficient authority, budget exceeded, or purpose mismatch",
    },
    "404": { description: "Unknown capability" },
  };

  return operation;
}

function buildQueryParameters(
  cap: ANIPCapability
): Array<Record<string, unknown>> {
  const params: Array<Record<string, unknown>> = [];
  for (const inp of cap.inputs) {
    const jsonType = TYPE_MAP[inp.type ?? "string"] ?? "string";
    const param: Record<string, unknown> = {
      name: inp.name,
      in: "query",
      required: inp.required ?? true,
      schema: { type: jsonType } as Record<string, unknown>,
      description: inp.description ?? "",
    };
    if (inp.type === "date") {
      (param.schema as Record<string, unknown>).format = "date";
    }
    if (inp.default !== undefined && inp.default !== null) {
      (param.schema as Record<string, unknown>).default = inp.default;
    }
    params.push(param);
  }
  return params;
}

function buildRequestBody(cap: ANIPCapability): Record<string, unknown> {
  const properties: Record<string, unknown> = {};
  const required: string[] = [];

  for (const inp of cap.inputs) {
    const jsonType = TYPE_MAP[inp.type ?? "string"] ?? "string";
    const prop: Record<string, unknown> = {
      type: jsonType,
      description: inp.description ?? "",
    };
    if (inp.type === "date") {
      prop.format = "date";
    }
    if (inp.default !== undefined && inp.default !== null) {
      prop.default = inp.default;
    }
    properties[inp.name] = prop;
    if (inp.required ?? true) {
      required.push(inp.name);
    }
  }

  const schema: Record<string, unknown> = { type: "object", properties };
  if (required.length > 0) {
    schema.required = required;
  }

  return {
    required: true,
    content: {
      "application/json": {
        schema,
      },
    },
  };
}
