/**
 * Manifest 本地缓存
 *
 * 将最近一次成功的更新检查结果持久化到磁盘，
 * 网络不可用时回退到缓存版本（但标记为离线数据）。
 */
const fs = require('fs')
const path = require('path')
const { app } = require('electron')

const CACHE_FILENAME = 'manifest-cache.json'
const CACHE_MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000 // 7 天

function getCachePath() {
  return path.join(app.getPath('userData'), CACHE_FILENAME)
}

/**
 * 保存 manifest 缓存到磁盘。
 */
function save(data) {
  if (!data) return
  try {
    const payload = {
      cached_at: new Date().toISOString(),
      timestamp: Date.now(),
      data,
    }
    fs.writeFileSync(getCachePath(), JSON.stringify(payload, null, 2), 'utf-8')
  } catch (err) {
    console.warn('[ManifestCache] save failed:', err.message)
  }
}

/**
 * 读取磁盘缓存。
 * @returns {{ data: object, cached_at: string, stale: boolean } | null}
 */
function load() {
  try {
    const raw = fs.readFileSync(getCachePath(), 'utf-8')
    const cached = JSON.parse(raw)
    if (!cached?.data || !cached.timestamp) return null

    const age = Date.now() - cached.timestamp
    return {
      data: cached.data,
      cached_at: cached.cached_at,
      stale: age > CACHE_MAX_AGE_MS,
      age_ms: age,
    }
  } catch {
    return null
  }
}

/**
 * 清除缓存。
 */
function clear() {
  try { fs.unlinkSync(getCachePath()) } catch { /* noop */ }
}

module.exports = {
  save,
  load,
  clear,
}
