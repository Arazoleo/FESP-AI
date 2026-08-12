'use client'

import { useEffect, useRef, useState } from 'react'
import { ShieldCheck, XCircle } from 'lucide-react'

type Caso = {
  afirmacao: string
  fatos: string[]
  corrigida: string
}

const CASOS: Caso[] = [
  {
    afirmacao: 'Compiladores não tem pré-requisitos, pode cursar direto.',
    fatos: [
      'PREREQUISITO_DE(Linguagens Formais e Autômatos → Compiladores)',
      'PREREQUISITO_DE(Algoritmos e Estruturas de Dados I → Compiladores)',
    ],
    corrigida: 'Compiladores exige LFA e Algoritmos e Estruturas de Dados I.',
  },
  {
    afirmacao: 'Para se formar no BCT bastam 3 UCs interdisciplinares.',
    fatos: ['PPC 2023: interdisciplinares_exigidas = 4'],
    corrigida: 'O PPC 2023 exige 4 UCs Eletivas Interdisciplinares.',
  },
  {
    afirmacao: 'Reprovar por falta não muda nada na disputa por vagas.',
    fatos: ['art. 143, III - sem reprovação por frequência na UC'],
    corrigida: 'Reprovação por frequência derruba sua prioridade de vaga (art. 143).',
  },
]

export default function VerifyDemo() {
  const [digitado, setDigitado] = useState('')
  const [fatosVisiveis, setFatosVisiveis] = useState(0)
  const [refutada, setRefutada] = useState(false)
  const [corrigida, setCorrigida] = useState(false)
  const [idx, setIdx] = useState(0)
  const vivo = useRef(true)

  useEffect(() => {
    vivo.current = true
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      const c = CASOS[0]
      setDigitado(c.afirmacao)
      setFatosVisiveis(c.fatos.length)
      setRefutada(true)
      setCorrigida(true)
      return
    }

    const esperar = (ms: number) =>
      new Promise<void>((res) => setTimeout(res, ms))

    const rodar = async () => {
      let i = 0
      while (vivo.current) {
        const caso = CASOS[i]
        setIdx(i)
        setDigitado('')
        setFatosVisiveis(0)
        setRefutada(false)
        setCorrigida(false)
        await esperar(600)

        for (let p = 1; p <= caso.afirmacao.length; p++) {
          if (!vivo.current) return
          setDigitado(caso.afirmacao.slice(0, p))
          await esperar(26)
        }
        await esperar(600)

        for (let f = 1; f <= caso.fatos.length; f++) {
          if (!vivo.current) return
          setFatosVisiveis(f)
          await esperar(650)
        }
        await esperar(400)

        setRefutada(true)
        await esperar(900)
        setCorrigida(true)
        await esperar(3800)

        i = (i + 1) % CASOS.length
      }
    }
    rodar()
    return () => {
      vivo.current = false
    }
  }, [])

  const caso = CASOS[idx]

  return (
    <div className="rounded-xl border border-line bg-ink-raise/80 p-6 backdrop-blur-xl">
      <div className="flex items-start gap-3">
        <span className="mt-0.5 w-14 flex-shrink-0 font-mono text-[10px] uppercase tracking-[0.15em] text-paper-mute">
          llm
        </span>
        <p
          className={`min-h-[1.4em] text-[14px] leading-relaxed transition-colors duration-500 ${
            refutada ? 'text-paper-mute line-through decoration-red-400/70 decoration-2' : 'text-paper'
          }`}
        >
          {digitado}
          {!refutada && digitado.length < caso.afirmacao.length && (
            <span className="caret-blink text-accent">▏</span>
          )}
        </p>
      </div>

      <div className="mt-4 flex items-start gap-3">
        <span className="mt-0.5 w-14 flex-shrink-0 font-mono text-[10px] uppercase tracking-[0.15em] text-paper-mute">
          grafo
        </span>
        <div className="min-h-[24px] space-y-1.5">
          {caso.fatos.slice(0, fatosVisiveis).map((f) => (
            <p key={f} className="demo-chip font-mono text-[11.5px] text-accent">
              {f}
            </p>
          ))}
          {refutada && (
            <p className="demo-chip flex items-center gap-1.5 font-mono text-[11.5px] text-red-400">
              <XCircle className="h-3.5 w-3.5" />
              afirmação refutada - reescrevendo com os fatos
            </p>
          )}
        </div>
      </div>

      <div className="mt-4 flex items-start gap-3 border-t border-line pt-4">
        <span className="mt-0.5 w-14 flex-shrink-0 font-mono text-[10px] uppercase tracking-[0.15em] text-accent">
          fesp-ai
        </span>
        <div className="min-h-[24px]">
          {corrigida && (
            <div className="demo-resposta flex flex-wrap items-center gap-2.5">
              <ShieldCheck className="h-4 w-4 flex-shrink-0 text-accent" />
              <span className="text-[14px] text-paper">{caso.corrigida}</span>
              <span className="rounded-md border border-accent/25 px-2 py-0.5 font-mono text-[9.5px] uppercase tracking-[0.14em] text-accent">
                verificado no grafo
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
