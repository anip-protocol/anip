import { describe, it, expect } from "vitest";
import {
  KeyManager,
  signJWT,
  verifyJWT,
  signJWSDetached,
  verifyJWSDetached,
  signJWSDetachedAudit,
  verifyJWSDetachedAudit,
  buildJWKS,
  canonicalize,
  verifyAuditEntrySignature,
  verifyManifestSignature,
} from "../src/index.js";

describe("KeyManager", () => {
  it("generates two key pairs", async () => {
    const km = new KeyManager();
    await km.ready();
    const jwks = await buildJWKS(km);
    expect(jwks.keys).toHaveLength(2);
    expect(jwks.keys[0].use).toBe("sig");
    expect(jwks.keys[1].use).toBe("audit");
  });

  it("has distinct delegation and audit KIDs", async () => {
    const km = new KeyManager();
    await km.ready();
    const jwks = await buildJWKS(km);
    expect(jwks.keys[0].kid).not.toBe(jwks.keys[1].kid);
  });
});

describe("JWT", () => {
  it("signs and verifies", async () => {
    const km = new KeyManager();
    await km.ready();
    const token = await signJWT(km, { sub: "agent", aud: "test" });
    const claims = await verifyJWT(km, token, { audience: "test" });
    expect(claims.sub).toBe("agent");
  });

  it("rejects wrong audience", async () => {
    const km = new KeyManager();
    await km.ready();
    const token = await signJWT(km, { sub: "agent", aud: "other-service" });
    await expect(
      verifyJWT(km, token, { audience: "my-service" }),
    ).rejects.toThrow();
  });

  it("verifies with correct issuer", async () => {
    const km = new KeyManager();
    await km.ready();
    const token = await signJWT(km, { sub: "agent", aud: "test", iss: "my-service" });
    const claims = await verifyJWT(km, token, { audience: "test", issuer: "my-service" });
    expect(claims.sub).toBe("agent");
  });

  it("rejects wrong issuer", async () => {
    const km = new KeyManager();
    await km.ready();
    const token = await signJWT(km, { sub: "agent", aud: "test", iss: "other-service" });
    await expect(
      verifyJWT(km, token, { audience: "test", issuer: "my-service" }),
    ).rejects.toThrow();
  });
});

describe("JWS Detached", () => {
  it("signs and verifies with delegation key", async () => {
    const km = new KeyManager();
    await km.ready();
    const payload = new TextEncoder().encode("manifest");
    const jws = await signJWSDetached(km, payload);
    const parts = jws.split(".");
    expect(parts).toHaveLength(3);
    expect(parts[1]).toBe("");
    await verifyJWSDetached(km, jws, payload);
  });

  it("signs and verifies with audit key", async () => {
    const km = new KeyManager();
    await km.ready();
    const payload = new TextEncoder().encode("checkpoint");
    const jws = await signJWSDetachedAudit(km, payload);
    await verifyJWSDetachedAudit(km, jws, payload);
  });

  it("delegation key cannot verify audit signature", async () => {
    const km = new KeyManager();
    await km.ready();
    const payload = new TextEncoder().encode("data");
    const jws = await signJWSDetachedAudit(km, payload);
    await expect(verifyJWSDetached(km, jws, payload)).rejects.toThrow();
  });
});

describe("canonicalize", () => {
  it("sorts keys and excludes specified fields", () => {
    const result = canonicalize(
      { b: 2, a: 1, signature: "skip" },
      new Set(["signature"]),
    );
    const parsed = JSON.parse(result);
    expect(Object.keys(parsed)).toEqual(["a", "b"]);
  });
});

describe("verifyAuditEntrySignature", () => {
  it("verifies a valid audit entry", async () => {
    const km = new KeyManager();
    await km.ready();
    const entry: Record<string, unknown> = {
      type: "action",
      agent_did: "did:anip:test",
      seq: 1,
    };
    const sig = await km.signAuditEntry(entry);
    entry.signature = sig;
    const claims = await verifyAuditEntrySignature(km, entry, sig);
    expect(claims.audit_hash).toBeDefined();
  });

  it("rejects a tampered entry", async () => {
    const km = new KeyManager();
    await km.ready();
    const entry: Record<string, unknown> = {
      type: "action",
      agent_did: "did:anip:test",
      seq: 1,
    };
    const sig = await km.signAuditEntry(entry);
    entry.signature = sig;
    entry.type = "tampered";
    await expect(
      verifyAuditEntrySignature(km, entry, sig),
    ).rejects.toThrow("Audit hash mismatch");
  });
});

describe("verifyManifestSignature", () => {
  it("verifies a valid manifest signature", async () => {
    const km = new KeyManager();
    await km.ready();
    const manifest = new TextEncoder().encode('{"protocol":"anip/0.8"}');
    const sig = await signJWSDetached(km, manifest);
    await verifyManifestSignature(km, manifest, sig);
  });

  it("rejects tampered manifest bytes", async () => {
    const km = new KeyManager();
    await km.ready();
    const manifest = new TextEncoder().encode('{"protocol":"anip/0.8"}');
    const sig = await signJWSDetached(km, manifest);
    const tampered = new TextEncoder().encode("tampered");
    await expect(verifyManifestSignature(km, tampered, sig)).rejects.toThrow();
  });
});
