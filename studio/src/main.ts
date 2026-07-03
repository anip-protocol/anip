import './theme.css'
import { createApp } from 'vue'
import { AnipClientKey } from '@anip-dev/vue'
import App from './App.vue'
import { router } from './router'
import { studioAnipClient } from './anip'
import { mountStudioApp } from './bootstrap'

const app = createApp(App)
app.use(router)
app.provide(AnipClientKey, studioAnipClient)

mountStudioApp(app)
