/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

function normalizeBase(base: string): string {
  return base.endsWith('/') ? base : base + '/'
}

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@anip-dev/client': fileURLToPath(new URL('../packages/typescript/client/src/index.ts', import.meta.url)),
      '@anip-dev/vue': fileURLToPath(new URL('../packages/typescript/vue/src/index.ts', import.meta.url)),
    },
  },
  base: normalizeBase(process.env.VITE_BASE_PATH ?? '/studio/'),
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8100',
        changeOrigin: true,
      },
      '/studio-assistant': {
        target: 'http://127.0.0.1:8100',
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
