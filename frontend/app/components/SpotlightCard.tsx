'use client'

import { useRef, type ReactNode, type CSSProperties } from 'react'

export default function SpotlightCard({
  children,
  className,
  style,
}: {
  children: ReactNode
  className?: string
  style?: CSSProperties
}) {
  const ref = useRef<HTMLDivElement>(null)

  const aoMover = (e: React.MouseEvent<HTMLDivElement>) => {
    const el = ref.current
    if (!el) return
    const rect = el.getBoundingClientRect()
    el.style.setProperty('--sx', `${e.clientX - rect.left}px`)
    el.style.setProperty('--sy', `${e.clientY - rect.top}px`)
  }

  return (
    <div
      ref={ref}
      onMouseMove={aoMover}
      className={`spotlight-card ${className || ''}`}
      style={style}
    >
      {children}
    </div>
  )
}
