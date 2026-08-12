'use client'

import { useEffect, useRef } from 'react'

export default function GraphConfetti({ trigger }: { trigger: number }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    if (!trigger) return
    const canvas = canvasRef.current
    if (!canvas) return
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    const w = window.innerWidth
    const h = window.innerHeight
    canvas.width = w * dpr
    canvas.height = h * dpr
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)

    const s = getComputedStyle(document.documentElement)
    const accent = s.getPropertyValue('--accent-rgb').trim() || '52 211 153'

    const cx = w / 2
    const cy = h * 0.22
    const parts = Array.from({ length: 28 }, (_, i) => {
      const ang = (Math.PI * 2 * i) / 28 + Math.random() * 0.4
      const vel = 3.5 + Math.random() * 5
      return {
        x: cx,
        y: cy,
        vx: Math.cos(ang) * vel,
        vy: Math.sin(ang) * vel - 2.2,
        r: 2 + Math.random() * 3,
      }
    })

    const inicio = performance.now()
    let raf = 0

    const desenhar = (agora: number) => {
      const p = (agora - inicio) / 1400
      ctx.clearRect(0, 0, w, h)
      if (p >= 1) return
      const alfa = 1 - p
      for (const pt of parts) {
        pt.x += pt.vx
        pt.y += pt.vy
        pt.vy += 0.12
        pt.vx *= 0.985
      }
      ctx.lineWidth = 1
      for (let i = 0; i < parts.length; i++) {
        for (let j = i + 1; j < parts.length; j++) {
          const d = Math.hypot(parts[i].x - parts[j].x, parts[i].y - parts[j].y)
          if (d < 70) {
            ctx.strokeStyle = `rgb(${accent} / ${alfa * (1 - d / 70) * 0.4})`
            ctx.beginPath()
            ctx.moveTo(parts[i].x, parts[i].y)
            ctx.lineTo(parts[j].x, parts[j].y)
            ctx.stroke()
          }
        }
      }
      for (const pt of parts) {
        ctx.fillStyle = `rgb(${accent} / ${alfa})`
        ctx.beginPath()
        ctx.arc(pt.x, pt.y, pt.r, 0, Math.PI * 2)
        ctx.fill()
      }
      raf = requestAnimationFrame(desenhar)
    }
    raf = requestAnimationFrame(desenhar)
    return () => {
      cancelAnimationFrame(raf)
      ctx.clearRect(0, 0, w, h)
    }
  }, [trigger])

  if (!trigger) return null
  return (
    <canvas
      ref={canvasRef}
      className="pointer-events-none fixed inset-0 z-[70]"
      style={{ width: '100%', height: '100%' }}
      aria-hidden
    />
  )
}
