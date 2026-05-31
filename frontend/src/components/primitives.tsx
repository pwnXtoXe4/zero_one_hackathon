import { cn } from '@/lib/utils'
import type { Confidence, Sector } from '@/data/types'

export const SECTOR_COLOR: Record<Sector, string> = {
  Steel: '#596B75', Cement: '#C19A16', Chemicals: '#009B72', Power: '#1E70B8',
  Aviation: '#6F5CB8', Refining: '#D66A2E', Paper: '#3F9B4F', Glass: '#00A1A7', Food: '#C97B3A',
}

export function Card({ className, children, ...rest }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn('card p-5', className)} {...rest}>
      {children}
    </div>
  )
}

export function SectorDot({ sector, size = 8 }: { sector: Sector; size?: number }) {
  const c = SECTOR_COLOR[sector]
  return (
    <span
      className="inline-block shrink-0 rounded-full ring-1 ring-black/5"
      style={{ width: size, height: size, background: c }}
    />
  )
}

export function ConfidenceBadge({ c }: { c: Confidence }) {
  const map: Record<Confidence, [string, string]> = {
    high: ['High confidence', 'text-signal border-signal/35 bg-signal/10'],
    medium: ['Medium confidence', 'text-amber border-amber/35 bg-amber/10'],
    low: ['Low confidence', 'text-muted border-border bg-surface2/60'],
  }
  return (
    <span className={cn('inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-[11px] font-medium', map[c][1])}>
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {map[c][0]}
    </span>
  )
}

export function AnimatedNumber({
  value, format,
}: {
  value: number
  format: (n: number) => string
}) {
  return <span className="tnum">{format(value)}</span>
}

export function Sparkline({
  data, width = 120, height = 34, color = '#009B72',
}: {
  data: number[]
  width?: number
  height?: number
  color?: string
}) {
  if (data.length < 2) return null
  const min = Math.min(...data)
  const max = Math.max(...data)
  const rng = max - min || 1
  const pts = data.map((v, i) => {
    const x = (i / (data.length - 1)) * width
    const y = height - ((v - min) / rng) * (height - 4) - 2
    return `${x.toFixed(1)},${y.toFixed(1)}`
  })
  const [lastX, lastY] = pts[pts.length - 1].split(',').map(Number)
  const id = `spark-${color.replace('#', '')}`
  return (
    <svg width={width} height={height} className="overflow-visible">
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.35" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polyline points={`0,${height} ${pts.join(' ')} ${width},${height}`} fill={`url(#${id})`} stroke="none" />
      <polyline points={pts.join(' ')} fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={lastX} cy={lastY} r="2.7" fill={color} />
    </svg>
  )
}

export const CHANNEL_COLOR: Record<string, string> = {
  AUCTION: '#009B72', // primary market
  SPOT: '#1E70B8', // secondary continuous
  RFQ: '#C19A16', // broker request-for-quote
  OTC: '#D66A2E', // bilateral
  WAIT: '#69756F', // held open
}

export const CHANNEL_LABEL: Record<string, string> = {
  AUCTION: 'Auction', SPOT: 'Spot', RFQ: 'RFQ · Broker', OTC: 'OTC', WAIT: 'Hold open',
}

/** Multi-segment donut for the channel mix. */
export function Donut({
  segments, size = 96, stroke = 13,
}: {
  segments: { value: number; color: string }[]
  size?: number
  stroke?: number
}) {
  const total = segments.reduce((s, x) => s + x.value, 0) || 1
  const r = (size - stroke) / 2
  const circ = 2 * Math.PI * r
  let acc = 0
  return (
    <svg width={size} height={size} className="-rotate-90">
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#E4ECE8" strokeWidth={stroke} />
      {segments.map((seg, i) => {
        const len = (seg.value / total) * circ
        const node = (
          <circle
            key={i}
            cx={size / 2} cy={size / 2} r={r} fill="none"
            stroke={seg.color} strokeWidth={stroke} strokeLinecap="butt"
            strokeDasharray={`${Math.max(0, len - 1.5)} ${circ - Math.max(0, len - 1.5)}`}
            strokeDashoffset={-acc}
          />
        )
        acc += len
        return node
      })}
    </svg>
  )
}

export function RingGauge({ pct, color = '#009B72', size = 76 }: { pct: number; color?: string; size?: number }) {
  const r = (size - 10) / 2
  const c = 2 * Math.PI * r
  const off = c - (pct / 100) * c
  return (
    <svg width={size} height={size} className="-rotate-90">
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#E4ECE8" strokeWidth="6" />
      <circle
        cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth="6" strokeLinecap="round"
        strokeDasharray={c} strokeDashoffset={off}
      />
    </svg>
  )
}
