'use client'

export interface DisciplineListItem {
  nome: string
  hint?: string | null
}

export interface DisciplineListData {
  type?: string
  title?: string
  items: DisciplineListItem[]
}

interface Props {
  data: DisciplineListData
  onSelect: (nome: string) => void
}

export default function DisciplineChips({ data, onSelect }: Props) {
  if (!data?.items?.length) return null

  return (
    <div className="mt-4 rounded-xl border border-line bg-ink-deep/70">
      <div className="flex items-baseline justify-between gap-3 border-b border-line px-4 py-2.5">
        <span className="font-mono text-[10.5px] uppercase tracking-[0.18em] text-paper-mute">
          {data.title || 'Disciplinas'}
        </span>
        <span className="hidden text-[11px] text-paper-mute sm:block">
          Clique para ver os detalhes
        </span>
      </div>
      <div className="flex flex-wrap gap-1.5 p-3">
        {data.items.map((item) => (
          <button
            key={item.nome}
            type="button"
            onClick={() => onSelect(item.nome)}
            className="rounded-full border border-line bg-ink px-3 py-1.5 text-left text-[12.5px] text-paper transition-colors hover:border-accent/50 hover:text-accent"
          >
            {item.nome}
            {item.hint && (
              <span className="ml-1.5 text-[10.5px] text-paper-mute">{item.hint}</span>
            )}
          </button>
        ))}
      </div>
    </div>
  )
}
