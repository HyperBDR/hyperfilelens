import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { sentryVitePlugin } from '@sentry/vite-plugin'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../..')
const devApiTarget = process.env.VITE_DEV_API_TARGET || 'http://api:8000'
const devWebSocketTarget = process.env.VITE_DEV_WEBSOCKET_TARGET || 'http://api:8001'
const sentrySourceMapUpload = Boolean(
  process.env.SENTRY_AUTH_TOKEN
  && process.env.SENTRY_URL
  && process.env.SENTRY_ORG
  && process.env.SENTRY_FRONTEND_PROJECT
  && process.env.SENTRY_RELEASE,
)

// https://vite.dev/config/
export default defineConfig(() => ({
  envDir: repoRoot,
  plugins: [
    vue(),
    tailwindcss(),
    ...(sentrySourceMapUpload
      ? [sentryVitePlugin({
          url: process.env.SENTRY_URL,
          authToken: process.env.SENTRY_AUTH_TOKEN,
          org: process.env.SENTRY_ORG,
          project: process.env.SENTRY_FRONTEND_PROJECT,
          telemetry: false,
          release: { name: process.env.SENTRY_RELEASE },
          sourcemaps: {
            assets: './dist/**',
            filesToDeleteAfterUpload: './dist/**/*.map',
          },
          errorHandler: (error) => {
            console.warn(`[sentry] Source Map upload failed; continuing build: ${error.message}`)
          },
        })]
      : []),
  ],
  build: {
    target: 'es2022',
    sourcemap: sentrySourceMapUpload ? 'hidden' : false,
  },
  optimizeDeps: {
    esbuildOptions: {
      target: 'es2022',
    },
  },
  server: {
    host: '0.0.0.0',
    allowedHosts: ['host.docker.internal'],
    port: 5173,
    strictPort: true,
    hmr: {
      path: '/__vite_hmr',
    },
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
