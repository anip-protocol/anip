import { createHash } from "crypto";

export function computeEntryHash(entry: Record<string, unknown>): string {
  const canonical = canonicalBytes(entry);
  const hash = createHash("sha256").update(canonical).digest("hex");
  return `sha256:${hash}`;
}

export function canonicalBytes(entry: Record<string, unknown>): string {
  const filtered: Record<string, unknown> = {};
  for (const key of Object.keys(entry).sort()) {
    if (key !== "signature" && key !== "id") {
      filtered[key] = entry[key];
    }
  }
  return JSON.stringify(filtered);
}
