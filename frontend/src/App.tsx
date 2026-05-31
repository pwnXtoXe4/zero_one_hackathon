import { useEffect, useState } from 'react'
import { motion } from 'motion/react'
import { ScenarioProvider, useScenario } from '@/state/scenario'
import { api, type View } from '@/data/api'
import type { HistoryPoint } from '@/data/types'
import { TopBar } from '@/components/TopBar'
import { AlertBanner } from '@/components/AlertBanner'
import { ShockDelta } from '@/components/ShockDelta'
import { PositionCard } from '@/components/PositionCard'
import { ExecutionPlanCard } from '@/components/ExecutionPlanCard'
import { MarketSnapshot } from '@/components/MarketSnapshot'
import { PriceForecastChart } from '@/components/PriceForecastChart'
import { DriverImportance } from '@/components/DriverImportance'
import { ChannelRouter } from '@/components/ChannelRouter'
import { AuctionCalendar } from '@/components/AuctionCalendar'
import { ExecutionTimeline } from '@/components/ExecutionTimeline'
import { SmartMatchFeed } from '@/components/SmartMatchFeed'

const container = {
  hidden: {},
  show: { transition: { staggerChildren: 0.025, delayChildren: 0.02 } },
}
const item = {
  hidden: { opacity: 0, y: 6 },
  show: { opacity: 1, y: 0, transition: { duration: 0.22, ease: [0.2, 0, 0.2, 1] } },
}

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

  useEffect(() => {
    api.getHistory().then(setHistory)
  }, [])

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
          {!view || !history.length ? (
            <Splash />
          ) : (
            <motion.div variants={container} initial="hidden" animate="show" className="grid grid-cols-12 gap-3 [&_.card]:h-full">
              {/* Row A — position · plan · market */}
              <motion.div variants={item} className="col-span-12 lg:col-span-3">
                <PositionCard firm={view.firm} position={view.position} />
              </motion.div>
              <motion.div variants={item} className="col-span-12 lg:col-span-6">
                <ExecutionPlanCard plan={view.plan} scenario={scenario} />
              </motion.div>
              <motion.div variants={item} className="col-span-12 lg:col-span-3">
                <MarketSnapshot history={history} forecast={view.forecast} scenario={scenario} />
              </motion.div>

              {/* Row B — forecast · drivers */}
              <motion.div variants={item} className="col-span-12 lg:col-span-8">
                <PriceForecastChart history={history} forecast={view.forecast} scenario={scenario} />
              </motion.div>
              <motion.div variants={item} className="col-span-12 lg:col-span-4">
                <DriverImportance drivers={view.drivers} />
              </motion.div>

              {/* Row C — channel router · auction calendar */}
              <motion.div variants={item} className="col-span-12 lg:col-span-5">
                <ChannelRouter channels={view.channels} scenario={scenario} />
              </motion.div>
              <motion.div variants={item} className="col-span-12 lg:col-span-7">
                <AuctionCalendar auctions={view.auctions} scenario={scenario} />
              </motion.div>

              {/* Row D — execution timeline · OTC desk */}
              <motion.div variants={item} className="col-span-12 lg:col-span-7">
                <ExecutionTimeline plan={view.plan} />
              </motion.div>
              <motion.div variants={item} className="col-span-12 lg:col-span-5">
                <SmartMatchFeed matches={view.matches} scenario={scenario} />
              </motion.div>
            </motion.div>
          )}

          <footer className="mt-8 flex items-center justify-between border-t border-border/60 pt-4 text-[11px] text-muted">
            <span>
              <span className="font-semibold text-signal">Live</span> · real EUA prices + Sybilion forecast · counterparties &amp; auctions simulated
            </span>
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
