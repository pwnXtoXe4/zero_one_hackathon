import { useEffect, useState } from 'react'
import { ScenarioProvider, useScenario } from '@/state/scenario'
import { api, getSourceState, onSourceChange, type View, type SourceState } from '@/data/api'
import type { EmissionsOutlook, HistoryPoint } from '@/data/types'
import { TopBar } from '@/components/TopBar'
import { AlertBanner } from '@/components/AlertBanner'
import { ShockDelta } from '@/components/ShockDelta'
import { CarbonEdgeTimeline } from '@/components/CarbonEdgeTimeline'
import { RecommendationCard } from '@/components/RecommendationCard'
import { PositionCard } from '@/components/PositionCard'
import { ExecutionPlanCard } from '@/components/ExecutionPlanCard'
import { MarketSnapshot } from '@/components/MarketSnapshot'
import { PriceForecastChart } from '@/components/PriceForecastChart'
import { DriverImportance } from '@/components/DriverImportance'
import { ChannelRouter } from '@/components/ChannelRouter'
import { AuctionCalendar } from '@/components/AuctionCalendar'
import { ExecutionTimeline } from '@/components/ExecutionTimeline'
import { TimingLadder } from '@/components/TimingLadder'
import { SmartMatchFeed } from '@/components/SmartMatchFeed'
import { OrderBook } from '@/components/OrderBook'

function Splash() {
  return (
    <div className="grid min-h-[70vh] place-items-center">
      <div className="flex flex-col items-center gap-3">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-border border-t-signal" />
        <span className="text-sm text-muted">Routing the deficit across channels…</span>
      </div>
    </div>
  )
}

function Dashboard() {
  const { firmId, scenario, shockActive } = useScenario()
  const [view, setView] = useState<View | null>(null)
  const [history, setHistory] = useState<HistoryPoint[]>([])
  const [outlook, setOutlook] = useState<EmissionsOutlook | null>(null)
  const [src, setSrc] = useState<SourceState>(getSourceState())

  useEffect(() => onSourceChange(setSrc), [])

  useEffect(() => {
    api.getHistory().then(setHistory)
  }, [])

  useEffect(() => {
    let on = true
    setOutlook(null)
    api.getEmissionsOutlook(firmId).then((o) => on && setOutlook(o))
    return () => {
      on = false
    }
  }, [firmId])

  useEffect(() => {
    let on = true
    api.getView(firmId, scenario).then((v) => on && setView(v))
    return () => {
      on = false
    }
  }, [firmId, scenario])

  return (
    <div className="grid-overlay min-h-screen">
      <div className="relative z-[1]">
        <TopBar />
        <AlertBanner />
        {view && <ShockDelta diff={view.diff} active={shockActive} />}

        <main className="mx-auto max-w-[1500px] px-6 py-6">
          {!view || !history.length || !outlook ? (
            <Splash />
          ) : (
<<<<<<< HEAD
            <motion.div variants={container} initial="hidden" animate="show" className="grid grid-cols-12 gap-4 [&_.card]:h-full">
              {/* HERO — the causal chain on one axis: emissions → overshoot → plan + price */}
              <motion.div variants={item} className="col-span-12">
                <CarbonEdgeTimeline outlook={outlook} forecast={view.forecast} plan={view.plan} scenario={scenario} />
              </motion.div>

              {/* Row A — recommendation · position · plan */}
              <motion.div variants={item} className="col-span-12 lg:col-span-4">
                <RecommendationCard recommendation={view.recommendation} scenario={scenario} />
              </motion.div>
              <motion.div variants={item} className="col-span-12 lg:col-span-3">
                <PositionCard firm={view.firm} position={view.position} />
              </motion.div>
              <motion.div variants={item} className="col-span-12 lg:col-span-5">
                <ExecutionPlanCard plan={view.plan} scenario={scenario} />
              </motion.div>
=======
            <div className="grid grid-cols-12 gap-3 [&_.card]:h-full">
              {/* Row A — position · plan · market */}
              <div className="col-span-12 lg:col-span-3">
                <PositionCard firm={view.firm} position={view.position} />
              </div>
              <div className="col-span-12 lg:col-span-6">
                <ExecutionPlanCard plan={view.plan} scenario={scenario} />
              </div>
              <div className="col-span-12 lg:col-span-3">
                <MarketSnapshot history={history} forecast={view.forecast} scenario={scenario} />
              </div>
>>>>>>> 13715d9ae121e06b585d401b19b77de167f4f3c8

              {/* Row B — forecast · drivers */}
              <div className="col-span-12 lg:col-span-8">
                <PriceForecastChart history={history} forecast={view.forecast} scenario={scenario} />
              </div>
              <div className="col-span-12 lg:col-span-4">
                <DriverImportance drivers={view.drivers} />
              </div>

              {/* Row C — channel router · auction calendar */}
              <div className="col-span-12 lg:col-span-5">
                <ChannelRouter channels={view.channels} scenario={scenario} />
              </div>
              <div className="col-span-12 lg:col-span-7">
                <AuctionCalendar auctions={view.auctions} scenario={scenario} />
              </div>

<<<<<<< HEAD
              {/* Row D — execution timeline · timing ladder · market snapshot */}
              <motion.div variants={item} className="col-span-12 lg:col-span-6">
                <ExecutionTimeline plan={view.plan} />
              </motion.div>
              <motion.div variants={item} className="col-span-12 lg:col-span-3">
                <TimingLadder ladder={view.ladder} recommendation={view.recommendation} />
              </motion.div>
              <motion.div variants={item} className="col-span-12 lg:col-span-3">
                <MarketSnapshot history={history} forecast={view.forecast} scenario={scenario} />
              </motion.div>

              {/* Row E — OTC desk · order book */}
              <motion.div variants={item} className="col-span-12 lg:col-span-7">
                <SmartMatchFeed matches={view.matches} scenario={scenario} />
              </motion.div>
              <motion.div variants={item} className="col-span-12 lg:col-span-5">
                <OrderBook orders={view.orders} />
              </motion.div>
            </motion.div>
=======
              {/* Row D — execution timeline · OTC desk */}
              <div className="col-span-12 lg:col-span-7">
                <ExecutionTimeline plan={view.plan} />
              </div>
              <div className="col-span-12 lg:col-span-5">
                <SmartMatchFeed matches={view.matches} scenario={scenario} />
              </div>
            </div>
>>>>>>> 13715d9ae121e06b585d401b19b77de167f4f3c8
          )}

          <footer className="mt-8 flex items-center justify-between border-t border-border/60 pt-4 text-[11px] text-muted">
            {src.source === 'live' ? (
              <span>
                <span className="font-semibold text-signal">● Live backend</span> · real EUA prices ·{' '}
                {src.forecastMode === 'fallback'
                  ? 'price forecast: deterministic fallback (Sybilion cache empty)'
                  : `Sybilion forecast (${src.forecastMode ?? 'cache'})`}{' '}
                · engine-routed plan · counterparties &amp; auction calendar simulated
              </span>
            ) : (
              <span>
                <span className="font-semibold text-amber">● Demo data (mock)</span> · backend offline ({src.reason}) ·
                start the API to see live Sybilion forecasts &amp; engine routing
              </span>
            )}
            <span>Forecasts powered by the Sybilion probabilistic API</span>
          </footer>
        </main>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <ScenarioProvider>
      <Dashboard />
    </ScenarioProvider>
  )
}
