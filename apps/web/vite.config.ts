import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const list = (value: string | undefined) =>
  value?.split(',').map((entry) => entry.trim()).filter(Boolean)

/**
 * The dev server binds to localhost unless REPOCITY_WEB_HOST says otherwise.
 *
 * Only this server needs to be reachable to use repoCity from another machine: it proxies
 * /api and /ws server-side, so the analyzer stays on loopback. Exposing the analyzer itself
 * would let anyone who can reach it read any file this machine can read.
 */
export default defineConfig({
  plugins: [react()],
  server: {
    host: process.env.REPOCITY_WEB_HOST ?? 'localhost',
    port: Number(process.env.REPOCITY_WEB_PORT ?? 5173),
    strictPort: true,
    // Vite rejects Host headers it does not know, which is what stops a hostile page from
    // pointing a name it controls at this server. Names have to be listed on purpose.
    allowedHosts: list(process.env.REPOCITY_ALLOWED_HOSTS),
    proxy: {
      '/api': { target: 'http://127.0.0.1:8787', changeOrigin: true },
      '/ws': { target: 'ws://127.0.0.1:8787', ws: true },
    },
  },
})
