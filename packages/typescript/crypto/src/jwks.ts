import type { KeyManager } from "./keys.js";
import type { JWK } from "jose";

export async function buildJWKS(
  km: KeyManager,
): Promise<{ keys: JWK[] }> {
  return km.getJWKS();
}
