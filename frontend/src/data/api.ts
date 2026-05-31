import * as mock from './mock'
import type {
  AuctionDay, ChannelOption, Driver, EmissionsOutlook, ExecutionPlan, Firm, ForecastPoint,
  HistoryPoint, LadderStep, Match, Position, Recommendation, Scenario, ScenarioDiff,
} from './types'

/**
 * BACKEND INTEGRATION
 * ───────────────────
 * Talks to the CarbonEdge FastAPI backend. A single POST to
 * `/decisions/scenario` returns baseline + shocked + diff (computed by the
 * src/engine execution optimizer on the live Sybilion forecast). If the
 * backend is unreachable or the engine is not connected, every call falls
 * back to the local mock (identical shape), so the UI never breaks on stage.
 *
 * Override the base URL with VITE_API_BASE.
 */
const API = (import.meta.env.VITE_API_BASE as string | undefined) ?? 'http://localhost:8000'
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** Where the rendered data came from, surfaced in the footer for honesty. */
export type DataSource = 'live' | 'mock'
export interface SourceState {
  source: DataSource
  forecastMode?: string // 'sybilion' | 'cache' | 'fallback' | 'mock'
  reason?: string // why we fell back, if we did
}
let _state: SourceState = { source: 'mock', reason: 'backend not yet reached' }
const _listeners = new Set<(s: SourceState) => void>()
export function getSourceState(): SourceState {
  return _state
}
export function onSourceChange(fn: (s: SourceState) => void): () => void {
  _listeners.add(fn)
  return () => _listeners.delete(fn)
}
function setSource(s: SourceState) {
  _state = s
  _listeners.forEach((fn) => fn(s))
}

/** A network failure (backend down) vs a valid HTTP error response. */
class HttpError extends Error {
  constructor(public status: number, path: string) {
    super(`${path} → ${status}`)
  }
}
function isNetworkError(e: unknown): boolean {
  return e instanceof TypeError || (e instanceof Error && e.name === 'AbortError')
}

interface ViewShape {
  firm: Firm
  position: Position
  plan: ExecutionPlan
  channels: ChannelOption[]
  auctions: AuctionDay[]
  diff: ScenarioDiff
  forecast: ForecastPoint[]
  drivers: Driver[]
  matches: Match[]
  currentPrice: number
  recommendation: Recommendation
  ladder: LadderStep[]
  orders: import('./types').Order[]
}

/** Derive the headline recommendation from the engine's execution plan. */
function deriveRecommendation(plan: ExecutionPlan, firmId: string): Recommendation {
  const D = Math.abs(plan.deficitVolume) || 1
  const executed = plan.tranches.filter((t) => t.status === 'EXECUTE').reduce((s, t) => s + t.volume, 0)
  const lockNowPct = Math.max(0, Math.min(100, Math.round((executed / D) * 100)))
  const rationale = (plan.triggers ?? []).slice(0, 3)
  if (!rationale.length) rationale.push(plan.headline)
  return {
    action: plan.action,
    headline: plan.headline,
    lockNowPct: plan.side === 'LONG' ? 0 : lockNowPct,
    confidence: plan.confidence,
    rationale,
    costAtRisk: plan.expectedTotal,
    savingsVsNaive: plan.savingsVsBuyAllNow,
  }
}

/** Derive a Now/Scheduled/Reserve timing ladder from the engine tranches. */
function deriveLadder(plan: ExecutionPlan): LadderStep[] {
  const D = Math.abs(plan.deficitVolume) || 1
  const sum = (st: string) => plan.tranches.filter((t) => t.status === st).reduce((s, t) => s + t.volume, 0)
  const reserve = plan.channelMix.find((m) => m.key === 'WAIT')?.volume ?? 0
  const whenOf = (st: string, fb: string) => plan.tranches.find((t) => t.status === st)?.when ?? fb
  const steps: LadderStep[] = []
  const now = sum('EXECUTE')
  const sched = sum('SCHEDULED')
  if (now > 0) steps.push({ label: 'Secure now', pct: Math.round((now / D) * 100), when: whenOf('EXECUTE', 'This week'), note: 'Execute immediately across the cheapest routed channels' })
  if (sched > 0) steps.push({ label: 'Scheduled', pct: Math.round((sched / D) * 100), when: whenOf('SCHEDULED', 'Next auction'), note: 'Place at the scheduled auction / broker window' })
  if (reserve > 0) steps.push({ label: 'Reserve', pct: Math.round((reserve / D) * 100), when: 'On trigger', note: 'Held — release if the price trigger fires' })
  return steps
}

function mapOutlook(d: any): EmissionsOutlook {
  return {
    companyId: d.company_id, company: d.company, unit: d.unit, year: d.year,
    source: d.source, freeAllocation: d.free_allocation,
    annualEmissionsP50: d.annual_emissions_p50, annualDeficitP50: d.annual_deficit_p50,
    months: d.months, overshoot: d.overshoot ?? null,
  }
}

async function jget(path: string): Promise<any> {
  const r = await fetch(`${API}${path}`)
  if (!r.ok) throw new HttpError(r.status, `GET ${path}`)
  return r.json()
}
async function jpost(path: string, body: unknown): Promise<any> {
  const r = await fetch(`${API}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!r.ok) throw new HttpError(r.status, `POST ${path}`)
  return r.json()
}

function mapFirm(c: any): Firm {
  return {
    id: c.id, name: c.name, sector: c.sector,
    baselineEmissions: c.forecast_emissions, freeAllocation: c.free_allocation, holdings: c.current_allowances,
  }
}
function mapHistory(rows: any[]): HistoryPoint[] {
  return rows.map((r) => {
    const [y, m] = String(r.date).split('-')
    return { month: `${y}-${m}`, label: `${MONTHS[+m - 1]} '${y.slice(2)}`, price: r.price }
  })
}
function mapPosition(decision: any, firmId: string): Position {
  const p = decision.position ?? {}
  const side = (p.side ?? p.status) as 'SHORT' | 'LONG'
  const mag = Math.abs(p.deficit ?? p.net_position ?? 0)
  return {
    firmId,
    forecastEmissions: p.required_allowances ?? 0,
    deficit: side === 'SHORT' ? mag : -mag,
    side,
    confidence: decision.plan?.confidence ?? 'medium',
  }
}

function mockView(firmId: string, scenario: Scenario): ViewShape {
  const firm = mock.FIRMS.find((f) => f.id === firmId) ?? mock.FIRMS[0]
  return {
    firm,
    position: mock.positionOf(firm),
    plan: mock.executionPlan(firm, scenario),
    channels: mock.channels(firm, scenario),
    auctions: mock.auctions(firm, scenario),
    diff: mock.scenarioDiff(firm),
    forecast: mock.forecast(scenario),
    drivers: mock.drivers(scenario),
    matches: mock.matches(firm, scenario),
    currentPrice: mock.CURRENT_PRICE,
    recommendation: mock.recommendation(firm, scenario),
    ladder: mock.ladder(firm, scenario),
    orders: mock.orders(),
  }
}

export const api = {
  async getFirms(): Promise<Firm[]> {
    try {
      return (await jget('/companies')).map(mapFirm)
    } catch {
      return mock.FIRMS
    }
  },

  async getHistory(): Promise<HistoryPoint[]> {
    try {
      return mapHistory((await jget('/market/eua-prices')).data)
    } catch {
      return mock.history()
    }
  },

  async getEmissionsOutlook(firmId: string): Promise<EmissionsOutlook> {
    try {
      return mapOutlook(await jget(`/companies/${firmId}/emissions-outlook`))
    } catch {
      const firm = mock.FIRMS.find((f) => f.id === firmId) ?? mock.FIRMS[0]
      return mock.emissionsOutlook(firm)
    }
  },

  async getView(firmId: string, scenario: Scenario): Promise<ViewShape> {
    try {
      const [company, scen] = await Promise.all([
        jget(`/companies/${firmId}`),
        jpost('/decisions/scenario', { company_id: firmId, event: 'msr_auction_cut', forecast_source: 'cache' }),
      ])
      const sc = scen.scenario
      if (!sc || !sc.baseline) throw new Error('engine not connected: no scenario payload')
      const decision = scenario === 'shock' ? sc.shocked : sc.baseline
      setSource({ source: 'live', forecastMode: decision.forecastMode })
      const plan = decision.plan as ExecutionPlan
      return {
        firm: mapFirm(company),
        position: mapPosition(decision, firmId),
        plan,
        channels: decision.channels as ChannelOption[],
        auctions: decision.auctions as AuctionDay[],
        diff: sc.diff as ScenarioDiff,
        forecast: decision.forecast as ForecastPoint[],
        drivers: decision.drivers as Driver[],
        matches: decision.matches as Match[],
        currentPrice: decision.currentPrice as number,
        recommendation: deriveRecommendation(plan, firmId),
        ladder: deriveLadder(plan),
        orders: mock.orders(), // no public live order book exists — illustrative
      }
    } catch (e) {
      // Network failure → backend is simply down. HTTP error / bad payload →
      // surface a clearer reason. Either way we fall back to the mock so the
      // stage demo never breaks, but the footer makes the source explicit.
      const reason = isNetworkError(e)
        ? 'backend unreachable'
        : e instanceof HttpError
          ? `backend error (${e.status})`
          : e instanceof Error
            ? e.message
            : 'unknown error'
      console.warn(`[CarbonEdge] falling back to mock data: ${reason}`)
      setSource({ source: 'mock', reason })
      return mockView(firmId, scenario)
    }
  },
}

export type View = ViewShape
