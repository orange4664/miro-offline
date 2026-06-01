import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 3100,
    open: true,
    proxy: {
      '/api': {
        target: 'http://localhost:5101',
        changeOrigin: true,
        secure: false
      }
    }
  }
})
