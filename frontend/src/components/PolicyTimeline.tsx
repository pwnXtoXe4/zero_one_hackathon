import { Card } from './primitives'
import type { PolicyEvent } from '@/data/types'

function fmtWhen(e: PolicyEvent): string {
  if (e.period) return e.period
  const d = new Date(e.date + 'T00:00:00')
  return Number.isNaN(d.getTime())
    ? e.date
    : d.toLocaleDateString('en-GB', { month: 'short', year: 'numeric' })
}

/**
 * EU-ETS policy overlay — CarbonEdge's own model of public regulatory facts
 * (MSR, CBAM, cap reduction, compliance deadline). Shown SEPARATELY from the
 * Sybilion statistical drivers so the demo never passes our domain knowledge
 * off as a model output.
 */
export function PolicyTimeline({ events }: { events?: PolicyEvent[] }) {
  if (!events?.length) return null
  const max = Math.max(...events.map((e) => e.importance), 1)
  return (
    <Card className="bg-[#FBF8F3]" style={{ '--card-accent': '#B07B2E' } as React.CSSProperties}>
      <span className="label">EU-ETS policy timeline</span>
      <p className="mt-1 text-[12px] leading-snug text-muted">
        CarbonEdge’s own model of public regulatory facts — kept separate from the statistical
        Sybilion signals, whose universe carries no ETS-specific policy series.
      </p>
      <div className="mt-3.5 space-y-3.5">
        {events.map((e) => {
          const up = e.direction >= 0
          const color = up ? '#009B72' : '#D66A2E'
          return (
            <div key={e.title}>
              <div className="mb-1 flex items-baseline justify-between gap-2 text-xs">
                <span className="text-ink/85">{e.title}</span>
                <span className="shrink-0 font-mono text-muted">
                  {up ? '↑' : '↓'} {e.importance}
                </span>
              </div>
              <div className="mb-1 h-1.5 overflow-hidden rounded-sm bg-surface2">
                <div
                  className="flow-bar h-full rounded-sm"
                  style={{ width: `${(e.importance / max) * 100}%`, background: color }}
                />
              </div>
              <p className="text-[11px] leading-snug text-muted">
                <span className="font-medium text-ink/70">{fmtWhen(e)}</span> · {e.detail}
              </p>
              <p className="mt-0.5 text-[10px] uppercase tracking-wide text-muted/70">{e.source}</p>
            </div>
          )
        })}
      </div>
    </Card>
  )
}
