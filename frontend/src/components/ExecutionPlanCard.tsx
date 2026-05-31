import { ArrowUpRight, Target, AlertTriangle, Activity, Coins, Shield, Scale } from 'lucide-react'
import { Card, ConfidenceBadge, AnimatedNumber, Donut, CHANNEL_COLOR, CHANNEL_LABEL } from './primitives'
import type { ExecutionPlan, Scenario } from '@/data/types'
import { eurM, eurMSavings, tons } from '@/lib/utils'

const ACTION_COLOR: Record<string, string> = {
  BUY: '#D18500', LADDER: '#1E70B8', SELL: '#009B72', WAIT: '#009B72',
}

function Stat({ label, value, color, format = eurM }: { label: string; value: number; color: string; format?: (n: number) => string }) {
  return (
    <div>
      <div className="label">{label}</div>
      <div className="mt-0.5 font-display text-xl font-bold" style={{ color }}>
        <AnimatedNumber value={value} format={format} />
      </div>
    </div>
  )
}

function parseTriggerText(t: string) {
  const match = t.match(/^\[(.*?)\]\s*(.*)$/)
  if (!match) {
    return { category: 'Trigger', message: t }
  }
  return { category: match[1], message: match[2] }
}

function TriggerItem({ text, planColor }: { text: string; planColor: string }) {
  const parsed = parseTriggerText(text)
  const category = parsed.category.toUpperCase()
  let msg = parsed.message

  // Default values
  let icon = <Target size={14} className="text-muted" />
  let badgeColor = 'bg-surface2 text-muted-foreground'
  let progressVal: number | null = null
  let progressColor = planColor
  let progressLabel = ''
  let progressMax = 100
  let budgetAllocated: number | null = null
  let budgetReserve: number | null = null

  if (category === 'EPU' || category === 'EPU SPIKE') {
    icon = <AlertTriangle size={14} className="text-amber" />
    badgeColor = 'bg-[#FFF8E8] text-amber border border-amber/20'
    
    // Parse EPU value e.g. "EPU: 456"
    const epuValMatch = msg.match(/EPU:\s*(\d+)/i)
    if (epuValMatch) {
      progressVal = parseInt(epuValMatch[1], 10)
      progressMax = 500
      progressLabel = `EPU Volatility Index: ${progressVal}`
      progressColor = progressVal > 250 ? '#D66A2E' : progressVal > 150 ? '#B07B2E' : '#009B72'
    }
    // Simplify message: extract crisis advisory if present
    if (msg.includes('CRISIS:')) {
      const parts = msg.split('|')
      msg = parts[parts.length - 1].trim()
    }
  } else if (category === 'DRIVERS') {
    icon = <Activity size={14} className="text-blue" />
    badgeColor = 'bg-blue/10 text-blue border border-blue/20'
    if (msg.includes('inactive')) {
      msg = 'External drivers neutral. Balanced weights active.'
    }
  } else if (category === 'DEMAND' || category === 'DEMAND DIVERGENCE') {
    icon = <Activity size={14} className="text-indigo" />
    badgeColor = 'bg-indigo/10 text-indigo border border-indigo/20'
    
    // Parse divergence: "divergence (1.00)"
    const divMatch = msg.match(/divergence\s*\(?(\d+\.?\d*)\)?/i)
    if (divMatch) {
      const val = parseFloat(divMatch[1])
      progressVal = Math.round(val * 100)
      progressLabel = `Sector Divergence: ${progressVal}%`
      progressColor = '#6366F1'
    }
    // Parse YoY: "Composite +0.1% YoY"
    if (msg.includes('Composite')) {
      const yoyMatch = msg.match(/Composite\s*([+-]\d+\.?\d*%)\s*YoY/i)
      if (yoyMatch) {
        msg = `Composite ${yoyMatch[1]} YoY. Industrial sectors pulling apart.`
      }
    }
  } else if (category === 'RISK') {
    icon = <Shield size={14} className="text-purple" />
    badgeColor = 'bg-purple/10 text-purple border border-purple/20'
    
    // Parse predictability: "predictability=0.85"
    const predMatch = msg.match(/predictability\s*=\s*(\d+\.?\d*)/i)
    if (predMatch) {
      const val = parseFloat(predMatch[1])
      progressVal = Math.round(val * 100)
      progressLabel = `Predictability Score: ${progressVal}%`
      progressColor = '#8B5CF6'
    }
    
    // Parse peers: "835 peers in steel/large"
    const peerMatch = msg.match(/(\d+)\s*peers\s*in\s*(\w+)/i)
    if (peerMatch) {
      msg = `${peerMatch[1]} peers monitored in ${peerMatch[2]} sector.`
    }
  } else if (category === 'BUDGET') {
    icon = <Coins size={14} className="text-emerald" />
    badgeColor = 'bg-emerald/10 text-emerald border border-emerald/20'
    
    // Parse budget: "EUR2,000,000 allocated... EUR200,000 held in reserve"
    const allocMatch = msg.match(/EUR([\d,]+)\s*allocated/i)
    const resMatch = msg.match(/EUR([\d,]+)\s*held\s*in\s*reserve/i)
    if (allocMatch && resMatch) {
      budgetAllocated = parseInt(allocMatch[1].replace(/,/g, ''), 10)
      budgetReserve = parseInt(resMatch[1].replace(/,/g, ''), 10)
    }
    
    // Clean up msg
    const tonsMatch = msg.match(/([\d,]+)\s*tons\s*reduced\s*@\s*EUR(\d+)/i)
    if (tonsMatch) {
      msg = `Decarbonization: ${tonsMatch[1]} t reduced @ €${tonsMatch[2]}/t.`
    }
  } else if (category === 'STRUCTURAL') {
    icon = <Scale size={14} className="text-amber" />
    badgeColor = 'bg-amber/10 text-amber border border-amber/20'
  }

  return (
    <div className="rounded-lg border border-border bg-surface px-3 py-2.5 transition-all hover:bg-surface2">
      <div className="flex items-center gap-1.5">
        {icon}
        <span className={`rounded px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider ${badgeColor}`}>
          {parsed.category}
        </span>
      </div>
      
      <p className="mt-1.5 text-[11.5px] leading-snug font-medium text-ink/90">{msg}</p>
      
      {/* Dynamic progress bar / meter */}
      {progressVal !== null && (
        <div className="mt-2">
          <div className="mb-0.5 flex items-center justify-between text-[9px] font-semibold text-muted">
            <span>{progressLabel}</span>
            <span>{Math.round((progressVal / progressMax) * 100)}%</span>
          </div>
          <div className="h-1 w-full rounded bg-surface3 overflow-hidden">
            <div 
              className="h-full rounded transition-all duration-500" 
              style={{ 
                width: `${(progressVal / progressMax) * 100}%`,
                backgroundColor: progressColor 
              }} 
            />
          </div>
        </div>
      )}

      {/* Dynamic Budget stack bar */}
      {budgetAllocated !== null && budgetReserve !== null && (
        <div className="mt-2">
          <div className="mb-0.5 flex items-center justify-between text-[9px] font-semibold text-muted">
            <span>Reserve/Allocated Split</span>
            <span>{Math.round((budgetReserve / (budgetAllocated + budgetReserve)) * 100)}% Reserve</span>
          </div>
          <div className="flex h-1 w-full rounded bg-surface3 overflow-hidden">
            <div 
              className="h-full bg-emerald transition-all duration-500" 
              style={{ width: `${(budgetAllocated / (budgetAllocated + budgetReserve)) * 100}%` }} 
              title="Allocated Spend"
            />
            <div 
              className="h-full bg-amber transition-all duration-500" 
              style={{ width: `${(budgetReserve / (budgetAllocated + budgetReserve)) * 100}%` }} 
              title="Held in Reserve"
            />
          </div>
        </div>
      )}
    </div>
  )
}

export function ExecutionPlanCard({ plan, scenario }: { plan: ExecutionPlan; scenario: Scenario }) {
  const shock = scenario === 'shock'
  const color = shock ? '#D18500' : ACTION_COLOR[plan.action] ?? '#1E70B8'
  const total = plan.channelMix.reduce((s, m) => s + m.volume, 0) || 1
  const segs = plan.channelMix.map((m) => ({ value: m.volume, color: CHANNEL_COLOR[m.key] }))

  // Filter out duplicate procurement logs
  const filteredTriggers = plan.triggers.filter((t) => !t.startsWith('[PROCUREMENT]'))

  return (
    <Card
      className="relative overflow-hidden bg-[#F8FBFF] p-4"
      style={
        {
          '--card-accent': color,
          ...(shock ? { borderColor: 'rgba(209,133,0,0.45)' } : {}),
        } as React.CSSProperties
      }
    >
      <div className="flex items-center justify-between">
        <span className="label">Execution plan · how to procure</span>
        <ConfidenceBadge c={plan.confidence} />
      </div>

      <div
        key={plan.action + scenario}
        className="mt-3 flex items-start gap-3"
      >
        <span className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1 font-display text-xl font-bold" style={{ color, background: color + '1A' }}>
          {plan.action}
          {shock && <ArrowUpRight size={18} />}
        </span>
        <p className="pt-0.5 text-[13px] leading-snug text-ink/80 line-clamp-2">{plan.headline}</p>
      </div>

      {/* channel mix donut + legend */}
      <div className="mt-4 flex items-center gap-5">
        <div className="relative grid shrink-0 place-items-center">
          <Donut segments={segs} size={80} stroke={11} />
          <div className="absolute text-center">
            <div className="font-display text-lg font-bold leading-none text-ink">
              <AnimatedNumber value={plan.deficitVolume} format={(n) => tons(n)} />
            </div>
            <div className="mt-0.5 text-[9px] uppercase tracking-wider text-muted">{plan.side}</div>
          </div>
        </div>
        <div className="grid flex-1 grid-cols-2 gap-x-3 gap-y-1.5">
          {plan.channelMix.map((m) => (
            <div key={m.key} className="flex items-center gap-2 text-[12px]">
              <span className="h-2.5 w-2.5 rounded-sm" style={{ background: CHANNEL_COLOR[m.key] }} />
              <span className="text-ink/85">{CHANNEL_LABEL[m.key]}</span>
              <span className="ml-auto font-mono text-muted">{Math.round((m.volume / total) * 100)}%</span>
            </div>
          ))}
        </div>
      </div>

      {/* cost summary */}
      <div className="mt-4 grid grid-cols-3 gap-3 border-t border-border pt-4">
        <Stat label="Expected spend" value={plan.expectedTotal} color="#0F172A" />
        <Stat label="Worst case" value={plan.worstCase} color="#D66A2E" />
        <Stat label="Saved vs naive" value={plan.savingsVsNaive ?? plan.savingsVsBuyAllNow} color={color} format={eurMSavings} />
      </div>

      {/* monitoring triggers */}
      <div className="mt-4 border-t border-border pt-4">
        <span className="label flex items-center gap-1.5"><Target size={12} /> Monitoring signals &amp; limits</span>
        <div className="mt-3 space-y-2 max-h-[300px] overflow-y-auto pr-1">
          {filteredTriggers.map((t) => (
            <TriggerItem key={t} text={t} planColor={color} />
          ))}
        </div>
      </div>
    </Card>
  )
}
