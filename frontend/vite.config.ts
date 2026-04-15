/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  server: {
    host: '0.0.0.0',
    port: 6969,
    allowedHosts: ['agentcll.local', 'nataly-unsneering-pinnately.ngrok-free.dev'],
    proxy: {
      '/api': {
        target: 'http://localhost:8989',
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'happy-dom',
  },
})
