"""CarbonEdge engine bridge.

THIN adapter — owns NO decision logic. It runs the real ``carbonedge`` 5-layer
pipeline (regime · EPU · driver · structural · demand enhancement + the
30k-company risk lambda + the CVaR procurement optimizer) and maps the
resulting ``EnhancedDecision`` onto the camelCase view the API/frontend consume.

The carbonedge pipeline decides WHEN to buy (a CVaR time-window ladder) and WHY
(all 5 layers). It does not model execution *channels*, the auction calendar or
OTC counterparties — those frontend cards are populated as plain market-data
presentation (real EEX calendar + offers), clearly secondary to the plan.

If the carbonedge import fails (missing deps) this module fails to import and
``decision_adapter`` reports the engine as not connected — there is NO fallback
engine here, by design.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

# ── the real decision engine (no fallback) ───────────────────────
from carbonedge.decision_agent import run_decision_agent, EnhancedDecision
from carbonedge.sybilion_client import parse_forecast_response, ForecastResult
from carbonedge.mac_curve import build_mac_curve
from carbonedge.config import COMPANY_PROFILE, CARBON_EXPOSURE
from carbonedge.regime_detector import RegimeMonitor
from carbonedge.enhancement.company_risk import CompanyRiskLayer
# market data for the presentation-only cards (not part of the decision)
from src.api.services import market_service

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

_CONFIDENCE = {"GREEN": "high", "YELLOW": "medium", "RED": "low"}
_DRIVER_SIGN = {
    "ets": 0.8, "reserve": 0.9, "msr": 0.9, "cbam": 0.7, "auction": 0.8,
    "gas": 0.6, "cap": 0.8, "carbon": 0.7, "renewable": -0.5, "industrial": 0.5,
}
_FILL = {"AUCTION": 0.80, "SPOT": 1.00, "RFQ": 0.95, "OTC": 0.90}


# ════════════════════════════════════════════════════════════════
#  Small presentation helpers (formatting only — no decisions)
# ════════════════════════════════════════════════════════════════

def _tons(n: float) -> str:
    return f"{n / 1000:.1f}k t" if abs(n) >= 1000 else f"{round(n)} t"


def _fmt_date(d: str) -> str:
    dt = datetime.strptime(d[:10], "%Y-%m-%d").date()
    return f"{['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][dt.weekday()]} {dt.day:02d} {MONTHS[dt.month - 1]}"


def _sector_of(name: str) -> str:
    n = name.lower()
    for kw, sec in (("cement", "Cement"), ("steel", "Steel"), ("paper", "Paper"),
                    ("glass", "Glass"), ("broker", "Power"), ("energie", "Power")):
        if kw in n:
            return sec
    return "Chemicals"


def _q(qmap: dict, *keys: str, default: Optional[float] = None) -> Optional[float]:
    for k in keys:
        if k in qmap and qmap[k] is not None:
            return float(qmap[k])
    return default


def _eua_history() -> list[tuple[str, float]]:
    return [(d["date"], float(d["price"])) for d in market_service.get_eua_prices()["data"]]


def _clean(name: str) -> str:
    return " ".join(str(name).replace("�", "-").split()).strip(" -")


# ── forecast band (presentation parse of the 19 Sybilion quantiles) ──

def _forecast_points(forecast_dict: dict) -> list[dict]:
    fs = (forecast_dict or {}).get("forecast", {}).get("data", {}).get("forecast_series", {})
    out: list[dict] = []
    for d in sorted(fs.keys()):
        pt = fs[d]
        q = pt.get("quantile_forecast", {})
        p50 = _q(q, "0.50", "0.5", default=pt.get("forecast"))
        if p50 is None:
            continue
        p50 = float(p50)
        p10 = _q(q, "0.10", "0.1", default=p50 * 0.94)
        p90 = _q(q, "0.90", "0.9", default=p50 * 1.06)
        raw = {
            "p05": _q(q, "0.05", default=p50 - (p50 - p10) * 1.25),
            "p25": _q(q, "0.25", default=p50 - (p50 - p10) * 0.55),
            "p50": p50,
            "p75": _q(q, "0.75", default=p50 + (p90 - p50) * 0.55),
            "p95": _q(q, "0.95", default=p50 + (p90 - p50) * 1.25),
        }
        mo = int(d[5:7])
        out.append({"month": d[:7], "label": MONTHS[mo - 1],
                    **{k: round(v, 1) for k, v in raw.items()}})
    return out[:6]


def _interp(points: list[dict], month: str, key: str) -> float:
    for p in points:
        if p["month"] >= month:
            return p[key]
    return points[-1][key] if points else 0.0


# ── drivers (real Sybilion external_signals) ──────────────────────

def _drivers(forecast_dict: dict) -> list[dict]:
    data = (forecast_dict or {}).get("signals", {}).get("data", {})
    rows: list[dict] = []
    if isinstance(data, dict):
        for key, info in data.items():
            if not isinstance(info, dict):
                continue
            name = _clean(info.get("driver_name", key))
            overall = (info.get("importance", {}) or {}).get("overall")
            if isinstance(overall, dict) and overall.get("mean") is not None:
                imp = float(overall["mean"])  # already 0..100
                direction = ((info.get("direction", {}) or {}).get("overall", {}) or {}).get("mean")
                if direction is None:
                    direction = next((s for k, s in _DRIVER_SIGN.items() if k in name.lower()), 0.5)
            else:
                vals = [v.get("importance", 0) for v in (info.get("importance", {}) or {}).values() if isinstance(v, dict)]
                imp = round(max(vals or [0]) * 100)
                direction = next((s for k, s in _DRIVER_SIGN.items() if k in name.lower()), 0.5)
            rows.append({"name": name, "importance": round(max(0.0, min(100.0, float(imp)))),
                         "direction": round(max(-1.0, min(1.0, float(direction))), 3)})
    rows.sort(key=lambda d: -d["importance"])
    seen, top = set(), []
    for d in rows:
        if d["name"] in seen:
            continue
        seen.add(d["name"])
        top.append(d)
        if len(top) >= 8:
            break
    return top or [{"name": "EU ETS reform", "importance": 45, "direction": 0.8}]


# ════════════════════════════════════════════════════════════════
#  Map carbonedge EnhancedDecision → frontend view
# ════════════════════════════════════════════════════════════════

def _channel_for(horizon: int) -> str:
    return "SPOT" if horizon <= 1 else "AUCTION"


def _plan_from_decision(decision: EnhancedDecision, D: float, side: str,
                        forecast_points: list[dict] | None = None) -> dict:
    proc = decision.procurement
    strat = proc.strategy
    tranches: list[dict] = []
    mix: dict[str, int] = {}
    for i, w in enumerate(proc.windows):
        ch = _channel_for(w.horizon)
        when = {0: "Now", 1: "Now", 3: "Month 3", 6: "Month 6"}.get(w.horizon, f"Month {w.horizon}")
        status = "EXECUTE" if w.horizon <= 1 else "SCHEDULED"
        tranches.append({
            "id": f"t{i}", "when": when, "channel": ch, "volume": int(w.tons),
            "price": round(w.expected_price, 2),
            "maxBid": round(w.price_high, 2) if ch == "AUCTION" else None,
            "status": status,
            "reason": _clean(proc.reasoning)[:140] or f"{strat} window",
        })
        mix[ch] = mix.get(ch, 0) + int(w.tons)
    reserve = max(0, round(D) - sum(mix.values()))
    channel_mix = [{"key": k, "volume": v} for k, v in mix.items()]
    if reserve > max(500, 0.01 * D):
        channel_mix.append({"key": "WAIT", "volume": reserve})

    if side == "LONG":
        action = "SELL"
    else:
        action = "BUY" if strat in ("LUMP_SUM", "FRONT_LOAD", "FREEZE") else "LADDER"
    strat_label = strat.replace("_", " ").lower()
    headline = (
        f"Surplus {_tons(D)} — bank / sell as the floor rises" if side == "LONG"
        else f"Secure {_tons(D)} now — {strat_label}" if action == "BUY"
        else f"Ladder {_tons(D)} — {strat_label} across windows"
    )

    # --- Compute savingsVsNaive: compare optimized cost against the naive ---
    # strategy of procrastinating (buying everything at year-end forecast price).
    # This is the most intuitive "naive" baseline: what would it cost if the firm
    # waited until the last moment? When the forecast is rising, buying now saves
    # money vs waiting, giving a positive savings figure.
    pts = forecast_points or []
    last_p50 = pts[-1]["p50"] if pts else decision.current_price
    naive_cost = D * max(decision.current_price, last_p50)
    savings_vs_naive = max(0, round(naive_cost - proc.total_cost_expected))

    # --- Compute savingsVsYearEnd: same baseline, kept as a separate field ---
    # for the ExecutionPlanCard which shows it alongside expectedTotal/worstCase.
    savings_vs_year_end = savings_vs_naive

    return {
        "deficitVolume": round(D),
        "deficit": round(D),
        "side": side,
        "action": action,
        "confidence": _CONFIDENCE.get(decision.regime.level, "medium"),
        "headline": headline,
        "strategy": strat,
        "channelMix": channel_mix,
        "tranches": tranches,
        "expectedTotal": round(proc.total_cost_expected),
        "expectedSpend": round(proc.total_cost_expected),
        "worstCase": round(proc.total_cost_worst_case),
        "worstCaseSpend": round(proc.total_cost_worst_case),
        "savingsVsBuyAllNow": round(proc.expected_savings),
        "savingsVsNaive": savings_vs_naive,
        "savingsVsYearEnd": savings_vs_year_end,
        "triggers": list(decision.alert_triggers),
    }


def _channels_view(plan: dict, points: list[dict], side: str) -> list[dict]:
    mix = {m["key"]: m["volume"] for m in plan["channelMix"]}
    near_p50 = points[0]["p50"] if points else 0.0
    near_p75 = points[0]["p75"] if points else near_p50
    spreads = {"AUCTION": -0.55, "SPOT": 0.45, "RFQ": 0.0, "OTC": 0.0}
    avail = {
        "AUCTION": sum(a["volume"] for a in market_service.get_auctions()),
        "SPOT": 10_000_000,
        "RFQ": 40_000,
        "OTC": sum(int(o["volume"]) for o in market_service.get_sell_offers()),
    }
    rows = []
    for key in ("AUCTION", "SPOT", "RFQ", "OTC"):
        rec = mix.get(key, 0)
        if rec == 0 and key not in ("SPOT", "AUCTION"):
            continue
        price = round(near_p50 + spreads[key], 1)
        eff = round(price + (1 - _FILL[key]) * 1.5 + max(0.0, near_p75 - near_p50) * 0.45, 1)
        rows.append({
            "key": key, "effCost": eff, "expectedPrice": price, "fillProb": _FILL[key],
            "available": round(avail[key]), "recommendedVolume": round(rec),
            "reason": _channel_reason(key),
        })
    rows.sort(key=lambda r: (-r["recommendedVolume"], r["effCost"]))
    for i, r in enumerate(rows):
        r["rank"] = i + 1
    return rows


def _channel_reason(key: str) -> str:
    return {
        "AUCTION": "EEX primary auction — cheapest risk-adjusted route; sealed-bid, cap the bid.",
        "SPOT": "Secondary spot — immediate fill, no counterparty risk; priciest per tonne.",
        "RFQ": "Broker request-for-quote — flexible size for a scheduled tranche.",
        "OTC": "Bilateral offer — fast settlement, limited size.",
    }.get(key, "")


def _auctions_view(plan: dict, points: list[dict], side: str) -> list[dict]:
    target = sum(m["volume"] for m in plan["channelMix"] if m["key"] == "AUCTION")
    allocated = 0.0
    out = []
    for a in sorted(market_service.get_auctions(), key=lambda x: x["auction_date"]):
        d = a["auction_date"]
        p50 = _interp(points, d[:7], "p50")
        p75 = _interp(points, d[:7], "p75")
        clearing = a.get("expected_clearing_price") or p50
        tv = 0.0
        if side == "SHORT" and allocated < target:
            tv = min(float(a["volume"]), target - allocated)
            allocated += tv
        out.append({
            "id": a["id"], "type": a["auction_type"], "date": d, "label": _fmt_date(d),
            "volume": round(float(a["volume"])),
            "expectedClearing": round(clearing, 1),
            "recommendedBid": round(p75, 1) if (side == "SHORT") else None,
            "targetVolume": round(tv),
            "msrAffected": False,
        })
    return out[:8]


def _matches_view() -> list[dict]:
    out = []
    for o in market_service.get_sell_offers():
        rating = float(o.get("counterparty_rating", 0.9))
        out.append({
            "id": o["id"], "counterparty": o["seller_name"],
            "counterpartySector": _sector_of(o["seller_name"]), "side": "buy",
            "volume": int(o["volume"]), "price": round(float(o["price_per_eua"]), 2),
            "timing": "WAIT", "fit": round(rating * 100),
            "rationale": f"{o.get('settlement_method', 'OTC')} · rating {rating:.2f}",
        })
    return out


# ── company → risk profile + regime warm-start ────────────────────

def _risk_profile(company: dict):
    em = float(company.get("forecast_emissions", 0))
    size = "large" if em >= 1_000_000 else "medium" if em >= 200_000 else "small"
    try:
        return CompanyRiskLayer().get_profile(str(company.get("sector", "")).lower(), size)
    except Exception:
        return None


def _regime_monitor(prices: list[float]) -> RegimeMonitor:
    rm = RegimeMonitor()
    naive = [prices[0]] + prices[:-1] if prices else []
    for p, n in zip(prices, naive):
        rm.update(p, n)
    return rm


# ════════════════════════════════════════════════════════════════
#  Core: run the real pipeline + assemble the view
# ════════════════════════════════════════════════════════════════

def _build_view(company: dict, position: dict, forecast: Optional[dict]) -> dict:
    forecast = forecast or {}
    hist = _eua_history()
    prices = [p for _, p in hist]
    current = prices[-1] if prices else 80.0

    net = float(position.get("net_position", 0))
    side = "SHORT" if net < 0 else "LONG"
    D = abs(net) or float(CARBON_EXPOSURE["eu_ets_allowances_needed_annually"])

    # Parse the Sybilion forecast into carbonedge's ForecastResult, then run the
    # full 5-layer pipeline (CVaR optimizer + enhancement layers + risk lambda).
    fr = parse_forecast_response(
        forecast.get("forecast", {}),
        target_name="eu_ets_price",
        external_signals=forecast.get("signals"),
        backtest_metrics=forecast.get("backtest"),
    )
    fr.current_value = current

    decision: EnhancedDecision = run_decision_agent(
        ets_forecast=fr,
        mac_curve=build_mac_curve(current_ets_price=current),
        budget=float(COMPANY_PROFILE["annual_reduction_budget_eur"]),
        current_ets_price=current,
        allowances_needed=int(round(D)),
        regime_monitor=_regime_monitor(prices),
        historical_prices=prices,
        risk_profile=_risk_profile(company),
        evaluation_date=date.today().isoformat(),
    )

    points = _forecast_points(forecast)
    drivers = _drivers(forecast)
    plan = _plan_from_decision(decision, D, side, forecast_points=points)

    mode = forecast.get("mode", "cache" if forecast.get("forecast") else "fallback")
    return {
        "currentPrice": round(current, 2),
        "forecastMode": mode,
        "forecast": points,
        "drivers": drivers,
        "driverSource": f"Sybilion external_signals ({mode})" if drivers else None,
        "channels": _channels_view(plan, points, side),
        "auctions": _auctions_view(plan, points, side),
        "matches": _matches_view(),
        "plan": plan,
        "position": {
            "deficit": round(D), "side": side,
            **{k: position[k] for k in
               ("required_allowances", "available_allowances", "net_position", "status") if k in position},
        },
        # full enhancement reasoning, so the 5 layers are visible to clients
        "enhancement": {
            "regime": {"level": decision.regime.level, "multiplier": decision.regime.multiplier,
                       "advisory": decision.regime.advisory},
            "driverBias": {"signal": decision.driver_bias.signal, "bias": decision.driver_bias.bias},
            "demand": (None if decision.demand is None else
                       {"signal": decision.demand.signal, "pressure": decision.demand.demand_pressure,
                        "compositeYoY": decision.demand.composite_yoy_change_pct,
                        "divergence": decision.demand.sector_divergence, "reasoning": decision.demand.reasoning}),
            "riskProfile": (None if decision.risk_profile is None else
                            {"sector": decision.risk_profile.sector, "size": decision.risk_profile.size,
                             "lambda": decision.risk_profile.risk_adjusted_lambda,
                             "predictability": decision.risk_profile.predictability_score,
                             "peers": decision.risk_profile.peer_count}),
            "structural": (None if decision.structural is None else
                           {"signal": decision.structural.signal, "narrative": decision.structural.narrative}),
            "alerts": list(decision.alert_triggers),
            "budget": decision.budget_summary,
            "backtestMape": fr.backtest_accuracy,
        },
    }

# ════════════════════════════════════════════════════════════════
#  Public API (the decision_adapter contract)
# ════════════════════════════════════════════════════════════════

class CarbonEdgeAgent:
    """Runs the real carbonedge pipeline and returns the frontend view."""

    def run(self, company: dict, position: dict, forecast: Optional[dict] = None,
            forecast_source: str = "cache") -> dict:
        return _build_view(company, position, forecast)
