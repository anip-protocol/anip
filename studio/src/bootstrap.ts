import type { App as VueApp } from 'vue'
import { initFromConfig, store } from './store'
import { syncStudioAnipBaseUrl } from './anip'

export function mountStudioApp(app: VueApp<Element>, selector = '#app') {
  app.mount(selector)

  void initFromConfig().finally(() => {
    syncStudioAnipBaseUrl(store.baseUrl)
  })
}
