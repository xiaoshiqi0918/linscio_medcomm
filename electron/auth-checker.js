/**
 * MedComm v3 授权检查（SaaS）
 * 6 小时缓存；使用权状态走 linscio.com POST /api/v1/client/license-status
 * 主程序更新：POST /api/v1/download/update-check（Bearer = SaaS JWT）
 */
const { net } = require('electron')
const manifestCompat = require('./manifest-compat')
const manifestCache = require('./manifest-cache')

const CACHE_TTL_MS = 6 * 60 * 60 * 1000
const FETCH_TIMEOUT_MS = 5000

/** 门户 API：仅当仍配置 LINSCIO_PORTAL_API_URL 时使用（激活码交换等遗留能力） */
const DEFAULT_PORTAL_API_BASE = ''
/** 激活说明外链默认落到站点设置页（可在部署时覆盖 LINSCIO_PORTAL_URL） */
const DEFAULT_PORTAL_SITE_BASE = 'https://www.linscio.com'

/** SaaS 站点根：使用权校验、软件更新（Bearer = saas_access_token） */
const DEFAULT_SAAS_CLIENT_API_BASE = 'https://www.linscio.com'

const MEDCOMM_PRODUCT_ID = 'medcomm'

function getSaaSClientApiBase() {
  const v =
    process.env.LINSCIO_SAAS_CLIENT_API_URL ||
    process.env.MEDCOMM_CLIENT_API_URL ||
    DEFAULT_SAAS_CLIENT_API_BASE
  return v.replace(/\/$/, '')
}

function getPortalApiBase() {
  return (
    process.env.MEDCOMM_PORTAL_API_URL ||
    process.env.LINSCIO_PORTAL_API_URL ||
    DEFAULT_PORTAL_API_BASE
  )
}

/** 激活 / 购买授权说明页（门户已下线时指向 SaaS 站点） */
function getPortalActivateUrl() {
  const base =
    process.env.MEDCOMM_PORTAL_URL ||
    process.env.LINSCIO_PORTAL_URL ||
    process.env.LINSCIO_SITE_URL ||
    DEFAULT_PORTAL_SITE_BASE
  if (!base) return ''
  return `${base.replace(/\/$/, '')}/settings`
}

function isCacheValid(cache) {
  if (!cache || !cache.timestamp) return false
  return Date.now() - cache.timestamp < CACHE_TTL_MS
}

/**
 * @param {Electron.BrowserWindow} mainWindow
 * @param {object} globalLicenseCache - 共享缓存 { timestamp, data }
 * @param {string} token - SaaS JWT（access_token from linscio.com）
 */
async function checkAuthStatus(mainWindow, globalLicenseCache, token) {
  if (!mainWindow || mainWindow.isDestroyed()) return

  if (!token) {
    if (globalLicenseCache?.data) applyLicenseStatus(mainWindow, globalLicenseCache.data)
    return
  }

  if (isCacheValid(globalLicenseCache)) {
    applyLicenseStatus(mainWindow, globalLicenseCache.data)
    return
  }

  const base = getSaaSClientApiBase()
  if (!base) {
    if (globalLicenseCache?.data) applyLicenseStatus(mainWindow, globalLicenseCache.data)
    return
  }

  try {
    const url = `${base}/api/v1/client/license-status`
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
    console.warn('[MedComm] SaaS license check failed (offline?):', err.message)
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

async function checkSoftwareUpdate(mainWindow, token, currentVersion, _localPacks) {
  if (!mainWindow || mainWindow.isDestroyed()) return
  const base = getSaaSClientApiBase()
  if (!base || !token) return

  try {
    const url = `${base}/api/v1/download/update-check`
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
      }),
      signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
    })
    if (!res.ok) return
    const raw = await res.json()
    const data = manifestCompat.parseUpdateResponse(raw)
    if (!data) return

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

    manifestCache.save(data)

    mainWindow.webContents.send('software-update-available', data)
  } catch (err) {
    console.warn('[MedComm] software update check failed:', err.message)

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

module.exports = {
  checkAuthStatus,
  checkSoftwareUpdate,
  applyLicenseStatus,
  clearLicenseCache,
  isCacheValid,
  getPortalApiBase,
  getSaaSClientApiBase,
  getPortalActivateUrl,
  MEDCOMM_PRODUCT_ID,
}
