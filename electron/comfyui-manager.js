/**
 * ComfyUI 进程管理：spawn / stop / health check / 崩溃重启
 *
 * 分包模式（v0.2+）：
 *   打包后 ComfyUI 不再随 extraResources 分发，而是由用户按需下载到
 *   {userData}/comfyui-bundles/v{version}/ 目录。本模块通过 bundle.json
 *   定位当前激活的 ComfyUI 版本目录。
 *
 * 开发模式仍兼容 build/comfyui 或环境变量 COMFYUI_DIR。
 */
const { spawn } = require('child_process')
const path = require('path')
const fs = require('fs')
const { app, net } = require('electron')

const pythonResolver = require('./python-resolver')

let comfyProcess = null
let healthCheckTimer = null
let restartCount = 0
const MAX_RESTARTS = 3

const DEFAULT_PORT = 8188
let activePort = DEFAULT_PORT

// ---------------------------------------------------------------------------
// Bundle 目录解析
// ---------------------------------------------------------------------------

function getBundlesRoot() {
  return path.join(app.getPath('userData'), 'comfyui-bundles')
}

function readBundleJson() {
  const bundlePath = path.join(getBundlesRoot(), 'bundle.json')
  try {
    if (fs.existsSync(bundlePath)) {
      return JSON.parse(fs.readFileSync(bundlePath, 'utf-8'))
    }
  } catch { /* corrupt or missing */ }
  return null
}

function getBundleDir() {
  const bundle = readBundleJson()
  if (!bundle || !bundle.version) return null
  const dir = path.join(getBundlesRoot(), `v${bundle.version}`)
  if (fs.existsSync(path.join(dir, 'main.py'))) return dir
  return null
}

function getComfyUIDir() {
  if (process.env.COMFYUI_DIR) {
    return process.env.COMFYUI_DIR
  }

  // 打包模式：优先读 userData 下的 bundle
  if (app && app.isPackaged) {
    const bundleDir = getBundleDir()
    if (bundleDir) return bundleDir

    // 兼容旧版：若 resources/comfyui 仍存在（用户未迁移）
    const resourcesPath = process.resourcesPath || path.join(app.getAppPath(), '..', 'resources')
    const legacyDir = path.join(resourcesPath, 'comfyui')
    if (fs.existsSync(path.join(legacyDir, 'main.py'))) return legacyDir

    return null
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

function isBundleInstalled() {
  return getBundleDir() !== null
}

function getInstalledBundleVersion() {
  const bundle = readBundleJson()
  return bundle?.version || null
}

// ---------------------------------------------------------------------------
// Python 路径
// ---------------------------------------------------------------------------

function getComfyPythonPath() {
  if (process.env.COMFYUI_PYTHON_PATH) {
    return process.env.COMFYUI_PYTHON_PATH
  }
  const comfyDir = getComfyUIDir()
  if (!comfyDir) return null

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

  if (app && app.isPackaged) {
    return pythonResolver.resolvePythonPath(app)
  }

  return process.platform === 'win32' ? 'python' : 'python3'
}

// ---------------------------------------------------------------------------
// 网络 / 健康检查
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// 启动 / 停止
// ---------------------------------------------------------------------------

function buildLaunchArgs() {
  const args = [
    'main.py',
    '--listen', '127.0.0.1',
    '--port', String(activePort),
    '--enable-cors-header', '*',
  ]

  if (process.platform === 'darwin') {
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
    process.stdout.write(`[ComfyUI] ${d.toString()}`)
  })
  comfyProcess.stderr?.on('data', (d) => {
    process.stderr.write(`[ComfyUI] ${d.toString()}`)
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
  const comfyDir = getComfyUIDir()
  return {
    running: comfyProcess !== null,
    port: activePort,
    pid: comfyProcess?.pid ?? null,
    dir: comfyDir,
    available: comfyDir !== null,
    bundleInstalled: isBundleInstalled(),
    bundleVersion: getInstalledBundleVersion(),
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
  getBundlesRoot,
  readBundleJson,
  isBundleInstalled,
  getInstalledBundleVersion,
  setPort,
}
