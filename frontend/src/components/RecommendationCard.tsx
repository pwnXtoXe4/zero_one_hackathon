import { ArrowUpRight, Check } from 'lucide-react'
import { Card, RingGauge, AnimatedNumber } from './primitives'
import type { Recommendation, Scenario } from '@/data/types'
import { eurM } from '@/lib/utils'

function actionColor(a: string, shock: boolean) {
  if (a === 'BUY') return shock ? '#D18500' : '#009B72'
  if (a === 'LADDER') return '#1E70B8'
  if (a === 'WAIT') return '#009B72'
  return '#1E70B8'
}

function Stat({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div>
      <div className="label">{label}</div>
      <div className="mt-0.5 font-display text-2xl font-bold" style={{ color }}>
        <AnimatedNumber value={value} format={eurM} />
      </div>
    </div>
  )
}

export function RecommendationCard({ recommendation: r, scenario }: { recommendation: Recommendation; scenario: Scenario }) {
  const shock = scenario === 'shock'
  const color = actionColor(r.action, shock)
  return (
    <Card
      className="relative overflow-hidden bg-[#F8FBFF]"
      style={
        {
          '--card-accent': color,
          ...(shock ? { borderColor: 'rgba(209,133,0,0.45)' } : {}),
        } as React.CSSProperties
      }
    >
      <span className="label">Agent recommendation</span>

      <div className="mt-3 flex items-start gap-4">
        <div className="relative grid shrink-0 place-items-center">
          <RingGauge pct={r.lockNowPct} color={color} />
          <span className="absolute font-display text-base font-bold" style={{ color }}>
            {r.lockNowPct}%
          </span>
        </div>

        <div className="flex-1">
          <div key={r.action + scenario}>
            <span className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1 font-display text-xl font-bold" style={{ color, background: color + '1A' }}>
              {r.action}
              {shock && <ArrowUpRight size={18} />}
            </span>
            <p className="mt-2 font-display text-[16px] font-semibold leading-snug text-ink">{r.headline}</p>
          </div>
        </div>
      </div>

      <ul className="mt-4 space-y-2">
        {r.rationale.map((x) => (
          <li
            key={x}
            className="flex items-start gap-2 text-[13px] leading-snug text-ink/85"
          >
            <Check size={14} className="mt-0.5 shrink-0" style={{ color }} />
            {x}
          </li>
        ))}
      </ul>

      <div className="mt-5 grid grid-cols-2 gap-3 border-t border-border pt-4">
        <Stat label="Exposure at risk" value={r.costAtRisk} color="#171C19" />
        <Stat label="Saved vs naive" value={r.savingsVsNaive} color={color} />
      </div>
    </Card>
  )
}
