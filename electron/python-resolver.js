/**
 * Python 路径解析：打包模式使用嵌入的 python-build-standalone，否则使用系统 Python
 */
const path = require('path')
const fs = require('fs')

const PYTHON_VERSION = '3.11.11'
const RELEASE_TAG = '20241205'
const BASE_URL = 'https://github.com/astral-sh/python-build-standalone/releases/download'

function getPlatformId(targetArch) {
  const arch = targetArch || process.env.TARGET_ARCH || process.arch
  if (process.platform === 'win32') return 'win32-x64'
  if (process.platform === 'darwin') return arch === 'arm64' ? 'darwin-arm64' : 'darwin-x64'
  return arch === 'arm64' ? 'linux-arm64' : 'linux-x64'
}

/** 嵌入 Python 的下载 URL（python-build-standalone install_only） */
function getDownloadUrl() {
  const platform = getPlatformId()
  const urls = {
    'darwin-arm64': `${BASE_URL}/${RELEASE_TAG}/cpython-${PYTHON_VERSION}+${RELEASE_TAG}-aarch64-apple-darwin-install_only.tar.gz`,
    'darwin-x64': `${BASE_URL}/${RELEASE_TAG}/cpython-${PYTHON_VERSION}+${RELEASE_TAG}-x86_64-apple-darwin-install_only.tar.gz`,
    'win32-x64': `${BASE_URL}/${RELEASE_TAG}/cpython-${PYTHON_VERSION}+${RELEASE_TAG}-x86_64-pc-windows-msvc-install_only.tar.gz`,
    'linux-x64': `${BASE_URL}/${RELEASE_TAG}/cpython-${PYTHON_VERSION}+${RELEASE_TAG}-x86_64-unknown-linux-gnu-install_only.tar.gz`,
    'linux-arm64': `${BASE_URL}/${RELEASE_TAG}/cpython-${PYTHON_VERSION}+${RELEASE_TAG}-aarch64-unknown-linux-gnu-install_only.tar.gz`,
  }
  // 若新版不存在可改用 20241015 / 3.11.9 等
  return urls[platform]
}

/** 打包后嵌入 Python 所在目录（extraResources 产出） */
function getEmbeddedPythonDir(app) {
  const resourcesPath = process.resourcesPath || path.join(app.getAppPath(), '..', 'resources')
  return path.join(resourcesPath, 'python')
}

/** 嵌入 Python 可执行文件路径 */
function getEmbeddedPythonPath(app) {
  const base = getEmbeddedPythonDir(app)
  if (process.platform === 'win32') {
    return path.join(base, 'python.exe')
  }
  return path.join(base, 'bin', 'python3')
}

/** 是否应使用嵌入 Python（打包且存在） */
function shouldUseEmbeddedPython(app) {
  if (!app.isPackaged) return false
  const p = getEmbeddedPythonPath(app)
  return fs.existsSync(p)
}

/** 解析最终使用的 Python 路径 */
function resolvePythonPath(app) {
  if (process.env.PYTHON_PATH) return process.env.PYTHON_PATH
  if (app && shouldUseEmbeddedPython(app)) return getEmbeddedPythonPath(app)
  if (app && !app.isPackaged) {
    const venvDir = path.join(__dirname, '..', 'backend', '.venv')
    const unixPy = path.join(venvDir, 'bin', 'python3')
    const winPy = path.join(venvDir, 'Scripts', 'python.exe')
    if (process.platform === 'win32') {
      if (fs.existsSync(winPy)) return winPy
    } else if (fs.existsSync(unixPy)) {
      return unixPy
    }
  }
  return process.platform === 'win32' ? 'python' : 'python3'
}

/** 解析 pip 命令：使用 python -m pip */
function resolvePipCommand(app) {
  const pythonPath = resolvePythonPath(app)
  return [pythonPath, '-m', 'pip']
}

module.exports = {
  getPlatformId,
  getDownloadUrl,
  getEmbeddedPythonDir,
  getEmbeddedPythonPath,
  shouldUseEmbeddedPython,
  resolvePythonPath,
  resolvePipCommand,
  PYTHON_VERSION,
  RELEASE_TAG,
}
