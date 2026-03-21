import { describe, it, expect, beforeAll, afterAll } from "vitest";
import { createOidcValidator } from "../src/oidc.js";
import * as jose from "jose";
import { createServer, type Server } from "node:http";

// Generate a test RSA key pair for signing OIDC tokens
let privateKey: jose.KeyLike;
let publicJwk: jose.JWK;
let jwksServer: Server;
let jwksPort: number;

const AUDIENCE = "test-service";

beforeAll(async () => {
  // Generate RSA key pair
  const { privateKey: priv, publicKey: pub } = await jose.generateKeyPair("RS256");
  privateKey = priv;
  publicJwk = await jose.exportJWK(pub);
  publicJwk.kid = "test-key-1";
  publicJwk.alg = "RS256";
  publicJwk.use = "sig";

  // Start a local JWKS server
  jwksServer = createServer((req, res) => {
    if (req.url === "/.well-known/openid-configuration") {
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({
        issuer: `http://localhost:${jwksPort}`,
        jwks_uri: `http://localhost:${jwksPort}/jwks`,
      }));
    } else if (req.url === "/jwks") {
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ keys: [publicJwk] }));
    } else {
      res.writeHead(404);
      res.end();
    }
  });

  await new Promise<void>((resolve) => {
    jwksServer.listen(0, () => {
      jwksPort = (jwksServer.address() as { port: number }).port;
      resolve();
    });
  });
});

afterAll(() => {
  jwksServer.close();
});

function issuer() {
  return `http://localhost:${jwksPort}`;
}

async function signToken(claims: Record<string, unknown>, opts?: { expiresIn?: string; kid?: string }) {
  return new jose.SignJWT(claims as jose.JWTPayload)
    .setProtectedHeader({ alg: "RS256", kid: opts?.kid ?? "test-key-1" })
    .setIssuer(issuer())
    .setAudience(AUDIENCE)
    .setIssuedAt()
    .setExpirationTime(opts?.expiresIn ?? "1h")
    .sign(privateKey);
}

describe("OIDC Validator", () => {
  it("validates token with email claim → human:{email}", async () => {
    const validate = createOidcValidator({ issuerUrl: issuer(), audience: AUDIENCE });
    const token = await signToken({ email: "samir@example.com" });
    const principal = await validate(token);
    expect(principal).toBe("human:samir@example.com");
  });

  it("validates token with preferred_username → human:{username}", async () => {
    const validate = createOidcValidator({ issuerUrl: issuer(), audience: AUDIENCE });
    const token = await signToken({ preferred_username: "samir", sub: "user-123" });
    const principal = await validate(token);
    expect(principal).toBe("human:samir");
  });

  it("validates token with only sub → oidc:{sub}", async () => {
    const validate = createOidcValidator({ issuerUrl: issuer(), audience: AUDIENCE });
    const token = await signToken({ sub: "service-account-xyz" });
    const principal = await validate(token);
    expect(principal).toBe("oidc:service-account-xyz");
  });

  it("rejects expired token", async () => {
    const validate = createOidcValidator({ issuerUrl: issuer(), audience: AUDIENCE });
    const token = await signToken({ email: "samir@example.com" }, { expiresIn: "-1h" });
    const principal = await validate(token);
    expect(principal).toBeNull();
  });

  it("rejects wrong issuer", async () => {
    const validate = createOidcValidator({ issuerUrl: "https://wrong-issuer.example.com", audience: AUDIENCE });
    const token = await signToken({ email: "samir@example.com" });
    const principal = await validate(token);
    expect(principal).toBeNull();
  });

  it("rejects wrong audience", async () => {
    const validate = createOidcValidator({ issuerUrl: issuer(), audience: "wrong-audience" });
    const token = await signToken({ email: "samir@example.com" });
    const principal = await validate(token);
    expect(principal).toBeNull();
  });

  it("rejects invalid signature", async () => {
    const validate = createOidcValidator({ issuerUrl: issuer(), audience: AUDIENCE });
    // Sign with a different key
    const { privateKey: otherKey } = await jose.generateKeyPair("RS256");
    const token = await new jose.SignJWT({ email: "samir@example.com" })
      .setProtectedHeader({ alg: "RS256", kid: "test-key-1" })
      .setIssuer(issuer())
      .setAudience(AUDIENCE)
      .setIssuedAt()
      .setExpirationTime("1h")
      .sign(otherKey);
    const principal = await validate(token);
    expect(principal).toBeNull();
  });

  it("handles JWKS fetch failure gracefully", async () => {
    const validate = createOidcValidator({
      issuerUrl: "http://localhost:1", // unreachable
      audience: AUDIENCE,
      jwksUrl: "http://localhost:1/jwks",
    });
    const token = await signToken({ email: "samir@example.com" });
    const principal = await validate(token);
    expect(principal).toBeNull();
  });

  it("handles unknown kid by refreshing JWKS", async () => {
    // Generate a second key pair and add it to the server's key set mid-test
    const { privateKey: newPriv, publicKey: newPub } = await jose.generateKeyPair("RS256");
    const newJwk = await jose.exportJWK(newPub);
    newJwk.kid = "rotated-key-2";
    newJwk.alg = "RS256";
    newJwk.use = "sig";

    // Start a fresh server that serves both keys (simulating key rotation)
    const rotatedServer = createServer((req, res) => {
      if (req.url === "/.well-known/openid-configuration") {
        const port = (rotatedServer.address() as { port: number }).port;
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ issuer: `http://localhost:${port}`, jwks_uri: `http://localhost:${port}/jwks` }));
      } else if (req.url === "/jwks") {
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ keys: [publicJwk, newJwk] }));
      } else {
        res.writeHead(404); res.end();
      }
    });
    const rotatedPort = await new Promise<number>((resolve) => {
      rotatedServer.listen(0, () => resolve((rotatedServer.address() as { port: number }).port));
    });

    try {
      const validate = createOidcValidator({
        issuerUrl: `http://localhost:${rotatedPort}`,
        audience: AUDIENCE,
      });

      // First call with original key — caches JWKS
      const token1Fixed = await new jose.SignJWT({ email: "first@example.com" } as jose.JWTPayload)
        .setProtectedHeader({ alg: "RS256", kid: "test-key-1" })
        .setIssuer(`http://localhost:${rotatedPort}`)
        .setAudience(AUDIENCE)
        .setIssuedAt()
        .setExpirationTime("1h")
        .sign(privateKey);
      expect(await validate(token1Fixed)).toBe("human:first@example.com");

      // Second call with rotated kid — triggers JWKS refresh
      const token2 = await new jose.SignJWT({ email: "rotated@example.com" } as jose.JWTPayload)
        .setProtectedHeader({ alg: "RS256", kid: "rotated-key-2" })
        .setIssuer(`http://localhost:${rotatedPort}`)
        .setAudience(AUDIENCE)
        .setIssuedAt()
        .setExpirationTime("1h")
        .sign(newPriv);
      const principal = await validate(token2);
      expect(principal).toBe("human:rotated@example.com");
    } finally {
      rotatedServer.close();
    }
  });

  it("returns null for non-JWT strings", async () => {
    const validate = createOidcValidator({ issuerUrl: issuer(), audience: AUDIENCE });
    const principal = await validate("not-a-jwt");
    expect(principal).toBeNull();
  });

  it("uses explicit jwksUrl when provided", async () => {
    const validate = createOidcValidator({
      issuerUrl: issuer(),
      audience: AUDIENCE,
      jwksUrl: `http://localhost:${jwksPort}/jwks`,
    });
    const token = await signToken({ email: "direct@example.com" });
    const principal = await validate(token);
    expect(principal).toBe("human:direct@example.com");
  });
});
