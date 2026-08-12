'use client'

import { useEffect, useRef, useState } from 'react'

const GLIFOS = '#%&@$?!<>[]{}=+*/\\|~^'

export default function DecryptText({
  text,
  delay = 0,
  className,
}: {
  text: string
  delay?: number
  className?: string
}) {
  const [exibido, setExibido] = useState(text)
  const rodou = useRef(false)

  useEffect(() => {
    if (rodou.current) return
    rodou.current = true
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return

    let frame = 0
    let raf = 0
    const total = text.length * 3 + 8

    const passo = () => {
      frame += 1
      const fixos = Math.max(0, Math.floor((frame - 8) / 3) + 1)
      const parcial = text
        .split('')
        .map((c, i) => {
          if (c === ' ' || i < fixos) return c
          return GLIFOS[Math.floor(Math.random() * GLIFOS.length)]
        })
        .join('')
      setExibido(parcial)
      if (frame < total) raf = requestAnimationFrame(passo)
      else setExibido(text)
    }

    const timer = setTimeout(() => { raf = requestAnimationFrame(passo) }, delay)
    return () => { clearTimeout(timer); cancelAnimationFrame(raf) }
  }, [text, delay])

  return <span className={className}>{exibido}</span>
}
