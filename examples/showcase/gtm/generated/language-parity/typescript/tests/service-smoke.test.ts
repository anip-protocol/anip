import { describe, expect, it } from "vitest";
import { generatedCapabilityMetadata } from "../src/generated/runtime-target.js";

// The smoke test invokes as the principal the generated policy lets reach the
// backend, if any; SMOKE_EXPECT is the outcome the policy gives that principal.
const SMOKE_EXPECT = "success";
const previousApiKeys = process.env.ANIP_API_KEYS_JSON;
process.env.ANIP_API_KEYS_JSON = "{\"smoke-test-key\":\"human:smoke-test|actor_id=sales_leader\"}";
const { app } = await import("../src/app.js");
if (previousApiKeys === undefined) delete process.env.ANIP_API_KEYS_JSON;
else process.env.ANIP_API_KEYS_JSON = previousApiKeys;

async function issueToken(capabilityId: string, scope: string[]) {
  const response = await app.request("/anip/tokens", {
    method: "POST",
    headers: {
      authorization: "Bearer smoke-test-key",
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
    const body = await response.json() as { success: boolean; result: { execution_status?: string }; failure?: { type?: string } };
    if (SMOKE_EXPECT !== "success") {
      expect(body.success).toBe(false);
      expect(body.failure?.type).toBe(SMOKE_EXPECT);
      return;
    }
    expect(response.status).toBe(200);
    expect(body.success).toBe(true);
    expect(body.result.execution_status).toBeTruthy();
  });
});
