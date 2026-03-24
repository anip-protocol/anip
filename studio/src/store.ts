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
    const res = await fetch('./config.json')
    if (res.ok) {
      const config = await res.json()
      if (config.embedded) {
        store.baseUrl = window.location.origin
      }
      store.serviceId = config.service_id || ''

      // Auto-connect in embedded mode
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
  } catch {
    // Standalone mode
  }
}
