/**
 * LinScio MedComm 统一错误码
 *
 * 编码规则：
 *   MC-1xxx  启动 / 环境
 *   MC-2xxx  授权 / 许可
 *   MC-3xxx  ComfyUI / 绘图
 *   MC-4xxx  网络 / 下载
 *   MC-5xxx  数据 / 存储
 *
 * 客服接到用户反馈时，可根据错误码快速定位问题。
 * 用户看到的提示中包含错误码，如：[MC-1001]
 */

const codes = {
  // --- 启动 / 环境 ---
  PYTHON_MISSING:       { code: 'MC-1001', message: '内置 Python 未找到，请重新安装应用' },
  PYTHON_SPAWN_FAILED:  { code: 'MC-1002', message: 'Python 启动失败' },
  PYTHON_DEPS_MISSING:  { code: 'MC-1003', message: '核心 Python 依赖缺失' },
  VCREDIST_MISSING:     { code: 'MC-1004', message: '缺少 Visual C++ 运行时库' },
  OS_UNSUPPORTED:       { code: 'MC-1005', message: '操作系统版本过低' },
  ARCH_MISMATCH:        { code: 'MC-1006', message: '不支持的系统架构' },
  BACKEND_TIMEOUT:      { code: 'MC-1007', message: '后端服务启动超时' },
  MIGRATION_FAILED:     { code: 'MC-1008', message: '数据库迁移失败' },
  QUARANTINE_BLOCKED:   { code: 'MC-1009', message: 'macOS 安全隔离未解除' },

  // --- 授权 / 许可 ---
  AUTH_NOT_ACTIVATED:   { code: 'MC-2001', message: '未激活，请先完成授权' },
  AUTH_EXPIRED:         { code: 'MC-2002', message: '授权已过期' },
  AUTH_SERVER_ERROR:    { code: 'MC-2003', message: '授权服务器异常' },
  AUTH_TOKEN_INVALID:   { code: 'MC-2004', message: '授权令牌无效' },

  // --- ComfyUI / 绘图 ---
  COMFY_NOT_INSTALLED:  { code: 'MC-3001', message: 'ComfyUI 基础包未安装' },
  COMFY_DEPS_MISSING:   { code: 'MC-3002', message: 'ComfyUI 依赖缺失' },
  COMFY_SPAWN_FAILED:   { code: 'MC-3003', message: 'ComfyUI 启动失败' },
  COMFY_HEALTH_FAIL:    { code: 'MC-3004', message: 'ComfyUI 服务无响应' },

  // --- 网络 / 下载 ---
  NETWORK_ERROR:        { code: 'MC-4001', message: '网络连接失败' },
  DOWNLOAD_FAILED:      { code: 'MC-4002', message: '文件下载失败' },
  CHECKSUM_MISMATCH:    { code: 'MC-4003', message: '文件完整性校验失败' },
  DISK_SPACE_LOW:       { code: 'MC-4004', message: '磁盘空间不足' },
  EXTRACT_FAILED:       { code: 'MC-4005', message: '文件解压失败' },

  // --- 数据 / 存储 ---
  DB_CORRUPT:           { code: 'MC-5001', message: '数据库文件损坏' },
  BACKUP_FAILED:        { code: 'MC-5002', message: '备份失败' },
  RESTORE_FAILED:       { code: 'MC-5003', message: '恢复失败' },
}

/**
 * 获取用户友好的错误信息，包含错误码。
 * @param {string} key - 错误码键名，如 'PYTHON_MISSING'
 * @param {string} [detail] - 附加细节
 * @returns {string}
 */
function formatError(key, detail) {
  const entry = codes[key]
  if (!entry) return detail || '未知错误'
  const base = `[${entry.code}] ${entry.message}`
  return detail ? `${base}\n${detail}` : base
}

/**
 * 获取日志文件存放路径。
 * Electron 默认日志路径：
 *   macOS: ~/Library/Logs/{appName}/
 *   Windows: %USERPROFILE%/AppData/Roaming/{appName}/logs/
 *   Linux: ~/.config/{appName}/logs/
 */
function getLogPaths() {
  const { app } = require('electron')
  const path = require('path')
  const logsPath = app.getPath('logs')
  const userDataPath = app.getPath('userData')
  return {
    logs: logsPath,
    userData: userDataPath,
    appData: path.join(userDataPath, 'data'),
    bundleData: path.join(userDataPath, 'comfyui-bundles'),
    crashDumps: app.getPath('crashDumps'),
  }
}

module.exports = {
  codes,
  formatError,
  getLogPaths,
}
