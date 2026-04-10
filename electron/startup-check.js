/**
 * 启动自检：系统环境、Python、依赖
 *
 * 返回结构化结果，由主进程决定如何展示（弹窗 / 渲染进程通知）。
 */
const os = require('os')
const fs = require('fs')
const path = require('path')
const { spawnSync } = require('child_process')
const { app } = require('electron')

const pythonResolver = require('./python-resolver')
const { windowsPythonStderrCategory, windowsExitCodeCategory } = require('./python-env-hints')

const ErrorCodes = {
  OS_UNSUPPORTED: 'OS_UNSUPPORTED',
  ARCH_MISMATCH: 'ARCH_MISMATCH',
  PYTHON_MISSING: 'PYTHON_MISSING',
  PYTHON_DEPS_MISSING: 'PYTHON_DEPS_MISSING',
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
      'Mac Intel (x64) — 部分功能处于有限支持阶段',
      '建议使用 Apple Silicon Mac 或 Windows')
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

  const pyTimeout = process.platform === 'win32' ? 60000 : 10000
  const r = spawnSync(pythonPath, ['--version'], { timeout: pyTimeout, stdio: ['ignore', 'pipe', 'pipe'] })
  if (r.error || r.status !== 0) {
    let hint
    let code = ErrorCodes.PYTHON_MISSING
    if (r.error?.code === 'ETIMEDOUT') {
      code = 'PYTHON_SPAWN_TIMEOUT'
      hint = '启动超时：常见于杀毒首次扫描内置 Python，请将应用安装目录加入排除后重试，或稍后再打开应用'
    } else if (process.platform === 'win32') {
      const stderr = r.stderr?.toString().trim() || ''
      const { category: sCat, extraHint: sHint } = windowsPythonStderrCategory(stderr)
      const { category: eCat, extraHint: eHint } = windowsExitCodeCategory(r.status)
      if (sCat === 'vcredist') {
        hint = sHint
        code = ErrorCodes.VCREDIST_MISSING
      } else if (eCat === 'vcredist' || eCat === 'vcredist_likely') {
        hint = eHint
        code = ErrorCodes.VCREDIST_MISSING
      } else {
        hint = '若持续失败，请优先将安装目录加入杀毒软件排除项再重试；仍不行可安装/修复 VC++ 2015-2022 x64'
      }
    } else {
      hint = '请重新安装应用'
    }
    return checkResult(false, code,
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
  const depTimeout = process.platform === 'win32' ? 90000 : 15000
  const r = spawnSync(pythonPath, ['-c', `import ${coreModules}`], {
    timeout: depTimeout, stdio: ['ignore', 'pipe', 'pipe'],
  })

  if (r.error || r.status !== 0) {
    const stderr = r.stderr?.toString().trim() || ''
    if (r.error?.code === 'ETIMEDOUT') {
      return checkResult(false, ErrorCodes.PYTHON_DEPS_MISSING,
        `导入依赖超时（${Math.round(depTimeout / 1000)}s）`,
        '杀毒扫描可能导致过慢，请将安装目录加入排除后重试')
    }
    if (process.platform === 'win32') {
      const { category: sCat, extraHint: sHint } = windowsPythonStderrCategory(stderr)
      if (sCat === 'vcredist') {
        return checkResult(false, ErrorCodes.VCREDIST_MISSING,
          `运行库/依赖加载失败：${stderr.slice(0, 400) || r.error?.message || `exit ${r.status}`}`,
          sHint || '请安装或修复 VC++ 2015-2022 x64')
      }
      const { category: eCat, extraHint: eHint } = windowsExitCodeCategory(r.status)
      if (eCat === 'vcredist' || eCat === 'vcredist_likely') {
        return checkResult(false, ErrorCodes.VCREDIST_MISSING,
          `运行库/依赖加载失败：exit ${r.status}`,
          eHint || '请安装或修复 VC++ 2015-2022 x64')
      }
    }
    return checkResult(false, ErrorCodes.PYTHON_DEPS_MISSING,
      `核心依赖缺失：${stderr || r.error?.message || `exit ${r.status}`}`,
      '请重新安装应用或联系支持')
  }

  return checkResult(true, null, '核心 Python 依赖就绪')
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
  ErrorCodes,
}
