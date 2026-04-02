/**
 * 后端进程管理：spawn Python、健康检查、崩溃重启
 * 打包模式使用嵌入的 python-build-standalone
 */
const { spawn } = require('child_process')
const path = require('path')
const { app, net } = require('electron')

const pythonResolver = require('./python-resolver')

let backendProcess = null
let healthCheckTimer = null
let restartCount = 0
const MAX_RESTARTS = 5

const BACKEND_URL = 'http://127.0.0.1:8765'

function getBackendDir() {
  return path.join(__dirname, '..', 'backend')
}

function getPythonPath() {
  return pythonResolver.resolvePythonPath(app)
}

async function checkHealth() {
  try {
    const res = await net.fetch(`${BACKEND_URL}/health`, { signal: AbortSignal.timeout(3000) })
    return res.ok
  } catch {
    return false
  }
}

function startHealthCheck(onUnhealthy) {
  if (healthCheckTimer) clearInterval(healthCheckTimer)
  healthCheckTimer = setInterval(async () => {
    if (!backendProcess) return
    const ok = await checkHealth()
    if (!ok && onUnhealthy) onUnhealthy()
  }, 10000)
}

async function start(envExtra = {}) {
  if (backendProcess) return
  const pythonPath = getPythonPath()
  const backendDir = getBackendDir()
  const env = { ...process.env, ...envExtra }

  backendProcess = spawn(
    pythonPath,
    ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8765'],
    { cwd: backendDir, env, stdio: ['ignore', 'pipe', 'pipe'] }
  )

  backendProcess.stdout?.on('data', (d) => process.stdout.write(d.toString()))
  backendProcess.stderr?.on('data', (d) => process.stderr.write(d.toString()))
  backendProcess.on('error', (err) => console.error('[MedComm] Backend spawn error:', err))
  backendProcess.on('exit', (code, signal) => {
    backendProcess = null
    if (code !== 0 && code !== null && restartCount < MAX_RESTARTS) {
      restartCount++
      console.warn(`[MedComm] Backend exited (code=${code}), restarting in 3s...`)
      setTimeout(() => start(envExtra), 3000)
    }
  })
}

function stop() {
  if (healthCheckTimer) {
    clearInterval(healthCheckTimer)
    healthCheckTimer = null
  }
  if (backendProcess) {
    backendProcess.removeAllListeners('exit')
    backendProcess.kill('SIGTERM')
    backendProcess = null
  }
}

module.exports = {
  start,
  stop,
  checkHealth,
  startHealthCheck,
  getBackendDir,
}
