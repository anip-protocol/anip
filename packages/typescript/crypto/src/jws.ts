import type { KeyManager } from "./keys.js";
import * as jose from "jose";

export async function signJWSDetached(
  km: KeyManager,
  payload: Uint8Array,
): Promise<string> {
  return km.signJWSDetached(payload);
}

/**
 * Verify a detached JWS (header..signature) against its payload using the
 * delegation public key.
 *
 * Reconstructs the full compact JWS by inserting the base64url-encoded payload
 * back into the empty middle segment, then verifies with `jose.compactVerify`.
 */
export async function verifyJWSDetached(
  km: KeyManager,
  jws: string,
  payload: Uint8Array,
): Promise<void> {
  const [header, , signature] = jws.split(".");
  const payloadB64 = jose.base64url.encode(payload);
  const fullJws = `${header}.${payloadB64}.${signature}`;
  await jose.compactVerify(fullJws, km.getDelegationPublicKey());
}

export async function signJWSDetachedAudit(
  km: KeyManager,
  payload: Uint8Array,
): Promise<string> {
  return km.signJWSDetachedAudit(payload);
}

/**
 * Verify a detached JWS (header..signature) against its payload using the
 * audit public key.
 */
export async function verifyJWSDetachedAudit(
  km: KeyManager,
  jws: string,
  payload: Uint8Array,
): Promise<void> {
  const [header, , signature] = jws.split(".");
  const payloadB64 = jose.base64url.encode(payload);
  const fullJws = `${header}.${payloadB64}.${signature}`;
  await jose.compactVerify(fullJws, km.getAuditPublicKey());
}
