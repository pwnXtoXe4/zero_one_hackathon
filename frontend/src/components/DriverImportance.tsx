import { Card } from './primitives'
import type { Driver } from '@/data/types'

export function DriverImportance({ drivers }: { drivers: Driver[] }) {
  const max = Math.max(...drivers.map((d) => d.importance))
  return (
    <Card className="bg-[#F6FCF9]" style={{ '--card-accent': '#009B72' } as React.CSSProperties}>
      <span className="label">What's moving the price · signals</span>
      <p className="mt-1 text-[12px] leading-snug text-muted">
        Statistical external signals from Sybilion, ranked by importance — regulatory drivers are
        shown in the policy timeline.
      </p>
      <div className="mt-3.5 space-y-3">
        {drivers.map((d) => {
          const color = d.direction >= 0 ? '#009B72' : '#D66A2E'
          return (
            <div key={d.name}>
              <div className="mb-1 flex items-center justify-between text-xs">
                <span className="text-ink/85">{d.name}</span>
                <span className="font-mono text-muted">
                  {d.direction >= 0 ? '↑' : '↓'} {d.importance}
                </span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-sm bg-surface2">
                <div
                  className="flow-bar h-full rounded-sm"
                  style={{ width: `${(d.importance / max) * 100}%`, background: color }}
                />
              </div>
            </div>
          )
        })}
      </div>
    </Card>
  )
}
