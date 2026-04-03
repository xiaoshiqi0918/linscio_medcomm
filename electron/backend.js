/**
 * 后端进程管理：spawn Python、健康检查、崩溃重启
 * 打包模式使用嵌入的 python-build-standalone
 */
const { spawn } = require('child_process')
const path = require('path')
const { app, net } = require('electron')

const pythonResolver = require('./python-resolver')
const { getBackendDir } = require('./path-utils')

let backendProcess = null
let healthCheckTimer = null
let restartCount = 0
const MAX_RESTARTS = 5

const BACKEND_URL = 'http://127.0.0.1:8765'

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

function startHealthCheck(onUnhealthy, onHealthy) {
  if (healthCheckTimer) clearInterval(healthCheckTimer)
  healthCheckTimer = setInterval(async () => {
    if (!backendProcess) return
    const ok = await checkHealth()
    if (ok) {
      if (onHealthy) onHealthy()
    } else {
      if (onUnhealthy) onUnhealthy()
    }
  }, 10000)
}

async function start(envExtra = {}) {
  if (backendProcess) return
  const pythonPath = getPythonPath()
  const backendDir = getBackendDir()
  const env = { ...process.env, ...envExtra }

  console.log('[MedComm] Spawning backend:', pythonPath, 'cwd:', backendDir)
  backendProcess = spawn(
    pythonPath,
    ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8765'],
    { cwd: backendDir, env, stdio: ['ignore', 'pipe', 'pipe'] }
  )
  console.log('[MedComm] Backend PID:', backendProcess.pid)

  backendProcess.stdout?.on('data', (d) => process.stdout.write(d.toString()))
  backendProcess.stderr?.on('data', (d) => process.stderr.write(d.toString()))
  backendProcess.on('error', (err) => console.error('[MedComm] Backend spawn error:', err))
  backendProcess.on('exit', (code, signal) => {
    backendProcess = null
    if (code !== 0 && code !== null && restartCount < MAX_RESTARTS) {
      restartCount++
      console.warn(`[MedComm] Backend exited (code=${code}), restarting in 3s (${restartCount}/${MAX_RESTARTS})...`)
      setTimeout(() => start(envExtra), 3000)
    } else if (code === 0) {
      restartCount = 0
    }
  })
}

function stop() {
  if (healthCheckTimer) {
    clearInterval(healthCheckTimer)
    healthCheckTimer = null
  }
  if (backendProcess) {
    const proc = backendProcess
    backendProcess.removeAllListeners('exit')
    backendProcess = null
    if (process.platform === 'win32') {
      try {
        require('child_process').execSync(`taskkill /pid ${proc.pid} /T /F`, { stdio: 'ignore' })
      } catch { /* already exited */ }
    } else {
      proc.kill('SIGTERM')
    }
  }
}

module.exports = {
  start,
  stop,
  checkHealth,
  startHealthCheck,
  getBackendDir,
}
