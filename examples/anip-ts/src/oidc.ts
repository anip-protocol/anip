/**
 * OIDC token validation for the ANIP example app.
 *
 * Validates external OIDC/OAuth2 JWTs against a provider's JWKS endpoint.
 * Maps OIDC claims to ANIP principal identifiers.
 *
 * This is example-app code, not an SDK package. Real deployments should
 * define their own claim-to-principal mapping policy.
 */
import * as jose from "jose";

export interface OidcConfig {
  issuerUrl: string;
  audience: string;
  jwksUrl?: string; // override — otherwise discovered from issuer
}

/**
 * Create an OIDC token validator.
 *
 * Returns an async function that validates a bearer token and returns
 * an ANIP principal string, or null if validation fails.
 *
 * JWKS is fetched and cached automatically. On unknown kid, jose's
 * createRemoteJWKSet handles refresh internally.
 */
export function createOidcValidator(
  config: OidcConfig,
): (bearer: string) => Promise<string | null> {
  let jwksUrl: string | null = config.jwksUrl ?? null;
  let jwks: ReturnType<typeof jose.createRemoteJWKSet> | null = null;

  async function getJwks(): Promise<ReturnType<typeof jose.createRemoteJWKSet> | null> {
    if (jwks) return jwks;

    // Discover JWKS URL from OIDC discovery if not explicitly set
    if (!jwksUrl) {
      try {
        const discoveryUrl = `${config.issuerUrl.replace(/\/$/, "")}/.well-known/openid-configuration`;
        const resp = await fetch(discoveryUrl);
        if (resp.ok) {
          const doc = await resp.json();
          jwksUrl = doc.jwks_uri ?? null;
        }
      } catch {
        // Discovery failed — will retry on next validation attempt
      }
    }

    if (!jwksUrl) return null;

    // jose's createRemoteJWKSet handles caching and kid-miss refresh internally
    jwks = jose.createRemoteJWKSet(new URL(jwksUrl));
    return jwks;
  }

  return async (bearer: string): Promise<string | null> => {
    try {
      const keySet = await getJwks();
      if (!keySet) return null;

      const { payload } = await jose.jwtVerify(bearer, keySet, {
        issuer: config.issuerUrl,
        audience: config.audience,
      });

      // Map OIDC claims to ANIP principal
      return mapClaimsToPrincipal(payload);
    } catch {
      // Any validation failure → not an OIDC token we recognize
      return null;
    }
  };
}

/**
 * Map OIDC JWT claims to an ANIP principal identifier.
 *
 * This is deployment policy, not protocol meaning:
 * - email → "human:{email}"
 * - preferred_username → "human:{username}"
 * - sub → "oidc:{sub}"
 */
function mapClaimsToPrincipal(claims: jose.JWTPayload): string | null {
  const email = claims.email as string | undefined;
  if (email) return `human:${email}`;

  const username = claims.preferred_username as string | undefined;
  if (username) return `human:${username}`;

  const sub = claims.sub;
  if (sub) return `oidc:${sub}`;

  return null;
}
