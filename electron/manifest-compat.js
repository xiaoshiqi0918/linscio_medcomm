/**
 * manifest 兼容性工具
 *
 * 原则：
 *   - 客户端只读取自己认识的字段，未知字段静默忽略
 *   - 支持 min_client_version 强制升级检查
 *   - 版本号比较使用语义化版本
 */

/**
 * 比较两个语义化版本号。
 * @returns 负数表示 a < b，0 表示相等，正数表示 a > b
 */
function compareVersions(a, b) {
  if (!a || !b) return 0
  const pa = String(a).split('.').map(Number)
  const pb = String(b).split('.').map(Number)
  const len = Math.max(pa.length, pb.length)
  for (let i = 0; i < len; i++) {
    const na = pa[i] || 0
    const nb = pb[i] || 0
    if (na !== nb) return na - nb
  }
  return 0
}

/**
 * 检查当前客户端版本是否满足最低版本要求。
 * @param {string} currentVersion - 当前客户端版本
 * @param {string} minVersion - 最低要求版本（来自 manifest 或 API 响应）
 * @returns {{ ok: boolean, message?: string }}
 */
function checkMinClientVersion(currentVersion, minVersion) {
  if (!minVersion) return { ok: true }
  if (compareVersions(currentVersion, minVersion) < 0) {
    return {
      ok: false,
      message: `当前客户端版本 v${currentVersion} 过旧，需升级至 v${minVersion} 或以上才能继续使用。`,
    }
  }
  return { ok: true }
}

/**
 * 安全解析 API 响应中的更新数据。
 * 只提取已知字段，未知字段自动忽略，不会因新字段导致解析报错。
 */
function parseUpdateResponse(data) {
  if (!data || typeof data !== 'object') return null

  return {
    base_valid: data.base_valid ?? true,
    has_software_update: data.has_software_update ?? false,
    latest_version: data.latest_version || null,
    download_url: data.download_url || null,
    update_download_url: data.update_download_url || null,
    update_filename: data.update_filename || null,
    update_size_bytes: data.update_size_bytes ?? 0,
    update_sha256: data.update_sha256 || null,
    release_notes: data.release_notes || null,
    platform_status: data.platform_status || null,
    min_client_version: data.min_client_version || null,
    specialty_updates: Array.isArray(data.specialty_updates) ? data.specialty_updates : [],
    drawing_pack_updates: Array.isArray(data.drawing_pack_updates) ? data.drawing_pack_updates : [],
    changelog: data.changelog || null,
  }
}

module.exports = {
  compareVersions,
  checkMinClientVersion,
  parseUpdateResponse,
}
