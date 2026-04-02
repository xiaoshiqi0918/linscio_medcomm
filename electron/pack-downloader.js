/**
 * 学科包下载 + 解压 + 调后端安装
 *
 * 流程：
 *   1. 从门户 API 获取预签名下载 URL
 *   2. 下载 .zip 到临时目录（带进度推送）
 *   3. 解压到 {APP_DATA}/specialty-packs/{specialty_id}/
 *   4. 调后端 POST /api/v1/specialty/install
 *   5. 清理临时文件
 */
const fs = require('fs')
const path = require('path')
const { app, net } = require('electron')
const { createWriteStream } = require('fs')

/** 与 main 进程在启动时设置的 LINSCIO_APP_DATA 一致 */
function getAppDataRoot() {
  return process.env.LINSCIO_APP_DATA || path.join(app.getPath('userData'), 'data')
}

function getPacksDir() {
  return path.join(getAppDataRoot(), 'specialty-packs')
}

function ensurePacksDir() {
  const dir = getPacksDir()
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true })
  }
}

/**
 * 完整的学科包安装流程
 * @param {Electron.BrowserWindow} mainWindow
 * @param {string} token - access_token
 * @param {string} specialtyId
 * @param {string} specialtyName - 显示名称
 * @param {string} version
 * @param {string|null} fromVersion - 增量更新的起始版本
 * @param {string} localApiKey - 后端 API Key
 * @returns {Promise<{ok: boolean, error?: string}>}
 */
async function installSpecialtyPack(mainWindow, token, specialtyId, specialtyName, version, fromVersion, localApiKey) {
  const sendProgress = (percent, status, detail) => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('specialty-download-progress', {
        specialty_id: specialtyId,
        name: specialtyName,
        percent,
        status,
        detail: detail || '',
      })
    }
  }

  try {
    ensurePacksDir()

    // Step 1: 获取下载 URL
    sendProgress(5, 'requesting', '正在获取下载地址...')
    const authChecker = require('./auth-checker')
    const dlData = await authChecker.downloadSpecialty(token, specialtyId, version, fromVersion)
    if (!dlData?.download_url) {
      throw new Error('门户未返回下载地址')
    }

    // Step 2: 下载文件
    sendProgress(10, 'downloading', '正在下载学科包...')
    const tmpZip = path.join(getPacksDir(), `${specialtyId}_${version}.zip.tmp`)
    await downloadFile(dlData.download_url, tmpZip, (downloaded, total) => {
      const pct = total > 0 ? Math.min(70, 10 + Math.floor((downloaded / total) * 60)) : 30
      sendProgress(pct, 'downloading', `已下载 ${formatBytes(downloaded)}${total > 0 ? ' / ' + formatBytes(total) : ''}`)
    })

    // Step 3: 解压
    sendProgress(75, 'extracting', '正在解压...')
    const extractDir = path.join(getPacksDir(), specialtyId)
    await extractZip(tmpZip, extractDir)

    // 清理临时文件
    try { fs.unlinkSync(tmpZip) } catch {}

    // Step 4: 调后端安装
    sendProgress(85, 'installing', '正在导入知识库、术语和范例...')
    const backendResult = await callBackendInstall(specialtyId, specialtyName, version, extractDir, localApiKey)
    if (!backendResult.ok) {
      throw new Error(backendResult.errors?.join('; ') || '后端安装失败')
    }

    sendProgress(100, 'done', `${specialtyName || specialtyId} 安装完成`)
    return { ok: true, result: backendResult }
  } catch (err) {
    sendProgress(0, 'error', err.message || '安装失败')
    return { ok: false, error: err.message }
  }
}

/**
 * 下载文件（带进度回调）
 */
function downloadFile(url, destPath, onProgress) {
  return new Promise((resolve, reject) => {
    const file = createWriteStream(destPath)
    const request = net.request(url)

    request.on('response', (response) => {
      if (response.statusCode >= 300 && response.statusCode < 400 && response.headers.location) {
        file.close()
        try { fs.unlinkSync(destPath) } catch {}
        const redirectUrl = Array.isArray(response.headers.location)
          ? response.headers.location[0]
          : response.headers.location
        downloadFile(redirectUrl, destPath, onProgress).then(resolve).catch(reject)
        return
      }
      if (response.statusCode !== 200) {
        file.close()
        try { fs.unlinkSync(destPath) } catch {}
        reject(new Error(`下载失败 HTTP ${response.statusCode}`))
        return
      }

      const contentLength = parseInt(
        (Array.isArray(response.headers['content-length'])
          ? response.headers['content-length'][0]
          : response.headers['content-length']) || '0',
        10
      )
      let downloaded = 0

      response.on('data', (chunk) => {
        file.write(chunk)
        downloaded += chunk.length
        if (onProgress) onProgress(downloaded, contentLength)
      })

      response.on('end', () => {
        file.end(() => resolve())
      })

      response.on('error', (err) => {
        file.close()
        try { fs.unlinkSync(destPath) } catch {}
        reject(err)
      })
    })

    request.on('error', (err) => {
      file.close()
      try { fs.unlinkSync(destPath) } catch {}
      reject(err)
    })

    request.end()
  })
}

/**
 * 解压 zip 到目标目录
 */
async function extractZip(zipPath, destDir) {
  if (fs.existsSync(destDir)) {
    fs.rmSync(destDir, { recursive: true, force: true })
  }
  fs.mkdirSync(destDir, { recursive: true })

  // 使用 Node.js 内置的 zlib + 第三方 yauzl 或回退到 unzip 命令
  try {
    // 优先使用系统 unzip（macOS/Linux 自带）
    const { execSync } = require('child_process')
    execSync(`unzip -o -q "${zipPath}" -d "${destDir}"`, { timeout: 60000 })
  } catch {
    // Windows 回退：使用 PowerShell
    try {
      const { execSync } = require('child_process')
      execSync(
        `powershell -Command "Expand-Archive -Path '${zipPath}' -DestinationPath '${destDir}' -Force"`,
        { timeout: 60000 }
      )
    } catch (e) {
      throw new Error(`解压失败: ${e.message}`)
    }
  }

  // 将学科包内容提升到 destDir 根目录（确保 config.json 在顶层）
  const entries = fs.readdirSync(destDir)
  if (entries.length === 1) {
    const singleDir = path.join(destDir, entries[0])
    if (fs.statSync(singleDir).isDirectory()) {
      const innerEntries = fs.readdirSync(singleDir)
      for (const e of innerEntries) {
        fs.renameSync(path.join(singleDir, e), path.join(destDir, e))
      }
      fs.rmdirSync(singleDir)
    }
  }

  // 如果 config.json 仍不在顶层，尝试从嵌套子目录查找并提升
  if (!fs.existsSync(path.join(destDir, 'config.json'))) {
    const dirs = fs.readdirSync(destDir).filter(e => fs.statSync(path.join(destDir, e)).isDirectory())
    for (const d of dirs) {
      if (fs.existsSync(path.join(destDir, d, 'config.json'))) {
        const innerEntries = fs.readdirSync(path.join(destDir, d))
        for (const e of innerEntries) {
          const src = path.join(destDir, d, e)
          const dst = path.join(destDir, e)
          if (!fs.existsSync(dst)) fs.renameSync(src, dst)
        }
        fs.rmSync(path.join(destDir, d), { recursive: true, force: true })
        break
      }
    }
  }
}

/**
 * 调后端安装 API
 */
async function callBackendInstall(specialtyId, name, version, packDir, localApiKey) {
  const url = 'http://127.0.0.1:8765/api/v1/specialty/install'
  const headers = { 'Content-Type': 'application/json' }
  if (localApiKey) headers['X-Local-Api-Key'] = localApiKey

  const res = await net.fetch(url, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      pack_dir: packDir,
      specialty_id: specialtyId,
      name: name || specialtyId,
      version: version || '1.0.0',
    }),
    signal: AbortSignal.timeout(120000),
  })

  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `后端安装 HTTP ${res.status}`)
  }

  return await res.json()
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

module.exports = { installSpecialtyPack, getPacksDir }
