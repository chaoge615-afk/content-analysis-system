import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '::',
    port: 3000,
    allowedHosts: true,
    proxy: {
      '/query': {
        target: 'http://localhost:8010',
        changeOrigin: true,
      },
    },
  },
})
