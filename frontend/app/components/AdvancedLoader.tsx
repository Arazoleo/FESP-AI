'use client'

import { motion } from 'framer-motion'
import { Bot, Loader2, Sparkles, Zap } from 'lucide-react'

interface AdvancedLoaderProps {
  isInitialLoad?: boolean
}

const AdvancedLoader = ({ isInitialLoad = false }: AdvancedLoaderProps) => {
  const dots = Array.from({ length: 3 }, (_, i) => i)

  const containerAnimation = {
    opacity: 1,
    scale: 1,
    transition: {
      duration: 0.5,
    },
  }

  const pulseAnimation = {
    scale: [1, 1.1, 1],
    opacity: [0.7, 1, 0.7],
    transition: {
      duration: 2,
      repeat: Infinity,
    },
  }

  const getDotAnimation = (i: number) => ({
    y: [0, -10, 0],
    opacity: [0.3, 1, 0.3],
    transition: {
      duration: 1.5,
      repeat: Infinity,
      delay: i * 0.2,
    },
  })

  const spinAnimation = {
    rotate: 360,
    transition: {
      duration: 2,
      repeat: Infinity,
    },
  }

  const morphAnimation = {
    borderRadius: [
      '60% 40% 30% 70% / 60% 30% 70% 40%',
      '30% 60% 70% 40% / 50% 60% 30% 60%',
      '50% 40% 30% 60% / 30% 60% 70% 40%',
      '40% 60% 50% 30% / 70% 40% 60% 50%',
      '60% 40% 30% 70% / 60% 30% 70% 40%',
    ],
    transition: {
      duration: 4,
      repeat: Infinity,
    },
  }

  return (
    <motion.div
      className="flex gap-6 justify-start animate-fade-in"
      initial={{ opacity: 0, scale: 0.8 }}
      animate={containerAnimation}
    >
      {/* Avatar com efeitos avançados */}
      <div className="flex-shrink-0 relative">
        {/* Glow animado */}
        <motion.div
          className="absolute inset-0 bg-gradient-unifesp rounded-full blur-xl"
          animate={pulseAnimation}
        />

        {/* Avatar principal com morphing */}
        <motion.div
          className="relative w-12 h-12 bg-gradient-unifesp rounded-full flex items-center justify-center shadow-glow-xl border-2 border-white/20"
          animate={morphAnimation}
        >
          <motion.div
            animate={spinAnimation}
          >
            <Bot className="w-7 h-7 text-white drop-shadow-lg" />
          </motion.div>

          {/* Partículas orbitais */}
          <motion.div
            className="absolute inset-0"
            animate={{ rotate: 360 }}
            transition={{ duration: 8, repeat: Infinity }}
          >
            <div className="absolute top-1 left-1/2 w-1 h-1 bg-white/60 rounded-full transform -translate-x-1/2" />
          </motion.div>
          <motion.div
            className="absolute inset-0"
            animate={{ rotate: -360 }}
            transition={{ duration: 6, repeat: Infinity }}
          >
            <div className="absolute top-1/2 right-1 w-1 h-1 bg-white/40 rounded-full transform translate-y-1/2" />
          </motion.div>
        </motion.div>

        {/* Indicador de atividade pulsante */}
        <motion.div
          className="absolute -bottom-1 -right-1 w-5 h-5 bg-primary-400 rounded-full border-2 border-white dark:border-slate-900 flex items-center justify-center"
          animate={{
            scale: [0.8, 1.3, 0.8],
            opacity: [0.7, 1, 0.7],
          }}
          transition={{
            duration: 1.5,
            repeat: Infinity,
          }}
        >
          <motion.div
            animate={{ scale: [0.5, 1, 0.5] }}
            transition={{ duration: 0.5, repeat: Infinity }}
          >
            <Zap className="w-2 h-2 text-white" />
          </motion.div>
        </motion.div>
      </div>

      {/* Conteúdo do loading */}
      <motion.div
        className="bg-white/90 dark:bg-slate-800/90 rounded-3xl px-6 py-5 border border-primary-200/50 dark:border-primary-800/50 shadow-xl backdrop-blur-sm max-w-md"
        initial={{ x: -20, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        transition={{ delay: 0.2, duration: 0.5 }}
      >
        <div className="flex items-center gap-4">
          {/* Spinner principal */}
          <motion.div
            className="relative"
            animate={{ rotate: 360 }}
            transition={{ duration: 1, repeat: Infinity }}
          >
            <Loader2 className="w-6 h-6 text-primary-600 dark:text-primary-400" />
            <motion.div
              className="absolute inset-0 border-2 border-primary-400 rounded-full"
              animate={{ scale: [0.8, 1.2, 0.8], opacity: [0.5, 1, 0.5] }}
              transition={{ duration: 1.5, repeat: Infinity }}
            />
          </motion.div>

          {/* Texto animado */}
          <div className="space-y-1">
            <motion.div
              className="flex items-center gap-2"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.4 }}
            >
              <span className="text-sm font-semibold text-slate-700 dark:text-slate-300">
                Processando
              </span>

              {/* Pontos animados */}
              <div className="flex gap-1">
                {dots.map((i) => (
                  <motion.div
                    key={i}
                    className="w-1 h-1 bg-primary-600 dark:bg-primary-400 rounded-full"
                    animate={getDotAnimation(i)}
                  />
                ))}
              </div>
            </motion.div>

            {/* Subtexto */}
            <motion.p
              className="text-xs text-slate-500 dark:text-slate-400 flex items-center gap-2"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.6 }}
            >
              <Sparkles className="w-3 h-3" />
              {isInitialLoad ? (
                <>
                  Primeira vez pode demorar ~30s
                  <motion.span
                    animate={{ opacity: [0.5, 1, 0.5] }}
                    transition={{ duration: 1.5, repeat: Infinity }}
                  >
                    ...
                  </motion.span>
                </>
              ) : (
                'Pensando na resposta perfeita'
              )}
            </motion.p>
          </div>
        </div>

        {/* Barra de progresso sutil */}
        <motion.div
          className="mt-4 h-1 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.8 }}
        >
          <motion.div
            className="h-full bg-gradient-to-r from-primary-500 to-primary-400 rounded-full"
            animate={{
              x: ['-100%', '100%'],
              scaleX: [0, 1, 0],
            }}
            transition={{
              duration: 2,
              repeat: Infinity,
            }}
            style={{ originX: 0 }}
          />
        </motion.div>

        {/* Efeito de shimmer */}
        <motion.div
          className="absolute inset-0 rounded-3xl opacity-20 pointer-events-none"
          animate={{
            background: [
              'linear-gradient(90deg, transparent 0%, rgba(34,197,94,0.1) 50%, transparent 100%)',
              'linear-gradient(90deg, transparent 0%, rgba(34,197,94,0.1) 50%, transparent 100%)',
            ],
            backgroundPosition: ['-200% 0', '200% 0'],
          }}
          transition={{
            duration: 3,
            repeat: Infinity,
          }}
        />
      </motion.div>
    </motion.div>
  )
}

export default AdvancedLoader
