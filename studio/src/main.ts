import './theme.css'
import { createApp } from 'vue'
import { AnipClientKey } from '@anip-dev/vue'
import App from './App.vue'
import { router } from './router'
import { initFromConfig, store } from './store'
import { studioAnipClient, syncStudioAnipBaseUrl } from './anip'

const app = createApp(App)
app.use(router)
app.provide(AnipClientKey, studioAnipClient)

initFromConfig().then(() => {
  syncStudioAnipBaseUrl(store.baseUrl)
  app.mount('#app')
})
