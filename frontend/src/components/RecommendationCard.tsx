import { motion } from 'motion/react'
import { ArrowUpRight, Check } from 'lucide-react'
import { Card, RingGauge, AnimatedNumber } from './primitives'
import type { Recommendation, Scenario } from '@/data/types'
import { eurM } from '@/lib/utils'

function actionColor(a: string, shock: boolean) {
  if (a === 'BUY') return shock ? '#D97706' : '#0EA371'
  if (a === 'LADDER') return '#2563EB'
  if (a === 'WAIT') return '#0EA371'
  return '#2563EB'
}

function Stat({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div>
      <div className="label">{label}</div>
      <div className="mt-0.5 font-display text-2xl font-bold" style={{ color }}>
        <AnimatedNumber value={value} format={eurM} />
      </div>
    </div>
  )
}

export function RecommendationCard({ recommendation: r, scenario }: { recommendation: Recommendation; scenario: Scenario }) {
  const shock = scenario === 'shock'
  const color = actionColor(r.action, shock)
  return (
    <Card
      className="relative overflow-hidden"
      style={shock ? { borderColor: 'rgba(255,178,62,0.45)', boxShadow: '0 0 70px -18px rgba(255,178,62,0.5)' } : undefined}
    >
      <span className="label">Agent recommendation</span>

      <div className="mt-3 flex items-start gap-4">
        <div className="relative grid shrink-0 place-items-center">
          <RingGauge pct={r.lockNowPct} color={color} />
          <span className="absolute font-display text-base font-bold" style={{ color }}>
            {r.lockNowPct}%
          </span>
        </div>

        <div className="flex-1">
          <motion.div key={r.action + scenario} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}>
            <span className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1 font-display text-xl font-bold" style={{ color, background: color + '1A' }}>
              {r.action}
              {shock && <ArrowUpRight size={18} />}
            </span>
            <p className="mt-2 font-display text-[16px] font-semibold leading-snug text-ink">{r.headline}</p>
          </motion.div>
        </div>
      </div>

      <ul className="mt-4 space-y-2">
        {r.rationale.map((x, i) => (
          <motion.li
            key={x}
            initial={{ opacity: 0, x: -6 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.12 + i * 0.07 }}
            className="flex items-start gap-2 text-[13px] leading-snug text-ink/85"
          >
            <Check size={14} className="mt-0.5 shrink-0" style={{ color }} />
            {x}
          </motion.li>
        ))}
      </ul>

      <div className="mt-5 grid grid-cols-2 gap-3 border-t border-border pt-4">
        <Stat label="Exposure at risk" value={r.costAtRisk} color="#0F172A" />
        <Stat label="Saved vs naive" value={r.savingsVsNaive} color={color} />
      </div>
    </Card>
  )
}
