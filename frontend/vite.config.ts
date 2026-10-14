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
    // through a tunnel gets a "Blocked request" error instead of the app.
    // Both the Cloudflare quick tunnel (Makefile's `tunnel` target) and an
    // ngrok tunnel get a fresh random hostname each time they (re)start (no
    // fixed-name option on ngrok's free tier either), so these are
    // wildcards rather than one fixed hostname.
    allowedHosts: ['.trycloudflare.com', '.ngrok-free.app', '.ngrok-free.dev', '.ngrok.io', '.ngrok.app'],
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
