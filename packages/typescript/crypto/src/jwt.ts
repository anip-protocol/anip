import type { KeyManager } from "./keys.js";
import type { JWTPayload } from "jose";

export async function signJWT(
  km: KeyManager,
  payload: JWTPayload,
): Promise<string> {
  return km.signJWT(payload);
}

export async function verifyJWT(
  km: KeyManager,
  token: string,
  opts: { audience: string; issuer?: string },
): Promise<JWTPayload> {
  return km.verifyJWT(token, opts);
}
