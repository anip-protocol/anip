import { describe, it, expect } from "vitest";
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { createANIPService, defineCapability } from "@anip-dev/service";
import { InMemoryStorage } from "@anip-dev/server";
import type { CapabilityDeclaration } from "@anip-dev/core";
import { mountAnipMcp } from "../src/routes.js";
import { capabilityToInputSchema, enrichDescription } from "../src/translation.js";

const API_KEY = "test-key-123";

function greetCap() {
  return defineCapability({
    declaration: {
      name: "greet",
      description: "Say hello",
      contract_version: "1.0",
      inputs: [{ name: "name", type: "string", required: true, description: "Who" }],
      output: { type: "object", fields: ["message"] },
      side_effect: { type: "read", rollback_window: "not_applicable" },
      minimum_scope: ["greet"],
      response_modes: ["unary"],
    } as CapabilityDeclaration,
    handler: (_ctx, params) => ({ message: `Hello, ${params.name}!` }),
  });
}

async function makeService() {
  return createANIPService({
    serviceId: "test-mcp-service",
    capabilities: [greetCap()],
    storage: new InMemoryStorage(),
    authenticate: (bearer) => (bearer === API_KEY ? "test-agent" : null),
  });
}

const CREDENTIALS = { apiKey: API_KEY, scope: ["greet"], subject: "test-agent" };

describe("Translation", () => {
  it("converts capability inputs to JSON Schema", () => {
    const decl = greetCap().declaration;
    const schema = capabilityToInputSchema(decl);
    expect(schema.type).toBe("object");
    expect(schema.properties.name).toBeDefined();
    expect(schema.properties.name.type).toBe("string");
    expect(schema.required).toContain("name");
  });

  it("enriches description with side-effect info", () => {
    const decl = greetCap().declaration;
    const desc = enrichDescription(decl);
    expect(desc).toContain("Read-only");
    expect(desc).toContain("Delegation scope: greet");
  });
});

// SPEC.md §4.10: a required input that sets resolution.on_missing is answered
// by the service, so the tool schema must not demand it.
function clarifyCap(calls: Array<Record<string, unknown>>) {
  return defineCapability({
    declaration: {
      name: "list_orders",
      description: "List orders",
      contract_version: "1.0",
      inputs: [
        { name: "status", type: "string", required: true, description: "Order status" },
        {
          name: "region", type: "string", required: true, description: "Region",
          resolution: { mode: "clarify", on_missing: "clarify" },
        },
        {
          name: "channel", type: "string", required: true, description: "Channel",
          resolution: { mode: "clarify" },
        },
      ],
      output: { type: "object", fields: ["orders"] },
      side_effect: { type: "read", rollback_window: "not_applicable" },
      minimum_scope: ["greet"],
      response_modes: ["unary"],
    } as unknown as CapabilityDeclaration,
    handler: (_ctx, params) => {
      calls.push({ ...params });
      return { orders: [], region: params.region ?? "asked" };
    },
  });
}

describe("Inputs that declare resolution.on_missing", () => {
  it("are not required by the tool input schema", () => {
    const schema = capabilityToInputSchema(clarifyCap([]).declaration);
    expect(Object.keys(schema.properties)).toEqual(["status", "region", "channel"]);
    expect(schema.required).toEqual(["status", "channel"]);
  });

  it("reach the handler when the tool call leaves them out", async () => {
    const calls: Array<Record<string, unknown>> = [];
    const service = createANIPService({
      serviceId: "test-mcp-on-missing",
      capabilities: [clarifyCap(calls)],
      storage: new InMemoryStorage(),
      authenticate: (bearer) => (bearer === API_KEY ? "test-agent" : null),
    });
    const server = new Server({ name: "test", version: "1.0" }, { capabilities: { tools: {} } });
    const lifecycle = await mountAnipMcp(server, service, { credentials: CREDENTIALS });
    const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
    await server.connect(serverTransport);
    const client = new Client({ name: "test-client", version: "1.0" });
    await client.connect(clientTransport);

    const tools = await client.listTools();
    expect(tools.tools[0].inputSchema.required).toEqual(["status", "channel"]);

    const ok = await client.callTool({ name: "list_orders", arguments: { status: "open", channel: "web" } });
    expect(ok.isError).toBeFalsy();
    expect(calls).toEqual([{ status: "open", channel: "web" }]);

    // `channel` declares a resolution without on_missing: it is still required.
    const refused = await client.callTool({ name: "list_orders", arguments: { status: "open" } });
    expect(refused.isError).toBe(true);
    expect((refused.content as any[])[0].text).toContain("list_orders is missing required input(s): channel");
    expect(calls).toHaveLength(1);

    await client.close();
    await lifecycle.shutdown();
  });
});

// The service checks a supplied value against a declared primitive type
// (SPEC.md §6.3), so the tool schema has to name that same JSON type.
describe("Declared primitive types in the tool input schema", () => {
  function quoteCap(calls: Array<Record<string, unknown>>) {
    return defineCapability({
      declaration: {
        name: "price_quote",
        description: "Price a quote",
        contract_version: "1.0",
        inputs: [
          { name: "quote", type: "object", required: true, description: "The quote" },
          { name: "tags", type: "array", required: false, description: "Tags" },
          { name: "count", type: "integer", required: false, description: "Count" },
          { name: "ratio", type: "number", required: false, description: "Ratio" },
          { name: "urgent", type: "boolean", required: false, description: "Urgent" },
          { name: "note", type: "string", required: false, description: "Note" },
          { name: "day", type: "date", required: false, description: "Day" },
          { name: "sku", type: "product_code", required: false, description: "A domain type" },
        ],
        output: { type: "object", fields: ["ok"] },
        side_effect: { type: "read", rollback_window: "not_applicable" },
        minimum_scope: ["greet"],
        response_modes: ["unary"],
      } as unknown as CapabilityDeclaration,
      handler: (_ctx, params) => {
        calls.push({ ...params });
        return { ok: true };
      },
    });
  }

  it("names the JSON type the service will accept", () => {
    const schema = capabilityToInputSchema(quoteCap([]).declaration);
    const types = Object.fromEntries(Object.entries(schema.properties).map(([name, p]) => [name, p.type]));
    expect(types).toEqual({
      quote: "object",
      tags: "array",
      count: "integer",
      ratio: "number",
      urgent: "boolean",
      note: "string",
      day: "string",
      sku: "string",
    });
  });

  it("a tool call that follows the schema is accepted", async () => {
    const calls: Array<Record<string, unknown>> = [];
    const service = createANIPService({
      serviceId: "test-mcp-types",
      capabilities: [quoteCap(calls)],
      storage: new InMemoryStorage(),
      authenticate: (bearer) => (bearer === API_KEY ? "test-agent" : null),
    });
    const server = new Server({ name: "test", version: "1.0" }, { capabilities: { tools: {} } });
    const lifecycle = await mountAnipMcp(server, service, { credentials: CREDENTIALS });
    const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
    await server.connect(serverTransport);
    const client = new Client({ name: "test-client", version: "1.0" });
    await client.connect(clientTransport);

    const tools = await client.listTools();
    const properties = tools.tools[0].inputSchema.properties as Record<string, { type: string }>;
    const sample: Record<string, unknown> = { object: { id: "q1" }, array: ["a"], integer: 2, number: 0.5, boolean: true, string: "x" };
    const args = Object.fromEntries(Object.entries(properties).map(([name, p]) => [name, sample[p.type]]));

    const result = await client.callTool({ name: "price_quote", arguments: args });

    expect((result.content as any[])[0].text).not.toContain("FAILED");
    expect(result.isError).toBeFalsy();
    expect(calls).toEqual([args]);

    await client.close();
    await lifecycle.shutdown();
  });
});

describe("mountAnipMcp", () => {
  it("requires credentials for MCP Server", async () => {
    const service = await makeService();
    const server = new Server(
      { name: "test", version: "1.0" },
      { capabilities: { tools: {} } },
    );
    await expect(mountAnipMcp(server, service)).rejects.toThrow("credentials");
  });

  it("mounts and returns lifecycle handle", async () => {
    const service = await makeService();
    const server = new Server(
      { name: "test", version: "1.0" },
      { capabilities: { tools: {} } },
    );
    const lifecycle = await mountAnipMcp(server, service, { credentials: CREDENTIALS });
    expect(lifecycle.stop).toBeTypeOf("function");
    expect(lifecycle.shutdown).toBeTypeOf("function");
    await lifecycle.shutdown();
  });
});

// Integration test: full tool call through MCP Client + Server
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";

describe("MCP tool invocation (integration)", () => {
  it("call_tool invokes ANIP capability and returns result", async () => {
    const service = await makeService();
    const server = new Server(
      { name: "test", version: "1.0" },
      { capabilities: { tools: {} } },
    );
    const lifecycle = await mountAnipMcp(server, service, { credentials: CREDENTIALS });

    const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
    await server.connect(serverTransport);
    const client = new Client({ name: "test-client", version: "1.0" });
    await client.connect(clientTransport);

    // List tools
    const tools = await client.listTools();
    expect(tools.tools.length).toBe(1);
    expect(tools.tools[0].name).toBe("greet");

    // Call tool
    const result = await client.callTool({ name: "greet", arguments: { name: "World" } });
    expect(result.isError).toBeFalsy();
    const text = (result.content as any[])[0].text;
    expect(text).toContain("Hello, World!");

    await client.close();
    await lifecycle.shutdown();
  });

  it("call_tool with unknown tool returns error", async () => {
    const service = await makeService();
    const server = new Server(
      { name: "test", version: "1.0" },
      { capabilities: { tools: {} } },
    );
    const lifecycle = await mountAnipMcp(server, service, { credentials: CREDENTIALS });

    const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
    await server.connect(serverTransport);
    const client = new Client({ name: "test-client", version: "1.0" });
    await client.connect(clientTransport);

    const result = await client.callTool({ name: "nonexistent", arguments: {} });
    expect(result.isError).toBe(true);
    const text = (result.content as any[])[0].text;
    expect(text).toContain("Unknown tool");

    await client.close();
    await lifecycle.shutdown();
  });

  it("call_tool with invalid credentials returns failure", async () => {
    const service = await makeService();
    const server = new Server(
      { name: "test", version: "1.0" },
      { capabilities: { tools: {} } },
    );
    const badCreds = { apiKey: "wrong-key", scope: ["greet"], subject: "test" };
    const lifecycle = await mountAnipMcp(server, service, { credentials: badCreds });

    const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
    await server.connect(serverTransport);
    const client = new Client({ name: "test-client", version: "1.0" });
    await client.connect(clientTransport);

    const result = await client.callTool({ name: "greet", arguments: { name: "World" } });
    expect(result.isError).toBe(true);
    const text = (result.content as any[])[0].text;
    expect(text).toContain("FAILED");
    expect(text).toContain("authentication_required");

    await client.close();
    await lifecycle.shutdown();
  });

  // SPEC.md §6.3 "Parameter Validation": the MCP adapter reports the refusal
  // as a tool error carrying the failure, not as a success.
  it("call_tool without a required input is an invalid_parameters tool error", async () => {
    const service = await makeService();
    const server = new Server(
      { name: "test", version: "1.0" },
      { capabilities: { tools: {} } },
    );
    const lifecycle = await mountAnipMcp(server, service, { credentials: CREDENTIALS });

    const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
    await server.connect(serverTransport);
    const client = new Client({ name: "test-client", version: "1.0" });
    await client.connect(clientTransport);

    const missing = await client.callTool({ name: "greet", arguments: {} });
    expect(missing.isError).toBe(true);
    const missingText = (missing.content as any[])[0].text;
    expect(missingText).toContain("FAILED: invalid_parameters");
    expect(missingText).toContain("greet is missing required input(s): name");
    expect(missingText).toContain("Resolution: retry_now");
    expect(missingText).toContain("Requires: parameters that match the capability's declared inputs");
    expect(missingText).toContain("Retryable: no");
    expect(missingText).not.toContain("Hello");

    const wrong = await client.callTool({ name: "greet", arguments: { name: ["World"] } });
    expect(wrong.isError).toBe(true);
    const wrongText = (wrong.content as any[])[0].text;
    expect(wrongText).toContain("FAILED: invalid_parameters");
    expect(wrongText).toContain("'name' must be string, got array");
    expect(wrongText).not.toContain("Hello");

    await client.close();
    await lifecycle.shutdown();
  });
});
