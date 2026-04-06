/**
 * LinScio MedComm Electron 主进程
 * 启动时序 7.1：① localApiKey → ② Splash → ③ Keychain → ④ image-protocol
 *          ⑤ first-run → ⑥ migration → ⑦ 数据目录 → ⑧ spawn → ⑨ 轮询 /health → ⑩ 主窗口
 */
const crypto = require('crypto')
const fs = require('fs')
const path = require('path')
const { app, BrowserWindow, ipcMain, dialog, shell } = require('electron')

const isDev = process.env.NODE_ENV === 'development'

/**
 * 开发模式默认用仓库 backend/.data，与 `cd backend && python run.py` 共用 medcomm.db；
 * 避免 Electron userData 与本地后端各用一套库导致迁移/表结构不一致。
 * 若要测「安装升级」场景：MEDCOMM_USE_USERDATA_DATA=1 或显式 LINSCIO_APP_DATA=...
 */
function resolveAppDataRoot() {
  if (process.env.LINSCIO_APP_DATA) {
    const v = process.env.LINSCIO_APP_DATA
    return path.isAbsolute(v) ? v : path.resolve(process.cwd(), v)
  }
  if (isDev && process.env.MEDCOMM_USE_USERDATA_DATA === '1') {
    return path.join(app.getPath('userData'), 'data')
  }
  if (isDev) {
    return path.join(__dirname, '..', 'backend', '.data')
  }
  return path.join(app.getPath('userData'), 'data')
}

const APP_DATA_ROOT = resolveAppDataRoot()
process.env.LINSCIO_APP_DATA = APP_DATA_ROOT
if (isDev) {
  console.log('[MedComm] dev LINSCIO_APP_DATA =', APP_DATA_ROOT)
}

const backend = require('./backend')
const comfyui = require('./comfyui-manager')
const comfyBundle = require('./comfyui-bundle')
const appUpdater = require('./app-updater')
const startupCheck = require('./startup-check')
const imageProtocol = require('./image-protocol')
const migration = require('./migration')
const firstRun = require('./first-run')
const backup = require('./backup')
const authChecker = require('./auth-checker')
const keychain = require('./keychain')
const packDownloader = require('./pack-downloader')

global.licenseCache = { timestamp: 0, data: null }

/** 开发模式默认走 Vite 热更新；设置 MEDCOMM_RENDERER=dist 则加载构建产物（如 npm run electron:dev:dist） */
const useViteDevServer = isDev && process.env.MEDCOMM_RENDERER !== 'dist'
const isDevAuthBypass = isDev && (
  process.env.MEDCOMM_DEV_BYPASS_AUTH === '1' ||
  process.env.LINSCIO_DEV_BYPASS_AUTH === '1'
)

let mainWindow = null
let splashWindow = null
let localApiKey = ''

function updateSplashStatus(text) {
  if (splashWindow && !splashWindow.isDestroyed()) {
    splashWindow.webContents.executeJavaScript(
      `document.getElementById('status').textContent = ${JSON.stringify(text)}`
    ).catch(() => {})
  }
}

function showSplash() {
  splashWindow = new BrowserWindow({
    width: 400,
    height: 280,
    frame: false,
    transparent: false,
    alwaysOnTop: true,
    resizable: false,
    webPreferences: { nodeIntegration: false },
  })
  splashWindow.loadFile(path.join(__dirname, 'splash.html'))
  splashWindow.on('closed', () => { splashWindow = null })
}

function closeSplash() {
  if (splashWindow && !splashWindow.isDestroyed()) {
    splashWindow.close()
    splashWindow = null
  }
}

function ensureDataDirs() {
  if (!fs.existsSync(APP_DATA_ROOT)) fs.mkdirSync(APP_DATA_ROOT, { recursive: true })
  const dirs = ['images', 'backups', 'uploads']
  dirs.forEach((d) => {
    const p = path.join(APP_DATA_ROOT, d)
    if (!fs.existsSync(p)) fs.mkdirSync(p, { recursive: true })
  })
}

function pollHealth(timeoutMs = 60000, intervalMs = 500) {
  return new Promise((resolve) => {
    const start = Date.now()
    const t = setInterval(async () => {
      const ok = await backend.checkHealth()
      if (ok) {
        clearInterval(t)
        resolve(true)
        return
      }
      if (Date.now() - start >= timeoutMs) {
        clearInterval(t)
        resolve(false)
      }
    }, intervalMs)
  })
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
    title: 'LinScio MedComm - 医学科普写作智能体',
  })

  const rendererIndex = path.join(__dirname, '../dist/index.html')
  const viteDevUrl = 'http://127.0.0.1:5173/'

  if (useViteDevServer) {
    let viteFallbackTried = false
    const tryLoadDistAfterViteFail = () => {
      if (viteFallbackTried) return
      viteFallbackTried = true
      if (fs.existsSync(rendererIndex)) {
        console.warn(
          '[MedComm] Vite 开发服务器不可用，已回退到 dist/index.html（界面可能不是最新，请执行 npm run build 或改用 npm run electron:dev）'
        )
        mainWindow.loadFile(rendererIndex)
      } else {
        dialog.showErrorBox(
          '开发模式需要 Vite',
          '未连接到 http://127.0.0.1:5173，且未找到 dist/index.html。\n请运行 npm run electron:dev（会同时启动 Vite），或先 npm run build 后再单独启动 Electron。'
        )
        app.quit()
      }
    }
    mainWindow.webContents.once('did-fail-load', (_e, _code, _desc, failedUrl) => {
      const u = String(failedUrl || '')
      if (u.startsWith('http://127.0.0.1:5173')) tryLoadDistAfterViteFail()
    })
    mainWindow.loadURL(viteDevUrl)
  } else if (fs.existsSync(rendererIndex)) {
    mainWindow.loadFile(rendererIndex)
  } else {
    dialog.showErrorBox(
      '前端构建产物缺失',
      '未找到 dist/index.html，请先在项目根目录执行 npm run build。'
    )
    app.quit()
    return
  }

  if (isDev) {
    mainWindow.webContents.openDevTools()
  }

  mainWindow.once('ready-to-show', async () => {
    if (isDevAuthBypass) {
      // 仅开发模式下可用：本地免激活联调
      mainWindow.webContents.send('license-valid', {
        valid: true,
        days_remaining: 3650,
        expires_at: null,
      })
      mainWindow.show()
      return
    }

    let token = null
    try {
      token = await keychain.getPassword('access_token')
    } catch (e) { /* keychain 不可用 */ }
    if (!token) {
      mainWindow.webContents.send('show-activation-guide')
    }
    mainWindow.show()
    if (token) {
      setTimeout(() => {
        authChecker.checkAuthStatus(mainWindow, global.licenseCache, token)
      }, 10000)
      setTimeout(() => {
        const pkgVersion = app.getVersion() || '0.0.0'
        authChecker.checkSoftwareUpdate(mainWindow, token, pkgVersion)
      }, 15000)
    }
  })
  mainWindow.on('closed', () => { mainWindow = null })
}

function handleDeepLink(url) {
  if (!url || !url.startsWith('linscio://')) return
  try {
    const u = new URL(url)
    const dlPath = ((u.hostname || '') + (u.pathname || '')).replace(/^\/+|\/+$/g, '') || u.hostname || ''
    const allIds = u.searchParams.getAll('ids')
    const params = Object.fromEntries(u.searchParams)

    if (dlPath === 'auth' && params.token) {
      storeTokenAndActivate(params.token)
    } else if (dlPath === 'auth' && params.activation_code) {
      exchangeActivationCode(params.activation_code)
    } else if (dlPath === 'specialty/new' && (params.ids || allIds.length)) {
      const ids = allIds.length > 1
        ? allIds
        : (params.ids || '').split(',').filter(Boolean)
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('new-specialties-available', { ids })
      }
    } else if (dlPath === 'import/document') {
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('import-document-prompt', {
          specialty: params.specialty,
          url: params.url,
          title: params.title,
        })
      }
    }
  } catch (e) {
    console.warn('[MedComm] deep link parse error:', e.message)
  }
}

function storeTokenAndActivate(token) {
  keychain.setPassword('access_token', token).then(() => {
    authChecker.clearLicenseCache(global.licenseCache)
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('license-activated', { token })
      setTimeout(() => {
        authChecker.checkAuthStatus(mainWindow, global.licenseCache, token)
      }, 500)
    }
  }).catch(console.warn)
}

async function exchangeActivationCode(activationCode) {
  const { net } = require('electron')
  const base = authChecker.getPortalApiBase()
  if (!base) {
    console.warn('[MedComm] No portal API base URL configured, cannot exchange activation code')
    return
  }

  const os = require('os')
  const deviceFingerprint = `${os.hostname()}-${os.platform()}-${os.arch()}`

  try {
    const apiUrl = `${base.replace(/\/$/, '')}/api/auth/activate-by-code`
    const res = await net.fetch(apiUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        activation_code: activationCode,
        device_fingerprint: deviceFingerprint,
      }),
      signal: AbortSignal.timeout(10000),
    })

    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      console.warn('[MedComm] activation code exchange failed:', res.status, body.detail || '')
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('activation-error', {
          message: body.detail || `激活失败 (${res.status})`,
        })
      }
      return
    }

    const data = await res.json()
    if (data.access_token) {
      storeTokenAndActivate(data.access_token)
    }
  } catch (e) {
    console.warn('[MedComm] activation code exchange error:', e.message)
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('activation-error', {
        message: '激活码交换失败，请重试',
      })
    }
  }
}

async function startBackend() {
  const env = {
    LINSCIO_APP_DATA: APP_DATA_ROOT,
    LINSCIO_LOCAL_API_KEY: localApiKey,
  }
  if (isDev) {
    env.DEBUG = '1'
  }
  try {
    const keychain = require('./keychain')
    Object.assign(env, await keychain.getApiKeysForBackend())
  } catch (e) { /* keychain 不可用时忽略 */ }

  if (!startBackend._restartCount) startBackend._restartCount = 0
  backend.start(env)
}

async function reloadBackendWithLatestKeys() {
  backend.stop()
  await new Promise((r) => setTimeout(r, 500))
  await startBackend()
  const ok = await pollHealth(20000, 300)
  return ok
}

// IPC
ipcMain.handle('save-api-key', async (_, account, value) => {
  try {
    await require('./keychain').setPassword(account, value)
    return { ok: true }
  } catch (e) {
    return { ok: false, error: e.message }
  }
})

ipcMain.handle('reload-backend-env', async () => {
  try {
    const ok = await reloadBackendWithLatestKeys()
    return ok ? { ok: true } : { ok: false, error: '后端重载超时' }
  } catch (e) {
    return { ok: false, error: e.message }
  }
})

ipcMain.handle('get-api-key', async (_, account) => {
  try {
    return await require('./keychain').getPassword(account)
  } catch (e) {
    return null
  }
})

ipcMain.handle('get-local-api-key', () => localApiKey)

ipcMain.handle('backup-full', async () => backup.backupFull())
ipcMain.handle('backup-db-only', async () => backup.backupDbOnly())
ipcMain.handle('restore-from-zip', async (_, zipPath, strategy) =>
  backup.restoreFromZip(zipPath, strategy))
ipcMain.handle('list-backups', async () => {
  const dir = backup.getBackupsDir()
  if (!fs.existsSync(dir)) return []
  return fs.readdirSync(dir)
    .filter((f) => f.endsWith('.linscio-backup'))
    .map((f) => ({ name: f, path: path.join(dir, f) }))
})

ipcMain.handle('show-open-backup-dialog', async () => {
  const { canceled, filePaths } = await dialog.showOpenDialog(mainWindow || undefined, {
    title: '选择备份文件',
    filters: [{ name: '备份', extensions: ['linscio-backup'] }],
    properties: ['openFile'],
  })
  return canceled ? null : filePaths[0]
})

ipcMain.handle('open-external-url', async (_, url) => {
  if (url && typeof url === 'string' && (url.startsWith('http://') || url.startsWith('https://'))) {
    await shell.openExternal(url)
  }
})

ipcMain.handle('get-portal-activate-url', async () => {
  return authChecker.getPortalActivateUrl()
})

ipcMain.handle('portal-login', async (_, email, password) => {
  const { net } = require('electron')
  const os = require('os')
  const base = authChecker.getPortalApiBase()
  if (!base) return { ok: false, error: '未配置门户 API 地址' }

  try {
    const apiUrl = `${base.replace(/\/$/, '')}/api/auth/client-login`
    const deviceFingerprint = `${os.hostname()}-${os.platform()}-${os.arch()}`
    const res = await net.fetch(apiUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email,
        password,
        product_id: authChecker.MEDCOMM_PRODUCT_ID,
        device_fingerprint: deviceFingerprint,
        device_name: os.hostname(),
      }),
      signal: AbortSignal.timeout(10000),
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) {
      return { ok: false, error: data.detail || `登录失败 (${res.status})` }
    }
    if (data.access_token) {
      await keychain.setPassword('access_token', data.access_token)
      authChecker.clearLicenseCache(global.licenseCache)
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('license-activated', { token: data.access_token })
        setTimeout(() => {
          authChecker.checkAuthStatus(mainWindow, global.licenseCache, data.access_token)
        }, 500)
      }
      return { ok: true, email: data.email, expires_at: data.expires_at, days_remaining: data.days_remaining }
    }
    return { ok: false, error: '服务端未返回 access_token' }
  } catch (e) {
    return { ok: false, error: e.message || '网络错误' }
  }
})

ipcMain.handle('deactivate-license', async () => {
  try {
    await keychain.deletePassword('access_token')
    authChecker.clearLicenseCache(global.licenseCache)
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('show-activation-guide')
    }
    return { ok: true }
  } catch (e) {
    return { ok: false, error: e.message }
  }
})

ipcMain.handle('download-specialty', async (_, specialtyId, specialtyName, version, fromVersion) => {
  try {
    const token = await keychain.getPassword('access_token')
    if (!token) return { ok: false, error: '未激活，请先完成授权' }
    return await packDownloader.installSpecialtyPack(
      mainWindow, token, specialtyId, specialtyName || specialtyId, version, fromVersion, localApiKey
    )
  } catch (e) {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('specialty-download-progress', {
        specialty_id: specialtyId, percent: 0, status: 'error', detail: e.message,
      })
    }
    return { ok: false, error: e.message }
  }
})

ipcMain.handle('get-pack-status', async () => {
  try {
    const { net: _net } = require('electron')
    const headers = { 'Content-Type': 'application/json' }
    if (localApiKey) headers['X-Local-Api-Key'] = localApiKey
    const res = await _net.fetch('http://127.0.0.1:8765/api/v1/specialty/status', { headers })
    if (!res.ok) return []
    return await res.json()
  } catch {
    return []
  }
})

ipcMain.handle('get-app-version', () => app.getVersion())

ipcMain.handle('check-for-update', async () => {
  try {
    const token = await keychain.getPassword('access_token')
    if (!token) return { ok: false, error: '未激活' }
    const pkgVersion = app.getVersion() || '0.0.0'
    let localPacks = []
    try {
      const { net: _net } = require('electron')
      const headers = { 'Content-Type': 'application/json' }
      if (localApiKey) headers['X-Local-Api-Key'] = localApiKey
      const packRes = await _net.fetch('http://127.0.0.1:8765/api/v1/specialty/status', { headers })
      if (packRes.ok) localPacks = await packRes.json()
    } catch { /* ignore */ }
    await authChecker.checkSoftwareUpdate(mainWindow, token, pkgVersion, localPacks)
    return { ok: true }
  } catch (e) {
    return { ok: false, error: e.message }
  }
})

// ── 应用内更新 IPC ──

ipcMain.handle('download-software-update', async (_, opts) => {
  if (!opts?.url || !opts?.filename) {
    return { ok: false, error: '缺少下载参数' }
  }
  appUpdater.cleanOldUpdates()
  return appUpdater.downloadUpdate({
    url: opts.url,
    filename: opts.filename,
    sizeBytes: opts.size_bytes || 0,
    sha256: opts.sha256 || '',
    onProgress: (progress) => {
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('software-update-progress', progress)
      }
    },
  })
})

ipcMain.handle('install-software-update', () => {
  return appUpdater.installAndRestart()
})

ipcMain.handle('cancel-software-update', () => {
  appUpdater.cancelDownload()
  return { ok: true }
})

ipcMain.handle('get-update-status', () => {
  return appUpdater.getStatus()
})

// ComfyUI IPC
ipcMain.handle('get-comfyui-status', () => comfyui.getStatus())
ipcMain.handle('get-comfyui-url', () => comfyui.getBaseUrl())
ipcMain.handle('restart-comfyui', async () => {
  comfyui.stop()
  await new Promise((r) => setTimeout(r, 1000))
  comfyui.start()
  return { ok: true }
})

// ComfyUI Bundle 管理 IPC
ipcMain.handle('get-comfyui-bundle-info', () => {
  return comfyBundle.readBundleJson()
})

ipcMain.handle('install-comfyui-bundle', async (_, opts) => {
  try {
    const result = await comfyBundle.installBundle({
      downloadUrl: opts.download_url,
      version: opts.version,
      platform: opts.platform,
      sizeBytes: opts.size_bytes || 0,
      sha256: opts.sha256,
      onProgress: (progress) => {
        if (mainWindow && !mainWindow.isDestroyed()) {
          mainWindow.webContents.send('comfyui-bundle-progress', progress)
        }
      },
    })
    if (result.ok && !comfyui.getStatus().running) {
      comfyui.start()
    }
    return result
  } catch (e) {
    return { ok: false, error: e.message, code: 'DOWNLOAD_FAILED' }
  }
})

ipcMain.handle('uninstall-comfyui-bundle', () => {
  comfyui.stop()
  comfyBundle.uninstallBundle()
  return { ok: true }
})

// 启动自检 IPC
ipcMain.handle('run-startup-check', () => {
  return startupCheck.runAllChecks()
})

// 错误码与日志路径
ipcMain.handle('get-log-paths', () => {
  const errorCodes = require('./error-codes')
  return errorCodes.getLogPaths()
})

ipcMain.handle('import-local-pack', async () => {
  const { dialog } = require('electron')
  try {
    const result = await dialog.showOpenDialog(mainWindow, {
      title: '选择扩展包文件',
      filters: [{ name: '扩展包', extensions: ['zip'] }],
      properties: ['openFile'],
    })
    if (result.canceled || !result.filePaths.length) {
      return { ok: false, error: 'cancelled' }
    }
    const zipPath = result.filePaths[0]
    const { net: _net } = require('electron')
    const headers = { 'Content-Type': 'application/json' }
    if (localApiKey) headers['X-Local-Api-Key'] = localApiKey
    const res = await _net.fetch('http://127.0.0.1:8765/api/v1/specialty/import-local', {
      method: 'POST',
      headers,
      body: JSON.stringify({ zip_path: zipPath }),
    })
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      return { ok: false, error: body.detail || `导入失败 (${res.status})` }
    }
    return await res.json()
  } catch (e) {
    return { ok: false, error: e.message }
  }
})

app.whenReady().then(async () => {
  const t0 = Date.now()

  if (!app.isDefaultProtocolClient('linscio')) {
    app.setAsDefaultProtocolClient('linscio')
  }
  if (typeof app.requestSingleInstanceLock === 'function' && !app.requestSingleInstanceLock()) {
    app.quit()
    return
  }
  app.on('second-instance', (_, argv) => {
    const url = argv.find((a) => a.startsWith('linscio://'))
    if (url) handleDeepLink(url)
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.focus()
    }
  })
  app.on('open-url', (e, url) => {
    e.preventDefault()
    handleDeepLink(url)
  })

  // ① localApiKey
  localApiKey = crypto.randomUUID()

  // ② Splash
  showSplash()
  updateSplashStatus('正在启动...')

  // ③ Keychain 读取（已在 startBackend 中执行，此处仅占位）
  updateSplashStatus('加载配置...')

  // ④ image-protocol
  imageProtocol.setAppDataRoot(APP_DATA_ROOT)
  imageProtocol.register()

  // ④b Mac Intel 开发中提示
  if (process.platform === 'darwin' && process.arch === 'x64') {
    console.warn('[MedComm] Mac Intel (x64) 版本处于有限支持阶段')
  }

  // ④c macOS 隔离检测（仅打包模式）
  if (process.platform === 'darwin' && app.isPackaged) {
    updateSplashStatus('检查系统安全设置...')
    const quarantineFix = require('./quarantine-fix')
    const qResult = await quarantineFix.checkAndFix(app)
    if (qResult.needed && !qResult.fixed) {
      const errorCodes = require('./error-codes')
      const cmd = quarantineFix.getManualCommand(app)
      closeSplash()
      dialog.showErrorBox(
        '需要手动解除安全限制',
        errorCodes.formatError('QUARANTINE_BLOCKED',
          `请打开"终端"应用，粘贴以下命令并回车：\n\n${cmd}\n\n然后重新打开应用。`)
      )
      app.quit()
      return
    }
  }

  // ⑤ 依赖检查（打包模式验证嵌入 Python 是否包含所需模块）
  updateSplashStatus('检查依赖...')
  const t5 = Date.now()
  const frResult = firstRun.runFirstRunInstall()
  if (frResult && !frResult.ok && !frResult.skipped) {
    const errorCodes = require('./error-codes')
    const errMsg = errorCodes.formatError(frResult.code || 'PYTHON_DEPS_MISSING', frResult.error)
    console.error('[MedComm] Dependency check failed:', frResult.error)
    closeSplash()
    dialog.showErrorBox('启动失败 - 依赖缺失', `${errMsg}\n\n请重新安装应用。`)
    app.quit()
    return
  }
  console.log('[MedComm] first-run:', Date.now() - t5, 'ms')

  // ⑥ 数据目录（需在 migration 前创建，否则首次启动时 DB 目录不存在）
  ensureDataDirs()

  // ⑦ migration
  updateSplashStatus('数据库迁移...')
  backup.setAppDataRoot(APP_DATA_ROOT)
  const t6 = Date.now()
  try {
    await migration.runMigrations(APP_DATA_ROOT)
  } catch (e) {
    const errorCodes = require('./error-codes')
    console.error('[MedComm] Migration failed:', e)
    closeSplash()
    dialog.showErrorBox('启动失败 - 数据库迁移',
      errorCodes.formatError('MIGRATION_FAILED', e.message || String(e)))
    backend.stop()
    app.quit()
    return
  }
  console.log('[MedComm] migration:', Date.now() - t6, 'ms')

  // ⑧ spawn Python
  updateSplashStatus('启动服务...')
  await startBackend()

  // ⑧b spawn ComfyUI（不阻塞主流程，后台启动）
  updateSplashStatus('启动绘图引擎...')
  if (comfyui.getComfyUIDir()) {
    comfyui.start()
  } else {
    console.log('[MedComm] ComfyUI not found, skipping')
  }

  // ⑨ 轮询 /health（超时 60 秒）
  updateSplashStatus('等待服务就绪...')
  const t9 = Date.now()
  const healthy = await pollHealth(120000)
  const healthMs = Date.now() - t9
  console.log('[MedComm] health poll:', healthMs, 'ms', healthy ? 'ok' : 'timeout')
  if (!healthy) {
    const errorCodes = require('./error-codes')
    closeSplash()
    dialog.showErrorBox('启动失败 - 服务超时',
      errorCodes.formatError('BACKEND_TIMEOUT', '后端服务在 120 秒内未就绪。\n请检查日志或重新启动应用。'))
    backend.stop()
    app.quit()
    return
  }

  // ⑨b 启动后台健康监控（只在首次就绪后开启，避免冷启动期间误重启）
  backend.startHealthCheck(() => {
    if (startBackend._restartCount >= 5) {
      console.error('[MedComm] Backend health-restart limit reached')
      return
    }
    startBackend._restartCount++
    console.warn(`[MedComm] Backend unhealthy, restarting (${startBackend._restartCount}/5)...`)
    backend.stop()
    setTimeout(() => startBackend(), 2000)
  }, () => {
    if (startBackend._restartCount > 0) startBackend._restartCount = 0
  })

  // ⑩ 主窗口
  closeSplash()
  createWindow()

  const launchUrl = process.argv.find((a) => a.startsWith('linscio://'))
  if (launchUrl) {
    setTimeout(() => handleDeepLink(launchUrl), 500)
  }

  const totalMs = Date.now() - t0
  console.log('[MedComm] startup total:', totalMs, 'ms (target: normal ≤10s, first ≤90s)')

  if (isDevAuthBypass) {
    console.log('[MedComm] dev auth bypass enabled')
  }

  // 定时备份：每小时 DB / 每日完整
  setInterval(() => backup.runScheduledBackup(), 15 * 60 * 1000)

  app.on('activate', async () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      const healthy = await backend.checkHealth()
      if (!healthy) await startBackend()
      createWindow()
    }
  })
})

app.on('before-quit', () => {
  comfyui.stop()
  backend.stop()
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})
