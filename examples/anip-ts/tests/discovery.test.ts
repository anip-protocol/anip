import { describe, it, expect, beforeAll } from "vitest";
import { app } from "../src/server";

// Use an in-memory database for test isolation
beforeAll(() => {
  process.env.ANIP_DB_PATH = ":memory:";
});

describe("Discovery", () => {
  it("protocol version is anip/0.3", async () => {
    const res = await app.request("/.well-known/anip");
    const data = await res.json();
    expect(data.anip_discovery.protocol).toBe("anip/0.3");
  });

  it("includes trust_level", async () => {
    const res = await app.request("/.well-known/anip");
    const data = await res.json();
    expect(data.anip_discovery.trust_level).toBeDefined();
    expect(["signed", "anchored", "attested"]).toContain(
      data.anip_discovery.trust_level
    );
  });

  it("includes jwks_uri", async () => {
    const res = await app.request("/.well-known/anip");
    const data = await res.json();
    expect(data.anip_discovery.jwks_uri).toContain("/.well-known/jwks.json");
  });

  it("auth format includes jwt-es256", async () => {
    const res = await app.request("/.well-known/anip");
    const data = await res.json();
    expect(data.anip_discovery.auth.supported_formats).toContain("jwt-es256");
  });

  it("endpoints include jwks", async () => {
    const res = await app.request("/.well-known/anip");
    const data = await res.json();
    expect(data.anip_discovery.endpoints.jwks).toBe("/.well-known/jwks.json");
  });
});

describe("Manifest", () => {
  it("includes trust posture", async () => {
    const res = await app.request("/anip/manifest");
    const manifest = await res.json();
    expect(manifest.trust).toBeDefined();
    expect(["signed", "anchored", "attested"]).toContain(manifest.trust.level);
  });

  it("protocol version is anip/0.3", async () => {
    const res = await app.request("/anip/manifest");
    const manifest = await res.json();
    expect(manifest.protocol).toBe("anip/0.3");
  });
});
