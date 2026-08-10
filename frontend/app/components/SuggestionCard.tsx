'use client'

import { MessageSquare, Sparkles, BookOpen, HelpCircle } from 'lucide-react'

interface SuggestionCardProps {
  question: string
  icon: 'message' | 'sparkle' | 'book' | 'help'
  delay: number
  onClick: () => void
}

const icons = {
  message: MessageSquare,
  sparkle: Sparkles,
  book: BookOpen,
  help: HelpCircle,
}

export default function SuggestionCard({ question, icon, delay, onClick }: SuggestionCardProps) {
  const Icon = icons[icon]

  return (
    <button
      onClick={onClick}
      className="
        group relative w-full text-left
        p-5 rounded-2xl
        glass card-interactive
        border border-emerald-200/30 dark:border-emerald-700/30
        hover:border-emerald-400/50 dark:hover:border-emerald-500/50
        animate-slide-up opacity-0
        focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:ring-offset-2
        dark:focus:ring-offset-slate-900
      "
      style={{ animationDelay: `${delay}ms`, animationFillMode: 'forwards' }}
    >
      <div className="
        absolute inset-0 rounded-2xl opacity-0 group-hover:opacity-100
        bg-gradient-to-br from-emerald-50/80 to-cyan-50/80
        dark:from-emerald-900/30 dark:to-cyan-900/30
        transition-opacity duration-300
      " />

      <div className="relative flex items-start gap-4">
        <div className="
          flex-shrink-0 w-11 h-11 rounded-xl
          bg-gradient-to-br from-emerald-500 to-emerald-600
          flex items-center justify-center
          shadow-lg shadow-emerald-500/25
          group-hover:shadow-emerald-500/40
          group-hover:scale-110
          transition-all duration-300
        ">
          <Icon className="w-5 h-5 text-white" />
        </div>

        <div className="flex-1 min-w-0">
          <p className="
            text-sm font-medium leading-relaxed
            text-slate-700 dark:text-slate-200
            group-hover:text-emerald-700 dark:group-hover:text-emerald-300
            transition-colors duration-300
          ">
            {question}
          </p>
        </div>

        <div className="
          flex-shrink-0 w-8 h-8 rounded-lg
          bg-slate-100 dark:bg-slate-800
          flex items-center justify-center
          opacity-0 group-hover:opacity-100
          transform translate-x-2 group-hover:translate-x-0
          transition-all duration-300
        ">
          <svg 
            className="w-4 h-4 text-emerald-600 dark:text-emerald-400" 
            fill="none" 
            viewBox="0 0 24 24" 
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </div>
      </div>
    </button>
  )
}
