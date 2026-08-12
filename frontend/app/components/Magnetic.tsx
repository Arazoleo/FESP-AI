'use client'

import { useRef, type ReactNode } from 'react'

export default function Magnetic({
  children,
  strength = 0.25,
  className,
}: {
  children: ReactNode
  strength?: number
  className?: string
}) {
  const ref = useRef<HTMLDivElement>(null)

  const aoMover = (e: React.MouseEvent<HTMLDivElement>) => {
    const el = ref.current
    if (!el) return
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const rect = el.getBoundingClientRect()
    const dx = e.clientX - (rect.left + rect.width / 2)
    const dy = e.clientY - (rect.top + rect.height / 2)
    el.style.transform = `translate(${dx * strength}px, ${dy * strength}px)`
  }

  const aoSair = () => {
    const el = ref.current
    if (el) el.style.transform = 'translate(0, 0)'
  }

  return (
    <div
      ref={ref}
      onMouseMove={aoMover}
      onMouseLeave={aoSair}
      className={className}
      style={{ display: 'inline-block', transition: 'transform 0.35s cubic-bezier(0.22, 1, 0.36, 1)' }}
    >
      {children}
    </div>
  )
}
