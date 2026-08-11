'use client'

import { useEffect, useState } from 'react'
import { Sun, Moon } from 'lucide-react'

export default function ThemeToggle() {
  const [light, setLight] = useState(false)
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
    const isLight = document.documentElement.classList.contains('light')
    setLight(isLight)
  }, [])

  const toggle = () => {
    const next = !light
    setLight(next)
    try {
      localStorage.setItem('fesp-theme', next ? 'light' : 'dark')
    } catch {}
    document.documentElement.classList.toggle('light', next)
  }

  if (!mounted) {
    return <div className="h-9 w-9 rounded-lg border border-line" aria-hidden />
  }

  return (
    <button
      onClick={toggle}
      aria-label={light ? 'Ativar modo escuro' : 'Ativar modo claro'}
      title={light ? 'Modo escuro' : 'Modo claro'}
      className="flex h-9 w-9 items-center justify-center rounded-lg border border-line text-paper-dim transition-colors hover:border-line-strong hover:text-paper"
    >
      {light ? (
        <Moon className="h-[17px] w-[17px]" />
      ) : (
        <Sun className="h-[17px] w-[17px]" />
      )}
    </button>
  )
}
