import { describe, expect, it } from "vitest";
import { app } from "../src/app.js";
import { generatedCapabilityMetadata } from "../src/generated/runtime-target.js";

async function issueToken(capabilityId: string, scope: string[]) {
  const response = await app.request("/anip/tokens", {
    method: "POST",
    headers: {
      authorization: "Bearer dev-admin-key",
      "content-type": "application/json",
    },
    body: JSON.stringify({ capability: capabilityId, scope, subject: "test-agent" }),
  });
  expect(response.status).toBe(200);
  const body = await response.json() as { token: string };
  return body.token;
}

describe("generated ANIP service", () => {
  it("serves discovery", async () => {
    const response = await app.request("/.well-known/anip");
    expect(response.status).toBe(200);
    const body = await response.json() as { anip_discovery: { capabilities: Record<string, unknown> } };
    expect(body.anip_discovery.capabilities[generatedCapabilityMetadata[0].capability_id]).toBeDefined();
  });

  it("invokes the first generated capability", async () => {
    const capability = generatedCapabilityMetadata[0];
    const token = await issueToken(capability.capability_id, capability.minimum_scope);
    const response = await app.request(`/anip/invoke/${capability.capability_id}`, {
      method: "POST",
      headers: {
        authorization: `Bearer ${token}`,
        "content-type": "application/json",
      },
      body: JSON.stringify({ parameters: capability.sample_parameters }),
    });
    expect(response.status).toBe(200);
    const body = await response.json() as { success: boolean; result: { execution_status?: string } };
    expect(body.success).toBe(true);
    expect(body.result.execution_status).toBeTruthy();
  });
});
