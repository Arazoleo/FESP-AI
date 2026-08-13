'use client'

import { useCallback, useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { X, Route, Loader2, CalendarDays, AlertTriangle, FileUp } from 'lucide-react'

interface PlanDisciplina {
  nome: string
  creditos: number
  termo_sugerido: number
  paridade?: 'par' | 'impar' | null
  prereqs: string[]
}

interface PlanSemestre {
  numero: number
  rotulo?: string
  paridade?: string
  disciplinas: PlanDisciplina[]
  creditos: number
}

interface Plan {
  curso: string
  max_creditos: number
  completed: string[]
  eletivas_cursadas?: number
  obrigatorias_completas?: boolean
  semestres: PlanSemestre[]
  total_semestres: number
  total_disciplinas: number
  total_creditos: number
  avisos: string[]
  usou_historico?: boolean
}

interface Curso {
  nome: string
  sigla: string
}

interface Props {
  apiUrl: string
  conversationId: string | null
  historicoCarregado: boolean
  cursoInicial?: string | null
  onClose: () => void
  onOpenDiscipline: (nome: string) => void
}

export default function PlannerDrawer({
  apiUrl,
  conversationId,
  historicoCarregado,
  cursoInicial,
  onClose,
  onOpenDiscipline,
}: Props) {
  const [plan, setPlan] = useState<Plan | null>(null)
  const [cursos, setCursos] = useState<Curso[]>([])
  const [curso, setCurso] = useState(cursoInicial || '')
  const [maxCreditos, setMaxCreditos] = useState(24)
  const [loading, setLoading] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  const carregar = useCallback(
    (cursoSel: string, cred: number) => {
      setLoading(true)
      setErro(null)
      const params = new URLSearchParams()
      if (cursoSel) params.set('curso', cursoSel)
      params.set('max_creditos', String(cred))
      if (conversationId) params.set('conversation_id', conversationId)
      fetch(`${apiUrl}/plan?${params.toString()}`)
        .then(async (r) => {
          if (!r.ok) {
            const body = await r.json().catch(() => null)
            throw new Error(body?.detail || `${r.status}`)
          }
          return r.json()
        })
        .then((p: Plan) => {
          setPlan(p)
          if (!cursoSel) setCurso(p.curso)
        })
        .catch((e: Error) => {
          setPlan(null)
          setErro(e.message)
        })
        .finally(() => setLoading(false))
    },
    [apiUrl, conversationId]
  )

  useEffect(() => {
    fetch(`${apiUrl}/cursos`)
      .then((r) => r.json())
      .then((d) => setCursos(d.cursos || []))
      .catch(() => {})
    if (historicoCarregado || cursoInicial) {
      carregar(cursoInicial || '', 24)
    }
  }, [apiUrl, historicoCarregado, cursoInicial, carregar])

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
        aria-label="Planejador de trajetória"
        className="fixed right-0 top-0 z-50 flex h-full w-full flex-col border-l border-line bg-ink-raise sm:w-[480px]"
      >
        <div className="flex items-start justify-between gap-3 border-b border-line px-5 py-4">
          <div>
            <div className="flex items-center gap-2 font-mono text-[10.5px] uppercase tracking-[0.18em] text-paper-mute">
              <Route className="h-3.5 w-3.5" />
              Planejador de trajetória
            </div>
            <h2 className="mt-1 text-[17px] font-semibold leading-snug text-paper">
              {plan ? plan.curso : 'Monte sua grade'}
            </h2>
            {plan?.usou_historico && (
              <p className="mt-1 text-[11.5px] text-accent">
                calculada a partir do seu histórico ✓
              </p>
            )}
          </div>
          <button
            onClick={onClose}
            aria-label="Fechar planejador"
            className="rounded-lg border border-line p-2 text-paper-dim transition-colors hover:border-line-strong hover:text-paper"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex items-end gap-3 border-b border-line px-5 py-3.5">
          <label className="flex-1">
            <span className="mb-1 block font-mono text-[10px] uppercase tracking-[0.15em] text-paper-mute">
              Curso
            </span>
            <select
              value={curso}
              onChange={(e) => setCurso(e.target.value)}
              className="w-full rounded-lg border border-line bg-ink px-3 py-2 text-[13px] text-paper focus:border-accent/50 focus:outline-none"
            >
              <option value="">
                {historicoCarregado ? 'do meu histórico' : 'selecione...'}
              </option>
              {cursos.map((c) => (
                <option key={c.nome} value={c.sigla || c.nome}>
                  {c.nome}
                </option>
              ))}
            </select>
          </label>
          <label className="w-24">
            <span className="mb-1 block font-mono text-[10px] uppercase tracking-[0.15em] text-paper-mute">
              Créd/sem
            </span>
            <input
              type="number"
              min={4}
              max={40}
              value={maxCreditos}
              onChange={(e) => setMaxCreditos(Number(e.target.value) || 24)}
              className="w-full rounded-lg border border-line bg-ink px-3 py-2 text-[13px] text-paper focus:border-accent/50 focus:outline-none"
            />
          </label>
          <button
            onClick={() => carregar(curso, maxCreditos)}
            disabled={loading || (!curso && !historicoCarregado)}
            className="rounded-lg bg-accent px-4 py-2 text-[13px] font-medium text-ink transition-colors hover:bg-accent-deep disabled:cursor-not-allowed disabled:opacity-40"
          >
            Planejar
          </button>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto px-5 py-5">
          {loading && (
            <div className="flex items-center gap-2 text-sm text-paper-mute">
              <Loader2 className="h-4 w-4 animate-spin" />
              Montando a grade no Knowledge Graph...
            </div>
          )}
          {erro && <p className="text-sm text-red-300">{erro}</p>}

          {!loading && !erro && !plan && (
            <div className="rounded-xl border border-line bg-ink p-5 text-[13.5px] leading-relaxed text-paper-dim">
              {historicoCarregado ? (
                'Clique em Planejar para montar a grade dos seus próximos semestres.'
              ) : (
                <span className="flex items-start gap-2">
                  <FileUp className="mt-0.5 h-4 w-4 flex-shrink-0 text-accent" />
                  <span>
                    Envie seu <strong className="text-paper">Histórico Acadêmico</strong> pelo
                    botão no topo do chat e a grade sai personalizada - ou escolha
                    um curso acima para o plano completo.
                  </span>
                </span>
              )}
            </div>
          )}

          {plan && !loading && plan.obrigatorias_completas && (
            <div className="rounded-xl border border-accent/30 bg-accent/5 p-5">
              <p className="text-[14px] font-medium text-paper">
                ✓ Você já cumpriu todas as obrigatórias da matriz do {plan.curso}
              </p>
              <p className="mt-2 text-[12.5px] leading-relaxed text-paper-dim">
                Não há mais UCs fixas para planejar
                {plan.eletivas_cursadas
                  ? ` - e ${plan.eletivas_cursadas} eletivas suas já contam para a integralização`
                  : ''}
                . O que resta são eletivas à sua escolha: pergunte no chat
                *"quanto falta para me formar?"* para o quadro completo, ou
                *"monte uma trilha para..."* para eletivas do seu interesse.
              </p>
            </div>
          )}

          {plan && !loading && !plan.obrigatorias_completas && (
            <>
              <div className="grid grid-cols-3 gap-2">
                {[
                  { v: plan.total_semestres, r: 'semestres' },
                  { v: plan.total_disciplinas, r: 'disciplinas' },
                  { v: plan.total_creditos, r: 'créditos' },
                ].map((s) => (
                  <div
                    key={s.r}
                    className="rounded-xl border border-line bg-ink px-3 py-2.5 text-center"
                  >
                    <div className="font-display text-xl font-medium text-accent">{s.v}</div>
                    <div className="font-mono text-[9.5px] uppercase tracking-[0.14em] text-paper-mute">
                      {s.r}
                    </div>
                  </div>
                ))}
              </div>

              {plan.completed.length > 0 && (
                <p className="text-[11.5px] text-paper-mute">
                  {plan.completed.length} disciplinas já resolvidas (cursadas ou em curso)
                  ficam fora do plano.
                </p>
              )}

              <ol className="relative space-y-4 border-l border-line pl-5">
                {plan.semestres.map((s, i) => (
                  <motion.li
                    key={s.numero}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.07 }}
                    className="relative"
                  >
                    <span className="absolute -left-[27px] top-1 flex h-4 w-4 items-center justify-center rounded-full border border-accent/40 bg-ink">
                      <span className="h-1.5 w-1.5 rounded-full bg-accent" />
                    </span>
                    <div className="mb-2 flex items-baseline justify-between">
                      <span className="flex items-center gap-2 font-mono text-[12px] text-paper">
                        <CalendarDays className="h-3.5 w-3.5 text-accent" />
                        {s.rotulo || `Semestre ${s.numero}`}
                      </span>
                      <span className="font-mono text-[10.5px] text-paper-mute">
                        {s.creditos} créditos
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {s.disciplinas.map((d) => (
                        <button
                          key={d.nome}
                          type="button"
                          onClick={() => onOpenDiscipline(d.nome)}
                          title={
                            d.prereqs.length
                              ? `pré-requisitos: ${d.prereqs.join(', ')}`
                              : 'sem pré-requisitos'
                          }
                          className="rounded-full border border-line bg-ink px-3 py-1.5 text-left text-[12px] text-paper transition-colors hover:border-accent/50 hover:text-accent"
                        >
                          {d.nome}
                          <span className="ml-1.5 font-mono text-[9.5px] text-paper-mute">
                            {d.creditos}cr
                          </span>
                        </button>
                      ))}
                    </div>
                  </motion.li>
                ))}
              </ol>

              {plan.avisos.map((a) => (
                <p
                  key={a}
                  className="flex items-start gap-2 rounded-lg border border-amber-400/25 bg-amber-400/5 px-3.5 py-2.5 text-[12px] leading-relaxed text-amber-200/90"
                >
                  <AlertTriangle className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-amber-400" />
                  {a}
                </p>
              ))}

              <p className="border-t border-line pt-3 text-[11px] leading-relaxed text-paper-mute">
                Plano 100% simbólico: DAG de pré-requisitos + termo de referência +
                paridade de oferta (UCs de termo ímpar em X/1, par em X/2). A oferta
                real é definida pela coordenação a cada semestre - vale confirmar.
              </p>
            </>
          )}
        </div>
      </motion.aside>
    </>
  )
}
