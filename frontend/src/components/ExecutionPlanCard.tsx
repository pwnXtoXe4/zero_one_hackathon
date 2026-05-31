import { ArrowUpRight } from 'lucide-react'
import { Card, ConfidenceBadge, AnimatedNumber, Donut, CHANNEL_COLOR, CHANNEL_LABEL } from './primitives'
import type { ExecutionPlan, Scenario } from '@/data/types'
import { eurM, tons } from '@/lib/utils'

const ACTION_COLOR: Record<string, string> = {
  BUY: '#D18500', LADDER: '#1E70B8', SELL: '#009B72', WAIT: '#009B72',
}

function Stat({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div>
      <div className="label">{label}</div>
      <div className="mt-0.5 font-display text-xl font-bold" style={{ color }}>
        <AnimatedNumber value={value} format={eurM} />
      </div>
    </div>
  )
}

export function ExecutionPlanCard({ plan, scenario }: { plan: ExecutionPlan; scenario: Scenario }) {
  const shock = scenario === 'shock'
  const color = shock ? '#D18500' : ACTION_COLOR[plan.action] ?? '#1E70B8'
  const total = plan.channelMix.reduce((s, m) => s + m.volume, 0) || 1
  const segs = plan.channelMix.map((m) => ({ value: m.volume, color: CHANNEL_COLOR[m.key] }))

  return (
    <Card
      className="relative overflow-hidden bg-[#F8FBFF] p-4"
      style={
        {
          '--card-accent': color,
          ...(shock ? { borderColor: 'rgba(209,133,0,0.45)' } : {}),
        } as React.CSSProperties
      }
    >
      <div className="flex items-center justify-between">
        <span className="label">Execution plan · how to procure</span>
        <ConfidenceBadge c={plan.confidence} />
      </div>

      <div
        key={plan.action + scenario}
        className="mt-3 flex items-start gap-3"
      >
        <span className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1 font-display text-xl font-bold" style={{ color, background: color + '1A' }}>
          {plan.action}
          {shock && <ArrowUpRight size={18} />}
        </span>
        <p className="pt-0.5 text-[13px] leading-snug text-ink/80 line-clamp-2">{plan.headline}</p>
      </div>

      {/* channel mix donut + legend */}
      <div className="mt-4 flex items-center gap-5">
        <div className="relative grid shrink-0 place-items-center">
          <Donut segments={segs} size={80} stroke={11} />
          <div className="absolute text-center">
            <div className="font-display text-lg font-bold leading-none text-ink">
              <AnimatedNumber value={plan.deficitVolume} format={(n) => tons(n)} />
            </div>
            <div className="mt-0.5 text-[9px] uppercase tracking-wider text-muted">{plan.side}</div>
          </div>
        </div>
        <div className="grid flex-1 grid-cols-2 gap-x-3 gap-y-1.5">
          {plan.channelMix.map((m) => (
            <div key={m.key} className="flex items-center gap-2 text-[12px]">
              <span className="h-2.5 w-2.5 rounded-sm" style={{ background: CHANNEL_COLOR[m.key] }} />
              <span className="text-ink/85">{CHANNEL_LABEL[m.key]}</span>
              <span className="ml-auto font-mono text-muted">{Math.round((m.volume / total) * 100)}%</span>
            </div>
          ))}
        </div>
      </div>

      {/* cost summary */}
      <div className="mt-4 grid grid-cols-3 gap-3 border-t border-border pt-4">
        <Stat label="Expected spend" value={plan.expectedTotal} color="#0F172A" />
        <Stat label="Worst case" value={plan.worstCase} color="#D66A2E" />
        <Stat label="Saved vs year-end" value={plan.savingsVsYearEnd} color={color} />
      </div>


    </Card>
  )
}
