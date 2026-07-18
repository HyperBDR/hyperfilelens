import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../..')
const devApiTarget = process.env.VITE_DEV_API_TARGET || 'http://api:8000'
const devWebSocketTarget = process.env.VITE_DEV_WEBSOCKET_TARGET || 'http://api:8001'

// https://vite.dev/config/
export default defineConfig(() => ({
  envDir: repoRoot,
  // Share repo-root SENTRY_* with backend (.env); VITE_* remains for other frontend-only keys.
  envPrefix: ['VITE_', 'SENTRY_'],
  plugins: [vue(), tailwindcss()],
  build: {
    target: 'es2022',
  },
  optimizeDeps: {
    esbuildOptions: {
      target: 'es2022',
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: devApiTarget,
        changeOrigin: true,
        secure: false,
        timeout: 300_000,
        proxyTimeout: 300_000,
      },
      '/media': {
        target: devApiTarget,
        changeOrigin: true,
        secure: false,
      },
      '/swagger': {
        target: devApiTarget,
        changeOrigin: true,
        secure: false,
      },
      '/redoc': {
        target: devApiTarget,
        changeOrigin: true,
        secure: false,
      },
      '/ws': {
        target: devWebSocketTarget,
        changeOrigin: true,
        ws: true,
      },
    },
  },
}))
