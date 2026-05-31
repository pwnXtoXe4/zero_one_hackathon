import { Area, ComposedChart, Line, ReferenceLine, ResponsiveContainer, XAxis, YAxis } from 'recharts'
import { Card, ConfidenceBadge, SectorDot } from './primitives'
import type { Firm, Position } from '@/data/types'
import { tons } from '@/lib/utils'

const M = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const SPREAD: Record<string, number> = { high: 0.03, medium: 0.045, low: 0.07 }

export function PositionCard({ firm, position }: { firm: Firm; position: Position }) {
  const annual = position.forecastEmissions
  const coverage = firm.freeAllocation + firm.holdings
  const short = position.side === 'SHORT'
  const accent = short ? '#D18500' : '#009B72'
  const sp = SPREAD[position.confidence] ?? 0.045

  // Monthly CUMULATIVE emissions forecast with a widening p10–p90 band.
  // (Illustrative for the synthetic company — drops in the real Sybilion
  //  emissions forecast unchanged once a company series is wired.)
  const data = M.map((label, i) => {
    const frac = (i + 1) / 12
    const p50 = annual * frac
    const s = sp * (0.3 + 0.7 * frac) // band widens through the year
    return { label, p50: Math.round(p50), lo: Math.round(p50 * (1 - s)), span: Math.round(p50 * 2 * s) }
  })
  const defLo = Math.max(0, Math.round((annual * (1 - sp) - coverage) / 1000))
  const defHi = Math.round((annual * (1 + sp) - coverage) / 1000)
  const defMid = Math.abs(position.deficit)

  return (
    <Card className="flex flex-col gap-3 bg-[#FFFDF7]" style={{ '--card-accent': accent } as React.CSSProperties}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <SectorDot sector={firm.sector} />
          <span className="label">Net position · 2026</span>
        </div>
        <ConfidenceBadge c={position.confidence} />
      </div>
      <p className="-mt-1 text-[12px] leading-snug text-muted">
        Forecast emissions − free allocation − holdings = allowances still to buy.
      </p>

      <div>
        <div className="flex items-end gap-2">
          <span className="font-display text-[46px] font-extrabold leading-none" style={{ color: accent }}>
            {tons(defMid)}
          </span>
          <span className="mb-1 rounded-md px-2 py-0.5 text-xs font-bold" style={{ color: accent, background: accent + '1A' }}>
            {position.side}
          </span>
        </div>
        <p className="mt-1.5 text-[12px] text-muted">
          {short ? 'Must buy' : 'Can sell'} — p10–p90 range{' '}
          <span className="font-mono font-medium text-ink">{defLo}–{defHi}k t</span>
        </p>
      </div>

      <div className="mt-0.5">
        <span className="label">Emissions forecast vs coverage</span>
        <div className="mt-1.5 h-[120px] w-full">
          <ResponsiveContainer>
            <ComposedChart data={data} margin={{ top: 8, right: 6, bottom: 0, left: -24 }}>
              <defs>
                <linearGradient id="emBand" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={accent} stopOpacity={0.22} />
                  <stop offset="100%" stopColor={accent} stopOpacity={0.05} />
                </linearGradient>
              </defs>
              <XAxis dataKey="label" tick={{ fill: '#7D8983', fontSize: 9 }} tickLine={false} axisLine={false} interval={2} />
              <YAxis hide domain={[0, Math.max(annual, coverage) * 1.12]} />
              <Area dataKey="lo" stackId="b" stroke="none" fill="transparent" isAnimationActive={false} />
              <Area dataKey="span" stackId="b" stroke="none" fill="url(#emBand)" animationDuration={700} />
              <Line dataKey="p50" stroke={accent} strokeWidth={2} dot={false} animationDuration={700} />
              <ReferenceLine
                y={coverage}
                stroke="#69756F"
                strokeDasharray="4 4"
                label={{ value: 'free allocation + holdings', fill: '#69756F', fontSize: 9, position: 'insideTopLeft' }}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-muted">
          <span className="flex items-center gap-1"><span className="h-0.5 w-3 rounded" style={{ background: accent }} />forecast (p50)</span>
          <span className="flex items-center gap-1"><span className="h-2 w-3 rounded-sm" style={{ background: accent + '33' }} />p10–p90 band</span>
          <span className="flex items-center gap-1"><span className="h-0.5 w-3 rounded bg-[#69756F]" />coverage</span>
        </div>
      </div>
    </Card>
  )
}
