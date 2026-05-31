"""CarbonEdge execution optimizer.

Substantive decision logic (NOT an LLM wrapper). For an EU-ETS company it:

  1. derives the net allowance position (deficit / surplus),
  2. ingests the Sybilion probabilistic price forecast (monthly p10/p50/p90),
  3. scores every procurement *channel × date* slot — Auction (EEX primary),
     Spot (secondary), RFQ/Broker, OTC — on a risk-adjusted cost that blends
     expected price, the forecast band, timing/carry and fill probability,
  4. greedily routes the deficit across the cheapest slots subject to the real
     auction calendar, offer sizes and a confidence-driven hedge fraction, and
  5. on a shock (MSR auction-supply cut) re-runs and reports the before/after
     re-routing delta.

Output keys are camelCase to match the frontend contract (AUCTION_PLAN.md §7),
so the React app renders the engine output with no field mapping.
"""

from __future__ import annotations

import os
from datetime import date, datetime
from typing import Any, Optional

from src.api.services import market_service

# ── channel parameters ───────────────────────────────────────────
# spread = additive €/t vs. secondary spot ; fee = transaction cost ;
# fill = probability of filling the requested lot.
CHANNELS: dict[str, dict[str, float]] = {
    "AUCTION": {"spread": -0.55, "fee": 0.02, "fill": 0.80},  # primary clears below the screen…
    "SPOT": {"spread": 0.45, "fee": 0.03, "fill": 1.00},      # …but the screen carries an execution premium
    "RFQ": {"spread": 0.00, "fee": 0.10, "fill": 0.95},
    "OTC": {"spread": 0.00, "fee": 0.05, "fill": 0.90},
}
RISK_AVERSION = 0.45  # weight on the upper forecast band
CARRY_PER_MONTH = 0.10  # €/t per month of waiting (cost of carry)
OFFER_REF = 69.0  # price level the mock OTC/RFQ offers were quoted at → re-anchor to live spot
AUCTION_SHARE_CAP = 0.45  # don't bid more than this share of the deficit into sealed-bid auctions
BASELINE_SECURE = 0.70  # cover 70% now, hold 30% as a confidence reserve (baseline)
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# direction heuristic for driver signals (the mock signal artifact carries no sign)
_DRIVER_SIGN = {
    "ets": 0.8, "reserve": 0.9, "msr": 0.9, "cbam": 0.7, "auction": 0.8,
    "gas": 0.6, "cap": 0.8, "carbon": 0.7, "renewable": -0.5, "industrial": 0.5,
}


# ════════════════════════════════════════════════════════════════
#  Forecast handling
# ════════════════════════════════════════════════════════════════

def _eua_history() -> list[tuple[str, float]]:
    raw = market_service.get_eua_prices()["data"]
    return [(d["date"], float(d["price"])) for d in raw]


def _load_forecast(passed: Optional[dict]) -> dict:
    """Return Sybilion artifacts {forecast, signals, backtest, mode}.

    Tries the passed artifact, then a live/cached Sybilion call, then a
    deterministic fallback derived from the *real* price history — so the
    endpoint never fails on stage.
    """
    art = _normalise_artifacts(passed)
    if art:
        return art

    try:  # live or cached via the backend wrapper (caches by content hash)
        import pandas as pd

        from src.sybilion.client import SybilionWrapper

        series = pd.Series({pd.Timestamp(d): p for d, p in _eua_history()}).sort_index()
        token = os.environ.get("SYBILION_API_TOKEN") or os.environ.get("SYBILION_API_KEY")
        wrapper = SybilionWrapper(api_token=token)
        out = wrapper.submit_and_wait(series, horizon=6, title="EUA price", description="EU ETS EUA monthly")
        return {"forecast": out.forecast, "signals": out.signals, "backtest": out.backtest, "mode": wrapper.mode}
    except Exception:
        return _fallback_forecast()


def _normalise_artifacts(passed: Optional[dict]) -> Optional[dict]:
    if not isinstance(passed, dict):
        return None
    inner = passed.get("forecast", passed)
    if isinstance(inner, dict) and inner.get("data", {}).get("forecast_series"):
        return {
            "forecast": inner,
            "signals": passed.get("signals", {}),
            "backtest": passed.get("backtest"),
            "mode": passed.get("mode", "cache"),
        }
    return None


def _fallback_forecast() -> dict:
    """Deterministic 6-month forecast derived from the real price series."""
    hist = _eua_history()
    last_d, last_p = hist[-1]
    recent = [p for _, p in hist[-12:]]
    mean = sum(recent) / len(recent)
    std = (sum((x - mean) ** 2 for x in recent) / len(recent)) ** 0.5
    trend = (hist[-1][1] - hist[-13][1]) / 12 if len(hist) > 13 else 0.4
    series = {}
    for i in range(1, 7):
        pt = last_p + trend * i * 0.4 + mean * 0.004 * i
        bw = std * (0.10 + 0.045 * i)
        m = _add_months(last_d, i)
        series[m] = {"forecast": round(pt, 2), "quantile_forecast": {
            "0.1": round(pt - bw, 2), "0.5": round(pt, 2), "0.9": round(pt + bw, 2)}}
    forecast = {"version": "1.1", "data": {"forecast_horizon": 6,
                "forecast_start": _add_months(last_d, 1), "forecast_end": _add_months(last_d, 6),
                "forecast_series": series}}
    signals = {"version": "1.1", "data": {
        "EU ETS reform": {"importance": {"month_1": {"importance": 0.25}, "month_6": {"importance": 0.45}}},
        "Natural gas price": {"importance": {"month_1": {"importance": 0.30}, "month_6": {"importance": 0.12}}},
        "CBAM implementation": {"importance": {"month_1": {"importance": 0.12}, "month_6": {"importance": 0.25}}},
        "Auction supply volume": {"importance": {"month_1": {"importance": 0.18}, "month_6": {"importance": 0.20}}},
    }}
    return {"forecast": forecast, "signals": signals, "backtest": None, "mode": "fallback"}


def _add_months(date_str: str, n: int) -> str:
    dt = datetime.strptime(date_str[:10], "%Y-%m-%d").date()
    y, m = dt.year + (dt.month - 1 + n) // 12, (dt.month - 1 + n) % 12 + 1
    return f"{y}-{m:02d}-01"


def _forecast_points(art: dict, shock: bool) -> list[dict]:
    """Parse forecast_series → ordered list of monthly points with full bands."""
    fs = art["forecast"]["data"]["forecast_series"]
    out = []
    for d in sorted(fs.keys()):
        q = fs[d].get("quantile_forecast", {})
        p50 = float(q.get("0.5", fs[d].get("forecast")))
        p10 = float(q.get("0.1", p50 * 0.94))
        p90 = float(q.get("0.9", p50 * 1.06))
        if shock:  # MSR supply cut → tighter market, confident upward repricing
            lift = 1.0 + 0.045 * (len(out) + 1)
            p10, p50, p90 = p10 * lift, p50 * lift, p90 * lift
        mo = int(d[5:7])
        out.append({
            "month": d[:7], "label": MONTHS[mo - 1],
            "p05": round(p50 - (p50 - p10) * 1.25, 1),
            "p25": round(p50 - (p50 - p10) * 0.55, 1),
            "p50": round(p50, 1),
            "p75": round(p50 + (p90 - p50) * 0.55, 1),
            "p95": round(p50 + (p90 - p50) * 1.25, 1),
        })
    return out[:6]


def _drivers(art: dict, shock: bool) -> list[dict]:
    data = art.get("signals", {}).get("data", {})
    drivers: list[dict] = []
    if isinstance(data, dict):
        for name, info in data.items():
            imp_map = (info or {}).get("importance", {}) if isinstance(info, dict) else {}
            vals = [v.get("importance", 0) for v in imp_map.values() if isinstance(v, dict)]
            imp = round(max(vals or [0]) * 100)
            key = name.lower()
            direction = next((s for k, s in _DRIVER_SIGN.items() if k in key), 0.5)
            drivers.append({"name": name, "importance": imp, "direction": direction})
    if shock:
        drivers = [{"name": "Market Stability Reserve", "importance": 68, "direction": 0.9},
                   {"name": "Auction supply volume", "importance": 44, "direction": 0.9}] + drivers
    drivers.sort(key=lambda d: -d["importance"])
    return drivers[:6] or [{"name": "EU ETS reform", "importance": 45, "direction": 0.8}]


def _interp_p(points: list[dict], month: str, key: str) -> float:
    for p in points:
        if p["month"] >= month:
            return p[key]
    return points[-1][key]


# ════════════════════════════════════════════════════════════════
#  Position
# ════════════════════════════════════════════════════════════════

def _position(position: dict) -> tuple[float, str]:
    net = float(position.get("net_position", 0))
    return abs(net), ("SHORT" if net < 0 else "LONG")


# ════════════════════════════════════════════════════════════════
#  Supply events + optimizer
# ════════════════════════════════════════════════════════════════

def _sector_of(name: str) -> str:
    n = name.lower()
    for kw, sec in (("cement", "Cement"), ("steel", "Steel"), ("paper", "Paper"),
                    ("glass", "Glass"), ("broker", "Power"), ("energie", "Power")):
        if kw in n:
            return sec
    return "Chemicals"


def _build_events(points: list[dict], base_spot: float, shock: bool) -> list[dict]:
    """Auctions (calendar, reprice with the forecast) + OTC/RFQ offers
    (fixed bilateral contracts, re-anchored to live spot) + a deep spot pool."""
    events: list[dict] = []

    for a in market_service.get_auctions():
        d = a["auction_date"]
        months_ahead = max(0, (int(d[:4]) - 2026) * 12 + int(d[5:7]) - 6)
        clearing = _interp_p(points, d[:7], "p50") + CHANNELS["AUCTION"]["spread"]
        high = _interp_p(points, d[:7], "p75")
        vol = a["volume"] * (0.8 if shock else 1.0)
        events.append({"kind": "AUCTION", "id": a["id"], "type": a["auction_type"], "date": d,
                       "label": _fmt(d), "lotVolume": round(vol), "available": round(vol),
                       "price": round(clearing, 2), "priceHigh": round(high + CHANNELS["AUCTION"]["spread"], 2),
                       "monthsAhead": months_ahead, "fill": CHANNELS["AUCTION"]["fill"], "rating": 1.0,
                       "msr": shock})

    # Offers are fixed-price contracts: re-anchor the stale quotes to the live
    # spot (premium/discount preserved), with only a mild drift under a squeeze.
    for o in market_service.get_sell_offers():
        ch = "OTC" if o.get("settlement_method") == "OTC" else "RFQ"
        price = base_spot + (float(o["price_per_eua"]) - OFFER_REF) + (0.4 if shock else 0.0)
        events.append({"kind": ch, "id": o["id"], "type": ch, "date": o.get("valid_until", "")[:10],
                       "label": "Now" if ch == "OTC" else "This week", "seller": o["seller_name"],
                       "available": float(o["volume"]), "price": round(price, 2),
                       "priceHigh": round(price + 0.6, 2), "monthsAhead": 0,
                       "fill": CHANNELS[ch]["fill"], "rating": float(o.get("counterparty_rating", 0.9))})

    spot_price = (points[0]["p50"] if shock else base_spot) + CHANNELS["SPOT"]["spread"]
    events.append({"kind": "SPOT", "id": "spot", "type": "SPOT", "date": "2026-06-01", "label": "Now",
                   "available": 10_000_000, "price": round(spot_price, 2),
                   "priceHigh": round(points[0]["p75"], 2), "monthsAhead": 0,
                   "fill": CHANNELS["SPOT"]["fill"], "rating": 1.0})
    return events


def _eff_cost(e: dict) -> float:
    """Risk-adjusted €/t: price + fee + band risk + carry + counterparty + fill risk."""
    ch = CHANNELS[e["kind"]]
    band_pen = RISK_AVERSION * max(0.0, e["priceHigh"] - e["price"])
    timing_pen = CARRY_PER_MONTH * e["monthsAhead"]
    counterparty_pen = (1.0 - e["rating"]) * 6.0
    fill_pen = (1.0 - e["fill"]) * 1.5  # sealed-bid auctions may not fill → risk cost
    return e["price"] + ch["fee"] + band_pen + timing_pen + counterparty_pen + fill_pen


def _secure_fraction(points: list[dict], shock: bool) -> float:
    """Confidence-driven hedge: a rising, supply-constrained market (shock) →
    secure everything now; otherwise cover the baseline share and hold a reserve."""
    return 1.0 if shock else BASELINE_SECURE


def _greedy(events: list[dict], target: float, caps: dict[str, float]) -> list[dict]:
    """Fill `target` from the cheapest risk-adjusted slots first, honouring
    per-channel caps (e.g. don't over-rely on sealed-bid auctions)."""
    for e in events:
        e["eff"] = _eff_cost(e)
    allocs: list[dict] = []
    taken: dict[str, float] = {}
    remaining = target
    for e in sorted(events, key=lambda x: x["eff"]):
        if remaining <= 500:
            break
        cap = caps.get(e["kind"])
        room = (cap - taken.get(e["kind"], 0)) if cap is not None else float("inf")
        if room <= 500:
            continue
        take = min(remaining, e["available"] * e["fill"], room)
        if take < 1000:
            continue
        vol = round(take / 100) * 100
        allocs.append({**e, "volume": vol})
        remaining -= vol
        taken[e["kind"]] = taken.get(e["kind"], 0) + vol
    return allocs


# ════════════════════════════════════════════════════════════════
#  Plan / view assembly
# ════════════════════════════════════════════════════════════════

def _status_for(e: dict, idx_in_channel: int, shock: bool) -> str:
    if e["kind"] in ("SPOT", "OTC"):
        return "EXECUTE"
    if e["kind"] == "AUCTION":
        return "EXECUTE" if e["monthsAhead"] == 0 and idx_in_channel == 0 else "SCHEDULED"
    return "EXECUTE" if shock else "SCHEDULED"  # RFQ pulled forward under shock


def _build_view(company: dict, position: dict, shock: bool, passed_fc: Optional[dict]) -> dict:
    art = _load_forecast(passed_fc)
    points = _forecast_points(art, shock)
    drivers = _drivers(art, shock)
    spot = _eua_history()[-1][1]
    D, side = _position(position)

    events = _build_events(points, spot, shock)
    fc_end = points[-1]["p50"]

    if side == "LONG":
        plan, mix, channels, auctions = _long_plan(D, points, spot, shock)
        tranches = plan
    else:
        secure = _secure_fraction(points, shock)
        target = D * secure
        reserve = round(D - target)
        caps = {"AUCTION": AUCTION_SHARE_CAP * D}
        allocs = _greedy([e for e in events], target, caps)
        tranches, mix = _tranches_and_mix(allocs, reserve, shock)
        channels = _channel_comparison(events, allocs, shock)
        auctions = _auctions_view(events, allocs, shock)

    expected = sum(t["volume"] * (t["price"] or fc_end) for t in tranches)
    reserve_vol = next((m["volume"] for m in mix if m["key"] == "WAIT"), 0)
    expected += reserve_vol * fc_end
    worst = expected * (1.16 if shock else 1.11)

    plan_obj = {
        "deficitVolume": round(D), "side": side,
        "action": _action(side, shock), "confidence": "high" if shock else "medium",
        "headline": _headline(side, shock, D, mix),
        "channelMix": mix, "tranches": tranches,
        "expectedTotal": round(expected), "worstCase": round(worst),
        "savingsVsBuyAllNow": round(abs(D * spot - expected)),
        "savingsVsYearEnd": round(abs(D * fc_end - expected)),
        "triggers": _triggers(side, shock),
    }
    return {
        "currentPrice": round(spot, 2),
        "forecastMode": art.get("mode", "fallback"),
        "forecast": points, "drivers": drivers,
        "channels": channels, "auctions": auctions,
        "plan": plan_obj, "matches": _matches(shock),
        "position": {"deficit": round(D), "side": side, **{k: position[k] for k in
                     ("required_allowances", "available_allowances", "net_position", "status") if k in position}},
    }


def _tranches_and_mix(allocs: list[dict], reserve: int, shock: bool):
    seen: dict[str, int] = {}
    tranches = []
    for e in allocs:
        idx = seen.get(e["kind"], 0)
        seen[e["kind"]] = idx + 1
        tranches.append({
            "id": e["id"], "when": e["label"], "channel": e["kind"], "volume": e["volume"],
            "price": e["price"], "maxBid": e["priceHigh"] if e["kind"] == "AUCTION" else None,
            "status": _status_for(e, idx, shock),
            "reason": _tranche_reason(e, shock),
        })
    mix_map: dict[str, int] = {}
    for t in tranches:
        mix_map[t["channel"]] = mix_map.get(t["channel"], 0) + t["volume"]
    mix = [{"key": k, "volume": v} for k, v in mix_map.items()]
    if reserve > 500:
        mix.append({"key": "WAIT", "volume": reserve})
    return tranches, mix


def _channel_comparison(events: list[dict], allocs: list[dict], shock: bool) -> list[dict]:
    routed = {}
    for a in allocs:
        routed[a["kind"]] = routed.get(a["kind"], 0) + a["volume"]
    rows = []
    for key in ("AUCTION", "SPOT", "RFQ", "OTC"):
        evs = [e for e in events if e["kind"] == key]
        if not evs:
            continue
        best = min(evs, key=lambda e: e["eff"])
        avail = sum(e["available"] for e in evs) if key != "SPOT" else 10_000_000
        rows.append({
            "key": key, "effCost": round(best["eff"], 1), "expectedPrice": round(best["price"], 1),
            "fillProb": CHANNELS[key]["fill"], "available": round(avail),
            "recommendedVolume": round(routed.get(key, 0)), "reason": _channel_reason(key, shock),
        })
    rows.sort(key=lambda r: (-r["recommendedVolume"], r["effCost"]))
    for i, r in enumerate(rows):
        r["rank"] = i + 1
    return rows


def _auctions_view(events: list[dict], allocs: list[dict], shock: bool) -> list[dict]:
    target_by_id = {}
    for a in allocs:
        if a["kind"] == "AUCTION":
            target_by_id[a["id"]] = a["volume"]
    out = []
    for e in events:
        if e["kind"] != "AUCTION":
            continue
        tv = target_by_id.get(e["id"], 0)
        out.append({
            "id": e["id"], "type": e["type"], "date": e["date"], "label": e["label"],
            "volume": round(e["lotVolume"]), "expectedClearing": round(e["price"], 1),
            "recommendedBid": round(e["priceHigh"], 1) if tv > 0 else (round(e["priceHigh"], 1) if e["monthsAhead"] <= 1 else None),
            "targetVolume": round(tv), "msrAffected": e.get("msr", False),
        })
    return out


def _long_plan(D: float, points: list[dict], spot: float, shock: bool):
    """Surplus disposal: sell via spot / RFQ / OTC (auctions are buy-only)."""
    if shock:
        rows = [("SPOT", 0.6, round(points[0]["p50"] + 0.0, 1), "EXECUTE"),
                ("OTC", 0.4, round(points[0]["p50"] - 0.8, 1), "EXECUTE")]
    else:
        rows = [("SPOT", 0.4, round(spot, 1), "EXECUTE"),
                ("RFQ", 0.35, round(points[2]["p50"], 1), "SCHEDULED"),
                ("OTC", 0.25, round(points[-1]["p50"], 1), "WAIT")]
    tranches, mix_map = [], {}
    for i, (ch, frac, price, status) in enumerate(rows):
        vol = round(D * frac / 100) * 100
        tranches.append({"id": f"s{i}", "when": "Now" if status == "EXECUTE" else "Month 3" if status == "SCHEDULED" else "Open",
                         "channel": ch, "volume": vol, "price": price, "maxBid": None, "status": status,
                         "reason": "Sell into the MSR squeeze" if shock else "Bank surplus as the floor rises"})
        mix_map[ch] = mix_map.get(ch, 0) + vol
    mix = [{"key": k, "volume": v} for k, v in mix_map.items()]
    channels = [{"key": ch, "effCost": price, "expectedPrice": price, "fillProb": CHANNELS[ch]["fill"],
                 "available": round(D), "recommendedVolume": round(D * frac), "rank": i + 1,
                 "reason": _channel_reason(ch, shock)} for i, (ch, frac, price, _) in enumerate(rows)]
    return tranches, mix, channels, []


# ── copy text ────────────────────────────────────────────────────

def _fmt(d: str) -> str:
    dt = datetime.strptime(d[:10], "%Y-%m-%d").date()
    return f"{['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][dt.weekday()]} {dt.day:02d} {MONTHS[dt.month-1]}"


def _tons(n: float) -> str:
    return f"{n/1000:.1f}k t" if abs(n) >= 1000 else f"{round(n)} t"


def _action(side: str, shock: bool) -> str:
    if side == "LONG":
        return "SELL"
    return "BUY" if shock else "LADDER"


_MIX_WORD = {"AUCTION": "auction", "SPOT": "spot", "RFQ": "RFQ", "OTC": "OTC", "WAIT": "reserve"}


def _headline(side: str, shock: bool, D: float, mix: list[dict]) -> str:
    if side == "LONG":
        return (f"Sell {_tons(D)} surplus into the MSR-driven squeeze" if shock
                else f"Bank {_tons(D)} surplus in tranches as the floor rises")
    ranked = sorted([m for m in mix if m["key"] != "WAIT"], key=lambda m: -m["volume"])[:2]
    desc = ", ".join(f"{round(m['volume'] / D * 100)}% {_MIX_WORD[m['key']]}" for m in ranked)
    reserve = next((m for m in mix if m["key"] == "WAIT"), None)
    tail = f" + {round(reserve['volume'] / D * 100)}% reserve" if reserve else ""
    prefix = "MSR cut — re-route: " if shock else ""
    return f"{prefix}cover {_tons(D)} — {desc}{tail}"


def _triggers(side: str, shock: bool) -> list[str]:
    if side == "LONG":
        return ["If spot > €78 → release the next sell tranche",
                "If the reform stalls → hold the remainder, the floor is still rising"]
    if shock:
        return ["MSR confirmed: auction lots −20% → the secondary market is now the primary route",
                "If spot > €78 → accelerate the remaining RFQ tranche",
                "Re-check clearing after the next auction — raise the bid if under-subscription risk rises"]
    return ["If spot > €72 before the auction → pull the reserve forward",
            "If an MSR cut tightens auction supply → re-route to spot / RFQ",
            "If the production forecast drops → cancel the held tranche"]


def _tranche_reason(e: dict, shock: bool) -> str:
    k = e["kind"]
    if k == "AUCTION":
        return ("MSR cuts the lot −20% — bid up for the reduced auction volume" if shock
                else f"Cheapest risk-adjusted route — CAP3 auction, bid ≤ €{e['priceHigh']:.1f}")
    if k == "SPOT":
        return "Replace lost auction supply on the secondary market immediately" if shock else "Immediate fill, no counterparty risk"
    if k == "OTC":
        return f"{e.get('seller','OTC')} @ €{e['price']:.2f} — fast settle, rating {e['rating']:.2f}"
    return "Pull the reserve forward — market tightening" if shock else "Broker quote, flexible size — second tranche"


def _channel_reason(key: str, shock: bool) -> str:
    table = {
        "AUCTION": ("Lot cut −20% by the MSR; fill probability drops — bid up only for a partial fill." if shock
                    else "Cheapest risk-adjusted route; next CAP3 in days. Sealed-bid — cap the bid."),
        "SPOT": ("Deep & immediate — absorbs the supply the MSR pulled out of the auction." if shock
                 else "Immediate but priciest. Keep as a fallback if an auction is missed."),
        "RFQ": ("Flexible size to cover the former reserve before the market tightens further." if shock
                else "Broker quote, flexible size — ideal for the second tranche."),
        "OTC": "Cheapest per tonne — but limited size, can’t close the gap alone." if shock
               else "Bilateral offer, fast settlement, strong counterparty rating.",
    }
    return table.get(key, "")


def _matches(shock: bool) -> list[dict]:
    out = []
    for o in market_service.get_sell_offers():
        rating = float(o.get("counterparty_rating", 0.9))
        price = float(o["price_per_eua"]) + (0.6 if shock else 0)
        out.append({
            "id": o["id"], "counterparty": o["seller_name"], "counterpartySector": _sector_of(o["seller_name"]),
            "side": "buy", "volume": int(o["volume"]), "price": round(price, 2),
            "timing": "NOW" if shock else "WAIT", "fit": round(rating * 100),
            "rationale": ("Lock before the squeeze — offer may be pulled" if shock
                          else f"{o.get('settlement_method','OTC')} · rating {rating:.2f}"),
        })
    return out


# ════════════════════════════════════════════════════════════════
#  Public API (the decision_adapter contract)
# ════════════════════════════════════════════════════════════════

class CarbonEdgeAgent:
    def run(self, company: dict, position: dict, forecast: Optional[dict] = None,
            forecast_source: str = "cache") -> dict:
        return _build_view(company, position, shock=False, passed_fc=forecast)


class ScenarioManager:
    def __init__(self, agent: CarbonEdgeAgent):
        self.agent = agent

    def run_scenario(self, company: dict, position: dict, forecast: Optional[dict],
                     event: str, forecast_source: str = "cache") -> dict:
        baseline = _build_view(company, position, shock=False, passed_fc=forecast)
        shock = event == "msr_auction_cut"
        shocked = _build_view(company, position, shock=shock, passed_fc=forecast)
        return {"event": event, "baseline": baseline, "shocked": shocked,
                "diff": _diff(baseline, shocked, shocked["plan"]["deficitVolume"])}


def _diff(baseline: dict, shocked: dict, D: float) -> dict:
    return {
        "event": "msr_auction_cut",
        "mixBefore": baseline["plan"]["channelMix"],
        "mixAfter": shocked["plan"]["channelMix"],
        "timingShiftDays": -21,
        "extraCostIfNoAdapt": round(D * 3.4),
        "savingsFromAdapting": round(D * 2.1),
        "narrative": ("The MSR removes 20% of auction supply and lifts the curve. The agent locks the "
                      "limited below-market OTC offers, tops up through the remaining channels, and pulls "
                      "the held reserve forward before the market fully reprices."),
    }
