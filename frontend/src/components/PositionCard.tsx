import { useEffect, useState } from 'react'
import { ArrowUp } from 'lucide-react'
import { Card, ConfidenceBadge, SectorDot } from './primitives'
import { api } from '@/data/api'
import type { EmissionsOutlook, Firm, Position } from '@/data/types'
import { tons } from '@/lib/utils'

export function PositionCard({ firm, position }: { firm: Firm; position: Position }) {
  const short = position.side === 'SHORT'
  const accent = short ? '#D97706' : '#0EA371'
  const defMid = Math.abs(position.deficit)

  // Companion to the hero timeline: summarise the same real outlook, no
  // competing chart. Fetched by firm id so this card stays self-contained.
  const [outlook, setOutlook] = useState<EmissionsOutlook | null>(null)
  useEffect(() => {
    let on = true
    setOutlook(null)
    api.getEmissionsOutlook(position.firmId).then((o) => on && setOutlook(o))
    return () => {
      on = false
    }
  }, [position.firmId])

  const last = outlook?.months[outlook.months.length - 1]
  const defLo = last ? Math.max(0, last.cumP10 - outlook!.freeAllocation) : null
  const defHi = last ? Math.max(0, last.cumP90 - outlook!.freeAllocation) : null
  const overshoot = outlook?.overshoot ? `${outlook.overshoot.label} ${outlook.year}` : null

  return (
    <Card className="flex flex-col gap-3">
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
        <p className="mt-1.5 text-[12px] text-muted">{short ? 'Must buy' : 'Can sell'} this compliance year</p>
      </div>

      {/* Summary of the real Sybilion forecast shown on the hero timeline above. */}
      <div className="mt-1 space-y-2 rounded-xl border border-border bg-surface2/40 p-3">
        <div className="flex items-center justify-between text-[13px]">
          <span className="text-muted">Overshoot window</span>
          {overshoot ? (
            <span className="font-medium" style={{ color: accent }}>{overshoot}</span>
          ) : outlook ? (
            <span className="font-medium text-signal">within allocation</span>
          ) : (
            <span className="font-mono text-muted">…</span>
          )}
        </div>
        <div className="flex items-center justify-between text-[13px]">
          <span className="text-muted">p10–p90 deficit</span>
          {defLo != null && defHi != null ? (
            <span className="font-mono font-medium text-ink">{tons(defLo)} – {tons(defHi)}</span>
          ) : (
            <span className="font-mono text-muted">…</span>
          )}
        </div>
        <div className="flex items-center gap-1 border-t border-border/60 pt-2 text-[11px] text-muted">
          <ArrowUp size={12} />
          See the CarbonEdge timeline above for the full emissions &amp; price forecast.
        </div>
      </div>
    </Card>
  )
}
