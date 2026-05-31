import {
  Area, CartesianGrid, ComposedChart, Line, ReferenceArea, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { Card, CHANNEL_COLOR, CHANNEL_LABEL } from './primitives'
import type { EmissionsOutlook, ExecutionPlan, ForecastPoint, Scenario, Tranche } from '@/data/types'
import { eur, tons } from '@/lib/utils'

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

function emTick(v: number): string {
  if (Math.abs(v) >= 1e6) return (v / 1e6).toFixed(1).replace(/\.0$/, '') + 'Mt'
  return Math.round(v / 1e3) + 'kt'
}

/** Map an engine tranche's free-text `when` to a 2026 month label. */
function trancheMonth(when: string): string {
  const m = MONTHS.find((mm) => when.includes(mm))
  if (m) return m
  if (/month\s*6/i.test(when)) return 'Nov'
  if (/month\s*3/i.test(when)) return 'Aug'
  return 'Jun' // "Now" / "This week" / "Open" → the near-term action window
}

function TipBox({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  const get = (k: string) => payload.find((p: any) => p.dataKey === k)?.value
  const cum = get('cumP50')
  const base = get('cumBase')
  const span = get('cumSpan')
  const price = get('priceP50')
  return (
    <div className="space-y-0.5 rounded-lg border border-border bg-surface/95 px-3 py-2 text-xs shadow-card backdrop-blur-xl">
      <div className="mb-1 font-medium text-ink">{label} 2026</div>
      {cum != null && <div className="flex justify-between gap-4"><span className="text-muted">cumulative</span><span className="font-mono text-ink">{emTick(+cum)}</span></div>}
      {base != null && span != null && +span > 0 && (
        <div className="flex justify-between gap-4"><span className="text-muted">p10–p90</span><span className="font-mono text-ink">{emTick(+base)} – {emTick(+base + +span)}</span></div>
      )}
      {price != null && <div className="flex justify-between gap-4"><span className="text-muted">EUA p50</span><span className="font-mono text-cool">{eur(+price)}</span></div>}
    </div>
  )
}

export function CarbonEdgeTimeline({
  outlook, forecast, plan, scenario,
}: {
  outlook: EmissionsOutlook
  forecast: ForecastPoint[]
  plan: ExecutionPlan
  scenario: Scenario
}) {
  const shock = scenario === 'shock'
  const priceAccent = shock ? '#D97706' : '#2563EB'
  const priceByLabel = new Map(forecast.map((f) => [f.label, f]))

  const data = outlook.months.map((m) => {
    const f = priceByLabel.get(m.label)
    return {
      label: m.label,
      cumP50: m.cumP50,
      cumBase: m.cumP10,
      cumSpan: m.cumP90 - m.cumP10,
      priceP50: f?.p50 ?? null,
      priceBase: f ? f.p05 : null,
      priceSpan: f ? +(f.p95 - f.p05).toFixed(2) : null,
    }
  })

  // Procurement actions placed on the timeline (grouped by month).
  const execTranches = plan.tranches.filter((t) => t.status !== 'WAIT')
  const procureMonth = execTranches.length ? trancheMonth(execTranches[0].when) : 'Jun'
  const securedNow = plan.tranches.filter((t) => t.status === 'EXECUTE').reduce((s, t) => s + t.volume, 0)
  const os = outlook.overshoot
  const sourceLabel =
    outlook.source === 'sybilion'
      ? 'Sybilion emissions forecast'
      : outlook.source === 'climate_trace_projection'
        ? 'Climate TRACE history + seasonal projection'
        : 'illustrative emissions path'

  return (
    <Card className="col-span-full">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <span className="label">CarbonEdge timeline · {outlook.company} · 2026</span>
          <div className="font-display text-lg font-semibold text-ink">
            Emissions {emTick(outlook.annualEmissionsP50)} vs {emTick(outlook.freeAllocation)} free —{' '}
            {os ? (
              <>overshoot <span className="text-amber">{os.label}</span>, deficit {tons(outlook.annualDeficitP50)}</>
            ) : (
              <span className="text-signal">within allocation all year</span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-4 text-[11px] text-muted">
          <span className="flex items-center gap-1.5"><span className="h-2.5 w-4 rounded-sm bg-cool/25" />cumulative p10–p90</span>
          <span className="flex items-center gap-1.5"><span className="h-0.5 w-4 rounded bg-[#64748B]" style={{ borderTop: '2px dashed #64748B' }} />free allocation</span>
          {os && <span className="flex items-center gap-1.5"><span className="h-2.5 w-4 rounded-sm bg-amber/20" />overshoot zone</span>}
          <span className="flex items-center gap-1.5"><span className="h-0.5 w-4 rounded" style={{ background: priceAccent, borderTop: `2px dashed ${priceAccent}` }} />EUA price band</span>
        </div>
      </div>

      <div className="h-[340px] w-full">
        <ResponsiveContainer>
          <ComposedChart data={data} margin={{ top: 10, right: 6, bottom: 0, left: 6 }}>
            <defs>
              <linearGradient id="emBand" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#2563EB" stopOpacity={0.26} />
                <stop offset="100%" stopColor="#2563EB" stopOpacity={0.06} />
              </linearGradient>
              <linearGradient id="tlPriceBand" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={priceAccent} stopOpacity={0.20} />
                <stop offset="100%" stopColor={priceAccent} stopOpacity={0.05} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="#EDF1F6" vertical={false} />
            <XAxis dataKey="label" tick={{ fill: '#94A3B8', fontSize: 11 }} tickLine={false} axisLine={false} />
            <YAxis yAxisId="em" tick={{ fill: '#94A3B8', fontSize: 11 }} tickLine={false} axisLine={false} width={52} tickFormatter={emTick} domain={[0, 'dataMax']} />
            <YAxis yAxisId="price" orientation="right" tick={{ fill: priceAccent, fontSize: 11 }} tickLine={false} axisLine={false} width={42} domain={['dataMin-4', 'dataMax+4']} tickFormatter={(v) => '€' + v} />
            <Tooltip content={<TipBox />} cursor={{ stroke: '#CBD5E1', strokeDasharray: '3 3' }} />

            {/* Overshoot zone */}
            {os && <ReferenceArea yAxisId="em" x1={os.startLabel} x2={os.endLabel} fill="#D97706" fillOpacity={0.12} stroke="#D97706" strokeOpacity={0.25} />}

            {/* Free allocation line */}
            <ReferenceLine yAxisId="em" y={outlook.freeAllocation} stroke="#64748B" strokeDasharray="6 4"
              label={{ value: `free allocation ${emTick(outlook.freeAllocation)}`, fill: '#64748B', fontSize: 10, position: 'insideBottomRight' }} />

            {/* Cumulative emissions band + median */}
            <Area yAxisId="em" dataKey="cumBase" stackId="em" stroke="none" fill="transparent" isAnimationActive={false} />
            <Area yAxisId="em" dataKey="cumSpan" stackId="em" stroke="none" fill="url(#emBand)" isAnimationActive={false} />
            <Line yAxisId="em" dataKey="cumP50" stroke="#2563EB" strokeWidth={2.4} dot={false} isAnimationActive={false} />

            {/* EUA price band + median (right axis) */}
            <Area yAxisId="price" dataKey="priceBase" stackId="pr" stroke="none" fill="transparent" isAnimationActive={false} connectNulls />
            <Area yAxisId="price" dataKey="priceSpan" stackId="pr" stroke="none" fill="url(#tlPriceBand)" isAnimationActive={false} connectNulls />
            <Line yAxisId="price" dataKey="priceP50" stroke={priceAccent} strokeWidth={2} strokeDasharray="5 4" dot={false} connectNulls isAnimationActive={false} />

            {/* Procurement action marker — placed before the overshoot */}
            {plan.side === 'SHORT' && securedNow > 0 && (
              <ReferenceLine yAxisId="em" x={procureMonth} stroke="#0EA371" strokeWidth={2}
                label={{ value: `◆ procure ${tons(securedNow)}`, fill: '#0EA371', fontSize: 10, position: 'insideTopLeft' }} />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Action strip — the routed plan, dated */}
      <div className="mt-4 border-t border-border pt-3">
        <div className="mb-2 flex items-center justify-between">
          <span className="label">Routed procurement — execute before the overshoot</span>
          <span className="text-[11px] text-muted">
            source: {sourceLabel} · price: Sybilion EUA forecast{outlook.source === 'synthetic' ? ' · emissions illustrative' : ''}
          </span>
        </div>
        <div className="flex flex-wrap gap-2">
          {plan.tranches.map((t: Tranche) => (
            <div key={t.id} className="flex items-center gap-2 rounded-lg border border-border bg-surface2/50 px-3 py-1.5 text-xs">
              <span className="h-2 w-2 rounded-full" style={{ background: CHANNEL_COLOR[t.channel] }} />
              <span className="font-medium text-ink">{t.when}</span>
              <span className="text-muted">{CHANNEL_LABEL[t.channel] ?? t.channel}</span>
              <span className="font-mono text-ink">{tons(t.volume)}</span>
              <span className="font-mono text-muted">{t.maxBid ? `≤ ${eur(t.maxBid)}` : `@ ${eur(t.price)}`}</span>
            </div>
          ))}
          {plan.channelMix.find((m) => m.key === 'WAIT') && (
            <div className="flex items-center gap-2 rounded-lg border border-dashed border-border px-3 py-1.5 text-xs text-muted">
              <span className="h-2 w-2 rounded-full" style={{ background: CHANNEL_COLOR.WAIT }} />
              reserve {tons(plan.channelMix.find((m) => m.key === 'WAIT')!.volume)} · release on trigger
            </div>
          )}
        </div>
      </div>
    </Card>
  )
}
