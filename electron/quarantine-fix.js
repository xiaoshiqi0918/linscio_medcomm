/**
 * macOS Gatekeeper 隔离属性检测与修复
 *
 * 未签名 .app 在 macOS 上首次运行时，内部二进制（嵌入 Python 等）
 * 仍带有 com.apple.quarantine 属性，导致 spawn 失败。
 * 本模块在启动早期检测该属性，并通过 osascript 请求管理员权限自动移除。
 */
const { spawnSync } = require('child_process')
const { dialog } = require('electron')

const pythonResolver = require('./python-resolver')

/**
 * 检测指定路径是否带有 com.apple.quarantine 扩展属性。
 * @param {string} targetPath
 * @returns {boolean}
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
 * exe 路径形如 /Applications/LinScio MedComm.app/Contents/MacOS/LinScio MedComm
 */
function getAppBundlePath(app) {
  const exePath = app.getPath('exe')
  return exePath.replace(/\/Contents\/MacOS\/.*$/, '')
}

/**
 * 通过 osascript 请求管理员权限执行 xattr -cr。
 * @param {string} appBundlePath
 * @returns {{ ok: boolean, error?: string }}
 */
function removeQuarantine(appBundlePath) {
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
 * 主入口：检测隔离属性，若存在则弹窗引导修复。
 * @param {Electron.App} app
 * @returns {Promise<{ needed: boolean, fixed: boolean }>}
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

  const { response } = await dialog.showMessageBox({
    type: 'warning',
    title: '首次启动 - 安全设置',
    message: 'LinScio MedComm 是未签名应用，macOS 会阻止部分组件运行。',
    detail: '点击「立即修复」并输入您的 Mac 登录密码，即可一键解除限制。',
    buttons: ['立即修复', '稍后手动处理'],
    defaultId: 0,
    cancelId: 1,
  })

  if (response !== 0) {
    return { needed: true, fixed: false }
  }

  const result = removeQuarantine(appBundlePath)

  if (result.ok) {
    console.log('[MedComm] Quarantine attribute removed successfully')
    return { needed: true, fixed: true }
  }

  if (result.error === 'user_canceled') {
    console.log('[MedComm] User canceled quarantine fix password dialog')
  } else {
    console.error('[MedComm] Failed to remove quarantine:', result.error)
  }

  return { needed: true, fixed: false }
}

/**
 * 生成用于手动修复的终端命令文本。
 * @param {Electron.App} app
 * @returns {string}
 */
function getManualCommand(app) {
  const bundlePath = getAppBundlePath(app)
  return `xattr -cr "${bundlePath}"`
}

module.exports = {
  hasQuarantine,
  removeQuarantine,
  checkAndFix,
  getManualCommand,
  getAppBundlePath,
}
