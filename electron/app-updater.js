/**
 * 应用内静默更新模块
 *
 * 下载安装包 → SHA256 校验 → 平台安装逻辑：
 *   - Windows: 启动 NSIS /S 静默安装 → quit
 *   - macOS: 解压 zip → 替换 .app → xattr -cr → relaunch
 */
const fs = require('fs')
const path = require('path')
const crypto = require('crypto')
const { app, net } = require('electron')
const { spawn, execSync } = require('child_process')

let _downloadAbortController = null
let _downloadedFilePath = null
let _downloadStatus = 'idle' // idle | downloading | downloaded | installing | error

function getUpdateDir() {
  const dir = path.join(app.getPath('userData'), 'updates')
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true })
  return dir
}

function getStatus() {
  return { status: _downloadStatus, filePath: _downloadedFilePath }
}

function cleanOldUpdates() {
  const dir = getUpdateDir()
  try {
    for (const f of fs.readdirSync(dir)) {
      const fp = path.join(dir, f)
      const stat = fs.statSync(fp)
      if (Date.now() - stat.mtimeMs > 7 * 24 * 3600 * 1000) {
        fs.unlinkSync(fp)
      }
    }
  } catch { /* noop */ }
}

/**
 * @param {object} opts
 * @param {string} opts.url - 预签名下载 URL
 * @param {string} opts.filename - 文件名
 * @param {number} [opts.sizeBytes] - 预期大小
 * @param {string} [opts.sha256] - 预期哈希
 * @param {function} [opts.onProgress] - ({ percent, downloaded, total, status }) => void
 * @returns {Promise<{ ok: boolean, filePath?: string, error?: string }>}
 */
async function downloadUpdate({ url, filename, sizeBytes, sha256, onProgress }) {
  if (_downloadStatus === 'downloading') {
    return { ok: false, error: '已有下载任务进行中' }
  }

  _downloadStatus = 'downloading'
  _downloadedFilePath = null
  _downloadAbortController = new AbortController()

  const destPath = path.join(getUpdateDir(), filename)
  if (fs.existsSync(destPath)) fs.unlinkSync(destPath)

  try {
    onProgress?.({ percent: 0, downloaded: 0, total: sizeBytes || 0, status: 'downloading' })

    const res = await net.fetch(url, {
      signal: _downloadAbortController.signal,
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)

    const contentLength = parseInt(res.headers.get('content-length') || '0', 10)
    const total = sizeBytes || contentLength || 0

    const ws = fs.createWriteStream(destPath)
    const reader = res.body.getReader()
    let downloaded = 0

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      ws.write(Buffer.from(value))
      downloaded += value.byteLength
      const percent = total > 0 ? Math.min(99, Math.round(downloaded / total * 100)) : 0
      onProgress?.({ percent, downloaded, total, status: 'downloading' })
    }

    ws.end()
    await new Promise((resolve, reject) => {
      ws.on('finish', resolve)
      ws.on('error', reject)
    })

    if (sha256) {
      onProgress?.({ percent: 99, downloaded, total, status: 'verifying' })
      const hash = await computeSHA256(destPath)
      if (hash !== sha256.toLowerCase()) {
        fs.unlinkSync(destPath)
        _downloadStatus = 'error'
        return { ok: false, error: `SHA256 校验失败\n预期: ${sha256}\n实际: ${hash}` }
      }
    }

    _downloadedFilePath = destPath
    _downloadStatus = 'downloaded'
    onProgress?.({ percent: 100, downloaded, total, status: 'done' })
    return { ok: true, filePath: destPath }
  } catch (err) {
    _downloadStatus = 'error'
    if (fs.existsSync(destPath)) fs.unlinkSync(destPath)
    if (err.name === 'AbortError') {
      return { ok: false, error: '下载已取消' }
    }
    return { ok: false, error: err.message }
  }
}

function cancelDownload() {
  if (_downloadAbortController) {
    _downloadAbortController.abort()
    _downloadAbortController = null
  }
  _downloadStatus = 'idle'
}

function computeSHA256(filePath) {
  return new Promise((resolve, reject) => {
    const hash = crypto.createHash('sha256')
    const rs = fs.createReadStream(filePath)
    rs.on('data', (chunk) => hash.update(chunk))
    rs.on('end', () => resolve(hash.digest('hex')))
    rs.on('error', reject)
  })
}

/**
 * 安装已下载的更新并重启应用。
 * @returns {{ ok: boolean, error?: string }}
 */
function installAndRestart() {
  if (!_downloadedFilePath || !fs.existsSync(_downloadedFilePath)) {
    return { ok: false, error: '未找到已下载的更新文件' }
  }

  _downloadStatus = 'installing'

  if (process.platform === 'win32') {
    return installWindows(_downloadedFilePath)
  } else if (process.platform === 'darwin') {
    return installMacOS(_downloadedFilePath)
  }
  return { ok: false, error: `不支持的平台: ${process.platform}` }
}

function installWindows(exePath) {
  try {
    const installDir = path.dirname(app.getPath('exe'))
    const child = spawn(exePath, ['/S', `/D=${installDir}`], {
      detached: true,
      stdio: 'ignore',
    })
    child.unref()

    setTimeout(() => app.quit(), 1000)
    return { ok: true }
  } catch (err) {
    _downloadStatus = 'error'
    return { ok: false, error: `启动安装程序失败: ${err.message}` }
  }
}

function installMacOS(zipPath) {
  try {
    const appPath = app.getPath('exe')
    // exe path: /Applications/LinScio MedComm.app/Contents/MacOS/LinScio MedComm
    const appBundlePath = appPath.replace(/\/Contents\/MacOS\/.*$/, '')
    const appName = path.basename(appBundlePath)
    const appParent = path.dirname(appBundlePath)
    const tempDir = path.join(getUpdateDir(), '_extract')
    const pid = process.pid

    if (fs.existsSync(tempDir)) fs.rmSync(tempDir, { recursive: true, force: true })
    fs.mkdirSync(tempDir, { recursive: true })

    const script = `#!/bin/bash
set -e
# Wait for old process to exit
while kill -0 ${pid} 2>/dev/null; do sleep 0.5; done
sleep 1

# Extract zip
unzip -o -q "${zipPath}" -d "${tempDir}"

# Find the .app in extracted content
APP_FOUND=""
for d in "${tempDir}"/*.app; do
  if [ -d "$d" ]; then APP_FOUND="$d"; break; fi
done

if [ -z "$APP_FOUND" ]; then
  echo "No .app found in zip" >&2
  exit 1
fi

# Replace old app
rm -rf "${appBundlePath}"
mv "$APP_FOUND" "${appBundlePath}"

# Remove quarantine
xattr -cr "${appBundlePath}" 2>/dev/null || true

# Cleanup
rm -rf "${tempDir}"
rm -f "${zipPath}"

# Relaunch
open "${appBundlePath}"
`
    const scriptPath = path.join(getUpdateDir(), 'update-install.sh')
    fs.writeFileSync(scriptPath, script, { mode: 0o755 })

    const child = spawn('/bin/bash', [scriptPath], {
      detached: true,
      stdio: 'ignore',
    })
    child.unref()

    setTimeout(() => app.quit(), 500)
    return { ok: true }
  } catch (err) {
    _downloadStatus = 'error'
    return { ok: false, error: `macOS 安装失败: ${err.message}` }
  }
}

module.exports = {
  downloadUpdate,
  cancelDownload,
  installAndRestart,
  getStatus,
  getUpdateDir,
  cleanOldUpdates,
}
