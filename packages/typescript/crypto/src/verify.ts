import { createHash } from "crypto";
import type { KeyManager } from "./keys.js";
import { canonicalize } from "./canonicalize.js";
import * as jose from "jose";

/**
 * Verify that an audit entry's JWT signature is valid and that the embedded
 * `audit_hash` matches the canonical hash of the entry data.
 *
 * Returns the decoded JWT claims on success; throws on any mismatch.
 */
export async function verifyAuditEntrySignature(
  km: KeyManager,
  entry: Record<string, unknown>,
  signature: string,
): Promise<jose.JWTPayload> {
  await km.ready();

  // Verify the JWT using the audit public key
  const { payload } = await jose.jwtVerify(
    signature,
    km.getAuditPublicKey(),
    { algorithms: ["ES256"] },
  );

  // Recompute the expected hash from entry data (excluding signature and id)
  const canonical = canonicalize(entry, new Set(["signature", "id"]));
  const expectedHash = createHash("sha256").update(canonical).digest("hex");

  if (payload.audit_hash !== expectedHash) {
    throw new Error(
      `Audit hash mismatch: expected ${expectedHash}, got ${payload.audit_hash as string}`,
    );
  }

  return payload;
}
