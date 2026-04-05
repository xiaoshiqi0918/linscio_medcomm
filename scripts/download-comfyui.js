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
 *   COMFYUI_RELEASE_URL       覆盖 ComfyUI 下载地址（仅此 URL）
 *   COMFYUI_SKIP_MIRROR=1     不用国内镜像，只从 GitHub 官方下
 *   SD15_MODEL_URL            覆盖 SD1.5 模型下载地址
 *   SD15_SKIP_MIRROR=1        不用 hf-mirror，只从 Hugging Face 官方下
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

/** v1-5-pruned-emaonly.safetensors is ~4GB; reject tiny/corrupt/HTML placeholder files */
const SD15_MIN_BYTES = 200 * 1024 * 1024

const SD15_OFFICIAL =
  'https://huggingface.co/stable-diffusion-v1-5/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.safetensors'

function comfyuiDownloadUrls() {
  if (process.env.COMFYUI_RELEASE_URL) {
    return [process.env.COMFYUI_RELEASE_URL]
  }
  const v = COMFYUI_VERSION
  const official = `https://github.com/comfyanonymous/ComfyUI/archive/refs/tags/v${v}.tar.gz`
  if (process.env.COMFYUI_SKIP_MIRROR === '1') {
    return [official]
  }
  const rel = `github.com/comfyanonymous/ComfyUI/archive/refs/tags/v${v}.tar.gz`
  return [
    `https://mirror.ghproxy.com/https://${rel}`,
    `https://ghfast.top/https://${rel}`,
    official,
  ]
}

function sd15DownloadUrls() {
  if (process.env.SD15_MODEL_URL) {
    return [process.env.SD15_MODEL_URL]
  }
  if (process.env.SD15_SKIP_MIRROR === '1') {
    return [SD15_OFFICIAL]
  }
  return [
    `https://hf-mirror.com/stable-diffusion-v1-5/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.safetensors`,
    SD15_OFFICIAL,
  ]
}

function isTransientNetError(err) {
  const c = err && err.code
  return (
    c === 'ECONNRESET'
    || c === 'ETIMEDOUT'
    || c === 'ECONNREFUSED'
    || c === 'EPIPE'
    || c === 'ENETUNREACH'
    || c === 'EAI_AGAIN'
  )
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms))
}

function download(url, dest, options = {}) {
  const { skipExistCheck = false } = options
  return new Promise((resolve, reject) => {
    if (!skipExistCheck && fs.existsSync(dest)) {
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

/**
 * Try each URL in order; per URL retry transient errors a few times.
 */
async function downloadWithMirrors(urls, dest) {
  if (fs.existsSync(dest)) {
    console.log('[download-comfyui] Cached:', path.basename(dest))
    return dest
  }
  let lastErr
  for (let u = 0; u < urls.length; u++) {
    const url = urls[u]
    const perSourceAttempts = 3
    for (let attempt = 1; attempt <= perSourceAttempts; attempt++) {
      if (fs.existsSync(dest)) {
        try {
          fs.unlinkSync(dest)
        } catch {
          /* ok */
        }
      }
      try {
        await download(url, dest, { skipExistCheck: true })
        return dest
      } catch (e) {
        lastErr = e
        if (fs.existsSync(dest)) {
          try {
            fs.unlinkSync(dest)
          } catch {
            /* ok */
          }
        }
        const transient = isTransientNetError(e)
        const msg = e.code || e.message
        if (transient && attempt < perSourceAttempts) {
          const ms = 2000 * attempt
          console.warn(
            `[download-comfyui] ${msg} — retry ${attempt}/${perSourceAttempts} in ${ms}ms`,
          )
          await sleep(ms)
        } else {
          console.warn(
            `[download-comfyui] Source ${u + 1}/${urls.length} failed: ${msg}`,
          )
          break
        }
      }
    }
    if (u < urls.length - 1) {
      console.log('[download-comfyui] Trying next mirror...')
    }
  }
  throw lastErr || new Error('All download sources failed')
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

function sd15ModelPath() {
  return path.join(COMFYUI_OUT, 'models', 'checkpoints', 'v1-5-pruned-emaonly.safetensors')
}

function sd15ModelOk() {
  const p = sd15ModelPath()
  if (!fs.existsSync(p)) return false
  try {
    return fs.statSync(p).size >= SD15_MIN_BYTES
  } catch {
    return false
  }
}

function copySceneWorkflows() {
  const userWorkflowDir = path.join(COMFYUI_OUT, 'user', 'default', 'workflows')
  fs.mkdirSync(userWorkflowDir, { recursive: true })
  if (!fs.existsSync(WORKFLOWS_SRC)) {
    console.warn('[download-comfyui] No workflow source dir:', WORKFLOWS_SRC)
    return
  }
  for (const f of fs.readdirSync(WORKFLOWS_SRC)) {
    if (f.endsWith('.json')) {
      fs.copyFileSync(path.join(WORKFLOWS_SRC, f), path.join(userWorkflowDir, f))
      console.log('[download-comfyui] Copied workflow:', f)
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
    console.log('[download-comfyui] ComfyUI core already present (use --force to re-fetch archive)')
    fs.mkdirSync(path.dirname(sd15ModelPath()), { recursive: true })
    if (!sd15ModelOk()) {
      if (fs.existsSync(sd15ModelPath())) {
        console.warn('[download-comfyui] SD1.5 checkpoint missing or too small — re-downloading')
        try {
          fs.unlinkSync(sd15ModelPath())
        } catch {
          /* ok */
        }
      }
      console.log('[download-comfyui] === Step 2: SD1.5 Model (incremental) ===')
      await downloadWithMirrors(sd15DownloadUrls(), sd15ModelPath())
      if (!sd15ModelOk()) {
        throw new Error('SD1.5 checkpoint still invalid after download (size check failed)')
      }
      console.log('[download-comfyui] SD1.5 model ready')
    } else {
      const sz = fs.statSync(sd15ModelPath()).size
      console.log('[download-comfyui] SD1.5 checkpoint OK (' + (sz / 1e9).toFixed(2) + ' GB)')
    }
    console.log('[download-comfyui] === Scene Workflows (refresh) ===')
    copySceneWorkflows()
    console.log('[download-comfyui] === Bridge Extension (refresh) ===')
    installBridgeExtension()
    console.log('[download-comfyui] Done!')
    return
  }

  fs.mkdirSync(BUILD_DIR, { recursive: true })

  // 1. Download ComfyUI
  console.log('[download-comfyui] === Step 1: ComfyUI ===')
  const comfyArchive = path.join(BUILD_DIR, `comfyui-v${COMFYUI_VERSION}.tar.gz`)
  await downloadWithMirrors(comfyuiDownloadUrls(), comfyArchive)

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
  const modelDest = sd15ModelPath()
  await downloadWithMirrors(sd15DownloadUrls(), modelDest)
  if (!sd15ModelOk()) {
    throw new Error('SD1.5 checkpoint invalid after download (size check failed)')
  }
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
