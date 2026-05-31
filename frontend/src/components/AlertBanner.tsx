import { AnimatePresence, motion } from 'motion/react'
import { AlertTriangle } from 'lucide-react'
import { useScenario } from '@/state/scenario'

export function AlertBanner() {
  const { shockActive } = useScenario()
  return (
    <AnimatePresence>
      {shockActive && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: 'auto', opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
          className="overflow-hidden"
        >
          <div className="relative mx-auto max-w-[1500px] px-6 pt-4">
            <div className="relative overflow-hidden rounded-xl border border-amber/40 bg-amber/10 px-5 py-3">
              <motion.div
                className="absolute inset-y-0 -left-1/3 w-1/3 bg-gradient-to-r from-transparent via-amber/20 to-transparent"
                animate={{ x: ['0%', '400%'] }}
                transition={{ duration: 2.2, repeat: Infinity, ease: 'linear' }}
              />
              <div className="relative flex items-center gap-3">
                <span className="grid h-8 w-8 place-items-center rounded-lg bg-amber/20">
                  <AlertTriangle size={16} className="text-amber" />
                </span>
                <div className="flex-1">
                  <span className="font-display text-sm font-semibold text-amber">MID-RUN SHOCK · MARKET STABILITY RESERVE</span>
                  <span className="ml-2 text-sm text-ink/90">
                    MSR withdraws 20% of auction supply from next quarter. The primary market tightens — the agent
                    re-routes off auctions onto spot &amp; RFQ and pulls the held reserve forward.
                  </span>
                </div>
              </div>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
