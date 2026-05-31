import { useState } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import { ChevronDown, Zap, RotateCcw, Activity } from 'lucide-react'
import { FIRMS, positionOf, CURRENT_PRICE } from '@/data/mock'
import { useScenario } from '@/state/scenario'
import { SectorDot } from './primitives'
import { cn, tons } from '@/lib/utils'

function FirmSelector() {
  const { firmId, setFirmId } = useScenario()
  const [open, setOpen] = useState(false)
  const active = FIRMS.find((f) => f.id === firmId)!
  const pos = positionOf(active)
  return (
    <div className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-3 rounded-xl border border-border bg-surface2/70 px-3.5 py-2.5 text-left transition-colors hover:border-signal/40"
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
      <AnimatePresence>
        {open && (
          <>
            <div className="fixed inset-0 z-20" onClick={() => setOpen(false)} />
            <motion.div
              initial={{ opacity: 0, y: -8, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -8, scale: 0.98 }}
              transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
              className="absolute right-0 z-30 mt-2 max-h-[420px] w-[320px] overflow-auto rounded-xl border border-border bg-surface/95 p-1.5 shadow-card backdrop-blur-xl"
            >
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
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  )
}

function ShockButton() {
  const { shockActive, toggleShock } = useScenario()
  return (
    <button
      onClick={toggleShock}
      className={cn(
        'group relative flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition-all',
        shockActive
          ? 'bg-amber text-bg shadow-glowAmber'
          : 'border border-amber/40 bg-amber/10 text-amber hover:bg-amber/20',
      )}
    >
      {!shockActive && <span className="absolute inset-0 rounded-xl animate-pulseRing" />}
      {shockActive ? <RotateCcw size={16} /> : <Zap size={16} className="fill-amber" />}
      {shockActive ? 'Reset market' : 'Inject MSR cut'}
    </button>
  )
}

export function TopBar() {
  return (
    <header className="sticky top-0 z-10 border-b border-border/70 bg-bg/70 backdrop-blur-xl">
      <div className="mx-auto flex max-w-[1500px] items-center justify-between gap-4 px-6 py-3.5">
        <div className="flex items-center gap-3">
          <div className="grid h-9 w-9 place-items-center rounded-lg bg-signal/15 ring-1 ring-signal/30">
            <span className="font-display text-lg font-bold text-signal">C</span>
          </div>
          <div className="leading-none">
            <div className="font-display text-lg font-bold tracking-tight text-ink">
              Carbon<span className="text-signal">Edge</span>
            </div>
            <div className="text-[10px] uppercase tracking-[0.25em] text-muted">Allowance Marketplace</div>
          </div>
        </div>

        <div className="hidden items-center gap-2 rounded-full border border-border bg-surface2/50 px-3.5 py-1.5 md:flex">
          <Activity size={14} className="text-signal" />
          <span className="text-xs text-muted">EU ETS · EUA Dec-26</span>
          <span className="font-mono text-sm font-semibold text-ink">€{CURRENT_PRICE.toFixed(2)}</span>
          <span className="text-xs font-medium text-signal">▲ 1.4%</span>
        </div>

        <div className="flex items-center gap-3">
          <FirmSelector />
          <ShockButton />
        </div>
      </div>
    </header>
  )
}
