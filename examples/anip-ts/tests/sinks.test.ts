import { describe, it, expect, afterEach } from "vitest";
import { mkdtempSync, readdirSync, readFileSync } from "fs";
import { join } from "path";
import { tmpdir } from "os";
import { LocalFileSink } from "@anip/server";
import { setSink, enqueueForSink, getPendingSinkCount, resetSink } from "../src/sink-queue";

describe("LocalFileSink", () => {
  it("writes signed checkpoint file", () => {
    const dir = mkdtempSync(join(tmpdir(), "sink-"));
    const sink = new LocalFileSink(dir);
    sink.publish({
      body: { checkpoint_id: "ckpt-001", merkle_root: "sha256:abc" },
      signature: "header..sig",
    });
    const files = readdirSync(dir);
    expect(files).toHaveLength(1);
    expect(files[0]).toBe("ckpt-001.json");
    const content = JSON.parse(readFileSync(join(dir, files[0]), "utf-8"));
    expect(content.body.checkpoint_id).toBe("ckpt-001");
    expect(content.signature).toBe("header..sig");
  });

  it("writes multiple files", () => {
    const dir = mkdtempSync(join(tmpdir(), "sink-"));
    const sink = new LocalFileSink(dir);
    for (let i = 0; i < 3; i++) {
      sink.publish({
        body: { checkpoint_id: `ckpt-${i}`, merkle_root: `sha256:${i}` },
        signature: `header..sig${i}`,
      });
    }
    expect(readdirSync(dir)).toHaveLength(3);
  });
});

describe("Sink queue", () => {
  afterEach(() => {
    resetSink();
  });

  it("enqueueForSink does nothing without a sink", () => {
    enqueueForSink({ body: { checkpoint_id: "ckpt-x" }, signature: "s" });
    expect(getPendingSinkCount()).toBe(0);
  });

  it("enqueueForSink queues when sink is set", () => {
    const published: Record<string, unknown>[] = [];
    const fakeSink = { publish: (c: Record<string, unknown>) => published.push(c) };
    setSink(fakeSink);
    enqueueForSink({ body: { checkpoint_id: "ckpt-1" }, signature: "s" });
    // Item is queued; drain loop will pick it up asynchronously
    // Wait briefly for the drain interval
    return new Promise<void>((resolve) => {
      setTimeout(() => {
        expect(published).toHaveLength(1);
        const body = (published[0] as { body: { checkpoint_id: string } }).body;
        expect(body.checkpoint_id).toBe("ckpt-1");
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
    enqueueForSink({ body: { checkpoint_id: "ckpt-retry" }, signature: "s" });
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
