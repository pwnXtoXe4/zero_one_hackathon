import { motion } from 'motion/react'
import { Card } from './primitives'
import type { Driver } from '@/data/types'

export function DriverImportance({ drivers }: { drivers: Driver[] }) {
  const max = Math.max(...drivers.map((d) => d.importance))
  return (
    <Card className="bg-[#F6FCF9]" style={{ '--card-accent': '#009B72' } as React.CSSProperties}>
      <span className="label">What's moving the price</span>
      <p className="mt-1 text-[12px] leading-snug text-muted">External signals pushing the EUA price, ranked by importance.</p>
      <div className="mt-3.5 space-y-3">
        {drivers.map((d, i) => {
          const color = d.direction >= 0 ? '#009B72' : '#D66A2E'
          return (
            <div key={d.name}>
              <div className="mb-1 flex items-center justify-between text-xs">
                <span className="text-ink/85">{d.name}</span>
                <span className="font-mono text-muted">
                  {d.direction >= 0 ? '↑' : '↓'} {d.importance}
                </span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-sm bg-surface2">
                <motion.div
                  className="h-full rounded-sm"
                  style={{ background: color }}
                  initial={{ width: 0 }}
                  animate={{ width: `${(d.importance / max) * 100}%` }}
                  transition={{ duration: 0.7, delay: i * 0.05, ease: [0.22, 1, 0.36, 1] }}
                />
              </div>
            </div>
          )
        })}
      </div>
    </Card>
  )
}
