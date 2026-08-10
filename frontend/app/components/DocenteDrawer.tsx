'use client'

import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import {
  X,
  Mail,
  MapPin,
  BookOpen,
  Microscope,
  MessageCircle,
  Loader2,
} from 'lucide-react'

export interface DocenteDetails {
  nome: string
  email?: string | null
  sala?: string | null
  areas: string[]
  disciplinas: string[]
}

interface Props {
  nome: string
  apiUrl: string
  onClose: () => void
  onOpenDisciplina: (nome: string) => void
  onAsk: (question: string) => void
}

function Section({
  icon,
  title,
  children,
}: {
  icon: React.ReactNode
  title: string
  children: React.ReactNode
}) {
  return (
    <div>
      <div className="mb-2 flex items-center gap-2 font-mono text-[10.5px] uppercase tracking-[0.18em] text-paper-mute">
        {icon}
        {title}
      </div>
      {children}
    </div>
  )
}

export default function DocenteDrawer({
  nome,
  apiUrl,
  onClose,
  onOpenDisciplina,
  onAsk,
}: Props) {
  const [details, setDetails] = useState<DocenteDetails | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let ativo = true
    setLoading(true)
    setError(null)
    fetch(`${apiUrl}/docente-details?nome=${encodeURIComponent(nome)}`)
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status}`)
        return r.json()
      })
      .then((d) => {
        if (ativo) setDetails(d)
      })
      .catch(() => {
        if (ativo) setError('Não encontrei os detalhes desse docente na base.')
      })
      .finally(() => {
        if (ativo) setLoading(false)
      })
    return () => {
      ativo = false
    }
  }, [nome, apiUrl])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  return (
    <>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.2 }}
        onClick={onClose}
        className="fixed inset-0 z-40 bg-ink/60 backdrop-blur-[2px]"
        aria-hidden
      />
      <motion.aside
        initial={{ x: '100%' }}
        animate={{ x: 0 }}
        exit={{ x: '100%' }}
        transition={{ type: 'tween', duration: 0.25, ease: 'easeOut' }}
        role="dialog"
        aria-modal="true"
        aria-label={`Detalhes do docente ${nome}`}
        className="fixed right-0 top-0 z-50 flex h-full w-full flex-col border-l border-line bg-ink-raise sm:w-[400px]"
      >
        <div className="flex items-start justify-between gap-3 border-b border-line px-5 py-4">
          <div>
            <div className="font-mono text-[10.5px] uppercase tracking-[0.18em] text-paper-mute">
              Docente
            </div>
            <h2 className="mt-1 text-[17px] font-semibold leading-snug text-paper">
              {details?.nome || nome}
            </h2>
          </div>
          <button
            onClick={onClose}
            aria-label="Fechar detalhes"
            className="rounded-lg border border-line p-2 text-paper-dim transition-colors hover:border-line-strong hover:text-paper"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex-1 space-y-6 overflow-y-auto px-5 py-5">
          {loading && (
            <div className="flex items-center gap-2 text-sm text-paper-mute">
              <Loader2 className="h-4 w-4 animate-spin" />
              Consultando o Knowledge Graph...
            </div>
          )}
          {error && <p className="text-sm text-red-300">{error}</p>}

          {!loading && !error && details && (
            <>
              {(details.email || details.sala) && (
                <Section icon={<Mail className="h-3.5 w-3.5" />} title="Contato">
                  <ul className="space-y-1.5 text-[13.5px] text-paper">
                    {details.email && (
                      <li className="flex items-center gap-2">
                        <Mail className="h-3.5 w-3.5 text-paper-mute" />
                        <a
                          href={`mailto:${details.email}`}
                          className="text-accent hover:underline"
                        >
                          {details.email}
                        </a>
                      </li>
                    )}
                    {details.sala && (
                      <li className="flex items-center gap-2">
                        <MapPin className="h-3.5 w-3.5 text-paper-mute" />
                        {details.sala}
                      </li>
                    )}
                  </ul>
                </Section>
              )}

              {details.areas.length > 0 && (
                <Section
                  icon={<Microscope className="h-3.5 w-3.5" />}
                  title="Áreas de pesquisa"
                >
                  <div className="flex flex-wrap gap-1.5">
                    {details.areas.map((a) => (
                      <span
                        key={a}
                        className="rounded-full border border-line bg-ink px-3 py-1.5 text-[12.5px] text-paper-dim"
                      >
                        {a}
                      </span>
                    ))}
                  </div>
                </Section>
              )}

              {details.disciplinas.length > 0 && (
                <Section icon={<BookOpen className="h-3.5 w-3.5" />} title="Leciona">
                  <div className="flex flex-wrap gap-1.5">
                    {details.disciplinas.map((d) => (
                      <button
                        key={d}
                        type="button"
                        onClick={() => onOpenDisciplina(d)}
                        className="rounded-full border border-line bg-ink px-3 py-1.5 text-left text-[12.5px] text-paper transition-colors hover:border-accent/50 hover:text-accent"
                      >
                        {d}
                      </button>
                    ))}
                  </div>
                </Section>
              )}
            </>
          )}
        </div>

        <div className="border-t border-line px-5 py-4">
          <button
            onClick={() => onAsk(`Quais as áreas de pesquisa de ${details?.nome || nome}?`)}
            className="flex items-center gap-1.5 rounded-lg border border-accent/40 bg-accent/10 px-3.5 py-2 text-[12.5px] text-accent transition-colors hover:bg-accent/20"
          >
            <MessageCircle className="h-3.5 w-3.5" />
            Perguntar no chat
          </button>
        </div>
      </motion.aside>
    </>
  )
}
