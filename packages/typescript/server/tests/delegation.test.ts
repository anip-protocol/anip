import { describe, it, expect } from "vitest";
import { DelegationEngine } from "../src/delegation.js";
import { InMemoryStorage } from "../src/storage.js";

function makeEngine() {
  return new DelegationEngine(new InMemoryStorage(), { serviceId: "test-svc" });
}

describe("DelegationEngine", () => {
  it("issues root token and validates", async () => {
    const engine = makeEngine();
    const { token } = await engine.issueRootToken({
      authenticatedPrincipal: "human:alice@example.com",
      subject: "agent",
      scope: ["travel.search"],
      capability: "search_flights",
    });
    expect(token.root_principal).toBe("human:alice@example.com");
    expect(token.issuer).toBe("test-svc");
    const result = await engine.validateDelegation(token, ["travel.search"], "search_flights");
    expect(result).toHaveProperty("token_id");
  });

  it("delegates from parent with derived trust context", async () => {
    const engine = makeEngine();
    const { token: parent } = await engine.issueRootToken({
      authenticatedPrincipal: "human:alice@example.com",
      subject: "agent-a",
      scope: ["travel.search", "travel.book"],
      capability: "search_flights",
    });
    const result = await engine.delegate({
      parentToken: parent,
      subject: "agent-b",
      scope: ["travel.search"],
      capability: "search_flights",
    });
    expect(result).not.toHaveProperty("type"); // not ANIPFailure
    const { token: child } = result as { token: any; tokenId: string };
    expect(child.root_principal).toBe("human:alice@example.com");
    expect(child.issuer).toBe("agent-a");
  });

  it("rejects insufficient scope", async () => {
    const engine = makeEngine();
    const { token } = await engine.issueRootToken({
      authenticatedPrincipal: "human:alice@example.com",
      subject: "agent",
      scope: ["travel.search"],
      capability: "search_flights",
    });
    const result = await engine.validateDelegation(token, ["travel.book"], "book_flight");
    expect(result).toHaveProperty("type", "scope_insufficient");
  });

  it("rejects scope widening in delegation", async () => {
    const engine = makeEngine();
    const { token: parent } = await engine.issueRootToken({
      authenticatedPrincipal: "human:alice@example.com",
      subject: "agent",
      scope: ["travel.search"],
      capability: "search_flights",
    });
    const result = await engine.delegate({
      parentToken: parent,
      subject: "sub-agent",
      scope: ["travel.search", "travel.book"],
      capability: "search_flights",
    });
    expect(result).toHaveProperty("type", "scope_escalation");
  });
});
