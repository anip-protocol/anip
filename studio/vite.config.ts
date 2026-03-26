/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

function normalizeBase(base: string): string {
  return base.endsWith('/') ? base : base + '/'
}

export default defineConfig({
  plugins: [vue()],
  base: normalizeBase(process.env.VITE_BASE_PATH ?? '/studio/'),
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
  test: {
    environment: 'jsdom',
  },
})
