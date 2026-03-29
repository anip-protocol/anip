import { reactive } from 'vue'

export const store = reactive({
  baseUrl: '',
  bearer: '',
  connected: false,
  serviceId: '',
  error: '',
  loading: false,
})

export async function initFromConfig() {
  try {
    const res = await fetch(`${import.meta.env.BASE_URL}config.json`)
    if (res.ok) {
      const config = await res.json()
      if (config.embedded) {
        store.baseUrl = window.location.origin
      }
      store.serviceId = config.service_id || ''
    }
  } catch {
    // Standalone mode
  }

  // Check for ?connect=URL query parameter (overrides config)
  const params = new URLSearchParams(window.location.search)
  const connectUrl = params.get('connect')
  if (connectUrl) {
    store.baseUrl = connectUrl.replace(/\/+$/, '')
  }

  // Auto-connect if we have a baseUrl (from embedded config or ?connect=)
  if (store.baseUrl) {
    try {
      const disco = await fetch(`${store.baseUrl}/.well-known/anip`)
      if (disco.ok) {
        store.connected = true
      }
    } catch {
      // Service not reachable — user can connect manually
    }
  }
}
