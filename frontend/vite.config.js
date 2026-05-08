import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
      '/dashboard': 'http://localhost:8000',
      '/metrics': 'http://localhost:8000',
    }
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  }
})
