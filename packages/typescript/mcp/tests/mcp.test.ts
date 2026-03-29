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
});
