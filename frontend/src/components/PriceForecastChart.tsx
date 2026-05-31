import {
  Area, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { Card } from './primitives'
import type { ForecastPoint, HistoryPoint, Scenario } from '@/data/types'

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-muted">{k}</span>
      <span className="font-mono text-ink">{v}</span>
    </div>
  )
}

function TipBox({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  const get = (k: string) => payload.find((p: any) => p.dataKey === k)?.value
  const price = get('price')
  const p50 = get('p50')
  const base = get('outerBase')
  const span = get('outerSpan')
  return (
    <div className="space-y-0.5 rounded-lg border border-border bg-surface px-3 py-2 text-xs shadow-card">
      <div className="mb-1 font-medium text-ink">{label}</div>
      {price != null && <Row k="price" v={`€${(+price).toFixed(2)}`} />}
      {p50 != null && <Row k="forecast p50" v={`€${(+p50).toFixed(1)}`} />}
      {base != null && span != null && span > 0 && (
        <Row k="90% band" v={`€${(+base).toFixed(0)} – €${(+base + +span).toFixed(0)}`} />
      )}
    </div>
  )
}

function Legend({ accent }: { accent: string }) {
  return (
    <div className="flex items-center gap-4 text-[11px] text-muted">
      <span className="flex items-center gap-1.5"><span className="h-0.5 w-4 rounded bg-[#7D8983]" />history</span>
      <span className="flex items-center gap-1.5">
        <span className="h-0.5 w-4 rounded" style={{ background: accent, borderTop: `2px dashed ${accent}` }} />forecast p50
      </span>
      <span className="flex items-center gap-1.5"><span className="h-2.5 w-4 rounded-sm" style={{ background: accent + '33' }} />confidence band</span>
    </div>
  )
}

export function PriceForecastChart({
  history, forecast, scenario,
}: {
  history: HistoryPoint[]
  forecast: ForecastPoint[]
  scenario: Scenario
}) {
  const hist = history.slice(-22)
  const accent = scenario === 'shock' ? '#D18500' : '#1E70B8'

  const data: any[] = hist.map((h) => ({ label: h.label, price: h.price }))
  const lastPrice = hist[hist.length - 1].price
  data[data.length - 1] = { ...data[data.length - 1], p50: lastPrice, outerBase: lastPrice, outerSpan: 0, innerBase: lastPrice, innerSpan: 0 }
  forecast.forEach((f) =>
    data.push({
      label: `${f.label} '26`,
      p50: f.p50,
      outerBase: f.p05,
      outerSpan: +(f.p95 - f.p05).toFixed(2),
      innerBase: f.p25,
      innerSpan: +(f.p75 - f.p25).toFixed(2),
    }),
  )
  const todayLabel = hist[hist.length - 1].label

  return (
    <Card className="col-span-full bg-[#F8FBFF]" style={{ '--card-accent': accent } as React.CSSProperties}>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <span className="label">EUA price · history &amp; probabilistic forecast</span>
          <div className="font-display text-lg font-semibold text-ink">
            €{hist[0].price.toFixed(0)} <span className="text-muted">({hist[0].label})</span> → €{lastPrice.toFixed(0)}{' '}
            <span className="text-muted">(today)</span> →{' '}
            <span style={{ color: accent }}>€{forecast[forecast.length - 1].p50.toFixed(0)} forecast</span>
          </div>
        </div>
        <Legend accent={accent} />
      </div>

      <div className="h-[300px] w-full">
        <ResponsiveContainer>
          <ComposedChart data={data} margin={{ top: 8, right: 18, bottom: 0, left: -10 }}>
            <defs>
              <linearGradient id="bandOuter" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={accent} stopOpacity={0.16} />
                <stop offset="100%" stopColor={accent} stopOpacity={0.04} />
              </linearGradient>
              <linearGradient id="bandInner" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={accent} stopOpacity={0.34} />
                <stop offset="100%" stopColor={accent} stopOpacity={0.12} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="#DDE8E2" vertical={false} />
            <XAxis
              dataKey="label" tick={{ fill: '#7D8983', fontSize: 11 }} tickLine={false} axisLine={false}
              interval={Math.ceil(data.length / 9)} minTickGap={16}
            />
            <YAxis
              tick={{ fill: '#7D8983', fontSize: 11 }} tickLine={false} axisLine={false} width={46}
              domain={['dataMin-6', 'dataMax+10']} tickFormatter={(v) => '€' + v}
            />
            <Tooltip content={<TipBox />} cursor={{ stroke: '#BFD0C8', strokeDasharray: '3 3' }} />
            <Area dataKey="outerBase" stackId="o" stroke="none" fill="transparent" isAnimationActive={false} />
            <Area dataKey="outerSpan" stackId="o" stroke="none" fill="url(#bandOuter)" isAnimationActive={false} />
            <Area dataKey="innerBase" stackId="i" stroke="none" fill="transparent" isAnimationActive={false} />
            <Area dataKey="innerSpan" stackId="i" stroke="none" fill="url(#bandInner)" isAnimationActive={false} />
            <Line dataKey="price" stroke="#7D8983" strokeWidth={2} dot={false} isAnimationActive={false} />
            <Line dataKey="p50" stroke={accent} strokeWidth={2.4} strokeDasharray="5 4" dot={false} isAnimationActive={false} />
            <ReferenceLine x={todayLabel} stroke="#7D8983" strokeDasharray="4 4" label={{ value: 'today', fill: '#7D8983', fontSize: 10, position: 'insideTopLeft' }} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </Card>
  )
}
