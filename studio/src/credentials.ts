/**
 * Turning what the user pastes into a delegation token.
 *
 * Inspect accepts either an ANIP delegation token or the service's own
 * credential (an API key, a session token). Invoke, permissions and audit
 * endpoints accept only delegation tokens, and a delegation token is bound to
 * one capability (SPEC §3.2). So when the user pastes something that is not a
 * delegation token, Inspect asks the service's token endpoint for a token for
 * the capability being looked at, scoped to that capability's minimum scope,
 * exactly as an agent would.
 */
import type { ANIPClient } from '@anip-dev/client'

/** A JWT: three non-empty base64url segments. Delegation tokens are JWTs. */
export function isDelegationToken(credential: string): boolean {
  return /^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$/.test(credential.trim())
}

export interface ResolvedToken {
  token: string
  /** Set when the token was issued from a non-token credential. */
  issuedFor?: { capability: string; scope: string[] }
}

interface CachedToken {
  token: string
  scope: string[]
  expiresAtMs: number
}

/** Refresh an issued token this long before it expires. */
const EXPIRY_MARGIN_MS = 60_000
/** Used when the service does not say when its token expires. */
const FALLBACK_LIFETIME_MS = 10 * 60_000

export function createTokenResolver(
  client: Pick<ANIPClient, 'issueCapabilityToken'>,
  minimumScope: (capability: string) => Promise<string[] | undefined>,
  now: () => number = Date.now,
) {
  const cache = new Map<string, CachedToken>()

  async function resolve(credential: string, capability: string | null): Promise<ResolvedToken> {
    const trimmed = credential.trim()
    if (isDelegationToken(trimmed)) {
      return { token: trimmed }
    }
    if (!capability) {
      throw new Error('Choose a capability: an API key is exchanged for a token bound to one capability.')
    }
    const scope = await minimumScope(capability)
    if (!scope) {
      throw new Error(`The service does not declare a capability named '${capability}'.`)
    }

    const key = `${trimmed}\u0000${capability}`
    const cached = cache.get(key)
    if (cached && cached.expiresAtMs - EXPIRY_MARGIN_MS > now()) {
      return { token: cached.token, issuedFor: { capability, scope: cached.scope } }
    }

    const issued = await client.issueCapabilityToken(trimmed, capability, scope)
    const expires = Date.parse(issued.expires)
    cache.set(key, {
      token: issued.token,
      scope,
      expiresAtMs: Number.isNaN(expires) ? now() + FALLBACK_LIFETIME_MS : expires,
    })
    return { token: issued.token, issuedFor: { capability, scope } }
  }

  /** Forget issued tokens, for example when the user changes the credential. */
  function clear() {
    cache.clear()
  }

  return { resolve, clear }
}
