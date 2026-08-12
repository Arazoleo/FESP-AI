'use client'

import { useEffect, useRef } from 'react'

type No = {
  hx: number
  hy: number
  x: number
  y: number
  vx: number
  vy: number
  r: number
  label?: string
  fase: number
}

const BASE: { x: number; y: number; r: number; label?: string }[] = [
  { x: 0.2, y: 0.24, r: 5, label: 'curso' },
  { x: 0.54, y: 0.14, r: 6, label: 'disciplina' },
  { x: 0.85, y: 0.29, r: 5, label: 'docente' },
  { x: 0.37, y: 0.52, r: 4, label: 'pré-requisito' },
  { x: 0.71, y: 0.59, r: 4, label: 'carga horária' },
  { x: 0.17, y: 0.78, r: 4, label: 'regimento' },
  { x: 0.53, y: 0.84, r: 5, label: 'matriz curricular' },
  { x: 0.88, y: 0.8, r: 3, label: 'conceito' },
  { x: 0.08, y: 0.5, r: 2.5 },
  { x: 0.73, y: 0.07, r: 2.5 },
  { x: 0.93, y: 0.55, r: 2.5 },
  { x: 0.33, y: 0.05, r: 2 },
  { x: 0.05, y: 0.12, r: 2 },
  { x: 0.42, y: 0.7, r: 2 },
]

const ARESTAS: [number, number][] = [
  [0, 1], [1, 2], [1, 3], [1, 4], [0, 6], [6, 3], [6, 4], [0, 5],
  [5, 6], [2, 10], [0, 8], [1, 9], [7, 4], [7, 2], [11, 1], [12, 0], [13, 6],
]

export default function LiveGraph({
  className,
  highlight,
  cursorLink = true,
}: {
  className?: string
  highlight?: number[]
  cursorLink?: boolean
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const highlightRef = useRef<number[]>([])

  useEffect(() => {
    highlightRef.current = highlight || []
  }, [highlight])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const reduzido = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    let accent = '52 211 153'
    let texto = '154 168 162'

    const lerCores = () => {
      const s = getComputedStyle(document.documentElement)
      accent = s.getPropertyValue('--accent-rgb').trim() || accent
      texto = s.getPropertyValue('--paper-mute-rgb').trim() || texto
    }
    lerCores()
    const obs = new MutationObserver(lerCores)
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })

    let w = 0
    let h = 0
    const dpr = Math.min(window.devicePixelRatio || 1, 2)

    const nos: No[] = BASE.map((b, i) => ({
      hx: b.x, hy: b.y, x: b.x, y: b.y,
      vx: 0, vy: 0, r: b.r, label: b.label,
      fase: i * 1.7,
    }))

    const mouse = { x: -1, y: -1, dentro: false }

    const redimensionar = () => {
      const rect = canvas.getBoundingClientRect()
      w = rect.width
      h = rect.height
      canvas.width = w * dpr
      canvas.height = h * dpr
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    }
    redimensionar()
    const ro = new ResizeObserver(redimensionar)
    ro.observe(canvas)

    const aoMover = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect()
      mouse.x = e.clientX - rect.left
      mouse.y = e.clientY - rect.top
      mouse.dentro = mouse.x >= 0 && mouse.y >= 0 && mouse.x <= rect.width && mouse.y <= rect.height
    }
    const aoSair = () => { mouse.dentro = false }
    window.addEventListener('mousemove', aoMover)
    canvas.addEventListener('mouseleave', aoSair)

    let raf = 0
    let t = 0

    const desenhar = () => {
      t += 0.008
      ctx.clearRect(0, 0, w, h)

      for (const n of nos) {
        const alvoX = (n.hx + Math.sin(t + n.fase) * 0.014) * w
        const alvoY = (n.hy + Math.cos(t * 0.9 + n.fase) * 0.018) * h
        let px = alvoX
        let py = alvoY
        if (mouse.dentro) {
          const dx = mouse.x - alvoX
          const dy = mouse.y - alvoY
          const d = Math.hypot(dx, dy)
          if (d < 140 && d > 0.001) {
            const forca = ((140 - d) / 140) * 14
            px += (dx / d) * forca
            py += (dy / d) * forca
          }
        }
        n.x += (px - n.x) * 0.06
        n.y += (py - n.y) * 0.06
      }

      const acesos = highlightRef.current

      ctx.lineWidth = 1
      for (const [a, b] of ARESTAS) {
        const na = nos[a]
        const nb = nos[b]
        let alfa = 0.16
        if (mouse.dentro) {
          const mx = (na.x + nb.x) / 2
          const my = (na.y + nb.y) / 2
          const d = Math.hypot(mouse.x - mx, mouse.y - my)
          if (d < 130) alfa = 0.16 + ((130 - d) / 130) * 0.35
        }
        ctx.strokeStyle = `rgb(${accent} / ${alfa})`
        ctx.beginPath()
        ctx.moveTo(na.x, na.y)
        ctx.lineTo(nb.x, nb.y)
        ctx.stroke()
      }

      if (acesos.length > 1) {
        ctx.lineWidth = 1.6
        const fluxo = (t * 40) % 16
        ctx.setLineDash([7, 9])
        ctx.lineDashOffset = -fluxo
        for (let i = 0; i < acesos.length - 1; i++) {
          const na = nos[acesos[i]]
          const nb = nos[acesos[i + 1]]
          ctx.strokeStyle = `rgb(${accent} / 0.85)`
          ctx.beginPath()
          ctx.moveTo(na.x, na.y)
          ctx.lineTo(nb.x, nb.y)
          ctx.stroke()
        }
        ctx.setLineDash([])
        ctx.lineWidth = 1
      }

      if (cursorLink && mouse.dentro) {
        const proximos = nos
          .map((n, i) => ({ i, d: Math.hypot(mouse.x - n.x, mouse.y - n.y) }))
          .filter((p) => p.d < 150)
          .sort((a, b) => a.d - b.d)
          .slice(0, 3)
        for (const p of proximos) {
          const n = nos[p.i]
          ctx.strokeStyle = `rgb(${accent} / ${((150 - p.d) / 150) * 0.4})`
          ctx.beginPath()
          ctx.moveTo(mouse.x, mouse.y)
          ctx.lineTo(n.x, n.y)
          ctx.stroke()
        }
        if (proximos.length) {
          ctx.fillStyle = `rgb(${accent} / 0.9)`
          ctx.beginPath()
          ctx.arc(mouse.x, mouse.y, 2.5, 0, Math.PI * 2)
          ctx.fill()
        }
      }

      for (let i = 0; i < nos.length; i++) {
        const n = nos[i]
        const aceso = acesos.includes(i)
        let brilho = aceso ? 1 : 0
        if (!aceso && mouse.dentro) {
          const d = Math.hypot(mouse.x - n.x, mouse.y - n.y)
          if (d < 110) brilho = (110 - d) / 110
        }
        const pulso = 0.55 + Math.sin(t * 2 + n.fase) * 0.2
        const alfa = n.label ? Math.min(1, pulso + brilho * 0.6) : 0.35 + brilho * 0.5
        if (brilho > 0.15) {
          ctx.fillStyle = `rgb(${accent} / ${brilho * (aceso ? 0.28 : 0.18)})`
          ctx.beginPath()
          ctx.arc(n.x, n.y, n.r + (aceso ? 12 : 9) * brilho, 0, Math.PI * 2)
          ctx.fill()
        }
        ctx.fillStyle = `rgb(${accent} / ${alfa})`
        ctx.beginPath()
        ctx.arc(n.x, n.y, n.r + brilho * 1.5, 0, Math.PI * 2)
        ctx.fill()
        if (n.label) {
          ctx.font = '11px ui-monospace, SFMono-Regular, Menlo, monospace'
          ctx.fillStyle = aceso
            ? `rgb(${accent} / 1)`
            : `rgb(${texto} / ${0.85 + brilho * 0.15})`
          ctx.fillText(n.label, n.x + n.r + 8, n.y + 4)
        }
      }

      if (!reduzido) raf = requestAnimationFrame(desenhar)
    }

    desenhar()
    if (reduzido) desenhar()

    return () => {
      cancelAnimationFrame(raf)
      ro.disconnect()
      obs.disconnect()
      window.removeEventListener('mousemove', aoMover)
      canvas.removeEventListener('mouseleave', aoSair)
    }
  }, [])

  return (
    <canvas
      ref={canvasRef}
      className={className}
      role="img"
      aria-label="Grafo de conhecimento animado: cursos, disciplinas, docentes e regimentos conectados"
      style={{ width: '100%', height: '100%' }}
    />
  )
}
