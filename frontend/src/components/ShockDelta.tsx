import { AnimatePresence, motion } from 'motion/react'
import { ArrowRight, Clock, ShieldCheck } from 'lucide-react'
import { CHANNEL_COLOR, CHANNEL_LABEL, AnimatedNumber } from './primitives'
import type { MixSlice, ScenarioDiff } from '@/data/types'
import { eurM } from '@/lib/utils'

function Ribbon({ mix, label }: { mix: MixSlice[]; label: string }) {
  const total = mix.reduce((s, m) => s + m.volume, 0) || 1
  return (
    <div className="min-w-0 flex-1">
      <div className="mb-1 text-[10px] uppercase tracking-wider text-muted">{label}</div>
      <div className="flex h-3 overflow-hidden rounded-sm bg-surface2">
        {mix.map((m) => (
          <motion.div
            key={m.key}
            initial={{ width: 0 }}
            animate={{ width: `${(m.volume / total) * 100}%` }}
            transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
            style={{ background: CHANNEL_COLOR[m.key] }}
            title={CHANNEL_LABEL[m.key]}
          />
        ))}
      </div>
      <div className="mt-1.5 flex flex-wrap gap-x-2.5 gap-y-0.5">
        {mix.map((m) => (
          <span key={m.key} className="flex items-center gap-1 text-[10px] text-muted">
            <span className="h-2 w-2 rounded-sm" style={{ background: CHANNEL_COLOR[m.key] }} />
            {CHANNEL_LABEL[m.key]} {Math.round((m.volume / total) * 100)}%
          </span>
        ))}
      </div>
    </div>
  )
}

export function ShockDelta({ diff, active }: { diff: ScenarioDiff; active: boolean }) {
  return (
    <AnimatePresence>
      {active && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: 'auto', opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
          className="overflow-hidden"
        >
          <div className="mx-auto max-w-[1500px] px-6 pt-4">
            <div className="rounded-lg border border-amber/35 bg-surface p-4 shadow-card">
              <div className="mb-3 flex items-center gap-2">
                <span className="font-display text-sm font-bold tracking-normal text-amber">ADAPTIVE RE-ROUTING</span>
                <span className="hidden text-[12px] leading-snug text-muted md:inline">{diff.narrative}</span>
              </div>
              <div className="flex flex-col items-stretch gap-4 lg:flex-row lg:items-center">
                <Ribbon mix={diff.mixBefore} label="Baseline mix" />
                <ArrowRight className="mx-auto shrink-0 text-amber lg:mx-1" size={20} />
                <Ribbon mix={diff.mixAfter} label="After MSR cut" />
                <div className="flex shrink-0 gap-6 border-t border-border pt-3 lg:border-l lg:border-t-0 lg:pl-6 lg:pt-0">
                  <div>
                    <div className="label flex items-center gap-1"><Clock size={11} /> Pulled forward</div>
                    <div className="font-display text-lg font-bold text-amber tnum">{diff.timingShiftDays}d</div>
                  </div>
                  <div>
                    <div className="label flex items-center gap-1"><ShieldCheck size={11} /> Saved by adapting</div>
                    <div className="font-display text-lg font-bold text-signal">
                      <AnimatedNumber value={diff.savingsFromAdapting} format={eurM} />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
