import { defineConfig } from 'vite'

const proxy = { '/api': { target: process.env.API_PROXY_TARGET || 'http://127.0.0.1:5090' } }

export default defineConfig({
  server: { host: '127.0.0.1', port: Number(process.env.PORT || 5173), strictPort: true, proxy },
  preview: { host: '127.0.0.1', proxy },
  esbuild: { jsx: 'automatic' },
})
