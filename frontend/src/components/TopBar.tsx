import { useEffect, useState } from 'react'
import { ChevronDown, Activity } from 'lucide-react'
import { FIRMS, positionOf, CURRENT_PRICE } from '@/data/mock'
import { api } from '@/data/api'
import { useScenario } from '@/state/scenario'
import { SectorDot } from './primitives'
import { cn, tons } from '@/lib/utils'
import type { HistoryPoint } from '@/data/types'

const TAPE = [
  ['EUA Dec-26', '€80.10', '+1.4%', 'ticker-up'],
  ['CAP3 Jun02', '29.0k t', 'bid ≤ €80.3', 'ticker-up'],
  ['MSR risk', 'watch', '+20bp', 'ticker-warn'],
  ['OTC flow', '36.5k t', 'live', 'ticker-hot'],
  ['Gas signal', '30', '↑', 'ticker-up'],
  ['CBAM', '25', '↑', 'ticker-up'],
]

function FirmSelector() {
  const { firmId, setFirmId } = useScenario()
  const [open, setOpen] = useState(false)
  const active = FIRMS.find((f) => f.id === firmId)!
  const pos = positionOf(active)
  return (
    <div className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-3 rounded-lg border border-border bg-surface px-3 py-2 text-left transition-colors hover:border-signal/50"
      >
        <SectorDot sector={active.sector} />
        <div className="leading-tight">
          <div className="font-display text-[15px] font-semibold text-ink">{active.name}</div>
          <div className="text-[11px] text-muted">
            {active.sector} ·{' '}
            <span className={pos.side === 'SHORT' ? 'text-amber' : 'text-signal'}>
              {pos.side} {tons(Math.abs(pos.deficit))}
            </span>
          </div>
        </div>
        <ChevronDown size={16} className={cn('text-muted transition-transform', open && 'rotate-180')} />
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-20" onClick={() => setOpen(false)} />
          <div className="absolute right-0 z-30 mt-2 max-h-[420px] w-[320px] overflow-auto rounded-lg border border-border bg-surface p-1.5 shadow-raised">
            {FIRMS.map((f) => {
              const p = positionOf(f)
              return (
                <button
                  key={f.id}
                  onClick={() => {
                    setFirmId(f.id)
                    setOpen(false)
                  }}
                  className={cn(
                    'flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-colors hover:bg-surface2',
                    f.id === firmId && 'bg-surface2',
                  )}
                >
                  <SectorDot sector={f.sector} />
                  <span className="flex-1 text-sm text-ink">{f.name}</span>
                  <span className={cn('text-[11px] font-medium', p.side === 'SHORT' ? 'text-amber' : 'text-signal')}>
                    {p.side === 'SHORT' ? '−' : '+'}
                    {tons(Math.abs(p.deficit))}
                  </span>
                </button>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}

function MarketTape() {
  const items = [...TAPE, ...TAPE, ...TAPE]
  return (
    <div className="market-tape">
      <div className="market-tape-track">
        {items.map(([name, value, change, tone], i) => (
          <span key={`${name}-${i}`} className="inline-flex items-center gap-2">
            <span className="text-white/70">{name}</span>
            <span className="font-semibold text-white">{value}</span>
            <span className={tone}>{change}</span>
          </span>
        ))}
      </div>
    </div>
  )
}

export function TopBar() {
  const [history, setHistory] = useState<HistoryPoint[]>([])
  useEffect(() => {
    api.getHistory().then(setHistory)
  }, [])
  const last = history[history.length - 1]
  const prev = history[history.length - 2]
  const price = last?.price ?? CURRENT_PRICE
  const change = last && prev && prev.price ? ((last.price - prev.price) / prev.price) * 100 : null
  const up = (change ?? 0) >= 0

  return (
    <header className="sticky top-0 z-10 border-b border-border bg-bg/95">
      <div className="mx-auto flex max-w-[1500px] items-center justify-between gap-4 px-6 py-3">
        <div className="flex items-center gap-3">
          <div className="grid h-9 w-9 place-items-center rounded-md border border-signal/35 bg-surface">
            <span className="font-display text-lg font-bold text-signal">C</span>
          </div>
          <div className="leading-none">
            <div className="font-display text-lg font-bold tracking-normal text-ink">
              Carbon<span className="text-signal">Edge</span>
            </div>
            <div className="text-[10px] uppercase tracking-normal text-muted">Allowance Marketplace</div>
          </div>
        </div>

        <div className="hidden items-center gap-2 rounded-md border border-border bg-surface px-3 py-1.5 md:flex">
          <Activity size={14} className="text-signal" />
          <span className="text-xs text-muted">EU ETS · EUA spot</span>
          <span className="font-mono text-sm font-semibold text-ink">€{price.toFixed(2)}</span>
          {change != null && (
            <span className={cn('text-xs font-medium', up ? 'text-signal' : 'text-danger')}>
              {up ? '▲' : '▼'} {Math.abs(change).toFixed(1)}%
            </span>
          )}
        </div>

        <div className="flex items-center gap-3">
          <FirmSelector />
        </div>
      </div>
      <MarketTape />
    </header>
  )
}
