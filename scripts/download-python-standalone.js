#!/usr/bin/env node
/**
 * 下载 python-build-standalone 3.11.x 到 build/python/
 * 用于 electron-builder 打包前准备
 * 用法: node scripts/download-python-standalone.js
 */
const fs = require('fs')
const path = require('path')
const https = require('https')
const { execSync } = require('child_process')

const resolver = require('../electron/python-resolver')
const BUILD_DIR = path.join(__dirname, '..', 'build')
const PYTHON_OUT = path.join(BUILD_DIR, 'python')

function getPlatformId() {
  const targetArch = process.env.TARGET_ARCH || process.env.npm_config_arch || process.arch
  if (process.platform === 'win32') return 'win32-x64'
  if (process.platform === 'darwin') return targetArch === 'arm64' ? 'darwin-arm64' : 'darwin-x64'
  return targetArch === 'arm64' ? 'linux-arm64' : 'linux-x64'
}

function download(url) {
  return new Promise((resolve, reject) => {
    const file = path.join(BUILD_DIR, path.basename(url))
    if (fs.existsSync(file)) {
      console.log('[download-python] Using cached', file)
      resolve(file)
      return
    }
    console.log('[download-python] Fetching', url)
    const stream = fs.createWriteStream(file)
    function doGet(u) {
      https.get(u, (res) => {
        if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
          stream.close()
          if (fs.existsSync(file)) fs.unlinkSync(file)
          doGet(res.headers.location)
          return
        }
        if (res.statusCode !== 200) {
          stream.close()
          if (fs.existsSync(file)) fs.unlinkSync(file)
          reject(new Error(`HTTP ${res.statusCode}`))
          return
        }
        res.pipe(stream)
        stream.on('finish', () => { stream.close(); resolve(file) })
      }).on('error', (e) => { stream.close(); if (fs.existsSync(file)) fs.unlinkSync(file); reject(e) })
    }
    doGet(url)
  })
}

function extract(archive, dest) {
  fs.mkdirSync(dest, { recursive: true })
  if (archive.endsWith('.tar.gz')) {
    execSync(`tar -xzf "${archive}" -C "${dest}"`, { stdio: 'inherit' })
  } else if (archive.endsWith('.zip')) {
    execSync(`unzip -o "${archive}" -d "${dest}"`, { stdio: 'inherit' })
  } else {
    throw new Error('Unknown archive format: ' + archive)
  }
}

function main() {
  if (process.env.SKIP_PREBUILD_PYTHON === '1') {
    console.log('[download-python] SKIP_PREBUILD_PYTHON=1, skip')
    return
  }
  const force = process.argv.includes('--force')
  const platform = getPlatformId()
  const url = resolver.getDownloadUrl()
  if (!url) {
    console.error('[download-python] Unsupported platform', platform)
    process.exit(1)
  }
  const pythonExe = process.platform === 'win32'
    ? path.join(PYTHON_OUT, 'python.exe')
    : path.join(PYTHON_OUT, 'bin', 'python3')
  if (fs.existsSync(pythonExe) && !force) {
    console.log('[download-python] Already exists, skip (use --force to re-download)')
    return
  }
  fs.mkdirSync(BUILD_DIR, { recursive: true })
  download(url).then((archive) => {
    if (fs.existsSync(PYTHON_OUT)) {
      console.log('[download-python] Removing existing', PYTHON_OUT)
      fs.rmSync(PYTHON_OUT, { recursive: true })
    }
    const extractDir = path.join(BUILD_DIR, 'python-extract')
    if (fs.existsSync(extractDir)) fs.rmSync(extractDir, { recursive: true })
    fs.mkdirSync(extractDir, { recursive: true })
    extract(archive, extractDir)
    const extracted = fs.readdirSync(extractDir)
    const inner = extracted.length === 1 ? path.join(extractDir, extracted[0]) : extractDir
    fs.renameSync(inner, PYTHON_OUT)
    if (extracted.length === 1) fs.rmSync(extractDir, { recursive: true })
    console.log('[download-python] Done:', PYTHON_OUT)
  }).catch((e) => {
    console.error('[download-python] Failed:', e.message)
    process.exit(1)
  })
}

main()
