'use client'

import { useRef, type ReactNode, type CSSProperties } from 'react'

export default function SpotlightCard({
  children,
  className,
  style,
  tilt = true,
}: {
  children: ReactNode
  className?: string
  style?: CSSProperties
  tilt?: boolean
}) {
  const ref = useRef<HTMLDivElement>(null)

  const aoMover = (e: React.MouseEvent<HTMLDivElement>) => {
    const el = ref.current
    if (!el) return
    const rect = el.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top
    el.style.setProperty('--sx', `${x}px`)
    el.style.setProperty('--sy', `${y}px`)
    if (tilt && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      const rx = ((y / rect.height) - 0.5) * -6
      const ry = ((x / rect.width) - 0.5) * 6
      el.style.transform = `perspective(800px) rotateX(${rx}deg) rotateY(${ry}deg) translateZ(0)`
    }
  }

  const aoSair = () => {
    const el = ref.current
    if (el) el.style.transform = 'perspective(800px) rotateX(0deg) rotateY(0deg)'
  }

  return (
    <div
      ref={ref}
      onMouseMove={aoMover}
      onMouseLeave={aoSair}
      className={`spotlight-card tilt-card ${className || ''}`}
      style={style}
    >
      {children}
    </div>
  )
}
