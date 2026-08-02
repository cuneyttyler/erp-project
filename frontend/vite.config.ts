import { fileURLToPath, URL } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    // Vite rejects requests whose Host header isn't localhost/127.0.0.1 by
    // default (DNS-rebinding protection) -- without this, traffic arriving
    // through the Cloudflare quick tunnel (Makefile's `tunnel` target) gets
    // a "Blocked request" error instead of the app. Quick tunnels get a
    // fresh random *.trycloudflare.com hostname every time they (re)start
    // (no fixed-name option without owning a domain in Cloudflare), so this
    // is a wildcard rather than one fixed hostname.
    allowedHosts: ['.trycloudflare.com'],
    proxy: {
      // Backend runs on 8000 in dev (technical.md §12) — proxy avoids CORS
      // fuss for plain REST calls; the AI chat WebSocket connects directly.
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
