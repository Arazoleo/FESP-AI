import type { CSSProperties } from 'react'
import Link from 'next/link'
import { ArrowRight, ArrowDown } from 'lucide-react'
import ScrollFX from './components/ScrollFX'

// ─── Motivo visual: grafo de conhecimento ─────────────────────────────────────
// Nós e arestas nomeados com entidades reais do KG do FESP-AI.

const NODES: {
  id: string
  x: number
  y: number
  r: number
  label?: string
  pulse?: boolean
  delay?: string
}[] = [
  { id: 'curso', x: 96, y: 96, r: 5, label: 'curso', pulse: true },
  { id: 'disciplina', x: 258, y: 58, r: 6, label: 'disciplina', pulse: true, delay: '1.2s' },
  { id: 'docente', x: 408, y: 118, r: 5, label: 'docente', pulse: true, delay: '2.1s' },
  { id: 'prereq', x: 176, y: 208, r: 4, label: 'pré-requisito' },
  { id: 'carga', x: 340, y: 236, r: 4, label: 'carga horária' },
  { id: 'regimento', x: 84, y: 312, r: 4, label: 'regimento' },
  { id: 'matriz', x: 256, y: 336, r: 5, label: 'matriz curricular', pulse: true, delay: '3s' },
  { id: 'p1', x: 430, y: 320, r: 2.5 },
  { id: 'p2', x: 40, y: 200, r: 2.5 },
  { id: 'p3', x: 350, y: 30, r: 2.5 },
]

const EDGES: [string, string][] = [
  ['curso', 'disciplina'],
  ['disciplina', 'docente'],
  ['disciplina', 'prereq'],
  ['disciplina', 'carga'],
  ['curso', 'matriz'],
  ['matriz', 'prereq'],
  ['matriz', 'carga'],
  ['curso', 'regimento'],
  ['regimento', 'matriz'],
  ['docente', 'p1'],
  ['curso', 'p2'],
  ['disciplina', 'p3'],
]

function KnowledgeGraphFigure({ className }: { className?: string }) {
  const byId = Object.fromEntries(NODES.map((n) => [n.id, n]))
  return (
    <svg
      viewBox="0 0 480 400"
      className={className}
      data-graph
      role="img"
      aria-label="Representação de um grafo de conhecimento: cursos, disciplinas, docentes e regimentos conectados"
    >
      {EDGES.map(([a, b], i) => (
        <line
          key={i}
          x1={byId[a].x}
          y1={byId[a].y}
          x2={byId[b].x}
          y2={byId[b].y}
          stroke="#34d399"
          strokeOpacity={0.16}
          strokeWidth={1}
          className="edge-draw"
          style={{ animationDelay: `${0.15 + i * 0.12}s` }}
        />
      ))}
      {NODES.map((n, i) => (
        <g key={n.id} className="kg-node" style={{ animationDelay: `${0.3 + i * 0.1}s` }}>
          <circle
            cx={n.x}
            cy={n.y}
            r={n.r}
            fill="#34d399"
            fillOpacity={n.label ? 0.9 : 0.35}
            className={n.pulse ? 'node-pulse' : undefined}
            style={n.delay ? { animationDelay: n.delay } : undefined}
          />
          {n.label && (
            <text
              x={n.x + n.r + 8}
              y={n.y + 4}
              className="font-mono"
              fontSize="11"
              fill="#9aa8a2"
            >
              {n.label}
            </text>
          )}
        </g>
      ))}
    </svg>
  )
}

// ─── Conteúdo ─────────────────────────────────────────────────────────────────

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
      {/* Efeitos de scroll (barra de progresso, reveals, parallax, nav) */}
      <ScrollFX />

      {/* Grade de fundo sutil */}
      <div className="pointer-events-none fixed inset-0 bg-grid-faint" aria-hidden />

      {/* ── Nav ── */}
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
          <Link
            href="/chat"
            className="group flex items-center gap-2 font-mono text-xs uppercase tracking-widest text-paper-dim transition-colors hover:text-accent"
          >
            Abrir o assistente
            <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
          </Link>
        </div>
      </header>

      {/* ── Hero ── */}
      <section className="relative z-10 mx-auto max-w-6xl px-6 pb-24 pt-20 sm:pt-28">
        <div className="grid items-center gap-16 lg:grid-cols-[1.15fr_1fr]">
          <div>
            <p className="animate-rise rise-1 mb-6 font-mono text-xs uppercase tracking-[0.25em] text-accent">
              UNIFESP — Instituto de Ciência e Tecnologia
            </p>
            <h1 className="animate-rise rise-2 font-display text-5xl font-medium leading-[1.05] tracking-tightest sm:text-6xl lg:text-7xl">
              Perguntas acadêmicas.
              <br />
              Respostas <span className="text-accent">verificadas</span>.
            </h1>
            <p className="animate-rise rise-3 mt-8 max-w-xl text-lg leading-relaxed text-paper-dim">
              O FESP-AI responde sobre a vida acadêmica do campus São José dos
              Campos consultando um grafo de conhecimento montado a partir de
              documentos oficiais — e confere os fatos antes de responder.
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
              <KnowledgeGraphFigure className="w-full" />
              <p className="mt-4 text-center font-mono text-[11px] text-paper-mute">
                fragmento do grafo de conhecimento do campus
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ── Como funciona ── */}
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

      {/* ── Domínios ── */}
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
              <div
                key={d.n}
                data-reveal
                style={{ '--fxd': `${i * 110}ms` } as CSSProperties}
                className="group rounded-xl border border-line bg-ink-raise p-7 transition-colors hover:border-accent/30"
              >
                <div className="flex items-baseline justify-between">
                  <h3 className="font-display text-xl font-medium text-paper">{d.title}</h3>
                  <span className="font-mono text-xs text-paper-mute transition-colors group-hover:text-accent">
                    {d.n}
                  </span>
                </div>
                <p className="mt-3 text-sm leading-relaxed text-paper-dim">{d.text}</p>
              </div>
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

      {/* ── Footer ── */}
      <footer className="relative z-10 border-t border-line">
        <div className="mx-auto max-w-6xl px-6 py-10">
          <div data-reveal className="flex flex-col gap-6 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <span className="font-mono text-sm tracking-widest text-paper">FESP-AI</span>
              <p className="mt-2 text-sm text-paper-mute">
                Projeto acadêmico — UNIFESP, Instituto de Ciência e Tecnologia,
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
