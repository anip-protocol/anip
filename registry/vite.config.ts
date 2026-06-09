import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

function normalizeBase(base: string): string {
  return base.endsWith('/') ? base : `${base}/`
}

const backendTarget = process.env.VITE_REGISTRY_BACKEND_URL ?? 'http://127.0.0.1:8200'

export default defineConfig({
  plugins: [vue()],
  base: normalizeBase(process.env.VITE_BASE_PATH ?? '/registry/'),
  server: {
    proxy: {
      '/registry-api': {
        target: backendTarget,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
