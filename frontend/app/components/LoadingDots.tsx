'use client'

export default function LoadingDots() {
  return (
    <div className="flex items-center gap-1.5">
      <span className="sr-only">Carregando...</span>
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className="w-2.5 h-2.5 rounded-full bg-gradient-to-br from-emerald-400 to-emerald-600 dark:from-emerald-300 dark:to-emerald-500 animate-wave"
          style={{
            animationDelay: `${i * 0.15}s`,
          }}
        />
      ))}
    </div>
  )
}
