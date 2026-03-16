import { describe, it, expect } from "vitest";
import type { InvocationContext } from "../src/types.js";

describe("InvocationContext.emitProgress", () => {
  it("is a callable method on the interface", () => {
    const received: Record<string, unknown>[] = [];
    const ctx: InvocationContext = {
      token: {} as any,
      rootPrincipal: "human:alice",
      subject: "agent:bot",
      scopes: ["test"],
      delegationChain: ["tok-1"],
      invocationId: "inv-000000000000",
      clientReferenceId: null,
      setCostActual(_cost) {},
      async emitProgress(payload) {
        received.push(payload);
      },
    };

    expect(ctx.emitProgress).toBeDefined();
  });

  it("receives payloads when called", async () => {
    const received: Record<string, unknown>[] = [];
    const ctx: InvocationContext = {
      token: {} as any,
      rootPrincipal: "human:alice",
      subject: "agent:bot",
      scopes: ["test"],
      delegationChain: ["tok-1"],
      invocationId: "inv-000000000000",
      clientReferenceId: null,
      setCostActual(_cost) {},
      async emitProgress(payload) {
        received.push(payload);
      },
    };

    await ctx.emitProgress({ percent: 50 });
    expect(received).toEqual([{ percent: 50 }]);
  });
});
