import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'

// The repo's /assets folder (studio plates, avatar clips) is served as-is at the web root,
// e.g. /studio/plate-landscape-final.png. In production FastAPI serves web/dist the same way.
export default defineConfig({
  // vitest config lives in vitest.config.ts
  plugins: [react()],
  publicDir: fileURLToPath(new URL('../assets', import.meta.url)),
  server: {
    port: 5173,
    proxy: { '/api': { target: 'http://127.0.0.1:8787', ws: true } },
  },
  build: { outDir: 'dist', emptyOutDir: true },
})
