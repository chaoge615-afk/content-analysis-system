import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '::',
    port: 3000,
    allowedHosts: true,
    proxy: {
      // Router Agent 统一入口
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // 保留向后兼容 Text-to-SQL 直连
      '/query': {
        target: 'http://localhost:8010',
        changeOrigin: true,
      },
    },
  },
})
