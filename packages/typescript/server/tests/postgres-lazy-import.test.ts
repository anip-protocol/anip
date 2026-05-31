import { execFileSync } from "node:child_process";
import { copyFileSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const __dirname = dirname(fileURLToPath(import.meta.url));
const packageDir = resolve(__dirname, "..");

describe("PostgresStorage optional pg dependency", () => {
  it("does not require pg until PostgresStorage is initialized", () => {
    const tempDir = mkdtempSync(join(tmpdir(), "anip-server-postgres-lazy-"));
    copyFileSync(join(packageDir, "dist/postgres.js"), join(tempDir, "postgres.js"));
    copyFileSync(join(packageDir, "dist/hashing.js"), join(tempDir, "hashing.js"));
    writeFileSync(join(tempDir, "package.json"), JSON.stringify({ type: "module" }));
    writeFileSync(
      join(tempDir, "check.mjs"),
      `
import { PostgresStorage } from "./postgres.js";

const storage = new PostgresStorage("postgres://example.invalid/anip");
try {
  await storage.initialize();
  console.error("expected initialize() to fail without pg");
  process.exit(2);
} catch (error) {
  if (!String(error?.message || "").includes("requires the optional peer dependency 'pg'")) {
    console.error(error);
    process.exit(3);
  }
}
`,
    );

    expect(() => execFileSync(process.execPath, [join(tempDir, "check.mjs")])).not.toThrow();
  });
});
