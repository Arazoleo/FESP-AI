import type { CSSProperties } from 'react'
import Link from 'next/link'
import { ArrowRight, ArrowDown } from 'lucide-react'
import ThemeToggle from './components/ThemeToggle'
import ScrollFX from './components/ScrollFX'
import LiveGraph from './components/LiveGraph'
import DecryptText from './components/DecryptText'
import SpotlightCard from './components/SpotlightCard'
import CountUp from './components/CountUp'
import QuestionsMarquee from './components/QuestionsMarquee'

const STATS = [
  { valor: 7, sufixo: '', rotulo: 'cursos do ICT cobertos' },
  { valor: 383, sufixo: '', rotulo: 'UCs no quadro oficial' },
  { valor: 527, sufixo: '', rotulo: 'páginas do site indexadas' },
  { valor: 6, sufixo: '', rotulo: 'regras de inferência simbólica' },
]

const PIPELINE_STEPS = [
  {
    n: '01',
    title: 'Interpretação',
    text: 'A pergunta é classificada e encaminhada ao agente certo: disciplinas, docentes, cursos ou regimentos.',
  },
  {
    n: '02',
    title: 'Consulta ao grafo',
    text: 'Entidades e relações são buscadas no Knowledge Graph, construído a partir das matrizes curriculares e dos regimentos oficiais do campus.',
  },
  {
    n: '03',
    title: 'Recuperação de documentos',
    text: 'Trechos relevantes dos documentos originais complementam o contexto usado para escrever a resposta.',
  },
  {
    n: '04',
    title: 'Verificação',
    text: 'Antes de chegar até você, os fatos citados na resposta são conferidos contra o grafo.',
  },
]

const DOMAINS = [
  {
    n: '01',
    title: 'Disciplinas',
    text: 'Ementas, pré-requisitos, carga horária teórica e prática de cada unidade curricular.',
  },
  {
    n: '02',
    title: 'Docentes',
    text: 'Quem leciona cada disciplina e em quais cursos atua.',
  },
  {
    n: '03',
    title: 'Cursos',
    text: 'Matrizes curriculares e estrutura dos cursos de graduação do ICT.',
  },
  {
    n: '04',
    title: 'Regimentos',
    text: 'Normas, prazos e regulamentos institucionais, com referência aos artigos.',
  },
]

export default function LandingPage() {
  return (
    <div className="relative min-h-screen bg-ink text-paper">
      <ScrollFX />

      <div className="pointer-events-none fixed inset-0 bg-grid-faint" aria-hidden />

      <header data-nav className="site-nav sticky top-0 z-40">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
          <div className="flex items-center gap-3">
            <svg viewBox="0 0 24 24" className="h-5 w-5" aria-hidden>
              <line x1="5" y1="18" x2="12" y2="6" stroke="#34d399" strokeOpacity="0.5" strokeWidth="1.2" />
              <line x1="12" y1="6" x2="19" y2="16" stroke="#34d399" strokeOpacity="0.5" strokeWidth="1.2" />
              <line x1="5" y1="18" x2="19" y2="16" stroke="#34d399" strokeOpacity="0.5" strokeWidth="1.2" />
              <circle cx="5" cy="18" r="2.4" fill="#34d399" />
              <circle cx="12" cy="6" r="2.4" fill="#34d399" />
              <circle cx="19" cy="16" r="2.4" fill="#34d399" />
            </svg>
            <span className="font-mono text-sm tracking-widest text-paper">FESP-AI</span>
          </div>
          <div className="flex items-center gap-3">
            <ThemeToggle />
            <Link
              href="/chat"
              className="group flex items-center gap-2 font-mono text-xs uppercase tracking-widest text-paper-dim transition-colors hover:text-accent"
            >
              Abrir o assistente
              <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
            </Link>
          </div>
        </div>
      </header>

      <section className="relative z-10 mx-auto max-w-6xl px-6 pb-24 pt-20 sm:pt-28">
        <div className="grid items-center gap-16 lg:grid-cols-[1.15fr_1fr]">
          <div>
            <p className="animate-rise rise-1 mb-6 font-mono text-xs uppercase tracking-[0.25em] text-accent">
              UNIFESP - Instituto de Ciência e Tecnologia
            </p>
            <h1 className="animate-rise rise-2 font-display text-5xl font-medium leading-[1.05] tracking-tightest sm:text-6xl lg:text-7xl">
              Perguntas acadêmicas.
              <br />
              Respostas{' '}
              <DecryptText text="verificadas" delay={500} className="text-accent" />.
            </h1>
            <p className="animate-rise rise-3 mt-8 max-w-xl text-lg leading-relaxed text-paper-dim">
              O FESP-AI responde sobre a vida acadêmica do campus São José dos
              Campos consultando um grafo de conhecimento montado a partir de
              documentos oficiais - e confere os fatos antes de responder.
            </p>
            <div className="animate-rise rise-4 mt-10 flex flex-wrap items-center gap-6">
              <Link
                href="/chat"
                className="group inline-flex items-center gap-3 rounded-lg bg-accent px-7 py-3.5 font-medium text-ink transition-colors hover:bg-accent-deep"
              >
                Abrir o assistente
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
              </Link>
              <a
                href="#como-funciona"
                className="inline-flex items-center gap-2 font-mono text-xs uppercase tracking-widest text-paper-mute transition-colors hover:text-paper-dim"
              >
                Como funciona
                <ArrowDown className="h-3.5 w-3.5" />
              </a>
            </div>
          </div>

          <div className="animate-rise rise-5 hidden lg:block">
            <div data-parallax="0.05">
              <div className="h-[400px] w-full">
                <LiveGraph className="h-full w-full" />
              </div>
              <p className="mt-4 text-center font-mono text-[11px] text-paper-mute">
                fragmento vivo do grafo de conhecimento do campus
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="relative z-10 border-t border-line">
        <div className="mx-auto max-w-6xl px-6 py-14">
          <div data-reveal className="grid grid-cols-2 gap-8 lg:grid-cols-4">
            {STATS.map((s) => (
              <div key={s.rotulo} className="text-center">
                <CountUp
                  value={s.valor}
                  suffix={s.sufixo}
                  className="font-display text-4xl font-medium text-accent sm:text-5xl"
                />
                <p className="mt-2 font-mono text-[11px] uppercase tracking-[0.15em] text-paper-mute">
                  {s.rotulo}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="relative z-10 border-t border-line py-14">
        <div data-reveal className="mx-auto mb-8 max-w-6xl px-6">
          <p className="font-mono text-xs uppercase tracking-[0.25em] text-accent">
            Pergunte de verdade
          </p>
        </div>
        <div data-reveal>
          <QuestionsMarquee />
        </div>
      </section>

      <section id="como-funciona" className="relative z-10 border-t border-line">
        <div className="mx-auto max-w-6xl px-6 py-24">
          <div data-reveal className="mb-14 max-w-2xl">
            <p className="mb-4 font-mono text-xs uppercase tracking-[0.25em] text-accent">
              Como funciona
            </p>
            <h2 className="font-display text-3xl font-medium tracking-tightest sm:text-4xl">
              Cada resposta percorre o mesmo caminho
            </h2>
          </div>

          <ol className="grid gap-px overflow-hidden rounded-xl border border-line bg-line md:grid-cols-2 lg:grid-cols-4">
            {PIPELINE_STEPS.map((step, i) => (
              <li
                key={step.n}
                data-reveal
                style={{ '--fxd': `${i * 110}ms` } as CSSProperties}
                className="bg-ink-raise p-7"
              >
                <span className="step-num font-mono text-xs text-accent">{step.n}</span>
                <h3 className="mt-4 font-display text-lg font-medium text-paper">
                  {step.title}
                </h3>
                <p className="mt-3 text-sm leading-relaxed text-paper-dim">{step.text}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="relative z-10 border-t border-line">
        <div className="mx-auto max-w-6xl px-6 py-24">
          <div data-reveal className="mb-14 max-w-2xl">
            <p className="mb-4 font-mono text-xs uppercase tracking-[0.25em] text-accent">
              Escopo
            </p>
            <h2 className="font-display text-3xl font-medium tracking-tightest sm:text-4xl">
              Sobre o que você pode perguntar
            </h2>
          </div>

          <div className="grid gap-5 sm:grid-cols-2">
            {DOMAINS.map((d, i) => (
              <SpotlightCard
                key={d.n}
                style={{ '--fxd': `${i * 110}ms` } as CSSProperties}
                className="group rounded-xl border border-line bg-ink-raise p-7 transition-colors hover:border-accent/30"
              >
                <div data-reveal>
                  <div className="flex items-baseline justify-between">
                    <h3 className="font-display text-xl font-medium text-paper">{d.title}</h3>
                    <span className="font-mono text-xs text-paper-mute transition-colors group-hover:text-accent">
                      {d.n}
                    </span>
                  </div>
                  <p className="mt-3 text-sm leading-relaxed text-paper-dim">{d.text}</p>
                </div>
              </SpotlightCard>
            ))}
          </div>

          <div data-reveal className="mt-16 flex justify-center">
            <Link
              href="/chat"
              className="group inline-flex items-center gap-3 rounded-lg border border-line-strong px-7 py-3.5 font-medium text-paper transition-colors hover:border-accent/50 hover:text-accent"
            >
              Fazer uma pergunta
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
            </Link>
          </div>
        </div>
      </section>

      <footer className="relative z-10 border-t border-line">
        <div className="mx-auto max-w-6xl px-6 py-10">
          <div data-reveal className="flex flex-col gap-6 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <span className="font-mono text-sm tracking-widest text-paper">FESP-AI</span>
              <p className="mt-2 text-sm text-paper-mute">
                Projeto acadêmico - UNIFESP, Instituto de Ciência e Tecnologia,
                São José dos Campos.
              </p>
            </div>
            <p className="max-w-md text-xs leading-relaxed text-paper-mute sm:text-right">
              As respostas são geradas automaticamente e podem conter erros.
              Confirme informações importantes nas fontes oficiais da UNIFESP.
            </p>
          </div>
        </div>
      </footer>
    </div>
  )
}
