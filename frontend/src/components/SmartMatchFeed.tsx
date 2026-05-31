import { ArrowRight, Clock, Zap } from 'lucide-react'
import { Card, SectorDot } from './primitives'
import type { Match, Scenario } from '@/data/types'
import { tons } from '@/lib/utils'

function TimingPill({ timing }: { timing: 'NOW' | 'WAIT' }) {
  const now = timing === 'NOW'
  return (
    <span
      className="inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-bold"
      style={now ? { color: '#D18500', background: '#D185001F' } : { color: '#1E70B8', background: '#1E70B81F' }}
    >
      {now ? <Zap size={11} className="fill-current" /> : <Clock size={11} />}
      {timing}
    </span>
  )
}

export function SmartMatchFeed({ matches, scenario }: { matches: Match[]; scenario: Scenario }) {
  return (
    <Card className="flex flex-col bg-[#FFF9F4]" style={{ '--card-accent': '#D66A2E' } as React.CSSProperties}>
      <div className="mb-3 flex items-center justify-between">
        <span className="label flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-sm" style={{ background: '#D66A2E' }} />
          OTC desk · bilateral offers
        </span>
        <span className="chip">{matches.length} live</span>
      </div>
      <div className="space-y-2.5">
        {matches.map((m) => (
          <div
            key={m.id + scenario}
            className="group rounded-lg border border-border bg-surface2/45 p-3 transition-colors hover:border-signal/40"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <SectorDot sector={m.counterpartySector} />
                <div>
                  <div className="text-sm font-medium text-ink">{m.counterparty}</div>
                  <div className="text-[11px] text-muted">{m.counterpartySector} · fit {m.fit}%</div>
                </div>
              </div>
              <TimingPill timing={m.timing} />
            </div>
            <div className="mt-2.5 flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm">
                <span className="font-mono text-ink">{tons(m.volume)}</span>
                <ArrowRight size={13} className="text-muted" />
                <span className="font-mono font-semibold text-signal">€{m.price.toFixed(2)}</span>
              </div>
              <button className="rounded-lg bg-signal/15 px-3 py-1.5 text-xs font-semibold text-signal opacity-0 transition-opacity hover:bg-signal/25 group-hover:opacity-100">
                Execute
              </button>
            </div>
            <p className="mt-2 text-[11px] leading-snug text-muted">{m.rationale}</p>
          </div>
        ))}
      </div>
    </Card>
  )
}
