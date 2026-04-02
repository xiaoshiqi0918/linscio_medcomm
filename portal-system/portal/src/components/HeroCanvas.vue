<template>
  <div class="hero-canvas-wrapper">
    <canvas ref="canvas" class="hero-canvas"></canvas>
    <div class="canvas-fade-bottom"></div>
    <div class="canvas-fade-right"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const canvas = ref(null)
let animationId = null
let resizeFn = null
let time = 0

onMounted(() => {
  const c = canvas.value
  if (!c) return
  const ctx = c.getContext('2d')

  resizeFn = () => {
    const dpr = window.devicePixelRatio || 1
    c.width = c.offsetWidth * dpr
    c.height = c.offsetHeight * dpr
    ctx.setTransform(1, 0, 0, 1, 0, 0)
    ctx.scale(dpr, dpr)
  }
  resizeFn()
  window.addEventListener('resize', resizeFn)

  const W = () => c.offsetWidth
  const H = () => c.offsetHeight

  const BLUE = '#1A3FCC'
  const CYAN = '#00C4AA'
  const PURPLE = '#7B5FCC'
  const BLUE_RGB = [26, 63, 204]
  const CYAN_RGB = [0, 196, 170]
  const PURPLE_RGB = [123, 95, 204]

  const LABELS = [
    'Literature', 'Neural Net', 'pgvector',
    'RAG', 'Schola', 'LLM', 'MedComm',
    'PDCA', 'Embeddings', 'QCC', 'Fine-tune',
    'Data Analyzer', 'Supervisor Agent',
  ]

  const PARTICLE_COUNT = 55
  const particles = Array.from({ length: PARTICLE_COUNT }, (_, i) => {
    const colorChoice = i % 3
    return {
      x: Math.random() * 520,
      y: Math.random() * 420,
      vx: (Math.random() - 0.5) * 0.35,
      vy: (Math.random() - 0.5) * 0.35,
      radius: Math.random() * 2 + 1,
      rgb: colorChoice === 0 ? BLUE_RGB : colorChoice === 1 ? CYAN_RGB : PURPLE_RGB,
      pulse: Math.random() * Math.PI * 2,
    }
  })

  const labelNodes = LABELS.map((text, i) => {
    const angle = (i / LABELS.length) * Math.PI * 2
    const rBase = 130 + Math.random() * 80
    return {
      text,
      angle,
      r: rBase,
      speed: (Math.random() > 0.5 ? 1 : -1) * (0.0003 + Math.random() * 0.0002),
      alpha: 0.7 + Math.random() * 0.3,
      colorIdx: i % 3,
    }
  })

  const DNA_POINTS = 18
  const DNA_HEIGHT = 220
  const DNA_WIDTH = 38
  const DNA_SPEED = 0.012

  const drawGlowDot = (x, y, r, color, glowSize = 8, alpha = 1) => {
    const grad = ctx.createRadialGradient(x, y, 0, x, y, glowSize)
    grad.addColorStop(0, `rgba(${color.join(',')},${alpha})`)
    grad.addColorStop(0.4, `rgba(${color.join(',')},${alpha * 0.4})`)
    grad.addColorStop(1, `rgba(${color.join(',')},0)`)
    ctx.beginPath()
    ctx.arc(x, y, glowSize, 0, Math.PI * 2)
    ctx.fillStyle = grad
    ctx.fill()
    ctx.beginPath()
    ctx.arc(x, y, r, 0, Math.PI * 2)
    ctx.fillStyle = `rgba(${color.join(',')},${alpha})`
    ctx.fill()
  }

  const drawGradientLine = (x1, y1, x2, y2, rgb1, rgb2, alpha, width = 1) => {
    const grad = ctx.createLinearGradient(x1, y1, x2, y2)
    grad.addColorStop(0, `rgba(${rgb1.join(',')},${alpha})`)
    grad.addColorStop(1, `rgba(${rgb2.join(',')},${alpha})`)
    ctx.beginPath()
    ctx.moveTo(x1, y1)
    ctx.lineTo(x2, y2)
    ctx.strokeStyle = grad
    ctx.lineWidth = width
    ctx.stroke()
  }

  const draw = () => {
    time += 1
    const w = W()
    const h = H()
    const cx = w * 0.52
    const cy = h * 0.5

    ctx.clearRect(0, 0, w, h)

    const bgGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, Math.max(w, h) * 0.75)
    bgGrad.addColorStop(0, 'rgba(10, 16, 40, 1)')
    bgGrad.addColorStop(0.5, 'rgba(6, 12, 30, 1)')
    bgGrad.addColorStop(1, 'rgba(2, 6, 18, 1)')
    ctx.fillStyle = bgGrad
    ctx.fillRect(0, 0, w, h)

    const aura1 = ctx.createRadialGradient(cx, cy, 0, cx, cy, 200)
    aura1.addColorStop(0, 'rgba(26, 63, 204, 0.10)')
    aura1.addColorStop(1, 'rgba(26, 63, 204, 0)')
    ctx.fillStyle = aura1
    ctx.fillRect(0, 0, w, h)

    const aura2 = ctx.createRadialGradient(cx + 100, cy + 80, 0, cx + 100, cy + 80, 160)
    aura2.addColorStop(0, 'rgba(0, 196, 170, 0.08)')
    aura2.addColorStop(1, 'rgba(0, 196, 170, 0)')
    ctx.fillStyle = aura2
    ctx.fillRect(0, 0, w, h)

    ctx.save()
    ctx.strokeStyle = 'rgba(26, 63, 204, 0.06)'
    ctx.lineWidth = 0.5
    const gridSize = 40
    for (let x = 0; x < w; x += gridSize) {
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke()
    }
    for (let y = 0; y < h; y += gridSize) {
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke()
    }
    ctx.restore()

    ctx.save()
    particles.forEach(p => {
      p.x += p.vx
      p.y += p.vy
      if (p.x < 0 || p.x > w) p.vx *= -1
      if (p.y < 0 || p.y > h) p.vy *= -1
      p.pulse += 0.02
    })
    const MAX_DIST = 110
    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const dx = particles[i].x - particles[j].x
        const dy = particles[i].y - particles[j].y
        const dist = Math.sqrt(dx * dx + dy * dy)
        if (dist < MAX_DIST) {
          const alpha = (1 - dist / MAX_DIST) * 0.35
          drawGradientLine(particles[i].x, particles[i].y, particles[j].x, particles[j].y, particles[i].rgb, particles[j].rgb, alpha, 0.8)
        }
      }
    }
    particles.forEach(p => {
      const pulse = Math.sin(p.pulse) * 0.5 + 0.5
      const radius = p.radius + pulse * 0.8
      const alpha = 0.6 + pulse * 0.4
      drawGlowDot(p.x, p.y, radius, p.rgb, radius * 4, alpha)
    })
    ctx.restore()

    ctx.save()
    const dnaOffsetX = cx
    const dnaOffsetY = cy - DNA_HEIGHT / 2
    const phase = time * DNA_SPEED
    const strand1 = []
    const strand2 = []
    for (let i = 0; i < DNA_POINTS; i++) {
      const t = i / (DNA_POINTS - 1)
      const y = dnaOffsetY + t * DNA_HEIGHT
      const angle = phase + t * Math.PI * 3.5
      strand1.push({ x: dnaOffsetX + Math.cos(angle) * DNA_WIDTH, y })
      strand2.push({ x: dnaOffsetX - Math.cos(angle) * DNA_WIDTH, y })
    }
    ;[
      { pts: strand1, rgb: BLUE_RGB },
      { pts: strand2, rgb: CYAN_RGB },
    ].forEach(({ pts, rgb }) => {
      ctx.beginPath()
      ctx.moveTo(pts[0].x, pts[0].y)
      for (let i = 1; i < pts.length - 1; i++) {
        const mx = (pts[i].x + pts[i + 1].x) / 2
        const my = (pts[i].y + pts[i + 1].y) / 2
        ctx.quadraticCurveTo(pts[i].x, pts[i].y, mx, my)
      }
      ctx.strokeStyle = `rgba(${rgb.join(',')}, 0.7)`
      ctx.lineWidth = 1.5
      ctx.stroke()
    })
    for (let i = 0; i < DNA_POINTS; i++) {
      const p1 = strand1[i]
      const p2 = strand2[i]
      const t = i / (DNA_POINTS - 1)
      const angle = phase + t * Math.PI * 3.5
      const depth = (Math.sin(angle) + 1) / 2
      const alpha = 0.25 + depth * 0.55
      drawGradientLine(p1.x, p1.y, p2.x, p2.y, BLUE_RGB, CYAN_RGB, alpha, 1)
      const r1 = 2.5 + depth * 1.5
      drawGlowDot(p1.x, p1.y, r1, BLUE_RGB, r1 * 3.5, 0.5 + depth * 0.5)
      drawGlowDot(p2.x, p2.y, r1, CYAN_RGB, r1 * 3.5, 0.5 + depth * 0.5)
    }
    ctx.restore()

    ctx.save()
    const eyePulse = Math.sin(time * 0.025) * 0.5 + 0.5
    const eyeRadius = 14 + eyePulse * 4
    ;[
      { r: eyeRadius * 6, a: 0.04 },
      { r: eyeRadius * 4, a: 0.07 },
      { r: eyeRadius * 2.5, a: 0.12 },
      { r: eyeRadius, a: 0.9 },
    ].forEach(({ r, a }) => {
      const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, r)
      g.addColorStop(0, `rgba(0, 220, 190, ${a})`)
      g.addColorStop(0.5, `rgba(26, 63, 204, ${a * 0.5})`)
      g.addColorStop(1, 'rgba(0,0,0,0)')
      ctx.fillStyle = g
      ctx.beginPath()
      ctx.arc(cx, cy, r, 0, Math.PI * 2)
      ctx.fill()
    })
    ctx.beginPath()
    ctx.arc(cx, cy, 5, 0, Math.PI * 2)
    ctx.fillStyle = '#ffffff'
    ctx.fill()
    ctx.restore()

    ctx.save()
    ctx.translate(cx, cy)
    const ringAngle1 = time * 0.003
    ctx.rotate(ringAngle1)
    ctx.beginPath()
    ctx.arc(0, 0, 72, 0, Math.PI * 2)
    ctx.setLineDash([4, 8])
    ctx.strokeStyle = 'rgba(26, 63, 204, 0.35)'
    ctx.lineWidth = 1
    ctx.stroke()
    ctx.setLineDash([])
    ctx.rotate(-ringAngle1 * 2)
    ctx.beginPath()
    ctx.arc(0, 0, 48, 0, Math.PI * 2)
    ctx.setLineDash([3, 6])
    ctx.strokeStyle = 'rgba(0, 196, 170, 0.30)'
    ctx.lineWidth = 1
    ctx.stroke()
    ctx.setLineDash([])
    for (let i = 0; i < 4; i++) {
      const a = ringAngle1 + (i / 4) * Math.PI * 2
      const x = Math.cos(a) * 72
      const y = Math.sin(a) * 72
      drawGlowDot(x, y, 3, BLUE_RGB, 10, 0.9)
    }
    for (let i = 0; i < 3; i++) {
      const a = -ringAngle1 * 2 + (i / 3) * Math.PI * 2
      const x = Math.cos(a) * 48
      const y = Math.sin(a) * 48
      drawGlowDot(x, y, 2.5, CYAN_RGB, 8, 0.9)
    }
    ctx.restore()

    ctx.save()
    ctx.font = '11px "DM Sans", "Noto Sans SC", sans-serif'
    labelNodes.forEach(node => {
      node.angle += node.speed
      const x = cx + Math.cos(node.angle) * node.r
      const y = cy + Math.sin(node.angle) * node.r
      const textW = ctx.measureText(node.text).width
      const padX = 8
      const padY = 4
      const boxW = textW + padX * 2
      const boxH = 20
      const boxX = x - boxW / 2
      const boxY = y - boxH / 2
      const rgb = node.colorIdx === 0 ? BLUE_RGB : node.colorIdx === 1 ? CYAN_RGB : PURPLE_RGB
      const alpha = node.alpha * (0.7 + Math.sin(time * 0.02 + node.angle) * 0.15)
      ctx.beginPath()
      if (typeof ctx.roundRect === 'function') {
        ctx.roundRect(boxX, boxY, boxW, boxH, 10)
      } else {
        ctx.rect(boxX, boxY, boxW, boxH)
      }
      ctx.fillStyle = `rgba(${rgb.join(',')}, ${alpha * 0.15})`
      ctx.strokeStyle = `rgba(${rgb.join(',')}, ${alpha * 0.5})`
      ctx.lineWidth = 0.8
      ctx.fill()
      ctx.stroke()
      ctx.fillStyle = `rgba(${rgb.join(',')}, ${alpha})`
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText(node.text, x, y)
    })
    ctx.restore()

    animationId = requestAnimationFrame(draw)
  }

  draw()
})

onUnmounted(() => {
  if (animationId) cancelAnimationFrame(animationId)
  if (resizeFn) window.removeEventListener('resize', resizeFn)
})
</script>

<style scoped>
.hero-canvas-wrapper {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  min-height: 480px;
  border-radius: 20px;
  overflow: hidden;
  box-shadow:
    0 0 0 1px rgba(26, 63, 204, 0.15),
    0 8px 40px rgba(26, 63, 204, 0.18),
    0 24px 80px rgba(0, 0, 0, 0.30);
}

.hero-canvas {
  width: 100%;
  height: 100%;
  display: block;
}

.canvas-fade-bottom {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 80px;
  background: linear-gradient(to bottom, transparent, rgba(255, 255, 255, 0.06));
  pointer-events: none;
}

.canvas-fade-right {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: 60px;
  background: linear-gradient(to right, transparent, rgba(255, 255, 255, 0.04));
  pointer-events: none;
}
</style>
