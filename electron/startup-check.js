/**
 * 启动自检：系统环境、Python、依赖、ComfyUI 健康检查
 *
 * 返回结构化结果，由主进程决定如何展示（弹窗 / 渲染进程通知）。
 */
const os = require('os')
const fs = require('fs')
const path = require('path')
const { spawnSync } = require('child_process')
const { app } = require('electron')

const pythonResolver = require('./python-resolver')
const comfyManager = require('./comfyui-manager')

const ErrorCodes = {
  OS_UNSUPPORTED: 'OS_UNSUPPORTED',
  ARCH_MISMATCH: 'ARCH_MISMATCH',
  PYTHON_MISSING: 'PYTHON_MISSING',
  PYTHON_DEPS_MISSING: 'PYTHON_DEPS_MISSING',
  COMFY_NOT_INSTALLED: 'COMFY_NOT_INSTALLED',
  COMFY_DEPS_MISSING: 'COMFY_DEPS_MISSING',
  VCREDIST_MISSING: 'VCREDIST_MISSING',
}

function checkResult(ok, code, message, suggestion) {
  return { ok, code: ok ? null : code, message, suggestion: ok ? null : suggestion }
}

// ---------------------------------------------------------------------------
// Individual checks
// ---------------------------------------------------------------------------

function checkOS() {
  const platform = process.platform
  const release = os.release()

  if (platform === 'darwin') {
    const parts = release.split('.').map(Number)
    const majorDarwin = parts[0] || 0
    // Darwin 21 = macOS 12 Monterey
    if (majorDarwin < 21) {
      return checkResult(false, ErrorCodes.OS_UNSUPPORTED,
        `当前 macOS 版本过低（Darwin ${release}）`,
        '请升级至 macOS 12 (Monterey) 或更高版本')
    }
  } else if (platform === 'win32') {
    const parts = release.split('.').map(Number)
    // Windows 10 = 10.0.x
    if (parts[0] < 10) {
      return checkResult(false, ErrorCodes.OS_UNSUPPORTED,
        `当前 Windows 版本过低（${release}）`,
        '请升级至 Windows 10 或更高版本')
    }
  }

  return checkResult(true, null, `系统版本正常（${platform} ${release}）`)
}

function checkArch() {
  const arch = process.arch
  const platform = process.platform
  if (platform === 'darwin' && arch !== 'arm64' && arch !== 'x64') {
    return checkResult(false, ErrorCodes.ARCH_MISMATCH,
      `不支持的架构：${arch}`,
      '请使用 Apple Silicon 或 Intel Mac')
  }
  if (platform === 'darwin' && arch === 'x64') {
    return checkResult(true, null,
      'Mac Intel (x64) — 部分功能处于有限支持阶段，ComfyUI 绘图功能暂不可用',
      '如需完整绘图功能，建议使用 Apple Silicon Mac 或 Windows')
  }
  if (platform === 'win32' && arch !== 'x64') {
    return checkResult(false, ErrorCodes.ARCH_MISMATCH,
      `不支持的架构：${arch}`,
      '请使用 64 位 Windows 系统')
  }
  return checkResult(true, null, `架构正常（${arch}）`)
}

function checkPython() {
  if (!app.isPackaged) {
    return checkResult(true, null, '开发模式，跳过 Python 检查')
  }

  const pythonPath = pythonResolver.resolvePythonPath(app)
  if (!fs.existsSync(pythonPath)) {
    return checkResult(false, ErrorCodes.PYTHON_MISSING,
      `内置 Python 未找到：${pythonPath}`,
      '请重新安装应用')
  }

  const r = spawnSync(pythonPath, ['--version'], { timeout: 10000, stdio: ['ignore', 'pipe', 'pipe'] })
  if (r.error || r.status !== 0) {
    const hint = process.platform === 'win32'
      ? '可能缺少 Visual C++ 运行时库，请安装 Microsoft Visual C++ Redistributable 后重试'
      : '请重新安装应用'
    return checkResult(false, ErrorCodes.PYTHON_MISSING,
      `Python 无法启动：${r.error?.message || `exit ${r.status}`}`,
      hint)
  }

  const version = (r.stdout?.toString() || '').trim()
  return checkResult(true, null, `Python 正常（${version}）`)
}

function checkPythonDeps() {
  if (!app.isPackaged) {
    return checkResult(true, null, '开发模式，跳过依赖检查')
  }

  const pythonPath = pythonResolver.resolvePythonPath(app)
  const coreModules = 'alembic, uvicorn, fastapi, sqlalchemy, greenlet, pydantic, httpx, openai'
  const r = spawnSync(pythonPath, ['-c', `import ${coreModules}`], {
    timeout: 15000, stdio: ['ignore', 'pipe', 'pipe'],
  })

  if (r.error || r.status !== 0) {
    const stderr = r.stderr?.toString().trim() || ''
    return checkResult(false, ErrorCodes.PYTHON_DEPS_MISSING,
      `核心依赖缺失：${stderr || r.error?.message || `exit ${r.status}`}`,
      '请重新安装应用或联系支持')
  }

  return checkResult(true, null, '核心 Python 依赖就绪')
}

function checkComfyUI() {
  const status = comfyManager.getStatus()
  if (!status.available && !status.bundleInstalled) {
    return checkResult(false, ErrorCodes.COMFY_NOT_INSTALLED,
      'ComfyUI 基础包未安装',
      '前往 MedPic 页面下载基础绘图组件包')
  }
  return checkResult(true, null,
    `ComfyUI 就绪（版本 ${status.bundleVersion || '内置'}，目录 ${status.dir || '无'}）`)
}

// ---------------------------------------------------------------------------
// Run all checks
// ---------------------------------------------------------------------------

function runAllChecks() {
  const results = {
    os: checkOS(),
    arch: checkArch(),
    python: checkPython(),
    pythonDeps: checkPythonDeps(),
    comfyui: checkComfyUI(),
  }

  const failures = Object.entries(results)
    .filter(([, r]) => !r.ok)
    .map(([key, r]) => ({ key, ...r }))

  return {
    allPassed: failures.length === 0,
    results,
    failures,
    summary: failures.length === 0
      ? '所有检查通过'
      : `${failures.length} 项检查未通过`,
  }
}

module.exports = {
  runAllChecks,
  checkOS,
  checkArch,
  checkPython,
  checkPythonDeps,
  checkComfyUI,
  ErrorCodes,
}
