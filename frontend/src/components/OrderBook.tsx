import { Card, SectorDot } from './primitives'
import type { Order } from '@/data/types'
import { tons } from '@/lib/utils'

function Side({ title, rows, color, align }: { title: string; rows: Order[]; color: string; align: 'left' | 'right' }) {
  return (
    <div>
      <div className="mb-2 text-[11px] font-semibold" style={{ color }}>
        {title}
      </div>
      <div className="space-y-1">
        {rows.slice(0, 7).map((o) => (
          <div key={o.id} className="relative flex items-center gap-2 overflow-hidden rounded-md px-2 py-1.5 text-xs">
            <div
              className="absolute inset-y-0 rounded-md"
              style={{ [align]: 0, width: `${Math.min(100, (o.volume / 120000) * 100)}%`, background: color + '14' }}
            />
            <SectorDot sector={o.sector} size={6} />
            <span className="relative flex-1 truncate text-ink/80">{o.firm}</span>
            <span className="relative font-mono text-muted">{tons(o.volume)}</span>
            <span className="relative font-mono font-semibold" style={{ color }}>
              €{o.price.toFixed(2)}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

export function OrderBook({ orders }: { orders: Order[] }) {
  const buys = orders.filter((o) => o.side === 'buy').sort((a, b) => b.price - a.price)
  const sells = orders.filter((o) => o.side === 'sell').sort((a, b) => a.price - b.price)
  return (
    <Card>
      <div className="mb-3 flex items-center justify-between">
        <span className="label">Live order book</span>
        <span className="chip">{orders.length} firms</span>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <Side title="Buyers · short" rows={buys} color="#D18500" align="left" />
        <Side title="Sellers · long" rows={sells} color="#009B72" align="right" />
      </div>
    </Card>
  )
}
