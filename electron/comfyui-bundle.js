/**
 * ComfyUI Bundle 下载、校验、解压管理
 *
 * 职责：
 *   - 从 portal API 获取 bundle 元数据（版本、大小、SHA256、下载地址）
 *   - 磁盘空间预检
 *   - 下载 zip 到临时目录
 *   - SHA256 完整性校验
 *   - 解压到 {userData}/comfyui-bundles/v{version}/
 *   - 写入 bundle.json
 *   - 清理临时文件
 */
const fs = require('fs')
const path = require('path')
const crypto = require('crypto')
const https = require('https')
const http = require('http')
const { app } = require('electron')
const AdmZip = require('adm-zip')

const comfyManager = require('./comfyui-manager')

// ---------------------------------------------------------------------------
// Error codes
// ---------------------------------------------------------------------------

const ErrorCodes = {
  DISK_SPACE_INSUFFICIENT: 'DISK_SPACE_INSUFFICIENT',
  DOWNLOAD_FAILED: 'DOWNLOAD_FAILED',
  CHECKSUM_MISMATCH: 'CHECKSUM_MISMATCH',
  EXTRACT_FAILED: 'EXTRACT_FAILED',
  BUNDLE_INVALID: 'BUNDLE_INVALID',
  NETWORK_ERROR: 'NETWORK_ERROR',
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getBundlesRoot() {
  return comfyManager.getBundlesRoot()
}

function getBundleJsonPath() {
  return path.join(getBundlesRoot(), 'bundle.json')
}

function getDownloadsDir() {
  const dir = path.join(app.getPath('userData'), 'downloads')
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true })
  return dir
}

function readBundleJson() {
  return comfyManager.readBundleJson()
}

function writeBundleJson(data) {
  const root = getBundlesRoot()
  if (!fs.existsSync(root)) fs.mkdirSync(root, { recursive: true })
  fs.writeFileSync(getBundleJsonPath(), JSON.stringify(data, null, 2), 'utf-8')
}

// ---------------------------------------------------------------------------
// Disk space check (best-effort, cross-platform)
// ---------------------------------------------------------------------------

async function getAvailableDiskSpace(targetPath) {
  const { execSync } = require('child_process')
  try {
    if (process.platform === 'win32') {
      const drive = path.parse(targetPath).root || 'C:\\'
      const out = execSync(`wmic logicaldisk where "DeviceID='${drive.replace('\\', '')}" get FreeSpace /format:value`, {
        encoding: 'utf-8', timeout: 5000,
      })
      const match = out.match(/FreeSpace=(\d+)/)
      return match ? parseInt(match[1], 10) : null
    }
    const out = execSync(`df -k "${targetPath}"`, { encoding: 'utf-8', timeout: 5000 })
    const lines = out.trim().split('\n')
    if (lines.length >= 2) {
      const parts = lines[1].split(/\s+/)
      return parseInt(parts[3], 10) * 1024
    }
  } catch { /* best effort */ }
  return null
}

function checkDiskSpace(requiredBytes, targetPath) {
  return getAvailableDiskSpace(targetPath).then(available => {
    if (available === null) return { ok: true, available: null }
    if (available < requiredBytes) {
      return {
        ok: false,
        available,
        required: requiredBytes,
        code: ErrorCodes.DISK_SPACE_INSUFFICIENT,
      }
    }
    return { ok: true, available }
  })
}

// ---------------------------------------------------------------------------
// Download with progress
// ---------------------------------------------------------------------------

function downloadFile(url, destPath, onProgress) {
  return new Promise((resolve, reject) => {
    const file = fs.createWriteStream(destPath)
    const proto = url.startsWith('https') ? https : http

    const doRequest = (reqUrl) => {
      proto.get(reqUrl, { timeout: 30000 }, (res) => {
        if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
          file.close()
          fs.unlinkSync(destPath)
          const redirectProto = res.headers.location.startsWith('https') ? https : http
          redirectProto.get(res.headers.location, { timeout: 30000 }, (res2) => {
            handleResponse(res2)
          }).on('error', reject)
          return
        }
        handleResponse(res)
      }).on('error', reject)
    }

    function handleResponse(res) {
      if (res.statusCode !== 200) {
        file.close()
        try { fs.unlinkSync(destPath) } catch {}
        reject(new Error(`HTTP ${res.statusCode}`))
        return
      }

      const totalBytes = parseInt(res.headers['content-length'] || '0', 10)
      let downloadedBytes = 0

      res.on('data', (chunk) => {
        downloadedBytes += chunk.length
        if (onProgress && totalBytes > 0) {
          onProgress({
            downloaded: downloadedBytes,
            total: totalBytes,
            percent: Math.round((downloadedBytes / totalBytes) * 100),
          })
        }
      })

      res.pipe(file)
      file.on('finish', () => {
        file.close()
        resolve({ downloaded: downloadedBytes, total: totalBytes })
      })
      file.on('error', (err) => {
        try { fs.unlinkSync(destPath) } catch {}
        reject(err)
      })
    }

    doRequest(url)
  })
}

// ---------------------------------------------------------------------------
// SHA256 verification
// ---------------------------------------------------------------------------

function computeSHA256(filePath) {
  return new Promise((resolve, reject) => {
    const hash = crypto.createHash('sha256')
    const stream = fs.createReadStream(filePath)
    stream.on('data', (d) => hash.update(d))
    stream.on('end', () => resolve(hash.digest('hex')))
    stream.on('error', reject)
  })
}

// ---------------------------------------------------------------------------
// Extract
// ---------------------------------------------------------------------------

function extractZip(zipPath, destDir) {
  if (!fs.existsSync(destDir)) fs.mkdirSync(destDir, { recursive: true })
  try {
    const zip = new AdmZip(zipPath)
    zip.extractAllTo(destDir, true)

    // If the zip contains a single root directory, move its contents up
    const entries = fs.readdirSync(destDir)
    if (entries.length === 1) {
      const inner = path.join(destDir, entries[0])
      if (fs.statSync(inner).isDirectory() && fs.existsSync(path.join(inner, 'main.py'))) {
        const tmpName = destDir + '_unwrap_tmp'
        fs.renameSync(inner, tmpName)
        fs.rmSync(destDir, { recursive: true })
        fs.renameSync(tmpName, destDir)
      }
    }
    return { ok: true }
  } catch (err) {
    return { ok: false, error: err.message, code: ErrorCodes.EXTRACT_FAILED }
  }
}

// ---------------------------------------------------------------------------
// Main install flow
// ---------------------------------------------------------------------------

/**
 * Install a ComfyUI bundle.
 *
 * @param {object} opts
 * @param {string} opts.downloadUrl  - Pre-signed URL for the zip
 * @param {string} opts.version      - Semantic version string
 * @param {string} opts.platform     - e.g. 'mac-arm64', 'win-x64'
 * @param {number} opts.sizeBytes    - Expected zip size in bytes
 * @param {string} [opts.sha256]     - Expected SHA256 hex digest
 * @param {function} [opts.onProgress] - Progress callback
 * @returns {Promise<{ok: boolean, error?: string, code?: string}>}
 */
async function installBundle({ downloadUrl, version, platform, sizeBytes, sha256, onProgress }) {
  const bundlesRoot = getBundlesRoot()
  const destDir = path.join(bundlesRoot, `v${version}`)
  const downloadsDir = getDownloadsDir()
  const zipFilename = `comfyui-bundle-${version}-${platform}.zip`
  const zipPath = path.join(downloadsDir, zipFilename)

  // 1. Disk space check (need roughly 2x: zip + extracted)
  const requiredSpace = (sizeBytes || 0) * 2.5
  if (requiredSpace > 0) {
    const spaceCheck = await checkDiskSpace(requiredSpace, bundlesRoot)
    if (!spaceCheck.ok) {
      const availMB = Math.round((spaceCheck.available || 0) / 1024 / 1024)
      const reqMB = Math.round(requiredSpace / 1024 / 1024)
      return {
        ok: false,
        code: ErrorCodes.DISK_SPACE_INSUFFICIENT,
        error: `磁盘空间不足：需要约 ${reqMB} MB，当前可用 ${availMB} MB`,
      }
    }
  }

  // 2. Download
  if (onProgress) onProgress({ status: 'downloading', percent: 0 })
  try {
    await downloadFile(downloadUrl, zipPath, (p) => {
      if (onProgress) onProgress({ status: 'downloading', ...p })
    })
  } catch (err) {
    try { fs.unlinkSync(zipPath) } catch {}
    return { ok: false, code: ErrorCodes.DOWNLOAD_FAILED, error: `下载失败：${err.message}` }
  }

  // 3. SHA256 check
  if (sha256) {
    if (onProgress) onProgress({ status: 'verifying', percent: 100 })
    const actual = await computeSHA256(zipPath)
    if (actual !== sha256.toLowerCase()) {
      try { fs.unlinkSync(zipPath) } catch {}
      return {
        ok: false,
        code: ErrorCodes.CHECKSUM_MISMATCH,
        error: `文件校验失败（期望 ${sha256.slice(0, 12)}…，实际 ${actual.slice(0, 12)}…），请重新下载`,
      }
    }
  }

  // 4. Extract
  if (onProgress) onProgress({ status: 'extracting', percent: 0 })
  if (fs.existsSync(destDir)) {
    fs.rmSync(destDir, { recursive: true, force: true })
  }
  const extractResult = extractZip(zipPath, destDir)
  if (!extractResult.ok) {
    try { fs.unlinkSync(zipPath) } catch {}
    return extractResult
  }

  // 5. Validate extraction
  if (!fs.existsSync(path.join(destDir, 'main.py'))) {
    try { fs.rmSync(destDir, { recursive: true }) } catch {}
    try { fs.unlinkSync(zipPath) } catch {}
    return { ok: false, code: ErrorCodes.BUNDLE_INVALID, error: '解压后未找到 ComfyUI main.py，包可能损坏' }
  }

  // 6. Write bundle.json
  writeBundleJson({
    version,
    platform,
    installed_at: new Date().toISOString(),
    dir: destDir,
  })

  // 7. Clean up zip
  try { fs.unlinkSync(zipPath) } catch {}

  if (onProgress) onProgress({ status: 'done', percent: 100 })
  return { ok: true, version, dir: destDir }
}

/**
 * Remove installed bundle and reset bundle.json.
 */
function uninstallBundle() {
  const bundle = readBundleJson()
  if (bundle?.version) {
    const dir = path.join(getBundlesRoot(), `v${bundle.version}`)
    try { fs.rmSync(dir, { recursive: true, force: true }) } catch {}
  }
  try { fs.unlinkSync(getBundleJsonPath()) } catch {}
}

module.exports = {
  installBundle,
  uninstallBundle,
  readBundleJson,
  writeBundleJson,
  checkDiskSpace,
  computeSHA256,
  ErrorCodes,
}
