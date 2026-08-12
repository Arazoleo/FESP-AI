'use client'

import { useEffect, useRef, useState } from 'react'
import { ShieldCheck, AlertTriangle } from 'lucide-react'
import LiveGraph from './LiveGraph'

type Cena = {
  pergunta: string
  nos: number[]
  regras: string[]
  resposta: string
  tom: 'ok' | 'alerta'
}

const CENAS: Cena[] = [
  {
    pergunta: 'Posso me matricular em Compiladores?',
    nos: [1, 3, 6],
    regras: ['unlock_condition', 'art. 143 - prioridade'],
    resposta: 'Sim - pré-requisitos cumpridos',
    tom: 'ok',
  },
  {
    pergunta: 'Se eu reprovar em Cálculo, o que trava?',
    nos: [1, 3, 0],
    regras: ['prereq_transitivity', 'critical_node (θ = 2)'],
    resposta: 'UCs bloqueadas em cascata - disciplina crítica',
    tom: 'alerta',
  },
  {
    pergunta: 'Quanto falta para me formar?',
    nos: [0, 6, 5],
    regras: ['PPC 2023', 'integralização'],
    resposta: 'Quadro requisito a requisito, direto do histórico',
    tom: 'ok',
  },
]

export default function HeroDemo() {
  const [digitado, setDigitado] = useState('')
  const [acesos, setAcesos] = useState<number[]>([])
  const [chips, setChips] = useState(0)
  const [resposta, setResposta] = useState<Cena | null>(null)
  const [cenaIdx, setCenaIdx] = useState(0)
  const vivo = useRef(true)

  useEffect(() => {
    vivo.current = true
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      const c = CENAS[0]
      setDigitado(c.pergunta)
      setAcesos(c.nos)
      setChips(c.regras.length)
      setResposta(c)
      return
    }

    const esperar = (ms: number) =>
      new Promise<void>((res) => setTimeout(res, ms))

    const rodar = async () => {
      let idx = 0
      while (vivo.current) {
        const cena = CENAS[idx]
        setCenaIdx(idx)
        setDigitado('')
        setAcesos([])
        setChips(0)
        setResposta(null)
        await esperar(700)

        for (let i = 1; i <= cena.pergunta.length; i++) {
          if (!vivo.current) return
          setDigitado(cena.pergunta.slice(0, i))
          await esperar(34)
        }
        await esperar(350)

        for (let i = 0; i < cena.nos.length; i++) {
          if (!vivo.current) return
          setAcesos(cena.nos.slice(0, i + 1))
          if (i < cena.regras.length) setChips(i + 1)
          await esperar(520)
        }
        setChips(cena.regras.length)
        await esperar(300)

        setResposta(cena)
        await esperar(3600)

        idx = (idx + 1) % CENAS.length
      }
    }
    rodar()
    return () => {
      vivo.current = false
    }
  }, [])

  const cena = CENAS[cenaIdx]

  return (
    <div className="relative h-[460px] w-full">
      <div className="absolute inset-x-0 top-0 h-[330px]">
        <LiveGraph highlight={acesos} className="h-full w-full" />
      </div>

      <div className="absolute inset-x-0 bottom-0 rounded-xl border border-line bg-ink-raise/80 p-5 backdrop-blur-xl">
        <div className="flex items-center gap-2 font-mono text-[13px] text-paper">
          <span className="text-accent">❯</span>
          <span className="min-h-[1.2em]">{digitado}</span>
          {!resposta && <span className="caret-blink text-accent">▏</span>}
        </div>

        <div className="mt-3 flex min-h-[26px] flex-wrap gap-2">
          {cena.regras.slice(0, chips).map((r) => (
            <span
              key={r}
              className="demo-chip rounded-full border border-accent/30 bg-accent/10 px-3 py-1 font-mono text-[10.5px] text-accent"
            >
              ⚙ {r}
            </span>
          ))}
        </div>

        <div className="mt-3 min-h-[24px]">
          {resposta && (
            <div className="demo-resposta flex items-center gap-2.5">
              {resposta.tom === 'ok' ? (
                <ShieldCheck className="h-4 w-4 flex-shrink-0 text-accent" />
              ) : (
                <AlertTriangle className="h-4 w-4 flex-shrink-0 text-amber-400" />
              )}
              <span className="text-[13.5px] text-paper">{resposta.resposta}</span>
              <span className="ml-auto hidden rounded-md border border-accent/25 px-2 py-0.5 font-mono text-[9.5px] uppercase tracking-[0.14em] text-accent sm:block">
                verificado no grafo
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
