import { describe, it, expect } from "vitest";
import {
  createANIPService,
  defineCapability,
} from "../src/index.js";
import type { CapabilityDef } from "../src/index.js";
import type { CapabilityDeclaration } from "@anip/core";
import { InMemoryStorage, CheckpointPolicy } from "@anip/server";

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

function testCap(name = "greet"): CapabilityDef {
  return defineCapability({
    declaration: {
      name,
      description: "Say hello",
      contract_version: "1.0",
      inputs: [
        { name: "name", type: "string", required: true, description: "Who to greet" },
      ],
      output: { type: "object", fields: ["message"] },
      side_effect: { type: "read", rollback_window: null },
      minimum_scope: ["greet"],
    } as CapabilityDeclaration,
    handler: (_ctx, params) => ({
      message: `Hello, ${params.name}!`,
    }),
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("getHealth()", () => {
  it("returns a valid HealthReport shape after start()", async () => {
    const service = createANIPService({
      serviceId: "health-test",
      capabilities: [testCap()],
      storage: new InMemoryStorage(),
    });
    await service.start();
    try {
      const report = service.getHealth();
      expect(report).toHaveProperty("status");
      expect(report).toHaveProperty("storage");
      expect(report).toHaveProperty("checkpoint");
      expect(report).toHaveProperty("retention");
      expect(report).toHaveProperty("aggregation");
    } finally {
      await service.stop();
    }
  });

  it("status is 'healthy' under normal conditions", async () => {
    const service = createANIPService({
      serviceId: "health-test",
      capabilities: [testCap()],
      storage: new InMemoryStorage(),
    });
    await service.start();
    try {
      const report = service.getHealth();
      expect(report.status).toBe("healthy");
    } finally {
      await service.stop();
    }
  });

  it("checkpoint is null when no checkpoint policy is configured", async () => {
    const service = createANIPService({
      serviceId: "health-test",
      capabilities: [testCap()],
      storage: new InMemoryStorage(),
    });
    await service.start();
    try {
      const report = service.getHealth();
      expect(report.checkpoint).toBeNull();
    } finally {
      await service.stop();
    }
  });

  it("checkpoint is present when trust is anchored with a checkpoint policy", async () => {
    const service = createANIPService({
      serviceId: "health-test",
      capabilities: [testCap()],
      storage: new InMemoryStorage(),
      trust: "anchored",
      checkpointPolicy: new CheckpointPolicy({ intervalSeconds: 300 }),
    });
    await service.start();
    try {
      const report = service.getHealth();
      expect(report.checkpoint).not.toBeNull();
      expect(report.checkpoint).toHaveProperty("healthy");
      expect(report.checkpoint).toHaveProperty("lastRunAt");
      expect(report.checkpoint).toHaveProperty("lagSeconds");
    } finally {
      await service.stop();
    }
  });

  it("aggregation is null when no aggregation window is configured", async () => {
    const service = createANIPService({
      serviceId: "health-test",
      capabilities: [testCap()],
      storage: new InMemoryStorage(),
    });
    await service.start();
    try {
      const report = service.getHealth();
      expect(report.aggregation).toBeNull();
    } finally {
      await service.stop();
    }
  });

  it("aggregation is present when an aggregation window is configured", async () => {
    const service = createANIPService({
      serviceId: "health-test",
      capabilities: [testCap()],
      storage: new InMemoryStorage(),
      aggregationWindow: 60,
    });
    await service.start();
    try {
      const report = service.getHealth();
      expect(report.aggregation).not.toBeNull();
      expect(report.aggregation).toHaveProperty("pendingWindows");
      expect(report.aggregation!.pendingWindows).toBe(0);
    } finally {
      await service.stop();
    }
  });

  it("storage.type reflects the backend (memory for in-memory tests)", async () => {
    const service = createANIPService({
      serviceId: "health-test",
      capabilities: [testCap()],
      storage: new InMemoryStorage(),
    });
    await service.start();
    try {
      const report = service.getHealth();
      expect(report.storage.type).toBe("memory");
    } finally {
      await service.stop();
    }
  });

  it("retention fields are present with correct defaults", async () => {
    const service = createANIPService({
      serviceId: "health-test",
      capabilities: [testCap()],
      storage: new InMemoryStorage(),
    });
    await service.start();
    try {
      const report = service.getHealth();
      expect(report.retention).toEqual({
        healthy: true,
        lastRunAt: null,
        lastDeletedCount: 0,
      });
    } finally {
      await service.stop();
    }
  });
});
