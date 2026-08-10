'use client'

import { useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import PrereqGraph, { PrereqGraphData } from './PrereqGraph'
import {
  X,
  BookOpen,
  Users,
  Lock,
  Unlock,
  GraduationCap,
  MessageCircle,
  Loader2,
} from 'lucide-react'

interface Prerequisito {
  nome: string
  confidence: number
}

interface Matriz {
  matriz: string
  termo?: number | string | null
  creditos?: number | string | null
}

export interface DisciplineDetails {
  nome: string
  codigo?: string | null
  sigla?: string | null
  termo?: number | string | null
  ementa?: string | null
  docentes: string[]
  prerequisitos: Prerequisito[]
  desbloqueia: string[]
  cursos: string[]
  matrizes: Matriz[]
  eletiva_em: string[]
}

interface Props {
  nome: string
  apiUrl: string
  onClose: () => void
  onNavigate: (nome: string) => void
  onOpenDocente?: (nome: string) => void
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

function Pill({
  label,
  hint,
  onClick,
}: {
  label: string
  hint?: string
  onClick?: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={!onClick}
      className="rounded-full border border-line bg-ink px-3 py-1.5 text-left text-[12.5px] text-paper transition-colors enabled:hover:border-accent/50 enabled:hover:text-accent disabled:cursor-default"
    >
      {label}
      {hint && <span className="ml-1.5 text-[10.5px] text-paper-mute">{hint}</span>}
    </button>
  )
}

export default function DisciplineDrawer({
  nome,
  apiUrl,
  onClose,
  onNavigate,
  onOpenDocente,
  onAsk,
}: Props) {
  const [details, setDetails] = useState<DisciplineDetails | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const miniGraph = useMemo<PrereqGraphData | null>(() => {
    if (!details) return null
    const edges = [
      ...details.prerequisitos.map((p) => ({
        source: p.nome,
        target: details.nome,
        confidence: p.confidence,
      })),
      ...details.desbloqueia.map((d) => ({
        source: details.nome,
        target: d,
        confidence: 1,
      })),
    ]
    if (!edges.length) return null
    const nodes = [
      { id: details.nome, nome: details.nome },
      ...details.prerequisitos.map((p) => ({ id: p.nome, nome: p.nome })),
      ...details.desbloqueia.map((d) => ({ id: d, nome: d })),
    ]
    return { nodes, edges }
  }, [details])

  useEffect(() => {
    let ativo = true
    setLoading(true)
    setError(null)
    fetch(`${apiUrl}/discipline-details?nome=${encodeURIComponent(nome)}`)
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status}`)
        return r.json()
      })
      .then((d) => {
        if (ativo) setDetails(d)
      })
      .catch(() => {
        if (ativo) setError('Não encontrei os detalhes dessa disciplina na base.')
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

  const chips = [
    details?.codigo && `Código ${details.codigo}`,
    details?.sigla && details.sigla,
    details?.termo && `Termo ${details.termo}`,
  ].filter(Boolean) as string[]

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
        aria-label={`Detalhes da disciplina ${nome}`}
        className="fixed right-0 top-0 z-50 flex h-full w-full flex-col border-l border-line bg-ink-raise sm:w-[400px]"
      >
        <div className="flex items-start justify-between gap-3 border-b border-line px-5 py-4">
          <div>
            <div className="font-mono text-[10.5px] uppercase tracking-[0.18em] text-paper-mute">
              Disciplina
            </div>
            <h2 className="mt-1 text-[17px] font-semibold leading-snug text-paper">
              {details?.nome || nome}
            </h2>
            {chips.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {chips.map((c) => (
                  <span
                    key={c}
                    className="rounded-md border border-line bg-ink px-2 py-0.5 font-mono text-[10.5px] text-paper-dim"
                  >
                    {c}
                  </span>
                ))}
              </div>
            )}
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
              {miniGraph && (
                <PrereqGraph
                  data={miniGraph}
                  onSelect={(n) => {
                    if (n !== details.nome) onNavigate(n)
                  }}
                />
              )}

              {details.ementa && (
                <Section icon={<BookOpen className="h-3.5 w-3.5" />} title="Ementa">
                  <p className="text-[13.5px] leading-relaxed text-paper-dim">
                    {details.ementa}
                  </p>
                </Section>
              )}

              {details.docentes.length > 0 && (
                <Section icon={<Users className="h-3.5 w-3.5" />} title="Docentes">
                  <div className="flex flex-wrap gap-1.5">
                    {details.docentes.map((d) => (
                      <Pill
                        key={d}
                        label={d}
                        onClick={onOpenDocente ? () => onOpenDocente(d) : undefined}
                      />
                    ))}
                  </div>
                </Section>
              )}

              <Section icon={<Lock className="h-3.5 w-3.5" />} title="Pré-requisitos">
                {details.prerequisitos.length ? (
                  <div className="flex flex-wrap gap-1.5">
                    {details.prerequisitos.map((p) => (
                      <Pill
                        key={p.nome}
                        label={p.nome}
                        hint={p.confidence < 1 ? `${Math.round(p.confidence * 100)}%` : undefined}
                        onClick={() => onNavigate(p.nome)}
                      />
                    ))}
                  </div>
                ) : (
                  <p className="text-[13px] text-paper-mute">
                    Nenhum pré-requisito formal.
                  </p>
                )}
              </Section>

              {details.desbloqueia.length > 0 && (
                <Section icon={<Unlock className="h-3.5 w-3.5" />} title="Desbloqueia">
                  <div className="flex flex-wrap gap-1.5">
                    {details.desbloqueia.map((d) => (
                      <Pill key={d} label={d} onClick={() => onNavigate(d)} />
                    ))}
                  </div>
                </Section>
              )}

              {(details.matrizes.length > 0 || details.eletiva_em.length > 0) && (
                <Section
                  icon={<GraduationCap className="h-3.5 w-3.5" />}
                  title="Nos cursos"
                >
                  <ul className="space-y-1.5">
                    {details.matrizes.map((m, i) => (
                      <li key={`${m.matriz}-${i}`} className="text-[13.5px] text-paper-dim">
                        {m.matriz}
                        {m.termo ? ` · termo ${m.termo}` : ''}
                        {m.creditos ? ` · ${m.creditos} créditos` : ''}
                      </li>
                    ))}
                    {details.eletiva_em.map((e) => (
                      <li key={e} className="text-[13.5px] text-paper-dim">
                        {e} · eletiva
                      </li>
                    ))}
                  </ul>
                </Section>
              )}
            </>
          )}
        </div>

        <div className="border-t border-line px-5 py-4">
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => onAsk(`Quais os pré-requisitos de ${details?.nome || nome}?`)}
              className="flex items-center gap-1.5 rounded-lg border border-accent/40 bg-accent/10 px-3.5 py-2 text-[12.5px] text-accent transition-colors hover:bg-accent/20"
            >
              <MessageCircle className="h-3.5 w-3.5" />
              Cadeia de pré-requisitos
            </button>
            <button
              onClick={() => onAsk(`Quem leciona ${details?.nome || nome}?`)}
              className="flex items-center gap-1.5 rounded-lg border border-line px-3.5 py-2 text-[12.5px] text-paper-dim transition-colors hover:border-line-strong hover:text-paper"
            >
              <Users className="h-3.5 w-3.5" />
              Quem leciona
            </button>
          </div>
        </div>
      </motion.aside>
    </>
  )
}
