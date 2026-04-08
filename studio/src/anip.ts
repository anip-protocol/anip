import { ANIPClient } from '@anip-dev/client'

export const studioAnipClient = new ANIPClient('')

export function syncStudioAnipBaseUrl(baseUrl: string) {
  studioAnipClient.setBaseUrl(baseUrl)
}
