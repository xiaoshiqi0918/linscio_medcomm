#!/usr/bin/env node
/**
 * 下载平台专属 wheels 到 build/wheels/<platform>/
 * 用于首次安装或 CI 预构建
 * 用法: node scripts/build-wheels.js [platform]
 *   platform: darwin-arm64 | darwin-x64 | win32-x64 | linux-x64（与 CI / first-run 一致）
 *   兼容旧名: macos-arm64 → darwin-arm64, macos-x64 → darwin-x64
 */
const { spawnSync } = require('child_process')
const path = require('path')
const fs = require('fs')

const PLATFORM_MAP = {
  'darwin-arm64': { tag: 'macosx_11_0_arm64', arch: 'arm64' },
  'darwin-x64': { tag: 'macosx_10_9_x86_64', arch: 'x64' },
  'macos-arm64': { tag: 'macosx_11_0_arm64', arch: 'arm64' },
  'macos-x64': { tag: 'macosx_10_9_x86_64', arch: 'x64' },
  'win32-x64': { tag: 'win_amd64', arch: 'x64' },
  'linux-x64': { tag: 'manylinux_2_17_x86_64', arch: 'x64' },
  'linux-arm64': { tag: 'manylinux_2_17_aarch64', arch: 'arm64' },
}

function getPlatformId() {
  if (process.platform === 'win32') return 'win32-x64'
  if (process.platform === 'darwin') return process.arch === 'arm64' ? 'darwin-arm64' : 'darwin-x64'
  return process.arch === 'arm64' ? 'linux-arm64' : 'linux-x64'
}

function main() {
  const platform = process.argv[2] || getPlatformId()
  const meta = PLATFORM_MAP[platform]
  if (!meta) {
    console.error('[build-wheels] Unknown platform:', platform)
    console.error('  Supported:', Object.keys(PLATFORM_MAP).join(', '))
    process.exit(1)
  }

  const root = path.join(__dirname, '..')
  const wheelsDir = path.join(root, 'build', 'wheels', platform)
  const requirementsPath = path.join(root, 'backend', 'requirements.txt')

  if (!fs.existsSync(requirementsPath)) {
    console.error('[build-wheels] requirements.txt not found')
    process.exit(1)
  }

  fs.mkdirSync(wheelsDir, { recursive: true })

  const pip = process.env.PIP_PATH || 'pip'
  const SDIST_ONLY = ['jieba', 'bibtexparser']

  const lines = fs.readFileSync(requirementsPath, 'utf-8').split('\n')
  const binaryLines = lines.filter((l) => !SDIST_ONLY.some((s) => l.trim().startsWith(s)))
  const sdistLines = lines.filter((l) => SDIST_ONLY.some((s) => l.trim().startsWith(s)))

  const tmpReq = path.join(root, 'build', '.tmp-req-binary.txt')
  fs.writeFileSync(tmpReq, binaryLines.join('\n'))

  console.log('[build-wheels] Phase 1: binary wheels (platform=%s)', meta.tag)
  const r1 = spawnSync(pip, [
    'download', '-r', tmpReq,
    '--platform', meta.tag,
    '--python-version', '311',
    '--only-binary', ':all:',
    '--dest', wheelsDir,
  ], { stdio: 'inherit', cwd: path.join(root, 'backend') })
  fs.unlinkSync(tmpReq)

  if (r1.status !== 0) {
    console.error('[build-wheels] Phase 1 failed, status', r1.status)
    process.exit(1)
  }

  if (sdistLines.length > 0) {
    console.log('[build-wheels] Phase 2: build sdist-only packages into wheels')
    const sdistArgs = sdistLines.filter((l) => l.trim()).map((l) => l.trim())
    const r2 = spawnSync(pip, ['wheel', ...sdistArgs, '-w', wheelsDir], {
      stdio: 'inherit', cwd: path.join(root, 'backend'),
    })
    if (r2.status !== 0) {
      console.error('[build-wheels] Phase 2 failed, status', r2.status)
      process.exit(1)
    }
    // remove leftover sdist archives
    for (const f of fs.readdirSync(wheelsDir)) {
      if (f.endsWith('.tar.gz') || f.endsWith('.zip')) {
        fs.unlinkSync(path.join(wheelsDir, f))
      }
    }
  }

  console.log('[build-wheels] Done:', wheelsDir)
}

main()
