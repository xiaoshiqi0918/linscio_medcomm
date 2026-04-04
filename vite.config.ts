import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  root: 'frontend',
  base: './',
  build: {
    outDir: '../dist',
    emptyOutDir: true,
  },
  resolve: {
    alias: {
      '@': resolve(__dirname, 'frontend/src'),
    },
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    proxy: {
      '/comfyui-proxy/ws': {
        target: 'ws://127.0.0.1:8188',
        ws: true,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/comfyui-proxy/, ''),
      },
      '/comfyui-proxy': {
        target: 'http://127.0.0.1:8188',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/comfyui-proxy/, ''),
      },
    },
  },
})
