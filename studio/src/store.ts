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
    }
  } catch {
    // Standalone mode
  }
}
