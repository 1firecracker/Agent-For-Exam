import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 开发环境下 API 代理目标：
// - 本地 start_all.ps1：默认走 http://localhost:8000
// - Docker dev：通过环境变量 VITE_DEV_API_PROXY_TARGET 指向 backend-dev:8000
const devApiTarget = process.env.VITE_DEV_API_PROXY_TARGET || 'http://localhost:8000'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: devApiTarget,
        changeOrigin: true
      }
    }
  }
})
