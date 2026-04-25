import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

const isElectronBuild = !process.env.VITE_API_BASE

export default defineConfig({
  plugins: [vue()],
  root: 'frontend',
  base: isElectronBuild ? './' : '/',
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
      '/api/v1': {
        target: process.env.VITE_API_BASE || 'http://127.0.0.1:8765',
        changeOrigin: true,
      },
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
