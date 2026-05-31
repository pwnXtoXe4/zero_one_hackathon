import { TrendingUp } from 'lucide-react'
import { Card, Sparkline, AnimatedNumber } from './primitives'
import type { ForecastPoint, HistoryPoint, Scenario } from '@/data/types'
import { CURRENT_PRICE } from '@/data/mock'

export function MarketSnapshot({
  history, forecast, scenario,
}: {
  history: HistoryPoint[]
  forecast: ForecastPoint[]
  scenario: Scenario
}) {
  const last = forecast.length ? forecast[forecast.length - 1] : null
  const spark = history.slice(-24).map((h) => h.price)
  const color = scenario === 'shock' ? '#D18500' : '#1E70B8'
  return (
    <Card className="flex flex-col justify-between gap-4 bg-[#F7FBFF]" style={{ '--card-accent': color } as React.CSSProperties}>
      <div className="flex items-start justify-between">
        <div>
          <span className="label">EUA spot price</span>
          <div className="font-display text-[32px] font-extrabold leading-none text-ink">€{CURRENT_PRICE.toFixed(2)}</div>
          <div className="mt-1 text-xs font-medium text-signal">▲ 1.4% today</div>
        </div>
        <Sparkline data={spark} color="#009B72" />
      </div>

      <div className="rounded-lg border border-border bg-surface2/45 p-3.5">
        <div className="flex items-center justify-between">
          <span className="text-xs text-muted">Forecast · Oct 2026 (p50)</span>
          <TrendingUp size={14} style={{ color }} />
        </div>
        <div className="mt-1 flex items-baseline gap-2">
          <span className="font-display text-2xl font-bold" style={{ color }}>
            {last ? <AnimatedNumber value={last.p50} format={(n) => '€' + n.toFixed(0)} /> : <span className="text-muted">—</span>}
          </span>
          <span className="text-sm font-semibold" style={{ color }}>
            {scenario === 'shock' ? '+66%' : '+8%'}
          </span>
        </div>
      </div>
    </Card>
  )
}
