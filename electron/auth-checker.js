/**
 * MedComm v3 授权检查
 * 6 小时缓存，延迟 10 秒异步验证，不阻塞界面
 *
 * 与 linscio-portal API 对齐：POST /api/license/status + Bearer access_token
 */
const { net } = require('electron')
const manifestCompat = require('./manifest-compat')
const manifestCache = require('./manifest-cache')

const CACHE_TTL_MS = 6 * 60 * 60 * 1000
const FETCH_TIMEOUT_MS = 5000

/** 生产环境默认 API 根（无环境变量时使用）；本地开发请设 LINSCIO_PORTAL_API_URL */
const DEFAULT_PORTAL_API_BASE = 'https://api.linscio.com.cn'
/** 生产环境默认门户根（用于激活页外链）；本地开发请设 LINSCIO_PORTAL_URL */
const DEFAULT_PORTAL_URL = 'https://portal.linscio.com.cn'

const MEDCOMM_PRODUCT_ID = 'medcomm'

function getPortalApiBase() {
  return (
    process.env.MEDCOMM_PORTAL_API_URL ||
    process.env.LINSCIO_PORTAL_API_URL ||
    DEFAULT_PORTAL_API_BASE
  )
}

/** 门户激活页完整 URL，用于 openExternal */
function getPortalActivateUrl() {
  const base =
    process.env.MEDCOMM_PORTAL_URL ||
    process.env.LINSCIO_PORTAL_URL ||
    DEFAULT_PORTAL_URL
  if (!base) return ''
  return `${base.replace(/\/$/, '')}/license/activate`
}

function isCacheValid(cache) {
  if (!cache || !cache.timestamp) return false
  return Date.now() - cache.timestamp < CACHE_TTL_MS
}

/**
 * @param {Electron.BrowserWindow} mainWindow
 * @param {object} globalLicenseCache - 共享缓存 { timestamp, data }
 * @param {string} token - access_token
 */
async function checkAuthStatus(mainWindow, globalLicenseCache, token) {
  if (!mainWindow || mainWindow.isDestroyed()) return

  if (isCacheValid(globalLicenseCache)) {
    applyLicenseStatus(mainWindow, globalLicenseCache.data)
    return
  }

  const base = getPortalApiBase()
  if (!base) {
    if (globalLicenseCache?.data) applyLicenseStatus(mainWindow, globalLicenseCache.data)
    return
  }

  try {
    const url = `${base.replace(/\/$/, '')}/api/license/status`
    const res = await net.fetch(url, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ product_id: MEDCOMM_PRODUCT_ID }),
      signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
    })
    if (!res.ok) throw new Error(`status ${res.status}`)
    const data = await res.json()
    globalLicenseCache.timestamp = Date.now()
    globalLicenseCache.data = data
    applyLicenseStatus(mainWindow, data)
  } catch (err) {
    if (globalLicenseCache?.data) {
      applyLicenseStatus(mainWindow, globalLicenseCache.data)
    }
    console.warn('[MedComm] auth check failed (offline?):', err.message)
  }
}

function applyLicenseStatus(mainWindow, status) {
  if (!mainWindow?.webContents || mainWindow.isDestroyed()) return
  if (!status?.base) return

  if (!status.base.valid) {
    mainWindow.webContents.send('license-expired', status.base)
  } else {
    mainWindow.webContents.send('license-valid', status.base)
    const days = status.base.days_remaining
    if (days != null && days <= 14) {
      mainWindow.webContents.send('license-expiry-reminder', {
        days_remaining: days,
        expires_at: status.base.expires_at,
      })
    }
  }

  if (status.specialties?.length) {
    mainWindow.webContents.send('specialty-status-update', status.specialties)
  }

  if (status.version_policies?.length) {
    mainWindow.webContents.send('version-policies', status.version_policies)
  }
}

function clearLicenseCache(globalLicenseCache) {
  if (globalLicenseCache) {
    globalLicenseCache.timestamp = 0
    globalLicenseCache.data = null
  }
}

/**
 * 检查主程序是否有新版本（调 POST /api/update/check）
 * 结果通过 IPC 'software-update-available' 推送到渲染进程
 */
async function checkSoftwareUpdate(mainWindow, token, currentVersion, localPacks) {
  if (!mainWindow || mainWindow.isDestroyed()) return
  const base = getPortalApiBase()
  if (!base || !token) return

  const specialties = {}
  const drawing_packs = {}
  for (const p of (localPacks || [])) {
    if (!p.specialty_id || !p.local_version) continue
    const isDrawing = p.category === 'drawing' || (p.specialty_id || '').startsWith('medpic-')
    if (isDrawing) {
      drawing_packs[p.specialty_id] = p.local_version
    } else {
      specialties[p.specialty_id] = p.local_version
    }
  }

  try {
    const url = `${base.replace(/\/$/, '')}/api/update/check`
    const res = await net.fetch(url, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        product_id: MEDCOMM_PRODUCT_ID,
        platform: process.platform === 'darwin'
          ? (process.arch === 'arm64' ? 'mac-arm64' : 'mac-x64')
          : 'win-x64',
        software_version: currentVersion || '0.0.0',
        specialties: Object.keys(specialties).length ? specialties : undefined,
        drawing_packs: Object.keys(drawing_packs).length ? drawing_packs : undefined,
      }),
      signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
    })
    if (!res.ok) return
    const raw = await res.json()
    const data = manifestCompat.parseUpdateResponse(raw)
    if (!data) return

    // min_client_version 强制升级检查
    if (data.min_client_version) {
      const check = manifestCompat.checkMinClientVersion(currentVersion, data.min_client_version)
      if (!check.ok) {
        mainWindow.webContents.send('software-update-available', {
          ...data,
          force_update: true,
          force_update_message: check.message,
        })
        return
      }
    }

    // 成功获取数据后持久化到本地缓存
    manifestCache.save(data)

    mainWindow.webContents.send('software-update-available', data)
  } catch (err) {
    console.warn('[MedComm] software update check failed:', err.message)

    // 网络不可用时回退到本地缓存
    const cached = manifestCache.load()
    if (cached && !cached.stale) {
      console.log('[MedComm] Using cached manifest data (offline fallback)')
      mainWindow.webContents.send('software-update-available', {
        ...cached.data,
        _offline: true,
        _cached_at: cached.cached_at,
      })
    } else {
      mainWindow.webContents.send('software-update-available', {
        base_valid: true,
        has_software_update: false,
        _offline: true,
        _error: '网络不可用，且本地缓存已过期。请检查网络连接后重试。',
      })
    }
  }
}

/**
 * 下载学科包（调 POST /api/download/specialty），返回签名 URL
 */
async function downloadSpecialty(token, specialtyId, version, fromVersion) {
  const base = getPortalApiBase()
  if (!base || !token) throw new Error('未配置 API 或未登录')

  const url = `${base.replace(/\/$/, '')}/api/download/specialty`
  const res = await net.fetch(url, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      product_id: MEDCOMM_PRODUCT_ID,
      specialty_id: specialtyId,
      version,
      from_version: fromVersion || null,
    }),
    signal: AbortSignal.timeout(15000),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `HTTP ${res.status}`)
  }
  return await res.json()
}

module.exports = {
  checkAuthStatus,
  checkSoftwareUpdate,
  downloadSpecialty,
  applyLicenseStatus,
  clearLicenseCache,
  isCacheValid,
  getPortalApiBase,
  getPortalActivateUrl,
  MEDCOMM_PRODUCT_ID,
}
