import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'
import { readFileSync } from 'fs'

const pkg = JSON.parse(readFileSync(resolve(__dirname, 'package.json'), 'utf-8'))

/** Electron 包内资源用相对 base；Web 用 /。勿再用「是否设置 VITE_API_BASE」判断，否则同域部署 VITE_API_BASE="" 会被误判为 Electron。 */
const isElectronBuild = process.env.VITE_IS_ELECTRON === '1'

export default defineConfig({
  plugins: [vue()],
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
  },
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
        target: process.env.VITE_DEV_PROXY_TARGET || 'http://127.0.0.1:8765',
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
