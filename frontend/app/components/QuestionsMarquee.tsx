import Link from 'next/link'

const PERGUNTAS = [
  'Quanto falta para me formar?',
  'Se eu reprovar em Cálculo, o que trava?',
  'Vai ter Compiladores no próximo semestre?',
  'Quantas horas de Atividades Complementares eu preciso?',
  'Quais os pré-requisitos de Compiladores?',
  'Se eu tirar 9 em POO, meu CR vai a quanto?',
  'Como faço para colar grau?',
  'Monte uma trilha para trabalhar com IA',
  'Bioestatística é interdisciplinar?',
  'Quem leciona Interação Humano-Computador?',
  'Posso me matricular em Redes de Computadores?',
  'Como funciona a rematrícula?',
]

function Faixa({ itens, reverso }: { itens: string[]; reverso?: boolean }) {
  const dobrado = [...itens, ...itens]
  return (
    <div className="marquee-mask overflow-hidden">
      <div className={`marquee-track flex w-max gap-3 ${reverso ? 'marquee-reverse' : ''}`}>
        {dobrado.map((q, i) => (
          <Link
            key={i}
            href={`/chat?q=${encodeURIComponent(q)}`}
            aria-hidden={i >= itens.length || undefined}
            tabIndex={i >= itens.length ? -1 : undefined}
            className="whitespace-nowrap rounded-full border border-line bg-ink-raise px-5 py-2.5 text-sm text-paper-dim transition-colors hover:border-accent/40 hover:text-accent"
          >
            {q}
          </Link>
        ))}
      </div>
    </div>
  )
}

export default function QuestionsMarquee() {
  const metade = Math.ceil(PERGUNTAS.length / 2)
  return (
    <div className="space-y-3" aria-label="Exemplos de perguntas que o FESP-AI responde">
      <Faixa itens={PERGUNTAS.slice(0, metade)} />
      <Faixa itens={PERGUNTAS.slice(metade)} reverso />
    </div>
  )
}
