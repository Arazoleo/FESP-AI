'use client'

import { Bot, User } from 'lucide-react'

interface AvatarProps {
  type: 'user' | 'assistant'
  isAnimating?: boolean
}

export default function Avatar({ type, isAnimating = false }: AvatarProps) {
  if (type === 'assistant') {
    return (
      <div className="relative flex-shrink-0">
        {/* Outer Glow Ring */}
        <div className={`
          absolute inset-0 rounded-2xl
          bg-gradient-to-br from-emerald-400 to-cyan-400
          blur-xl opacity-40
          ${isAnimating ? 'animate-pulse-ring' : ''}
        `} />
        
        {/* Main Avatar */}
        <div className={`
          relative w-12 h-12 rounded-2xl
          bg-gradient-to-br from-emerald-500 via-emerald-600 to-teal-600
          flex items-center justify-center
          shadow-lg shadow-emerald-500/30
          border border-white/20
          ${isAnimating ? 'animate-glow-pulse' : ''}
        `}>
          <Bot className="w-6 h-6 text-white drop-shadow-md" />
          
          {/* Status Indicator */}
          <div className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-emerald-400 border-2 border-white dark:border-slate-900 flex items-center justify-center">
            <div className={`w-2 h-2 rounded-full bg-white ${isAnimating ? 'animate-ping' : ''}`} />
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="relative flex-shrink-0">
      {/* Outer Glow Ring */}
      <div className="absolute inset-0 rounded-2xl bg-gradient-to-br from-slate-400 to-slate-500 dark:from-slate-500 dark:to-slate-600 blur-xl opacity-30" />
      
      {/* Main Avatar */}
      <div className="
        relative w-12 h-12 rounded-2xl
        bg-gradient-to-br from-slate-500 via-slate-600 to-slate-700
        dark:from-slate-600 dark:via-slate-700 dark:to-slate-800
        flex items-center justify-center
        shadow-lg shadow-slate-500/20
        border border-white/10
      ">
        <User className="w-6 h-6 text-white drop-shadow-md" />
      </div>
    </div>
  )
}
