import { ANIPClient } from '@anip-dev/client'
import { createTokenResolver } from './credentials'

export const studioAnipClient = new ANIPClient('')

/**
 * Exchanges a pasted API key for a delegation token bound to one capability,
 * using that capability's minimum scope from the discovery document.
 * A pasted delegation token is used as it is.
 */
export const studioTokens = createTokenResolver(
  studioAnipClient,
  async (capability) => (await studioAnipClient.discover()).capabilities[capability]?.minimumScope,
)

export function syncStudioAnipBaseUrl(baseUrl: string) {
  studioAnipClient.setBaseUrl(baseUrl)
  // Tokens issued by one service mean nothing to another.
  studioTokens.clear()
}
