/**
 * 迁移前备份 + 失败回滚
 * 调用 Python run_migrations.py
 */
const { spawn } = require('child_process')
const path = require('path')
const { app } = require('electron')
const pythonResolver = require('./python-resolver')
const { getBackendDir } = require('./path-utils')

/**
 * @param {string} appDataRoot 与 main 中 APP_DATA_ROOT 一致（userData/data），供 settings.db_path 解析
 */
function runMigrations(appDataRoot) {
  const root = appDataRoot || process.env.LINSCIO_APP_DATA || path.join(app.getPath('userData'), 'data')
  return new Promise((resolve, reject) => {
    const pythonPath = pythonResolver.resolvePythonPath(app)
    const scriptPath = path.join(getBackendDir(), 'scripts', 'run_migrations.py')
    const proc = spawn(pythonPath, [scriptPath], {
      cwd: getBackendDir(),
      stdio: ['ignore', 'pipe', 'pipe'],
      env: { ...process.env, LINSCIO_APP_DATA: root },
    })
    let out = ''
    let err = ''
    proc.stdout?.on('data', (d) => { out += d.toString() })
    proc.stderr?.on('data', (d) => { err += d.toString() })
    proc.on('close', (code) => {
      if (code === 0) resolve({ ok: true, out })
      else reject(new Error(err || out || `exit ${code}`))
    })
    proc.on('error', reject)
  })
}

module.exports = {
  runMigrations,
  getBackendDir,
}
