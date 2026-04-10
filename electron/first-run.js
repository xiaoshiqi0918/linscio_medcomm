/**
 * 首次启动检查：验证嵌入 Python 依赖是否就绪。
 * 依赖在打包前已通过 scripts/build-mac.sh 预装到 build/python；
 * 此处仅做验证，不再尝试 pip install（/Applications 只读会失败）。
 */
const { spawnSync } = require('child_process')
const path = require('path')
const fs = require('fs')
const { app } = require('electron')
const pythonResolver = require('./python-resolver')
const { resolveUnpacked } = require('./path-utils')
const { windowsPythonStderrCategory, windowsExitCodeCategory } = require('./python-env-hints')

function getWheelsDir() {
  const appDir = path.join(__dirname, '..')
  return resolveUnpacked(path.join(appDir, 'build', 'wheels'))
}

function getPlatformTag() {
  return pythonResolver.getPlatformId()
}

function runFirstRunInstall() {
  if (!app.isPackaged) {
    console.log('[MedComm] Dev mode, skipping first-run check')
    return { skipped: true, reason: 'dev' }
  }

  const pythonPath = pythonResolver.resolvePythonPath(app)
  if (!fs.existsSync(pythonPath)) {
    console.error('[MedComm] Embedded Python not found:', pythonPath)
    return { ok: false, error: 'embedded Python missing' }
  }

  // Windows: spawn 前预检关键 DLL 是否存在
  if (process.platform === 'win32') {
    const dllCheck = checkWindowsCriticalDlls()
    if (!dllCheck.ok) {
      return { ok: false, error: dllCheck.error, code: 'VCREDIST_MISSING' }
    }
  }

  const spawnTimeoutMs = process.platform === 'win32' ? 90000 : 15000
  const r = spawnSync(pythonPath, ['-c', 'import alembic, uvicorn, fastapi, sqlalchemy, greenlet, pydantic, httpx, openai'], {
    timeout: spawnTimeoutMs,
    stdio: ['ignore', 'pipe', 'pipe'],
  })

  if (r.error) {
    console.error('[MedComm] Python spawn error:', r.error)
    if (r.error.code === 'ENOENT') {
      return {
        ok: false,
        error: `Python 可执行文件无法启动: ${pythonPath}`,
        code: 'PYTHON_SPAWN_FAILED',
      }
    }
    if (r.error.code === 'ETIMEDOUT') {
      const sec = Math.round(spawnTimeoutMs / 1000)
      const msg =
        `在 ${sec} 秒内未完成启动（常见于杀毒软件首次扫描内置 Python，不一定缺少 VC++）。\n\n`
        + '请依次尝试：\n'
        + '1) 关闭应用后重新打开，多等一会儿；\n'
        + '2) 将「LinScio MedComm」安装目录（含 resources\\python）加入 Windows 安全中心 / 杀毒软件的排除项；\n'
        + '3) 若仍失败，再安装官方 VC++ 2015-2022 x64：\n'
        + '   https://aka.ms/vs/17/release/vc_redist.x64.exe'
      return { ok: false, error: msg, code: 'PYTHON_SPAWN_TIMEOUT' }
    }
    if (process.platform === 'win32') {
      const { category: eCat, extraHint: eHint } = windowsExitCodeCategory(r.status)
      if (eCat === 'vcredist' || eCat === 'vcredist_likely') {
        return { ok: false, error: `Python 启动失败: ${r.error.message}\n\n${eHint}`, code: 'VCREDIST_MISSING' }
      }
      const msg = `Python 启动失败: ${r.error.message}\n\n`
        + '可能的原因（按可能性排序）：\n'
        + '1) 安全软件（Windows Defender / 360 / 火绒等）拦截了内置 Python\n'
        + '   → 将安装目录加入杀毒软件排除项后重试\n'
        + '2) 安装文件损坏或不完整\n'
        + '   → 重新下载安装包并安装\n'
        + '3) 缺少 VC++ 运行库\n'
        + '   → 安装 https://aka.ms/vs/17/release/vc_redist.x64.exe 后重启电脑'
      return { ok: false, error: msg, code: 'PYTHON_SPAWN_FAILED' }
    }
    return { ok: false, error: `Python 启动失败: ${r.error.message}`, code: 'PYTHON_SPAWN_FAILED' }
  }

  if (r.status === 0) {
    console.log('[MedComm] Dependencies verified OK')
    return { ok: true }
  }

  const stderr = r.stderr?.toString().trim() || ''
  console.error('[MedComm] Dependency check failed:', stderr, 'exit:', r.status, 'signal:', r.signal)
  const detail = stderr || (r.signal ? `被信号终止: ${r.signal}` : `exit ${r.status}`)
  if (process.platform === 'win32') {
    const { category, extraHint } = windowsPythonStderrCategory(stderr)
    if (category === 'vcredist') {
      return { ok: false, error: `${detail}\n\n${extraHint}`, code: 'VCREDIST_MISSING' }
    }
    const { category: eCat, extraHint: eHint } = windowsExitCodeCategory(r.status)
    if (eCat === 'vcredist' || eCat === 'vcredist_likely') {
      return { ok: false, error: `${detail}\n\n${eHint}`, code: 'VCREDIST_MISSING' }
    }
  }
  return { ok: false, error: detail }
}

/**
 * Windows 关键 DLL 预检：在 spawn Python 之前主动探测。
 * 搜索顺序：Python 目录（打包时已捆绑）→ System32（系统安装的 VC++）
 * 两处都找不到才报错。
 */
function checkWindowsCriticalDlls() {
  const pythonPath = pythonResolver.resolvePythonPath(app)
  const pythonDir = path.dirname(pythonPath)
  const sys32 = process.env.SystemRoot
    ? path.join(process.env.SystemRoot, 'System32')
    : 'C:\\Windows\\System32'

  const criticalDlls = [
    { name: 'vcruntime140.dll', hint: 'VC++ 运行时核心库' },
    { name: 'vcruntime140_1.dll', hint: 'VC++ 运行时扩展库' },
    { name: 'msvcp140.dll', hint: 'VC++ 标准库' },
  ]

  const missing = criticalDlls.filter((d) => {
    const inPython = fs.existsSync(path.join(pythonDir, d.name))
    const inSystem = fs.existsSync(path.join(sys32, d.name))
    if (inPython) console.log(`[MedComm] ${d.name} found in Python directory`)
    else if (inSystem) console.log(`[MedComm] ${d.name} found in System32`)
    else console.error(`[MedComm] ${d.name} NOT FOUND anywhere`)
    return !inPython && !inSystem
  })

  if (missing.length === 0) return { ok: true }

  const { VCREDIST_REPAIR_HINT } = require('./python-env-hints')
  const list = missing.map((d) => `  - ${d.name}（${d.hint}）`).join('\n')
  return {
    ok: false,
    error:
      `系统缺少以下运行库文件：\n${list}\n\n${VCREDIST_REPAIR_HINT || '请安装 VC++ 2015-2022 x64 后重启电脑。'}`,
  }
}

module.exports = {
  runFirstRunInstall,
  getPlatformTag,
  getWheelsDir,
}
