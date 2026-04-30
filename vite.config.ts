import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'
import { readFileSync } from 'fs'

const pkg = JSON.parse(readFileSync(resolve(__dirname, 'package.json'), 'utf-8'))

/**
 * 统一使用 './' 相对路径作为 base：
 * - Electron 必须用 './'，否则 file:// 协议下绝对路径 /assets/xxx 会解析为 file:///assets/xxx 导致白屏
 * - Web 部署从根目录提供时 './' 与 '/' 等价
 * - 若 Web 需部署在子目录（如 /app/），可通过 VITE_BASE_PATH 显式指定
 */
const basePath = process.env.VITE_BASE_PATH || './'

export default defineConfig({
  plugins: [vue()],
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
  },
  root: 'frontend',
  base: basePath,
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
