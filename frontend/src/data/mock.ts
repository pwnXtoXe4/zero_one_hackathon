import type {
  AuctionDay, ChannelOption, Driver, EmissionsMonth, EmissionsOutlook, ExecutionPlan, Firm,
  ForecastPoint, HistoryPoint, LadderStep, Match, MixKey, MixSlice, Order, Position, Recommendation,
  Scenario, ScenarioDiff, Tranche,
} from './types'
import { tons } from '@/lib/utils'

export const CURRENT_PRICE = 80.1
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

// Mirrors the backend's data/mock/companies.json (same ids) so the firm
// selector and the live /companies endpoint stay in sync.
// Real companies (Climate TRACE v5.5 facility emissions + Heidelberg group).
// Same ids as the backend companies.json so selector ↔ /companies stay in sync.
export const FIRMS: Firm[] = [
  { id: 'salzgitter_steel', name: 'Salzgitter Flachstahl', sector: 'Steel', baselineEmissions: 7569792, freeAllocation: 6400000, holdings: 250000 },
  { id: 'lengerich_cement', name: 'Lengerich Cement Plant', sector: 'Cement', baselineEmissions: 846693, freeAllocation: 690000, holdings: 30000 },
  { id: 'deuna_cement', name: 'Deuna Cement Plant', sector: 'Cement', baselineEmissions: 344341, freeAllocation: 285000, holdings: 15000 },
  { id: 'nordzucker_food', name: 'Nordzucker Klein Wanzleben', sector: 'Food', baselineEmissions: 107000, freeAllocation: 112000, holdings: 8000 },
  { id: 'uxheim_cement', name: 'Uxheim Cement Plant', sector: 'Cement', baselineEmissions: 41375, freeAllocation: 33000, holdings: 2000 },
]

export function positionOf(f: Firm): Position {
  const forecastEmissions = f.baselineEmissions
  const deficit = forecastEmissions - f.freeAllocation - f.holdings
  const mag = Math.abs(deficit)
  return {
    firmId: f.id,
    forecastEmissions,
    deficit,
    side: deficit >= 0 ? 'SHORT' : 'LONG',
    confidence: mag > 120000 ? 'high' : mag > 40000 ? 'medium' : 'low',
  }
}

// ---- emissions outlook (cumulative 2026 vs free allocation) ----
const SEASONAL = [0.86, 0.84, 0.95, 1.02, 1.05, 1.07, 1.08, 1.09, 1.05, 1.04, 0.99, 0.96]
const LATEST_ACTUAL = 5 // through May 2026

export function emissionsOutlook(f: Firm): EmissionsOutlook {
  const annual = f.baselineEmissions
  const base = annual / SEASONAL.reduce((s, x) => s + x, 0)
  const months: EmissionsMonth[] = []
  let c10 = 0
  let c50 = 0
  let c90 = 0
  for (let m = 1; m <= 12; m++) {
    const p50 = base * SEASONAL[m - 1]
    const isFc = m > LATEST_ACTUAL
    const spread = isFc ? 0.05 + 0.012 * (m - LATEST_ACTUAL) : 0
    const p10 = p50 * (1 - spread)
    const p90 = p50 * (1 + spread)
    c10 += p10
    c50 += p50
    c90 += p90
    months.push({
      month: `2026-${String(m).padStart(2, '0')}`,
      label: MONTHS[m - 1],
      isForecast: isFc,
      p10: Math.round(p10), p50: Math.round(p50), p90: Math.round(p90),
      cumP10: Math.round(c10), cumP50: Math.round(c50), cumP90: Math.round(c90),
    })
  }
  const alloc = f.freeAllocation
  const cross = (k: 'cumP10' | 'cumP50' | 'cumP90') => months.find((mm) => mm[k] >= alloc)
  const expected = cross('cumP50')
  const overshoot = expected
    ? (() => {
        const start = cross('cumP90') ?? expected
        const end = cross('cumP10') ?? months[months.length - 1]
        return {
          startMonth: start.month, startLabel: start.label,
          expectedMonth: expected.month, expectedLabel: expected.label,
          endMonth: end.month, endLabel: end.label,
          label: start.month !== end.month ? `${start.label}–${end.label}` : start.label,
        }
      })()
    : null
  return {
    companyId: f.id, company: f.name, unit: 'tCO2', year: 2026, source: 'synthetic',
    freeAllocation: alloc,
    annualEmissionsP50: months[months.length - 1].cumP50,
    annualDeficitP50: months[months.length - 1].cumP50 - alloc,
    months, overshoot,
  }
}

// ---- price history: 2018 (~€9) -> 2026 (€73), realistic arc ----
const ANCHORS: [string, number][] = [
  ['2018-01', 9], ['2018-07', 16], ['2018-12', 25], ['2019-06', 26], ['2020-03', 17],
  ['2020-12', 33], ['2021-07', 55], ['2021-12', 80], ['2022-08', 96], ['2023-02', 100],
  ['2023-09', 83], ['2024-02', 58], ['2024-09', 64], ['2025-03', 71], ['2025-10', 74],
]
export function history(): HistoryPoint[] {
  const out: HistoryPoint[] = []
  for (let i = 0; i < ANCHORS.length - 1; i++) {
    const [d0, p0] = ANCHORS[i]
    const [d1, p1] = ANCHORS[i + 1]
    const [y0, m0] = d0.split('-').map(Number)
    const [y1, m1] = d1.split('-').map(Number)
    const span = (y1 - y0) * 12 + (m1 - m0)
    for (let k = 0; k < span; k++) {
      const t = k / span
      const idx = m0 - 1 + k
      const yy = y0 + Math.floor(idx / 12)
      const mm = ((idx % 12) + 12) % 12
      const noise = Math.sin(i * 5.1 + k * 1.7) * 1.6
      out.push({
        month: `${yy}-${String(mm + 1).padStart(2, '0')}`,
        label: `${MONTHS[mm]} '${String(yy).slice(2)}`,
        price: +(p0 + (p1 - p0) * t + noise).toFixed(2),
      })
    }
  }
  out.push({ month: '2026-04', label: `Apr '26`, price: CURRENT_PRICE })
  return out
}

// ---- forecast (May–Oct 2026) ----
const FC_MONTHS = ['2026-05', '2026-06', '2026-07', '2026-08', '2026-09', '2026-10']
const BASE_P50 = [74.0, 74.8, 75.6, 76.5, 77.6, 79.0]
// MSR auction-supply cut → tighter primary market, moderate but confident upward repricing
const SHOCK_P50 = [78.0, 82.5, 85.4, 87.6, 89.3, 91.0]
export function forecast(scenario: Scenario): ForecastPoint[] {
  const p50s = scenario === 'shock' ? SHOCK_P50 : BASE_P50
  return FC_MONTHS.map((m, i) => {
    const p50 = p50s[i]
    const s = (scenario === 'shock' ? 0.09 : 0.055) + i * (scenario === 'shock' ? 0.016 : 0.011)
    return {
      month: m,
      label: MONTHS[+m.split('-')[1] - 1],
      p05: +(p50 * (1 - s * 1.6)).toFixed(1),
      p25: +(p50 * (1 - s * 0.7)).toFixed(1),
      p50: +p50.toFixed(1),
      p75: +(p50 * (1 + s * 0.7)).toFixed(1),
      p95: +(p50 * (1 + s * 1.6)).toFixed(1),
    }
  })
}

export function drivers(scenario: Scenario): Driver[] {
  return scenario === 'shock'
    ? [
        { name: 'Market Stability Reserve', importance: 68, direction: 0.9 },
        { name: 'Auction supply volume', importance: 44, direction: 0.9 },
        { name: 'EU ETS reform', importance: 33, direction: 0.7 },
        { name: 'CBAM phase-in', importance: 21, direction: 0.6 },
        { name: 'Natural gas price', importance: 12, direction: 0.4 },
      ]
    : [
        { name: 'EU ETS reform', importance: 45, direction: 0.8 },
        { name: 'Natural gas price', importance: 30, direction: 0.6 },
        { name: 'CBAM phase-in', importance: 25, direction: 0.7 },
        { name: 'Renewable auctions', importance: 18, direction: -0.5 },
        { name: 'Industrial output', importance: 15, direction: 0.5 },
      ]
}

export function recommendation(f: Firm, scenario: Scenario): Recommendation {
  const pos = positionOf(f)
  const vol = Math.abs(pos.deficit)
  if (pos.side === 'LONG') {
    return scenario === 'shock'
      ? {
          action: 'WAIT', headline: 'HOLD surplus — sell into the spike', lockNowPct: 0, confidence: 'high',
          rationale: ['Reform shock lifts EUA to €121 (p50, +66%)', 'Your surplus gains value every week held', 'Sell laddered above €110'],
          costAtRisk: vol * CURRENT_PRICE, savingsVsNaive: vol * (121 - CURRENT_PRICE),
        }
      : {
          action: 'WAIT', headline: 'HOLD surplus — structural drift up', lockNowPct: 0, confidence: 'medium',
          rationale: ['Cap tightens −4.2%/yr → rising floor', 'Forecast drifts to €79 by Oct', 'Sell partial above €78'],
          costAtRisk: vol * CURRENT_PRICE, savingsVsNaive: vol * (79 - CURRENT_PRICE),
        }
  }
  return scenario === 'shock'
    ? {
        action: 'BUY', headline: 'BUY 100% NOW — lock before the reform spike', lockNowPct: 100, confidence: 'high',
        rationale: ['EU accelerates ETS cap −20% → p50 €121 by Oct', 'Confidence band narrowed after policy confirmation', `Each month of delay ≈ €${Math.round((vol * 8) / 1e6)}M extra`],
        costAtRisk: vol * CURRENT_PRICE, savingsVsNaive: vol * (121 - CURRENT_PRICE) * 0.7,
      }
    : {
        action: 'LADDER', headline: 'BUY 60% NOW, ladder the rest', lockNowPct: 60, confidence: 'medium',
        rationale: ['Trajectory up €73 → €79 (p50)', 'Near-term band narrow, month 6 wide', '“EU ETS reform” driver importance rising'],
        costAtRisk: vol * CURRENT_PRICE, savingsVsNaive: vol * 4.5,
      }
}

export function matches(f: Firm, scenario: Scenario): Match[] {
  const sellers = FIRMS.filter((x) => x.id !== f.id && positionOf(x).side === 'LONG').slice(0, 4)
  const base = scenario === 'shock' ? 84.4 : 68.9
  const caps = [40000, 28000, 18000, 12000]
  return sellers.map((s, i) => ({
    id: `m${i}`,
    counterparty: s.name,
    counterpartySector: s.sector,
    side: 'buy',
    volume: Math.min(Math.abs(positionOf(s).deficit), caps[i] ?? 10000),
    price: +(base + i * 1.15).toFixed(2),
    timing: scenario === 'shock' ? 'NOW' : i < 2 ? 'NOW' : 'WAIT',
    fit: 96 - i * 7,
    rationale:
      scenario === 'shock'
        ? 'Lock before reform spike — offer may be pulled'
        : i < 2
          ? 'Best price + tight delivery window'
          : 'Price likely to dip — schedule for month 3',
  }))
}

export function orders(): Order[] {
  return FIRMS.map((f, i) => {
    const p = positionOf(f)
    const vol = Math.max(5000, Math.round((Math.abs(p.deficit) * 0.25) / 1000) * 1000)
    const off = ((i % 5) - 2) * 0.6
    return {
      id: `${f.id}-o`,
      firm: f.name,
      sector: f.sector,
      side: p.side === 'SHORT' ? 'buy' : 'sell',
      volume: vol,
      price: +(CURRENT_PRICE + (p.side === 'SHORT' ? 1.2 : -1.2) + off).toFixed(2),
    }
  })
}

export function ladder(_f: Firm, scenario: Scenario): LadderStep[] {
  if (scenario === 'shock')
    return [{ label: 'Now', pct: 100, when: 'Immediately', note: 'Lock entire deficit before the spike' }]
  return [
    { label: 'Now', pct: 60, when: 'This week', note: 'Trajectory up — lock the majority' },
    { label: 'Month 3', pct: 30, when: 'Aug 2026', note: 'Execute if price < €80' },
    { label: 'Month 6', pct: 10, when: 'Nov 2026', note: 'Re-evaluate at band position' },
  ]
}

// ════════════════════════════════════════════════════════════════
//  EXECUTION OPTIMIZER  ·  channel + auction routing
//  Shapes mirror the backend engine contract (AUCTION_PLAN.md §7),
//  so wiring the real /decisions/* endpoints is a drop-in swap.
// ════════════════════════════════════════════════════════════════

const FORECAST_END = (s: Scenario) => {
  const arr = s === 'shock' ? SHOCK_P50 : BASE_P50
  return arr[arr.length - 1]
}

function mixFromTranches(tr: Tranche[], waitVol: number): MixSlice[] {
  const m = new Map<MixKey, number>()
  for (const t of tr) m.set(t.channel, (m.get(t.channel) ?? 0) + t.volume)
  if (waitVol > 0) m.set('WAIT', waitVol)
  return [...m.entries()].map(([key, volume]) => ({ key, volume }))
}

/** Ranked channel comparison for the active deficit. */
export function channels(f: Firm, scenario: Scenario): ChannelOption[] {
  const pos = positionOf(f)
  const D = Math.abs(pos.deficit)
  const r1 = (k: number) => Math.round((D * k) / 100) * 100
  const shock = scenario === 'shock'

  if (pos.side === 'LONG') {
    return shock
      ? [
          { key: 'SPOT', effCost: 87.8, expectedPrice: 88.0, fillProb: 1.0, available: 999999, recommendedVolume: r1(0.6), rank: 1, reason: 'Deepest bid side — offload surplus into the MSR-driven spike now.' },
          { key: 'OTC', effCost: 87.0, expectedPrice: 87.2, fillProb: 0.9, available: r1(0.5), recommendedVolume: r1(0.4), rank: 2, reason: 'Bilateral buyers paying a premium for size — lock it.' },
          { key: 'RFQ', effCost: 86.2, expectedPrice: 86.0, fillProb: 0.95, available: 40000, recommendedVolume: 0, rank: 3, reason: 'Keep as fallback; spot is already absorbing volume.' },
        ]
      : [
          { key: 'SPOT', effCost: 73.0, expectedPrice: 73.1, fillProb: 1.0, available: 999999, recommendedVolume: r1(0.4), rank: 1, reason: 'Bank a partial surplus at today’s spot, no counterparty risk.' },
          { key: 'RFQ', effCost: 76.0, expectedPrice: 76.0, fillProb: 0.95, available: 40000, recommendedVolume: r1(0.35), rank: 2, reason: 'Sell into the rising floor over the next quarter.' },
          { key: 'OTC', effCost: 78.0, expectedPrice: 78.0, fillProb: 0.85, available: r1(0.5), recommendedVolume: r1(0.25), rank: 3, reason: 'Hold remainder for an OTC buyer at €78+.' },
        ]
  }

  // SHORT — procurement. Note: ranking blends price AND ability to fill,
  // so the cheapest per-tonne channel is not always rank 1.
  return shock
    ? [
        { key: 'SPOT', effCost: 74.8, expectedPrice: 74.6, fillProb: 1.0, available: 999999, recommendedVolume: r1(0.26), rank: 1, reason: 'Deep & immediate — absorbs the supply the MSR pulled out of the auction.' },
        { key: 'RFQ', effCost: 75.4, expectedPrice: 75.2, fillProb: 0.95, available: 30000, recommendedVolume: r1(0.27), rank: 2, reason: 'Flexible size to cover the former reserve before the market tightens further.' },
        { key: 'OTC', effCost: 70.9, expectedPrice: 70.6, fillProb: 0.9, available: 24000, recommendedVolume: r1(0.19), rank: 3, reason: 'Cheapest per tonne — but only 24k available, can’t close the gap alone.' },
        { key: 'AUCTION', effCost: 76.2, expectedPrice: 73.0, fillProb: 0.55, available: 23000, recommendedVolume: r1(0.28), rank: 4, reason: 'Lot cut −20% by the MSR; fill probability drops — bid up only for a partial fill.' },
      ]
    : [
        { key: 'AUCTION', effCost: 70.1, expectedPrice: 69.8, fillProb: 0.8, available: 29000, recommendedVolume: r1(0.4), rank: 1, reason: 'Cheapest risk-adjusted route; next CAP3 in 2 days. Sealed-bid — cap the bid at €71.2.' },
        { key: 'OTC', effCost: 70.6, expectedPrice: 69.9, fillProb: 0.9, available: 40000, recommendedVolume: r1(0.19), rank: 2, reason: 'NordCement @ €69.90 — instant settlement, counterparty rating 0.92.' },
        { key: 'RFQ', effCost: 71.3, expectedPrice: 70.5, fillProb: 0.95, available: 30000, recommendedVolume: r1(0.12), rank: 3, reason: 'Broker quote, flexible size — ideal for the second tranche.' },
        { key: 'SPOT', effCost: 72.4, expectedPrice: 73.1, fillProb: 1.0, available: 999999, recommendedVolume: 0, rank: 4, reason: 'Immediate but priciest. Keep as a fallback if an auction is missed.' },
      ]
}

/** Upcoming primary-market auctions in the planning horizon. */
export function auctions(f: Firm, scenario: Scenario): AuctionDay[] {
  const pos = positionOf(f)
  const short = pos.side === 'SHORT'
  const D = Math.abs(pos.deficit)
  const r1 = (k: number) => Math.round((D * k) / 100) * 100

  const base: AuctionDay[] = [
    { id: 'cap3-0602', type: 'CAP3', date: '2026-06-02', label: 'Tue 02 Jun', volume: 29000, expectedClearing: 69.8, recommendedBid: short ? 71.2 : null, targetVolume: short ? r1(0.4) : 0, msrAffected: false },
    { id: 'ger-0605', type: 'GERMANY', date: '2026-06-05', label: 'Fri 05 Jun', volume: 42000, expectedClearing: 70.1, recommendedBid: short ? 71.5 : null, targetVolume: 0, msrAffected: false },
    { id: 'cap3-0609', type: 'CAP3', date: '2026-06-09', label: 'Tue 09 Jun', volume: 29000, expectedClearing: 70.5, recommendedBid: short ? 71.8 : null, targetVolume: 0, msrAffected: false },
    { id: 'pol-0610', type: 'POLAND', date: '2026-06-10', label: 'Wed 10 Jun', volume: 18500, expectedClearing: 70.3, recommendedBid: null, targetVolume: 0, msrAffected: false },
    { id: 'cap3-0611', type: 'CAP3', date: '2026-06-11', label: 'Thu 11 Jun', volume: 29000, expectedClearing: 70.8, recommendedBid: null, targetVolume: 0, msrAffected: false },
  ]

  if (scenario !== 'shock') return base
  return base.map((a) => ({
    ...a,
    volume: Math.round((a.volume * 0.8) / 100) * 100,
    expectedClearing: +(a.expectedClearing + 3.2).toFixed(1),
    recommendedBid: a.recommendedBid != null ? +(a.recommendedBid + 3.3).toFixed(1) : null,
    targetVolume: a.id === 'cap3-0602' && short ? r1(0.28) : 0,
    msrAffected: true,
  }))
}

function buildPlan(side: 'SHORT' | 'LONG', D: number, tranches: Tranche[], reserve: number, scenario: Scenario): ExecutionPlan {
  const shock = scenario === 'shock'
  const fcEnd = FORECAST_END(scenario)
  const channelMix = mixFromTranches(tranches, reserve)
  const placedSpend = tranches.reduce((s, t) => s + t.volume * (t.price || fcEnd), 0)
  const expectedTotal = Math.round(placedSpend + reserve * fcEnd)
  const worstCase = Math.round(expectedTotal * (shock ? 1.16 : 1.11))
  const savingsVsBuyAllNow = Math.round(Math.abs(D * CURRENT_PRICE - expectedTotal))
  const savingsVsYearEnd = Math.round(Math.abs(D * fcEnd - expectedTotal))

  const short = side === 'SHORT'
  const action = short ? (shock ? 'BUY' : 'LADDER') : 'SELL'
  const headline = short
    ? shock
      ? `MSR cut — re-route off auctions: cover ${tons(D)} now via spot + RFQ`
      : `Cover ${tons(D)}: 40% at the next CAP3 auction, rest OTC + reserve`
    : shock
      ? `Sell ${tons(D)} surplus into the MSR-driven squeeze`
      : `Bank ${tons(D)} surplus in tranches as the floor rises`

  const triggers = short
    ? shock
      ? [
          'MSR confirmed: auction lots −20% → the secondary market is now the primary route',
          'If spot > €78 → accelerate the remaining RFQ tranche',
          'Re-check clearing after Tue’s auction — raise the bid if under-subscription risk rises',
        ]
      : [
          'If spot > €72 before the auction → pull the reserve forward',
          'If an MSR cut tightens auction supply → re-route to spot / RFQ',
          'If the production forecast drops → cancel the held tranche',
        ]
    : [
        'If spot > €78 → release the next sell tranche',
        'If the reform stalls → hold the remainder, the floor is still rising',
      ]

  return {
    deficitVolume: D, side, headline, action,
    confidence: shock ? 'high' : 'medium',
    channelMix, tranches,
    expectedTotal, worstCase, savingsVsBuyAllNow, savingsVsYearEnd, triggers,
  }
}

/** The full procurement / disposal plan: how much, when, through which channel. */
export function executionPlan(f: Firm, scenario: Scenario): ExecutionPlan {
  const pos = positionOf(f)
  const D = Math.abs(pos.deficit)
  const shock = scenario === 'shock'
  const r1 = (k: number) => Math.round((D * k) / 100) * 100

  if (pos.side === 'LONG') {
    const tr: Tranche[] = shock
      ? [
          { id: 's1', when: 'Now', channel: 'SPOT', volume: r1(0.6), price: 88.0, maxBid: null, status: 'EXECUTE', reason: 'MSR squeeze lifts secondary spot — sell surplus into strength.' },
          { id: 's2', when: 'This week', channel: 'OTC', volume: r1(0.4), price: 87.2, maxBid: null, status: 'EXECUTE', reason: 'Bilateral buyers bidding up; lock the premium.' },
        ]
      : [
          { id: 's1', when: 'Now', channel: 'SPOT', volume: r1(0.4), price: 73.0, maxBid: null, status: 'EXECUTE', reason: 'Bank a partial surplus at today’s spot.' },
          { id: 's2', when: 'Month 3', channel: 'RFQ', volume: r1(0.35), price: 76.0, maxBid: null, status: 'SCHEDULED', reason: 'Sell into the structural drift up.' },
          { id: 's3', when: 'Open', channel: 'OTC', volume: r1(0.25), price: 78.0, maxBid: null, status: 'WAIT', reason: 'Hold the remainder for an €78+ target.' },
        ]
    return buildPlan('LONG', D, tr, 0, scenario)
  }

  const tr: Tranche[] = shock
    ? [
        { id: 't1', when: 'Tue 02 Jun', channel: 'AUCTION', volume: r1(0.28), price: 73.0, maxBid: 74.5, status: 'EXECUTE', reason: 'MSR cuts the lot −20% — bid up for the reduced auction volume.' },
        { id: 't2', when: 'Now', channel: 'SPOT', volume: r1(0.26), price: 74.6, maxBid: null, status: 'EXECUTE', reason: 'Replace the lost auction supply on the secondary market immediately.' },
        { id: 't3', when: 'Now', channel: 'OTC', volume: r1(0.19), price: 70.6, maxBid: null, status: 'EXECUTE', reason: 'Lock NordCement before the offer is pulled — cheapest tonne available.' },
        { id: 't4', when: 'This week', channel: 'RFQ', volume: r1(0.27), price: 75.2, maxBid: null, status: 'EXECUTE', reason: 'Pull the former reserve forward — the market is tightening, don’t wait.' },
      ]
    : [
        { id: 't1', when: 'Tue 02 Jun', channel: 'AUCTION', volume: r1(0.4), price: 69.8, maxBid: 71.2, status: 'EXECUTE', reason: 'Cheapest risk-adjusted route — next CAP3 auction, bid ≤ €71.2.' },
        { id: 't2', when: 'Now', channel: 'OTC', volume: r1(0.19), price: 69.9, maxBid: null, status: 'EXECUTE', reason: 'NordCement @ €69.90 — fast settlement, counterparty rating 0.92.' },
        { id: 't3', when: 'Mon 09 Jun', channel: 'RFQ', volume: r1(0.12), price: 70.5, maxBid: null, status: 'SCHEDULED', reason: 'Broker quote, flexible size — second tranche.' },
      ]
  const placed = tr.reduce((s, t) => s + t.volume, 0)
  const reserve = shock ? 0 : Math.max(0, D - placed)
  return buildPlan('SHORT', D, tr, reserve, scenario)
}

/** Before/after delta for the MSR mid-run shock — drives the adaptive demo. */
export function scenarioDiff(f: Firm): ScenarioDiff {
  const D = Math.abs(positionOf(f).deficit)
  return {
    event: 'msr_auction_cut',
    mixBefore: executionPlan(f, 'baseline').channelMix,
    mixAfter: executionPlan(f, 'shock').channelMix,
    timingShiftDays: -21,
    extraCostIfNoAdapt: Math.round(D * 3.4),
    savingsFromAdapting: Math.round(D * 2.1),
    narrative:
      'The MSR removes 20% of auction supply. The auction-heavy baseline can no longer fill — the agent re-routes the deficit onto spot + RFQ and pulls the held reserve forward before the market reprices.',
  }
}
