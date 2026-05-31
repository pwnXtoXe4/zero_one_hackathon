import { Gavel } from 'lucide-react'
import { Card } from './primitives'
import type { AuctionDay, Scenario } from '@/data/types'
import { tons } from '@/lib/utils'

const TYPE: Record<string, [string, string]> = {
  CAP3: ['CAP3 · EU', '#009B72'], GERMANY: ['Germany', '#1E70B8'], POLAND: ['Poland', '#C19A16'],
}

export function AuctionCalendar({ auctions, scenario }: { auctions: AuctionDay[]; scenario: Scenario }) {
  const shock = scenario === 'shock'
  const maxVol = Math.max(...auctions.map((a) => a.volume), 1)

  return (
    <Card className="bg-[#F8FBFF]" style={{ '--card-accent': '#1E70B8' } as React.CSSProperties}>
      <div className="flex items-center justify-between">
        <span className="label flex items-center gap-1.5">
          <Gavel size={13} /> Primary market · EU ETS auctions
        </span>
        <span className={shock ? 'chip border-amber/40 text-amber' : 'chip'}>
          {shock ? 'MSR supply −20%' : 'EEX · 09:00–11:00 CET'}
        </span>
      </div>
      <p className="mt-1 text-[12px] leading-snug text-muted">
        Days the EU sells newly issued allowances. A coloured border marks the days the agent recommends bidding on.
      </p>

      <div className="mt-3.5 flex gap-3 overflow-x-auto pb-1">
        {auctions.map((a) => {
          const [tag, tc] = TYPE[a.type] ?? [a.type, '#69756F']
          const targeted = a.targetVolume > 0
          const accent = a.msrAffected ? '#D18500' : targeted ? '#009B72' : null
          return (
            <div
              key={a.id + scenario}
              className="relative min-w-[162px] flex-1 rounded-lg border bg-surface2/55 p-3"
              style={{ borderColor: accent ? accent + '66' : undefined }}
            >
              <div className="flex items-center justify-between">
                <span className="rounded-md px-1.5 py-0.5 text-[10px] font-semibold" style={{ color: tc, background: tc + '14' }}>
                  {tag}
                </span>
                {a.msrAffected && (
                  <span className="rounded bg-amber/15 px-1.5 py-0.5 text-[9px] font-bold text-amber">−20% MSR</span>
                )}
              </div>

              <div className="mt-2 text-sm font-semibold text-ink">{a.label}</div>

              <div className="mt-2.5 space-y-1.5">
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-muted">Volume</span>
                  <span className="font-mono text-ink">{tons(a.volume)}</span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-sm bg-surface2">
                  <div
                    className="flow-bar h-full rounded-sm"
                    style={{ width: `${(a.volume / maxVol) * 100}%`, background: tc }}
                  />
                </div>
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-muted">Est. clearing</span>
                  <span className="font-mono text-ink">€{a.expectedClearing.toFixed(1)}</span>
                </div>
              </div>

              {targeted ? (
                <div className="mt-2.5 rounded-lg bg-signal/10 px-2 py-1.5">
                  <div className="text-[9px] font-semibold uppercase tracking-wide text-signal/80">Recommended bid</div>
                  <div className="font-mono text-[12px] text-signal">
                    {tons(a.targetVolume)} @ ≤€{a.recommendedBid?.toFixed(1)}
                  </div>
                </div>
              ) : (
                <div className="mt-2.5 text-[10px] text-muted">
                  {a.recommendedBid != null ? `Watch · max €${a.recommendedBid.toFixed(1)}` : 'Monitor only'}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </Card>
  )
}
