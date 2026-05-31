export type Sector =
  | 'Steel' | 'Cement' | 'Chemicals' | 'Power' | 'Aviation' | 'Refining' | 'Paper' | 'Glass' | 'Food'
export type Scenario = 'baseline' | 'shock'
export type Side = 'buy' | 'sell'
export type Action = 'BUY' | 'WAIT' | 'LADDER' | 'SELL'
export type Confidence = 'high' | 'medium' | 'low'

export interface Firm {
  id: string
  name: string
  sector: Sector
  baselineEmissions: number // tCO2 / yr
  freeAllocation: number // tCO2 / yr
  holdings: number // allowances held
}

export interface Position {
  firmId: string
  forecastEmissions: number
  deficit: number // >0 = SHORT (must buy) ; <0 = LONG (surplus to sell)
  side: 'SHORT' | 'LONG'
  confidence: Confidence
}

export interface ForecastPoint {
  month: string
  label: string
  p05: number
  p25: number
  p50: number
  p75: number
  p95: number
}

export interface HistoryPoint {
  month: string
  label: string
  price: number
}

export interface EmissionsMonth {
  month: string
  label: string
  isForecast: boolean
  p10: number
  p50: number
  p90: number
  cumP10: number
  cumP50: number
  cumP90: number
}

export interface EmissionsOvershoot {
  startMonth: string
  startLabel: string
  expectedMonth: string
  expectedLabel: string
  endMonth: string
  endLabel: string
  label: string
}

/** Cumulative emissions outlook vs free allocation → overshoot zone. */
export interface EmissionsOutlook {
  companyId: string
  company: string
  unit: string
  year: number
  source: 'sybilion' | 'climate_trace_actuals + sybilion_forecast' | 'climate_trace_projection' | 'synthetic'
  freeAllocation: number
  annualEmissionsP50: number
  annualDeficitP50: number
  months: EmissionsMonth[]
  overshoot: EmissionsOvershoot | null
}

export interface Driver {
  name: string
  importance: number // 0..100
  direction: number // -1..1
}

/** A public EU-ETS policy fact with its expected sign on the EUA price.
 *  CarbonEdge's own domain model — deliberately separate from the statistical
 *  Sybilion `Driver`s (whose signal universe has no ETS-specific series). */
export interface PolicyEvent {
  date: string // YYYY-MM-DD
  period?: string // e.g. "Sep 2025 – Aug 2026"
  title: string
  type: 'supply' | 'demand' | 'regulatory'
  direction: number // -1..1 expected sign on the price
  importance: number // 0..100
  detail: string
  source: string
}

export interface Recommendation {
  action: Action
  headline: string
  lockNowPct: number
  confidence: Confidence
  rationale: string[]
  costAtRisk: number
  savingsVsNaive: number
}

export interface Match {
  id: string
  counterparty: string
  counterpartySector: Sector
  side: Side // from active firm's perspective
  volume: number
  price: number
  timing: 'NOW' | 'WAIT'
  fit: number // 0..100
  rationale: string
}

export interface Order {
  id: string
  firm: string
  sector: Sector
  side: Side
  volume: number
  price: number
}

export interface LadderStep {
  label: string
  pct: number
  when: string
  note: string
}

// ── Execution Optimizer · channel + auction routing ──────────────
export type ChannelKey = 'AUCTION' | 'SPOT' | 'RFQ' | 'OTC'
export type MixKey = ChannelKey | 'WAIT'
export type TrancheStatus = 'EXECUTE' | 'SCHEDULED' | 'WAIT'

/** One procurement channel scored for the active deficit. */
export interface ChannelOption {
  key: ChannelKey
  effCost: number // risk-adjusted €/t (the ranking metric)
  expectedPrice: number // raw €/t
  fillProb: number // 0..1 chance of filling the requested lot
  available: number // EUA reachable via this channel over the horizon
  recommendedVolume: number
  rank: number // 1 = best
  reason: string
}

/** A concrete primary-market auction in the planning horizon. */
export interface AuctionDay {
  id: string
  type: 'CAP3' | 'GERMANY' | 'POLAND'
  date: string // YYYY-MM-DD
  label: string // "Tue 02 Jun"
  volume: number // lot offered that day
  expectedClearing: number // €/t derived from the forecast
  recommendedBid: number | null // max bid the agent would place
  targetVolume: number // how much the plan takes here
  msrAffected: boolean
}

/** One slice of the execution plan: buy X via channel Y at time Z. */
export interface Tranche {
  id: string
  when: string
  channel: ChannelKey
  volume: number
  price: number // expected €/t (0 = held / wait)
  maxBid: number | null
  status: TrancheStatus
  reason: string
}

export interface MixSlice {
  key: MixKey
  volume: number
}

export interface ExecutionPlan {
  deficitVolume: number
  side: 'SHORT' | 'LONG'
  headline: string
  action: Action
  confidence: Confidence
  channelMix: MixSlice[]
  tranches: Tranche[]
  expectedTotal: number // total € spend (executed + scheduled + held@forecast)
  worstCase: number
  savingsVsBuyAllNow: number
  savingsVsYearEnd: number
  triggers: string[]
}

/** Before/after delta produced by a mid-run shock (MSR auction cut). */
export interface ScenarioDiff {
  event: string
  mixBefore: MixSlice[]
  mixAfter: MixSlice[]
  timingShiftDays: number
  extraCostIfNoAdapt: number
  savingsFromAdapting: number
  narrative: string
}
