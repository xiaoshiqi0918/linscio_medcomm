/**
 * ComfyUI 进程管理：spawn / stop / health check / 崩溃重启
 * 打包模式从 resources/comfyui 启动；开发模式使用 COMFYUI_DIR 环境变量
 */
const { spawn } = require('child_process')
const path = require('path')
const fs = require('fs')
const { app, net } = require('electron')

const pythonResolver = require('./python-resolver')
const { resolveUnpacked } = require('./path-utils')

let comfyProcess = null
let healthCheckTimer = null
let restartCount = 0
const MAX_RESTARTS = 3

const DEFAULT_PORT = 8188
let activePort = DEFAULT_PORT

function getComfyUIDir() {
  if (process.env.COMFYUI_DIR) {
    return process.env.COMFYUI_DIR
  }
  if (app && app.isPackaged) {
    const resourcesPath = process.resourcesPath || path.join(app.getAppPath(), '..', 'resources')
    return path.join(resourcesPath, 'comfyui')
  }
  // 开发模式：build 目录、项目兄弟目录、用户 HOME
  const devPaths = [
    path.join(__dirname, '..', 'build', 'comfyui'),
    path.join(__dirname, '..', '..', 'ComfyUI'),
    path.join(require('os').homedir(), 'ComfyUI'),
  ]
  for (const p of devPaths) {
    if (fs.existsSync(path.join(p, 'main.py'))) return p
  }
  return null
}

function getComfyPythonPath() {
  if (process.env.COMFYUI_PYTHON_PATH) {
    return process.env.COMFYUI_PYTHON_PATH
  }
  const comfyDir = getComfyUIDir()
  if (!comfyDir) return null

  // 检查 ComfyUI 目录下是否自带 venv
  const venvPaths = [
    path.join(comfyDir, 'venv', 'bin', 'python3'),
    path.join(comfyDir, 'venv', 'Scripts', 'python.exe'),
    path.join(comfyDir, '.venv', 'bin', 'python3'),
    path.join(comfyDir, '.venv', 'Scripts', 'python.exe'),
    path.join(comfyDir, 'python_embeded', 'python.exe'),
  ]
  for (const p of venvPaths) {
    if (fs.existsSync(p)) return p
  }

  // 打包模式复用嵌入 Python（需要确保 PyTorch 已预装）
  if (app && app.isPackaged) {
    return pythonResolver.resolvePythonPath(app)
  }

  return process.platform === 'win32' ? 'python' : 'python3'
}

function getBaseUrl() {
  return `http://127.0.0.1:${activePort}`
}

async function checkHealth() {
  try {
    const res = await net.fetch(`${getBaseUrl()}/system_stats`, {
      signal: AbortSignal.timeout(3000),
    })
    return res.ok
  } catch {
    return false
  }
}

function buildLaunchArgs() {
  const args = [
    'main.py',
    '--listen', '127.0.0.1',
    '--port', String(activePort),
    '--enable-cors-header', '*',
  ]

  if (process.platform === 'darwin') {
    // MPS backend: force ALL computations to fp32 to prevent NaN accumulation
    // that causes black images after the first generation on Apple Silicon.
    // SD1.5 in fp32 uses ~4GB — well within 16GB unified memory.
    args.push('--force-fp32')
  }

  if (process.env.COMFYUI_EXTRA_ARGS) {
    args.push(...process.env.COMFYUI_EXTRA_ARGS.split(/\s+/).filter(Boolean))
  }

  return args
}

async function start(envExtra = {}) {
  if (comfyProcess) return

  const comfyDir = getComfyUIDir()
  if (!comfyDir || !fs.existsSync(path.join(comfyDir, 'main.py'))) {
    console.warn('[ComfyUI] ComfyUI directory not found, skipping:', comfyDir)
    return
  }

  const pythonPath = getComfyPythonPath()
  if (!pythonPath) {
    console.warn('[ComfyUI] Python path not resolved, skipping')
    return
  }

  const mpsEnv = process.platform === 'darwin' ? {
    PYTORCH_MPS_HIGH_WATERMARK_RATIO: '0.0',
    PYTORCH_ENABLE_MPS_FALLBACK: '1',
  } : {}
  const env = { ...process.env, ...mpsEnv, ...envExtra }
  const args = buildLaunchArgs()

  console.log('[ComfyUI] Spawning:', pythonPath, args.join(' '), 'cwd:', comfyDir)
  comfyProcess = spawn(pythonPath, args, {
    cwd: comfyDir,
    env,
    stdio: ['ignore', 'pipe', 'pipe'],
  })
  console.log('[ComfyUI] PID:', comfyProcess.pid)

  comfyProcess.stdout?.on('data', (d) => {
    const s = d.toString()
    process.stdout.write(`[ComfyUI] ${s}`)
  })
  comfyProcess.stderr?.on('data', (d) => {
    const s = d.toString()
    process.stderr.write(`[ComfyUI] ${s}`)
  })
  comfyProcess.on('error', (err) => {
    console.error('[ComfyUI] Spawn error:', err)
  })
  comfyProcess.on('exit', (code, signal) => {
    console.warn(`[ComfyUI] Exited code=${code} signal=${signal}`)
    comfyProcess = null
    if (code !== 0 && code !== null && restartCount < MAX_RESTARTS) {
      restartCount++
      console.warn(`[ComfyUI] Restarting in 3s (${restartCount}/${MAX_RESTARTS})...`)
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
  if (comfyProcess) {
    const proc = comfyProcess
    comfyProcess.removeAllListeners('exit')
    comfyProcess = null
    if (process.platform === 'win32') {
      try {
        require('child_process').execSync(`taskkill /pid ${proc.pid} /T /F`, { stdio: 'ignore' })
      } catch { /* already exited */ }
    } else {
      proc.kill('SIGTERM')
    }
  }
}

function startHealthCheck(onUnhealthy, onHealthy) {
  if (healthCheckTimer) clearInterval(healthCheckTimer)
  healthCheckTimer = setInterval(async () => {
    if (!comfyProcess) return
    const ok = await checkHealth()
    if (ok) {
      if (onHealthy) onHealthy()
    } else {
      if (onUnhealthy) onUnhealthy()
    }
  }, 15000)
}

function getStatus() {
  return {
    running: comfyProcess !== null,
    port: activePort,
    pid: comfyProcess?.pid ?? null,
    dir: getComfyUIDir(),
    available: getComfyUIDir() !== null,
  }
}

function setPort(port) {
  activePort = port || DEFAULT_PORT
}

module.exports = {
  start,
  stop,
  checkHealth,
  startHealthCheck,
  getStatus,
  getBaseUrl,
  getComfyUIDir,
  setPort,
}
