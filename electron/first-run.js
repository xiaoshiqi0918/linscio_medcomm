/**
 * 平台专属 Wheels 离线安装（幂等）
 * CI 构建时需预先执行：
 *   pip download -r requirements.txt --platform <tag> --python-version 3.11
 *     --only-binary=:all: -d build/wheels/<platform>/
 */
const { spawnSync } = require('child_process')
const path = require('path')
const fs = require('fs')
const { app } = require('electron')
const pythonResolver = require('./python-resolver')

function getWheelsDir() {
  const appDir = path.join(__dirname, '..')
  return path.join(appDir, 'build', 'wheels')
}

function getPlatformTag() {
  if (process.platform === 'win32') return 'windows-x64'
  if (process.platform === 'darwin') {
    return process.arch === 'arm64' ? 'macos-arm64' : 'macos-x64'
  }
  return process.arch === 'arm64' ? 'linux-arm64' : 'linux-x64'
}

/**
 * 幂等执行：若 wheels 目录存在则 pip install --no-index
 * 若不存在则跳过（开发环境通常已有 venv）
 */
function runFirstRunInstall() {
  const wheelsDir = getWheelsDir()
  const platform = getPlatformTag()
  const platformWheels = path.join(wheelsDir, platform)

  if (!fs.existsSync(platformWheels)) {
    console.log('[MedComm] No wheels found for', platform, ', skipping first-run install')
    return { skipped: true, reason: 'no wheels' }
  }

  const backendDir = path.join(__dirname, '..', 'backend')
  const requirementsPath = path.join(backendDir, 'requirements.txt')
  if (!fs.existsSync(requirementsPath)) {
    console.log('[MedComm] No requirements.txt, skipping')
    return { skipped: true, reason: 'no requirements' }
  }

  try {
    const pipCmd = pythonResolver.resolvePipCommand(app)
    const r = spawnSync(pipCmd[0], [
      pipCmd[1], pipCmd[2], 'install', '--no-index', `--find-links=${platformWheels}`, '-r', requirementsPath,
    ], { cwd: backendDir, stdio: 'inherit', env: { ...process.env } })
    if (r.status !== 0) throw new Error(`pip exited ${r.status}`)
    console.log('[MedComm] First-run wheels install completed')
    return { ok: true }
  } catch (e) {
    console.warn('[MedComm] First-run wheels install failed:', e.message)
    return { ok: false, error: e.message }
  }
}

module.exports = {
  runFirstRunInstall,
  getPlatformTag,
  getWheelsDir,
}
