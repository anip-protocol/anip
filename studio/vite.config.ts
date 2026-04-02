/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

function normalizeBase(base: string): string {
  return base.endsWith('/') ? base : base + '/'
}

export default defineConfig({
  plugins: [vue()],
  base: normalizeBase(process.env.VITE_BASE_PATH ?? '/studio/'),
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8100',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
  test: {
    environment: 'jsdom',
  },
})
