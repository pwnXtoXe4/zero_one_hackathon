import { Card, CHANNEL_COLOR, CHANNEL_LABEL } from './primitives'
import type { ChannelOption, Scenario } from '@/data/types'
import { cn, tons } from '@/lib/utils'

export function ChannelRouter({ channels, scenario }: { channels: ChannelOption[]; scenario: Scenario }) {
  const maxRec = Math.max(...channels.map((c) => c.recommendedVolume), 1)
  const routed = channels.filter((c) => c.recommendedVolume > 0).length

  return (
    <Card className="bg-[#F6FCF9]" style={{ '--card-accent': '#009B72' } as React.CSSProperties}>
      <div className="mb-1 flex items-center justify-between">
        <span className="label">Channel router · where to buy</span>
        <span className="chip">{routed} routed</span>
      </div>
      <p className="mb-3 text-[11px] leading-snug text-muted">
        Ranked by risk-adjusted cost <span className="text-ink/60">and</span> ability to fill — the cheapest per-tonne channel isn&rsquo;t always&nbsp;#1.
      </p>

      <div className="space-y-2">
        {channels.map((c) => {
          const color = CHANNEL_COLOR[c.key]
          const isRouted = c.recommendedVolume > 0
          return (
            <div
              key={c.key + scenario}
              className={cn(
                'rounded-lg border p-3 transition-colors',
                isRouted ? 'border-border bg-surface2/40' : 'border-border/50 bg-surface2/20 opacity-70',
              )}
              style={isRouted ? { boxShadow: `inset 2.5px 0 0 ${color}` } : undefined}
            >
              <div className="flex items-center gap-2.5">
                <span className="grid h-6 w-6 shrink-0 place-items-center rounded-md font-display text-xs font-bold" style={{ color, background: color + '1A' }}>
                  {c.rank}
                </span>
                <span className="text-sm font-semibold text-ink">{CHANNEL_LABEL[c.key]}</span>
                {c.rank === 1 && isRouted && (
                  <span className="rounded-md px-1.5 py-0.5 text-[10px] font-bold" style={{ color, background: color + '1A' }}>
                    BEST FIT
                  </span>
                )}
                <div className="ml-auto flex items-center gap-3 font-mono text-[12px]">
                  <span className="text-ink">€{c.expectedPrice.toFixed(1)}</span>
                  <span className="text-muted">{Math.round(c.fillProb * 100)}% fill</span>
                </div>
              </div>

              <div className="mt-2 flex items-center gap-3">
                <div className="h-1.5 flex-1 overflow-hidden rounded-sm bg-surface2">
                  <div
                    className="flow-bar h-full rounded-sm"
                    style={{ width: `${(c.recommendedVolume / maxRec) * 100}%`, background: color }}
                  />
                </div>
                <span className="w-16 shrink-0 text-right font-mono text-[12px]" style={{ color: isRouted ? color : '#7D8983' }}>
                  {isRouted ? tons(c.recommendedVolume) : '—'}
                </span>
              </div>

              <p className="mt-1.5 text-[11px] leading-snug text-muted">{c.reason}</p>
            </div>
          )
        })}
      </div>
    </Card>
  )
}
