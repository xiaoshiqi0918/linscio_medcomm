/**
 * macOS Gatekeeper 隔离属性检测与修复
 *
 * 未签名 .app 在 macOS 上首次运行时，内部二进制（嵌入 Python 等）
 * 仍带有 com.apple.quarantine 属性，导致 spawn 失败。
 *
 * 修复策略（三级递进，绝大多数情况在第 1 级静默完成）：
 *   1. 直接 xattr -cr（用户自己拖拽安装的 app，无需 sudo）
 *   2. osascript 提权 xattr -cr（罕见：app 被其他用户安装到 /Applications）
 *   3. 提供手动命令（兜底）
 */
const { spawnSync } = require('child_process')
const { dialog } = require('electron')

const pythonResolver = require('./python-resolver')

/**
 * 检测指定路径是否带有 com.apple.quarantine 扩展属性。
 */
function hasQuarantine(targetPath) {
  if (process.platform !== 'darwin') return false
  try {
    const r = spawnSync('xattr', ['-p', 'com.apple.quarantine', targetPath], {
      timeout: 5000,
      stdio: ['ignore', 'pipe', 'pipe'],
    })
    return r.status === 0
  } catch {
    return false
  }
}

/**
 * 获取 .app bundle 的根路径。
 */
function getAppBundlePath(app) {
  const exePath = app.getPath('exe')
  return exePath.replace(/\/Contents\/MacOS\/.*$/, '')
}

/**
 * 第 1 级：直接 xattr -cr（不需要密码）。
 * 用户自己拖拽安装时文件归当前用户所有，这一步通常就能成功。
 */
function removeQuarantineDirect(appBundlePath) {
  try {
    const r = spawnSync('xattr', ['-cr', appBundlePath], {
      timeout: 30000,
      stdio: ['ignore', 'pipe', 'pipe'],
    })
    if (r.status === 0) return { ok: true }
    const stderr = r.stderr?.toString().trim() || ''
    return { ok: false, error: stderr || `exit ${r.status}` }
  } catch (err) {
    return { ok: false, error: err.message }
  }
}

/**
 * 第 2 级：通过 osascript 请求管理员权限执行 xattr -cr。
 * 仅在第 1 级失败时使用（app 位于非用户所有的目录）。
 */
function removeQuarantineAdmin(appBundlePath) {
  const escaped = appBundlePath.replace(/'/g, "'\\''")
  const script = `do shell script "xattr -cr '${escaped}'" with administrator privileges`

  try {
    const r = spawnSync('osascript', ['-e', script], {
      timeout: 60000,
      stdio: ['ignore', 'pipe', 'pipe'],
    })
    if (r.status === 0) {
      return { ok: true }
    }
    const stderr = r.stderr?.toString().trim() || ''
    if (stderr.includes('User canceled') || stderr.includes('user canceled') || stderr.includes('-128')) {
      return { ok: false, error: 'user_canceled' }
    }
    return { ok: false, error: stderr || `exit ${r.status}` }
  } catch (err) {
    return { ok: false, error: err.message }
  }
}

/**
 * 主入口：检测隔离属性，自动修复。
 *
 * 绝大多数情况下，第 1 级（直接 xattr -cr）即可静默完成，用户无感知。
 */
async function checkAndFix(app) {
  if (process.platform !== 'darwin' || !app.isPackaged) {
    return { needed: false, fixed: false }
  }

  const pythonPath = pythonResolver.getEmbeddedPythonPath(app)
  if (!hasQuarantine(pythonPath)) {
    return { needed: false, fixed: false }
  }

  console.log('[MedComm] Quarantine attribute detected on embedded Python')
  const appBundlePath = getAppBundlePath(app)

  // 第 1 级：静默去除（不弹窗、不需要密码）
  const directResult = removeQuarantineDirect(appBundlePath)
  if (directResult.ok) {
    console.log('[MedComm] Quarantine removed (direct, no password needed)')
    return { needed: true, fixed: true }
  }
  console.warn('[MedComm] Direct xattr -cr failed:', directResult.error, '— escalating to admin')

  // 第 2 级：需要管理员密码（极少触发，仅当 app 非用户所有时）
  const { response } = await dialog.showMessageBox({
    type: 'warning',
    title: '首次启动 - 安全设置',
    message: '需要管理员权限来解除 macOS 安全限制。',
    detail: '点击「授权」并输入 Mac 登录密码，即可完成（仅需一次）。',
    buttons: ['授权', '稍后手动处理'],
    defaultId: 0,
    cancelId: 1,
  })

  if (response !== 0) {
    return { needed: true, fixed: false }
  }

  const adminResult = removeQuarantineAdmin(appBundlePath)
  if (adminResult.ok) {
    console.log('[MedComm] Quarantine removed (admin privilege)')
    return { needed: true, fixed: true }
  }

  if (adminResult.error === 'user_canceled') {
    console.log('[MedComm] User canceled admin password dialog')
  } else {
    console.error('[MedComm] Admin xattr -cr also failed:', adminResult.error)
  }

  return { needed: true, fixed: false }
}

/**
 * 生成用于手动修复的终端命令文本（第 3 级兜底）。
 */
function getManualCommand(app) {
  const bundlePath = getAppBundlePath(app)
  return `xattr -cr "${bundlePath}"`
}

module.exports = {
  hasQuarantine,
  removeQuarantineDirect,
  removeQuarantineAdmin,
  checkAndFix,
  getManualCommand,
  getAppBundlePath,
}
