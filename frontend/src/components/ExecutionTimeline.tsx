import { Card, CHANNEL_COLOR, CHANNEL_LABEL } from './primitives'
import type { ExecutionPlan } from '@/data/types'
import { tons } from '@/lib/utils'

const STATUS_LABEL: Record<string, string> = {
  EXECUTE: 'execute now', SCHEDULED: 'scheduled', WAIT: 'hold open',
}

type Row = {
  id: string; when: string; key: string; volume: number
  price: number; maxBid: number | null; status: string; reason: string
}

export function ExecutionTimeline({ plan }: { plan: ExecutionPlan }) {
  const total = plan.deficitVolume || 1
  const waitSlice = plan.channelMix.find((m) => m.key === 'WAIT')

  const rows: Row[] = plan.tranches.map((t) => ({
    id: t.id, when: t.when, key: t.channel, volume: t.volume,
    price: t.price, maxBid: t.maxBid, status: t.status, reason: t.reason,
  }))
  if (waitSlice) {
    rows.push({
      id: 'reserve', when: 'Open', key: 'WAIT', volume: waitSlice.volume,
      price: 0, maxBid: null, status: 'WAIT', reason: 'Reserve — deploy only if a trigger fires.',
    })
  }

  return (
    <Card className="bg-[#FFFDF7]" style={{ '--card-accent': '#D18500' } as React.CSSProperties}>
      <span className="label">Execution timeline · when &amp; through which channel</span>

      {/* proportional channel ribbon */}
      <div className="mt-3 flex h-2.5 overflow-hidden rounded-sm bg-surface2">
        {plan.channelMix.map((m) => (
          <div
            key={m.key}
            className="flow-bar"
            style={{ width: `${(m.volume / total) * 100}%`, background: CHANNEL_COLOR[m.key] }}
            title={`${CHANNEL_LABEL[m.key]} · ${tons(m.volume)}`}
          />
        ))}
      </div>

      <div className="mt-4 space-y-3">
        {rows.map((r, i) => {
          const color = CHANNEL_COLOR[r.key]
          const pct = Math.round((r.volume / total) * 100)
          return (
            <div
              key={r.id}
              className="flex items-start gap-3"
            >
              <div className="flex flex-col items-center pt-1">
                <span className="h-2.5 w-2.5 rounded-sm" style={{ background: color }} />
                {i < rows.length - 1 && <span className="mt-1 h-10 w-px bg-border" />}
              </div>
              <div className="flex-1">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-ink">{r.when}</span>
                    <span className="rounded px-1.5 py-0.5 text-[10px] font-bold" style={{ color, background: color + '1A' }}>
                      {CHANNEL_LABEL[r.key]}
                    </span>
                  </div>
                  <span className="font-mono text-[12px]" style={{ color }}>{tons(r.volume)} · {pct}%</span>
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-x-2 text-[11px] text-muted">
                  {r.price > 0 ? <span className="font-mono text-ink/80">€{r.price.toFixed(1)}/t</span> : <span>held</span>}
                  {r.maxBid != null && <span>· max bid €{r.maxBid.toFixed(1)}</span>}
                  <span>· {STATUS_LABEL[r.status]}</span>
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </Card>
  )
}
