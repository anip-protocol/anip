import './theme.css'
import { createApp } from 'vue'
import App from './App.vue'
import { router } from './router'
import { initFromConfig } from './store'

const app = createApp(App)
app.use(router)

initFromConfig().then(() => {
  app.mount('#app')
})
