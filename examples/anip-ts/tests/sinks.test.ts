import { describe, it, expect, afterEach } from "vitest";
import { mkdtempSync, readdirSync, readFileSync } from "fs";
import { join } from "path";
import { tmpdir } from "os";
import { LocalFileSink } from "../src/sinks";
import { setSink, enqueueForSink, getPendingSinkCount, resetSink } from "../src/checkpoint";

describe("LocalFileSink", () => {
  it("writes checkpoint file", () => {
    const dir = mkdtempSync(join(tmpdir(), "sink-"));
    const sink = new LocalFileSink(dir);
    sink.publish({ checkpoint_id: "ckpt-001", merkle_root: "sha256:abc" });
    const files = readdirSync(dir);
    expect(files).toHaveLength(1);
    expect(files[0]).toBe("ckpt-001.json");
    const content = JSON.parse(readFileSync(join(dir, files[0]), "utf-8"));
    expect(content.checkpoint_id).toBe("ckpt-001");
    expect(content.merkle_root).toBe("sha256:abc");
  });

  it("writes sorted keys in output", () => {
    const dir = mkdtempSync(join(tmpdir(), "sink-"));
    const sink = new LocalFileSink(dir);
    sink.publish({ zebra: 1, checkpoint_id: "ckpt-002", alpha: 2 });
    const content = readFileSync(join(dir, "ckpt-002.json"), "utf-8");
    const keys = Object.keys(JSON.parse(content));
    expect(keys).toEqual(["alpha", "checkpoint_id", "zebra"]);
  });

  it("writes multiple files", () => {
    const dir = mkdtempSync(join(tmpdir(), "sink-"));
    const sink = new LocalFileSink(dir);
    for (let i = 0; i < 3; i++) {
      sink.publish({ checkpoint_id: `ckpt-${i}`, merkle_root: `sha256:${i}` });
    }
    expect(readdirSync(dir)).toHaveLength(3);
  });
});

describe("Sink queue", () => {
  afterEach(() => {
    resetSink();
  });

  it("enqueueForSink does nothing without a sink", () => {
    enqueueForSink({ checkpoint_id: "ckpt-x" });
    expect(getPendingSinkCount()).toBe(0);
  });

  it("enqueueForSink queues when sink is set", () => {
    const published: Record<string, unknown>[] = [];
    const fakeSink = { publish: (c: Record<string, unknown>) => published.push(c) };
    setSink(fakeSink);
    enqueueForSink({ checkpoint_id: "ckpt-1" });
    // Item is queued; drain loop will pick it up asynchronously
    // Wait briefly for the drain interval
    return new Promise<void>((resolve) => {
      setTimeout(() => {
        expect(published).toHaveLength(1);
        expect(published[0].checkpoint_id).toBe("ckpt-1");
        expect(getPendingSinkCount()).toBe(0);
        resolve();
      }, 200);
    });
  });

  it("retries on publish failure", () => {
    let callCount = 0;
    const fakeSink = {
      publish: (_c: Record<string, unknown>) => {
        callCount++;
        if (callCount === 1) throw new Error("transient");
        // Second call succeeds
      },
    };
    setSink(fakeSink);
    enqueueForSink({ checkpoint_id: "ckpt-retry" });
    return new Promise<void>((resolve) => {
      setTimeout(() => {
        // After enough drain cycles, the item should have been retried and succeeded
        expect(callCount).toBeGreaterThanOrEqual(2);
        expect(getPendingSinkCount()).toBe(0);
        resolve();
      }, 300);
    });
  });
});
