#!/usr/bin/env node
/**
 * 下载 ComfyUI + SD1.5 基础模型到 build/comfyui/
 * 用于 electron-builder 打包前准备
 *
 * 用法:
 *   node scripts/download-comfyui.js           # 下载 ComfyUI + 模型
 *   node scripts/download-comfyui.js --force   # 强制重新下载
 *
 * 环境变量:
 *   SKIP_PREBUILD_COMFYUI=1   跳过下载
 *   COMFYUI_RELEASE_URL       覆盖 ComfyUI 下载地址
 *   SD15_MODEL_URL            覆盖 SD1.5 模型下载地址
 */
const fs = require('fs')
const path = require('path')
const https = require('https')
const http = require('http')
const { execSync } = require('child_process')

const BUILD_DIR = path.join(__dirname, '..', 'build')
const COMFYUI_OUT = path.join(BUILD_DIR, 'comfyui')
const WORKFLOWS_SRC = path.join(__dirname, '..', 'workflows', 'comfyui', 'scenes')

const COMFYUI_VERSION = '0.3.10'
const COMFYUI_GITHUB_URL = process.env.COMFYUI_RELEASE_URL
  || `https://github.com/comfyanonymous/ComfyUI/archive/refs/tags/v${COMFYUI_VERSION}.tar.gz`

const SD15_MODEL_URL = process.env.SD15_MODEL_URL
  || 'https://huggingface.co/stable-diffusion-v1-5/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.safetensors'

function download(url, dest) {
  return new Promise((resolve, reject) => {
    if (fs.existsSync(dest)) {
      console.log('[download-comfyui] Cached:', path.basename(dest))
      resolve(dest)
      return
    }
    console.log('[download-comfyui] Downloading:', url)
    fs.mkdirSync(path.dirname(dest), { recursive: true })
    const stream = fs.createWriteStream(dest)
    const proto = url.startsWith('https') ? https : http

    function doGet(u) {
      proto.get(u, { headers: { 'User-Agent': 'LinScio-MedComm-Build' } }, (res) => {
        if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
          stream.close()
          if (fs.existsSync(dest)) fs.unlinkSync(dest)
          const next = res.headers.location.startsWith('http')
            ? res.headers.location
            : new URL(res.headers.location, u).href
          const nextProto = next.startsWith('https') ? https : http
          function doRedirect(rUrl) {
            nextProto.get(rUrl, { headers: { 'User-Agent': 'LinScio-MedComm-Build' } }, (r2) => {
              if (r2.statusCode >= 300 && r2.statusCode < 400 && r2.headers.location) {
                const rr = r2.headers.location.startsWith('http')
                  ? r2.headers.location
                  : new URL(r2.headers.location, rUrl).href
                doRedirect(rr)
                return
              }
              if (r2.statusCode !== 200) {
                reject(new Error(`HTTP ${r2.statusCode}`))
                return
              }
              const ws = fs.createWriteStream(dest)
              let downloaded = 0
              const total = parseInt(r2.headers['content-length'] || '0', 10)
              r2.on('data', (chunk) => {
                downloaded += chunk.length
                if (total > 0) {
                  const pct = ((downloaded / total) * 100).toFixed(1)
                  process.stdout.write(`\r[download-comfyui] ${pct}% (${(downloaded / 1e6).toFixed(1)}MB)`)
                }
              })
              r2.pipe(ws)
              ws.on('finish', () => { ws.close(); console.log(''); resolve(dest) })
            }).on('error', (e) => reject(e))
          }
          doRedirect(next)
          return
        }
        if (res.statusCode !== 200) {
          stream.close()
          if (fs.existsSync(dest)) fs.unlinkSync(dest)
          reject(new Error(`HTTP ${res.statusCode}`))
          return
        }
        let downloaded = 0
        const total = parseInt(res.headers['content-length'] || '0', 10)
        res.on('data', (chunk) => {
          downloaded += chunk.length
          if (total > 0) {
            const pct = ((downloaded / total) * 100).toFixed(1)
            process.stdout.write(`\r[download-comfyui] ${pct}% (${(downloaded / 1e6).toFixed(1)}MB)`)
          }
        })
        res.pipe(stream)
        stream.on('finish', () => { stream.close(); console.log(''); resolve(dest) })
      }).on('error', (e) => { stream.close(); if (fs.existsSync(dest)) fs.unlinkSync(dest); reject(e) })
    }
    doGet(url)
  })
}

function extract(archive, dest) {
  fs.mkdirSync(dest, { recursive: true })
  if (archive.endsWith('.tar.gz') || archive.endsWith('.tgz')) {
    execSync(`tar -xzf "${archive}" -C "${dest}"`, { stdio: 'inherit' })
  } else if (archive.endsWith('.zip')) {
    execSync(`unzip -o "${archive}" -d "${dest}"`, { stdio: 'inherit' })
  } else {
    throw new Error('Unknown archive format: ' + archive)
  }
}

function copySceneWorkflows() {
  const userWorkflowDir = path.join(COMFYUI_OUT, 'user', 'default', 'workflows')
  fs.mkdirSync(userWorkflowDir, { recursive: true })
  if (fs.existsSync(WORKFLOWS_SRC)) {
    for (const f of fs.readdirSync(WORKFLOWS_SRC)) {
      if (f.endsWith('.json')) {
        fs.copyFileSync(path.join(WORKFLOWS_SRC, f), path.join(userWorkflowDir, f))
        console.log('[download-comfyui] Copied workflow:', f)
      }
    }
  }
}

function installBridgeExtension() {
  const bridgeSrc = path.join(__dirname, '..', 'resources', 'comfyui-bridge', 'medcommBridge.js')
  const bridgeDir = path.join(COMFYUI_OUT, 'web', 'extensions', 'medcomm')
  fs.mkdirSync(bridgeDir, { recursive: true })
  const bridgeDest = path.join(bridgeDir, 'medcommBridge.js')
  if (fs.existsSync(bridgeSrc)) {
    fs.copyFileSync(bridgeSrc, bridgeDest)
    console.log('[download-comfyui] Installed MedComm bridge extension')
  }
  const oldFile = path.join(COMFYUI_OUT, 'web', 'extensions', 'core', 'medcommBridge.js')
  if (fs.existsSync(oldFile)) {
    try { fs.unlinkSync(oldFile) } catch { /* ok */ }
  }
}

async function main() {
  if (process.env.SKIP_PREBUILD_COMFYUI === '1') {
    console.log('[download-comfyui] SKIP_PREBUILD_COMFYUI=1, skip')
    return
  }
  const force = process.argv.includes('--force')

  const mainPy = path.join(COMFYUI_OUT, 'main.py')
  if (fs.existsSync(mainPy) && !force) {
    console.log('[download-comfyui] ComfyUI already exists, skip (use --force to re-download)')
    copySceneWorkflows()
    installBridgeExtension()
    return
  }

  fs.mkdirSync(BUILD_DIR, { recursive: true })

  // 1. Download ComfyUI
  console.log('[download-comfyui] === Step 1: ComfyUI ===')
  const comfyArchive = path.join(BUILD_DIR, `comfyui-v${COMFYUI_VERSION}.tar.gz`)
  await download(COMFYUI_GITHUB_URL, comfyArchive)

  if (fs.existsSync(COMFYUI_OUT)) {
    console.log('[download-comfyui] Removing existing ComfyUI dir')
    fs.rmSync(COMFYUI_OUT, { recursive: true })
  }

  const extractDir = path.join(BUILD_DIR, 'comfyui-extract')
  if (fs.existsSync(extractDir)) fs.rmSync(extractDir, { recursive: true })
  extract(comfyArchive, extractDir)

  const entries = fs.readdirSync(extractDir)
  const inner = entries.length === 1 ? path.join(extractDir, entries[0]) : extractDir
  fs.renameSync(inner, COMFYUI_OUT)
  if (entries.length === 1 && fs.existsSync(extractDir)) {
    try { fs.rmSync(extractDir, { recursive: true }) } catch { /* ok */ }
  }
  console.log('[download-comfyui] ComfyUI extracted to:', COMFYUI_OUT)

  // 2. Create required directories
  const dirs = [
    'models/checkpoints',
    'models/vae',
    'models/loras',
    'models/upscale_models',
    'custom_nodes',
    'user/default/workflows',
    'input',
    'output',
  ]
  for (const d of dirs) {
    fs.mkdirSync(path.join(COMFYUI_OUT, d), { recursive: true })
  }

  // 3. Download SD1.5 model
  console.log('[download-comfyui] === Step 2: SD1.5 Model ===')
  const modelDest = path.join(COMFYUI_OUT, 'models', 'checkpoints', 'v1-5-pruned-emaonly.safetensors')
  await download(SD15_MODEL_URL, modelDest)
  console.log('[download-comfyui] SD1.5 model ready')

  // 4. Copy scene workflows
  console.log('[download-comfyui] === Step 3: Scene Workflows ===')
  copySceneWorkflows()

  // 5. Install MedComm bridge extension
  console.log('[download-comfyui] === Step 4: Bridge Extension ===')
  installBridgeExtension()

  console.log('[download-comfyui] Done!')
}

main().catch((e) => {
  console.error('[download-comfyui] Failed:', e.message)
  process.exit(1)
})
