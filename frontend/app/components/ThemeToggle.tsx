'use client'

import { useState, useEffect } from 'react'
import { Sun, Moon, Stars } from 'lucide-react'

export default function ThemeToggle() {
  const [theme, setTheme] = useState<'light' | 'dark'>('light')
  const [mounted, setMounted] = useState(false)
  const [isAnimating, setIsAnimating] = useState(false)

  useEffect(() => {
    setMounted(true)
    const savedTheme = localStorage.getItem('fesp-theme') as 'light' | 'dark' | null
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
    
    const initialTheme = savedTheme || (prefersDark ? 'dark' : 'light')
    setTheme(initialTheme)
    document.documentElement.classList.toggle('dark', initialTheme === 'dark')
  }, [])

  const toggleTheme = () => {
    setIsAnimating(true)
    const newTheme = theme === 'light' ? 'dark' : 'light'
    setTheme(newTheme)
    localStorage.setItem('fesp-theme', newTheme)
    document.documentElement.classList.toggle('dark', newTheme === 'dark')
    
    setTimeout(() => setIsAnimating(false), 500)
  }

  if (!mounted) {
    return (
      <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-slate-200 to-slate-300 dark:from-slate-700 dark:to-slate-800 animate-pulse" />
    )
  }

  return (
    <button
      onClick={toggleTheme}
      className={`
        relative w-14 h-14 rounded-2xl overflow-hidden
        bg-gradient-to-br from-slate-100 to-slate-200 
        dark:from-slate-800 dark:to-slate-900
        border border-slate-200/50 dark:border-slate-700/50
        shadow-lg hover:shadow-xl
        transition-all duration-500 ease-out
        hover:scale-105 active:scale-95
        group
        ${isAnimating ? 'animate-scale-bounce' : ''}
      `}
      aria-label={theme === 'light' ? 'Ativar modo escuro' : 'Ativar modo claro'}
    >
      {/* Background Glow */}
      <div className={`
        absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500
        ${theme === 'light' 
          ? 'bg-gradient-to-br from-amber-200/50 to-orange-200/50' 
          : 'bg-gradient-to-br from-indigo-500/30 to-violet-500/30'
        }
      `} />
      
      {/* Stars decoration for dark mode */}
      <div className={`
        absolute inset-0 transition-opacity duration-500
        ${theme === 'dark' ? 'opacity-100' : 'opacity-0'}
      `}>
        <div className="absolute top-2 left-2 w-1 h-1 bg-white rounded-full animate-pulse" />
        <div className="absolute top-4 right-3 w-0.5 h-0.5 bg-white/80 rounded-full animate-pulse delay-300" />
        <div className="absolute bottom-3 left-4 w-0.5 h-0.5 bg-white/60 rounded-full animate-pulse delay-500" />
      </div>

      {/* Icons Container */}
      <div className="relative w-full h-full flex items-center justify-center">
        {/* Sun Icon */}
        <Sun
          className={`
            absolute w-6 h-6 transition-all duration-500 ease-out
            ${theme === 'light'
              ? 'rotate-0 scale-100 opacity-100 text-amber-500'
              : 'rotate-90 scale-0 opacity-0 text-amber-500'
            }
          `}
        />
        
        {/* Moon Icon */}
        <Moon
          className={`
            absolute w-6 h-6 transition-all duration-500 ease-out
            ${theme === 'dark'
              ? 'rotate-0 scale-100 opacity-100 text-indigo-300'
              : '-rotate-90 scale-0 opacity-0 text-indigo-300'
            }
          `}
        />
      </div>

      {/* Ripple Effect on Click */}
      <span className={`
        absolute inset-0 rounded-2xl
        ${theme === 'light' ? 'bg-amber-400' : 'bg-indigo-400'}
        ${isAnimating ? 'animate-ping opacity-30' : 'opacity-0'}
      `} />
    </button>
  )
}
