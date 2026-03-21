import { describe, it, expect, beforeAll, afterAll } from "vitest";
import { Hono } from "hono";
import { serve } from "@hono/node-server";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";
import { createANIPService, defineCapability } from "@anip/service";
import { InMemoryStorage } from "@anip/server";
import type { CapabilityDeclaration } from "@anip/core";
import { mountAnipMcpHono } from "../src/index.js";
import type { AddressInfo } from "node:net";

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

describe("MCP Streamable HTTP (Hono)", () => {
  let server: ReturnType<typeof serve>;
  let port: number;
  let closeTransport: () => Promise<void>;

  beforeAll(async () => {
    const service = createANIPService({
      serviceId: "test-mcp-hono",
      capabilities: [greetCap()],
      storage: new InMemoryStorage(),
      authenticate: (bearer) => (bearer === API_KEY ? "test-agent" : null),
    });

    const app = new Hono();
    const result = await mountAnipMcpHono(app, service);
    closeTransport = result.closeTransport;

    await new Promise<void>((resolve) => {
      server = serve({ fetch: app.fetch, port: 0 }, (info) => {
        port = (info as AddressInfo).port;
        resolve();
      });
    });
  });

  afterAll(async () => {
    await closeTransport();
    await new Promise<void>((resolve, reject) => {
      server.close((err) => (err ? reject(err) : resolve()));
    });
  });

  function makeClient(headers?: Record<string, string>) {
    const transport = new StreamableHTTPClientTransport(
      new URL(`http://localhost:${port}/mcp`),
      { requestInit: { headers } },
    );
    const client = new Client({ name: "test-client", version: "1.0" });
    return { client, transport };
  }

  it("listTools returns registered tools", async () => {
    const { client, transport } = makeClient({ Authorization: `Bearer ${API_KEY}` });
    await client.connect(transport);
    try {
      const result = await client.listTools();
      expect(result.tools.length).toBe(1);
      expect(result.tools[0].name).toBe("greet");
    } finally {
      await client.close();
    }
  });

  it("callTool with valid API key returns result", async () => {
    const { client, transport } = makeClient({ Authorization: `Bearer ${API_KEY}` });
    await client.connect(transport);
    try {
      const result = await client.callTool({ name: "greet", arguments: { name: "World" } });
      expect(result.isError).toBeFalsy();
      const text = (result.content as Array<{ type: string; text: string }>)[0].text;
      expect(text).toContain("Hello, World!");
    } finally {
      await client.close();
    }
  });

  it("callTool without auth returns authentication_required", async () => {
    const { client, transport } = makeClient(); // no Authorization header
    await client.connect(transport);
    try {
      const result = await client.callTool({ name: "greet", arguments: { name: "World" } });
      expect(result.isError).toBe(true);
      const text = (result.content as Array<{ type: string; text: string }>)[0].text;
      expect(text).toContain("authentication_required");
    } finally {
      await client.close();
    }
  });

  it("callTool with unknown tool returns error", async () => {
    const { client, transport } = makeClient({ Authorization: `Bearer ${API_KEY}` });
    await client.connect(transport);
    try {
      const result = await client.callTool({ name: "nonexistent", arguments: {} });
      expect(result.isError).toBe(true);
      const text = (result.content as Array<{ type: string; text: string }>)[0].text;
      expect(text).toContain("Unknown tool");
    } finally {
      await client.close();
    }
  });
});
