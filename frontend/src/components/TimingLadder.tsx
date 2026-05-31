import { Card } from './primitives'
import type { LadderStep, Recommendation } from '@/data/types'

export function TimingLadder({ ladder, recommendation }: { ladder: LadderStep[]; recommendation: Recommendation }) {
  const color = recommendation.action === 'BUY' ? '#D18500' : '#1E70B8'
  const summary = ladder.map((s) => `${s.pct}% ${s.when}`).join(' · ')
  return (
    <Card>
      <div className="flex items-center justify-between">
        <span className="label">Timing plan · when to execute</span>
        <span className="chip text-muted">{ladder.length} tranches</span>
      </div>
      <p className="mt-0.5 text-[11px] text-muted">{summary}</p>
      <div className="mt-3 space-y-2.5">
        {ladder.map((s) => (
          <div
            key={s.label + s.pct}
            className="flex items-center gap-3"
          >
            <div
              className="grid h-9 w-9 shrink-0 place-items-center rounded-lg font-display text-sm font-bold"
              style={{ color, background: color + '1A' }}
            >
              {s.pct}%
            </div>
            <div className="flex-1">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-ink">{s.label}</span>
                <span className="text-[11px] text-muted">{s.when}</span>
              </div>
              <div className="mt-1 h-1 overflow-hidden rounded-sm bg-surface2">
                <div
                  className="h-full rounded-sm"
                  style={{ width: `${s.pct}%`, background: color }}
                />
              </div>
            </div>
          </div>
        ))}
      </div>
    </Card>
  )
}
