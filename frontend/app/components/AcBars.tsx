'use client'

export interface AcEixo {
  eixo: number
  nome: string
  validas: number
  brutas: number
  teto?: number | null
  ok: boolean
}

export interface AcReportData {
  type?: string
  alvo: number
  total: number
  faltam: number
  apto: boolean
  eixos: AcEixo[]
}

interface Props {
  data: AcReportData
}

function Bar({
  label,
  value,
  max,
  hint,
  ok,
}: {
  label: string
  value: number
  max: number
  hint?: string
  ok: boolean
}) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100))
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between gap-2">
        <span className="text-[12px] text-paper-dim">{label}</span>
        <span className="font-mono text-[11px] text-paper">
          {value}h{hint ? ` ${hint}` : ''} {ok ? '' : '✗'}
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-ink">
        <div
          className={`h-full rounded-full transition-all ${ok ? 'bg-accent' : 'bg-amber-400/70'}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

export default function AcBars({ data }: Props) {
  if (!data?.eixos?.length) return null
  const pctTotal = Math.max(0, Math.min(100, (data.total / data.alvo) * 100))

  return (
    <div className="mt-4 rounded-xl border border-line bg-ink-deep/70">
      <div className="flex items-baseline justify-between gap-3 border-b border-line px-4 py-2.5">
        <span className="font-mono text-[10.5px] uppercase tracking-[0.18em] text-paper-mute">
          Suas horas de AC
        </span>
        <span
          className={`font-mono text-[11px] ${data.apto ? 'text-accent' : 'text-paper-mute'}`}
        >
          {data.apto ? 'Pronto para validar' : `faltam ${data.faltam}h`}
        </span>
      </div>
      <div className="space-y-3.5 p-4">
        <div>
          <div className="mb-1 flex items-baseline justify-between gap-2">
            <span className="text-[12.5px] font-medium text-paper">
              Total válido
            </span>
            <span className="font-mono text-[12px] text-paper">
              {data.total}h / {data.alvo}h
            </span>
          </div>
          <div className="h-3 overflow-hidden rounded-full bg-ink">
            <div
              className={`h-full rounded-full ${data.apto ? 'bg-accent' : 'bg-accent/70'}`}
              style={{ width: `${pctTotal}%` }}
            />
          </div>
        </div>
        {data.eixos.map((e) => (
          <Bar
            key={e.eixo}
            label={e.nome}
            value={e.validas}
            max={e.teto || data.alvo}
            hint={
              e.teto
                ? `/ ${e.teto}h${e.brutas > e.teto ? ` (${e.brutas}h informadas)` : ''}`
                : undefined
            }
            ok={e.ok}
          />
        ))}
      </div>
    </div>
  )
}
