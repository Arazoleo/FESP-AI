'use client'

import { useEffect, useRef, useState } from 'react'
import { CheckCircle2, CircleDashed, FileText } from 'lucide-react'

const LINHAS_DOC = [
  '5702 - CÁLCULO EM UMA VARIÁVEL          108h  9,4  APROVADO',
  '9394 - LÓGICA DE PROGRAMAÇÃO             72h  8,7  APROVADO',
  '2832 - ALGORITMOS E ESTRUTURAS DE DADOS  72h  7,9  APROVADO',
  '2609 - PROBABILIDADE E ESTATÍSTICA       72h  8,1  APROVADO',
  '8240 - PRÁTICA EM PROJETOS EXT. I        72h  10   APROVADO',
  '5168 - PROJETO ORIENTADO A OBJETOS       72h  9,2  APROVADO',
  'RESUMO   FIXAS 468   ELETIVAS 2016   EXT 248',
]

const ITENS = [
  { rotulo: 'UCs fixas', atual: 468, meta: 468 },
  { rotulo: 'UCs eletivas', atual: 2016, meta: 1620 },
  { rotulo: 'Extensão', atual: 248, meta: 240 },
  { rotulo: 'Interdisciplinares', atual: 6, meta: 4, unidade: ' UCs' },
]

const TOTAL_PASSOS = ITENS.length + 3

export default function HistoricoScan() {
  const [passo, setPasso] = useState(0)
  const vivo = useRef(true)

  useEffect(() => {
    vivo.current = true
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setPasso(TOTAL_PASSOS)
      return
    }
    const esperar = (ms: number) =>
      new Promise<void>((res) => setTimeout(res, ms))
    const rodar = async () => {
      while (vivo.current) {
        setPasso(0)
        await esperar(900)
        for (let p = 1; p <= TOTAL_PASSOS; p++) {
          if (!vivo.current) return
          setPasso(p)
          await esperar(p === TOTAL_PASSOS ? 4200 : 750)
        }
      }
    }
    rodar()
    return () => {
      vivo.current = false
    }
  }, [])

  const progresso = Math.min(1, passo / TOTAL_PASSOS)

  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_1.05fr]">
      <div className="relative overflow-hidden rounded-xl border border-line bg-ink-raise/80 p-5 backdrop-blur-xl">
        <div className="mb-4 flex items-center gap-2 font-mono text-[10.5px] uppercase tracking-[0.18em] text-paper-mute">
          <FileText className="h-3.5 w-3.5" />
          historico_academico.pdf
        </div>
        <div className="space-y-2.5">
          {LINHAS_DOC.map((l, i) => (
            <p
              key={i}
              className={`whitespace-nowrap font-mono text-[10.5px] transition-colors duration-500 ${
                progresso * LINHAS_DOC.length > i ? 'text-paper-dim' : 'text-paper-mute/40'
              }`}
            >
              {l}
            </p>
          ))}
        </div>
        <div
          className="pointer-events-none absolute inset-x-0 h-10"
          style={{
            top: `${14 + progresso * 72}%`,
            background:
              'linear-gradient(180deg, transparent, rgb(var(--accent-rgb) / 0.12) 50%, transparent)',
            borderBottom: '1px solid rgb(var(--accent-rgb) / 0.5)',
            transition: 'top 0.7s cubic-bezier(0.4, 0, 0.2, 1)',
            opacity: passo > 0 && passo < TOTAL_PASSOS ? 1 : 0,
          }}
        />
      </div>

      <div className="rounded-xl border border-line bg-ink-raise/80 p-5 backdrop-blur-xl">
        <div className="mb-4 flex items-baseline justify-between">
          <span className="font-mono text-[10.5px] uppercase tracking-[0.18em] text-paper-mute">
            integralização - BCT
          </span>
          <span className="font-mono text-[13px] text-paper">
            CR{' '}
            <span className="text-accent">{passo >= 1 ? '8.02' : '-.--'}</span>
          </span>
        </div>
        <div className="space-y-3.5">
          {ITENS.map((item, i) => {
            const ativo = passo >= i + 2
            const pct = Math.min(1, item.atual / item.meta) * 100
            return (
              <div key={item.rotulo}>
                <div className="mb-1 flex items-center justify-between text-[12px]">
                  <span className="flex items-center gap-1.5 text-paper-dim">
                    {ativo ? (
                      <CheckCircle2 className="demo-chip h-3.5 w-3.5 text-accent" />
                    ) : (
                      <CircleDashed className="h-3.5 w-3.5 text-paper-mute/50" />
                    )}
                    {item.rotulo}
                  </span>
                  <span className="font-mono text-[11px] text-paper-mute">
                    {ativo ? `${item.atual}${item.unidade || 'h'} de ${item.meta}${item.unidade || 'h'}` : '...'}
                  </span>
                </div>
                <div className="h-1 overflow-hidden rounded-full bg-line">
                  <div
                    className="h-full rounded-full bg-accent"
                    style={{
                      width: ativo ? `${pct}%` : '0%',
                      transition: 'width 0.8s cubic-bezier(0.16, 1, 0.3, 1)',
                    }}
                  />
                </div>
              </div>
            )
          })}
          <div className="flex items-center justify-between border-t border-line pt-3 text-[12px]">
            <span className="flex items-center gap-1.5 text-paper-dim">
              {passo >= TOTAL_PASSOS ? (
                <span className="demo-chip text-amber-400">…</span>
              ) : (
                <CircleDashed className="h-3.5 w-3.5 text-paper-mute/50" />
              )}
              Atividades Complementares
            </span>
            <span className="font-mono text-[11px] text-paper-mute">
              {passo >= TOTAL_PASSOS ? 'a confirmar via SEI' : '...'}
            </span>
          </div>
        </div>
        <p className="mt-4 border-t border-line pt-3 text-[11px] leading-relaxed text-paper-mute">
          Os dados ficam apenas na conversa e são descartados depois - sem conta,
          sem servidor.
        </p>
      </div>
    </div>
  )
}
