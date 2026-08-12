'use client'

import { useEffect, useRef, useState } from 'react'

export default function CountUp({
  value,
  suffix = '',
  duration = 1400,
  className,
}: {
  value: number
  suffix?: string
  duration?: number
  className?: string
}) {
  const ref = useRef<HTMLSpanElement>(null)
  const [atual, setAtual] = useState(0)
  const rodou = useRef(false)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setAtual(value)
      return
    }
    const io = new IntersectionObserver(
      (entries) => {
        if (!entries[0].isIntersecting || rodou.current) return
        rodou.current = true
        const inicio = performance.now()
        const passo = (agora: number) => {
          const p = Math.min(1, (agora - inicio) / duration)
          const ease = 1 - Math.pow(1 - p, 3)
          setAtual(Math.round(value * ease))
          if (p < 1) requestAnimationFrame(passo)
        }
        requestAnimationFrame(passo)
      },
      { threshold: 0.4 }
    )
    io.observe(el)
    return () => io.disconnect()
  }, [value, duration])

  return (
    <span ref={ref} className={className}>
      {atual}
      {suffix}
    </span>
  )
}
