import * as mock from './mock'
import type {
  AuctionDay, ChannelOption, Driver, ExecutionPlan, Firm, ForecastPoint,
  HistoryPoint, Match, Position, Scenario, ScenarioDiff,
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
}

async function jget(path: string): Promise<any> {
  const r = await fetch(`${API}${path}`)
  if (!r.ok) throw new Error(`GET ${path} → ${r.status}`)
  return r.json()
}
async function jpost(path: string, body: unknown): Promise<any> {
  const r = await fetch(`${API}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!r.ok) throw new Error(`POST ${path} → ${r.status}`)
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

  async getView(firmId: string, scenario: Scenario): Promise<ViewShape> {
    try {
      const [company, scen] = await Promise.all([
        jget(`/companies/${firmId}`),
        jpost('/decisions/scenario', { company_id: firmId, event: 'msr_auction_cut', forecast_source: 'cache' }),
      ])
      const sc = scen.scenario
      if (!sc || !sc.baseline) throw new Error('engine not connected')
      const decision = scenario === 'shock' ? sc.shocked : sc.baseline
      return {
        firm: mapFirm(company),
        position: mapPosition(decision, firmId),
        plan: decision.plan as ExecutionPlan,
        channels: decision.channels as ChannelOption[],
        auctions: decision.auctions as AuctionDay[],
        diff: sc.diff as ScenarioDiff,
        forecast: decision.forecast as ForecastPoint[],
        drivers: decision.drivers as Driver[],
        matches: decision.matches as Match[],
        currentPrice: decision.currentPrice as number,
      }
    } catch {
      return mockView(firmId, scenario)
    }
  },
}

export type View = ViewShape
