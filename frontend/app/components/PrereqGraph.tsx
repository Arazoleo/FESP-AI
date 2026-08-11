'use client'

import { useMemo } from 'react'

export interface PrereqGraphNode {
  id: string
  nome: string
  fase?: number
  cursada?: boolean
  inferida?: boolean
}

export interface PrereqGraphEdge {
  source: string
  target: string
  confidence: number
  inferida?: boolean
}

export interface PrereqGraphData {
  type?: string
  nodes: PrereqGraphNode[]
  edges: PrereqGraphEdge[]
}

interface Props {
  data: PrereqGraphData
  onAsk?: (question: string) => void
  onSelect?: (nome: string) => void
}

const NODE_H = 34
const V_GAP = 22
const COL_GAP = 84
const PAD = 20
const HEADER_H = 26
const MAX_LABEL = 26
const CHAR_W = 6.8

const C = {
  pillFill: 'var(--g-pill)',
  pillStroke: 'var(--g-pill-stroke)',
  pillStrokeRoot: 'rgb(var(--accent-rgb) / 0.55)',
  text: 'var(--g-text)',
  textMute: 'var(--g-text-mute)',
  edge: 'var(--g-edge)',
  accent: 'var(--accent)',
  amber: '#fbbf24',
  amberDim: 'rgba(251, 191, 36, 0.55)',
} as const

function truncate(nome: string): string {
  return nome.length > MAX_LABEL ? `${nome.slice(0, MAX_LABEL - 1)}…` : nome
}

function pillLabel(node: PrereqGraphNode, pct?: number): string {
  const base = truncate(node.nome)
  return pct !== undefined ? `${base} · ${pct}%` : base
}

function pillWidth(node: PrereqGraphNode, pct?: number): number {
  const label = pillLabel(node, pct)
  return Math.round(label.length * CHAR_W + 30 + (node.cursada ? 18 : 0))
}

interface LaidNode extends PrereqGraphNode {
  x: number
  y: number
  w: number
  layer: number
  pct?: number
}

function computeLayout(data: PrereqGraphData) {
  const nodes = data?.nodes || []
  if (!nodes.length) {
    return {
      laid: new Map<string, LaidNode>(),
      edges: [] as PrereqGraphEdge[],
      colHeaders: [] as { label: string; x: number; w: number }[],
      width: 0,
      height: 0,
    }
  }
  const edges = (data.edges || []).filter(
    (e) =>
      nodes.some((n) => n.id === e.source) &&
      nodes.some((n) => n.id === e.target),
  )
  const hasFases = nodes.some((n) => typeof n.fase === 'number')

  const layerOf = new Map<string, number>()
  if (hasFases) {
    nodes.forEach((n) => layerOf.set(n.id, n.fase ?? 0))
  } else {
    nodes.forEach((n) => layerOf.set(n.id, 0))
    for (let pass = 0; pass < nodes.length; pass++) {
      let changed = false
      for (const e of edges) {
        const next = (layerOf.get(e.source) ?? 0) + 1
        if (next > (layerOf.get(e.target) ?? 0) && next < nodes.length) {
          layerOf.set(e.target, next)
          changed = true
        }
      }
      if (!changed) break
    }
  }

  const layerIds = Array.from(new Set(Array.from(layerOf.values()))).sort(
    (a, b) => a - b,
  )
  const columns = layerIds.map((l) =>
    nodes.filter((n) => layerOf.get(n.id) === l),
  )

  const showHeaders = hasFases
  const topY = PAD + (showHeaders ? HEADER_H : 0)
  const maxRows = Math.max(...columns.map((c) => c.length), 1)
  const height = topY + maxRows * (NODE_H + V_GAP) - V_GAP + PAD

  const pctOf = new Map<string, number>()
  edges.forEach((e) => {
    if (e.inferida) {
      pctOf.set(e.source, Math.round(e.confidence * 100))
    }
  })

  const laid = new Map<string, LaidNode>()
  const colHeaders: { label: string; x: number; w: number }[] = []
  let x = PAD
  columns.forEach((col, ci) => {
    const w = Math.max(...col.map((n) => pillWidth(n, pctOf.get(n.id))), 60)
    const colH = col.length * (NODE_H + V_GAP) - V_GAP
    const startY = topY + Math.max(0, (height - topY - PAD - colH) / 2)
    col.forEach((n, ri) => {
      laid.set(n.id, {
        ...n,
        x,
        y: startY + ri * (NODE_H + V_GAP),
        w,
        layer: ci,
        pct: pctOf.get(n.id),
      })
    })
    if (showHeaders) {
      const allCursada = col.every((n) => n.cursada)
      colHeaders.push({
        label: allCursada ? 'Cursadas' : `Fase ${layerIds[ci]}`,
        x,
        w,
      })
    }
    x += w + COL_GAP
  })
  const width = x - COL_GAP + PAD

  return { laid, edges, colHeaders, width, height }
}

export default function PrereqGraph({ data, onAsk, onSelect }: Props) {
  const layout = useMemo(() => computeLayout(data), [data])

  if (!data?.nodes?.length) return null
  const { laid, edges, colHeaders, width, height } = layout
  const rootId = data.nodes[0]?.id
  const hasInferidas = edges.some((e) => e.inferida)

  const ask = (nome: string) => {
    if (onSelect) {
      onSelect(nome)
      return
    }
    onAsk?.(`Quais os pré-requisitos de ${nome}?`)
  }

  return (
    <div className="mb-4 rounded-xl border border-line bg-ink-deep/70">
      <div className="flex items-baseline justify-between gap-3 border-b border-line px-4 py-2.5">
        <span className="font-mono text-[10.5px] uppercase tracking-[0.18em] text-paper-mute">
          Grafo de pré-requisitos
        </span>
        <span className="hidden text-[11px] text-paper-mute sm:block">
          Clique numa disciplina para ver os detalhes
        </span>
      </div>

      <div className="p-3">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-label="Grafo interativo de pré-requisitos entre disciplinas"
          style={{ width: '100%', maxWidth: width, height: 'auto', display: 'block', margin: '0 auto' }}
        >
          <defs>
            <marker
              id="prereq-arrow"
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="7"
              markerHeight="7"
              orient="auto-start-reverse"
            >
              <path d="M 0 1 L 9 5 L 0 9 z" style={{ fill: C.edge }} />
            </marker>
            <marker
              id="prereq-arrow-inferida"
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="7"
              markerHeight="7"
              orient="auto-start-reverse"
            >
              <path d="M 0 1 L 9 5 L 0 9 z" style={{ fill: C.amberDim }} />
            </marker>
          </defs>

          {colHeaders.map((h) => (
            <text
              key={h.label + h.x}
              x={h.x + h.w / 2}
              y={PAD + 8}
              textAnchor="middle"
              style={{ fill: C.textMute, letterSpacing: '0.14em' }}
              fontSize={10}
              className="prereq-in font-mono uppercase"
            >
              {h.label}
            </text>
          ))}

          {edges.map((e, i) => {
            const s = laid.get(e.source)
            const t = laid.get(e.target)
            if (!s || !t) return null
            const x1 = s.x + s.w
            const y1 = s.y + NODE_H / 2
            const x2 = t.x - 3
            const y2 = t.y + NODE_H / 2
            const mx = (x1 + x2) / 2
            const partial = e.confidence < 1
            const inferida = Boolean(e.inferida)
            return (
              <g
                key={`${e.source}->${e.target}`}
                className="prereq-in"
                style={{ animationDelay: `${140 + s.layer * 110 + i * 25}ms` }}
              >
                <path
                  d={`M ${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}`}
                  fill="none"
                  style={{ stroke: inferida ? C.amberDim : C.edge }}
                  strokeWidth={1.4}
                  strokeDasharray={partial || inferida ? '5 4' : undefined}
                  markerEnd={
                    inferida
                      ? 'url(#prereq-arrow-inferida)'
                      : 'url(#prereq-arrow)'
                  }
                />
                {!inferida && partial && (
                  <text
                    x={mx}
                    y={(y1 + y2) / 2 - 6}
                    textAnchor="middle"
                    style={{ fill: C.textMute }}
                    fontSize={10}
                    className="font-mono"
                  >
                    {Math.round(e.confidence * 100)}%
                  </text>
                )}
              </g>
            )
          })}

          {Array.from(laid.values()).map((n, i) => {
            const label = pillLabel(n, n.pct)
            const isRoot = n.id === rootId
            return (
              <g
                key={n.id}
                transform={`translate(${n.x}, ${n.y})`}
                className="prereq-node prereq-in"
                style={{ animationDelay: `${n.layer * 110 + i * 20}ms` }}
                role="button"
                tabIndex={0}
                aria-label={`Ver detalhes de ${n.nome}`}
                onClick={() => ask(n.nome)}
                onKeyDown={(ev) => {
                  if (ev.key === 'Enter' || ev.key === ' ') {
                    ev.preventDefault()
                    ask(n.nome)
                  }
                }}
              >
                <g opacity={n.cursada ? 0.55 : 1}>
                  <rect
                    width={n.w}
                    height={NODE_H}
                    rx={NODE_H / 2}
                    style={{
                      fill: C.pillFill,
                      stroke: isRoot
                        ? C.pillStrokeRoot
                        : n.inferida
                          ? C.amberDim
                          : C.pillStroke,
                    }}
                    strokeWidth={isRoot ? 1.4 : 1}
                    strokeDasharray={n.inferida ? '4 3' : undefined}
                  />
                  {n.cursada && (
                    <path
                      d="M 14 17 l 3.5 3.5 l 6 -7"
                      fill="none"
                      style={{ stroke: C.accent }}
                      strokeWidth={2}
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  )}
                  <text
                    x={n.cursada ? (n.w + 14) / 2 : n.w / 2}
                    y={NODE_H / 2 + 4}
                    textAnchor="middle"
                    style={{ fill: C.text }}
                    fontSize={12}
                  >
                    {label}
                  </text>
                </g>
                <title>{n.nome}</title>
              </g>
            )
          })}
        </svg>
      </div>

      {hasInferidas && (
        <div className="border-t border-line px-4 py-2 text-[10.5px] text-paper-mute">
          <span
            className="mr-1.5 inline-block align-middle"
            style={{
              width: 18,
              borderTop: `1.5px dashed ${C.amberDim}`,
            }}
            aria-hidden
          />
          <span style={{ color: C.amber }}>disciplina · NN%</span> - recomendada
          por inferência (não é pré-requisito formal; o percentual é a confiança)
        </div>
      )}
    </div>
  )
}
