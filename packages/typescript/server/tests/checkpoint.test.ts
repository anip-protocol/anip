import { describe, it, expect } from "vitest";
import { CheckpointPolicy } from "../src/checkpoint.js";
import { LocalFileSink } from "../src/sinks.js";
import { mkdtempSync, readdirSync } from "fs";
import { join } from "path";
import { tmpdir } from "os";

describe("CheckpointPolicy", () => {
  it("triggers on entry count", () => {
    const policy = new CheckpointPolicy({ entryCount: 5 });
    expect(policy.shouldCheckpoint(4)).toBe(false);
    expect(policy.shouldCheckpoint(5)).toBe(true);
  });

  it("never triggers without policy", () => {
    const policy = new CheckpointPolicy({});
    expect(policy.shouldCheckpoint(1000)).toBe(false);
  });
});

describe("LocalFileSink", () => {
  it("writes checkpoint file", () => {
    const dir = mkdtempSync(join(tmpdir(), "sink-"));
    const sink = new LocalFileSink(dir);
    sink.publish({
      body: { checkpoint_id: "ckpt-001", merkle_root: "sha256:abc" },
      signature: "header..sig",
    });
    const files = readdirSync(dir);
    expect(files).toHaveLength(1);
    expect(files[0]).toBe("ckpt-001.json");
  });
});
