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

  const r = spawnSync(pythonPath, ['-c', 'import alembic, uvicorn, fastapi, sqlalchemy, greenlet, pydantic, httpx, openai'], {
    timeout: 10000,
    stdio: ['ignore', 'pipe', 'pipe'],
  })
  if (r.status === 0) {
    console.log('[MedComm] Dependencies verified OK')
    return { ok: true }
  }

  const stderr = r.stderr?.toString().trim() || ''
  console.error('[MedComm] Dependency check failed:', stderr)
  return { ok: false, error: stderr || `exit ${r.status}` }
}

module.exports = {
  runFirstRunInstall,
  getPlatformTag,
  getWheelsDir,
}
