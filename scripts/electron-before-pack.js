/**
 * electron-builder beforePack: avoid silent incomplete ComfyUI bundles.
 *
 * - Local: require main.py + SD1.5 checkpoint (min size) unless SKIP_COMFYUI_PACK=1
 * - GitHub Actions: warn only if something is missing (workflow may skip large downloads)
 */
const fs = require('fs')
const path = require('path')

const SD15_MIN_BYTES = 200 * 1024 * 1024

function sd15Ok(root) {
  const p = path.join(
    root,
    'build',
    'comfyui',
    'models',
    'checkpoints',
    'v1-5-pruned-emaonly.safetensors',
  )
  if (!fs.existsSync(p)) return { ok: false, p, reason: 'missing' }
  try {
    const sz = fs.statSync(p).size
    if (sz < SD15_MIN_BYTES) return { ok: false, p, reason: `too small (${sz} bytes)` }
    return { ok: true, p }
  } catch {
    return { ok: false, p, reason: 'stat failed' }
  }
}

module.exports = async function beforePack() {
  if (process.env.SKIP_COMFYUI_PACK === '1') {
    return
  }

  const root = path.join(__dirname, '..')
  const mainPy = path.join(root, 'build', 'comfyui', 'main.py')

  const onGha = process.env.GITHUB_ACTIONS === 'true'

  if (!fs.existsSync(mainPy)) {
    if (onGha) {
      console.warn(
        '[electron-before-pack] build/comfyui/main.py missing — artifact will NOT embed ComfyUI.',
      )
      return
    }
    throw new Error(
      'Missing build/comfyui/main.py. Run: node scripts/download-comfyui.js ' +
        '(or scripts\\\\build-win.bat without --no-comfyui). Slim pack: SKIP_COMFYUI_PACK=1.',
    )
  }

  const sd = sd15Ok(root)
  if (!sd.ok) {
    const detail =
      `SD1.5 checkpoint invalid (${sd.reason}): ${sd.p.replace(/\\/g, '/')}`
    if (onGha) {
      console.warn('[electron-before-pack]', detail)
      return
    }
    throw new Error(
      `${detail}. Re-run: node scripts/download-comfyui.js (incremental fix: same command re-downloads the model).`,
    )
  }
}
