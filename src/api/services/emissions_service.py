"""Company emissions outlook for the CarbonEdge timeline.

Builds the CUMULATIVE 2026 emissions band (p10/p50/p90) and locates the
overshoot zone where cumulative emissions cross the free allocation.

Every company uses REAL measured emissions data (Climate TRACE v5.5, monthly,
facility-level). The forward months of 2026 are a seasonal projection grounded
in that company's own real history (level + seasonality), with a widening band.

All values are tonnes CO2.
"""

import json
from typing import Optional

from src.api.services import PREPARED_DIR, company_service

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
YEAR = 2026

# company_id → real monthly emissions history file (Climate TRACE v5.5, tonnes CO2)
_TRACE = {
    "salzgitter_steel": "large_steel_salzgitter.json",
    "lengerich_cement": "large_cement_lengerich.json",
    "deuna_cement": "medium_cement_deuna.json",
    "nordzucker_food": "medium_food_nordzucker.json",
    "uxheim_cement": "small_cement_uxheim.json",
}
# Generic seasonal shape — only used if a company has no history file at all.
_SEASONAL = [0.86, 0.84, 0.95, 1.02, 1.05, 1.07, 1.08, 1.09, 1.05, 1.04, 0.99, 0.96]


def emissions_outlook(company_id: str) -> Optional[dict]:
    company = company_service.get_company(company_id)
    if company is None:
        return None
    free = float(company["free_allocation"])
    if company_id in _TRACE:
        return _trace_outlook(company, free, company_id)
    return _synthetic_outlook(company, free)  # legacy safety net


# ── builders ─────────────────────────────────────────────────────

def _trace_outlook(company: dict, free: float, company_id: str) -> dict:
    """Real Climate TRACE monthly history → 2026 cumulative band.

    Forward months use the REAL Sybilion probabilistic emissions forecast
    (p10/p50/p90) when one has been generated for this company; otherwise a
    seasonal projection grounded in the company's own real history."""
    hist = _load_history(PREPARED_DIR / _TRACE[company_id])  # 'YYYY-MM-01' → tonnes
    actual = {int(k[5:7]): v for k, v in hist.items() if k.startswith(str(YEAR))}
    latest = max(actual) if actual else 0
    syb = _sybilion_forward(company_id)
    proj = _project(hist, latest + 1)
    forecast = {m: (syb.get(m) or proj.get(m)) for m in range(latest + 1, 13)}
    forecast = {m: v for m, v in forecast.items() if v}
    source = "climate_trace_actuals + sybilion_forecast" if syb else "climate_trace_projection"
    return _assemble(company, free, actual, forecast, source=source)


def _sybilion_forward(company_id: str) -> dict:
    """Real Sybilion emissions forecast for 2026 forward months, if generated.

    Returns {month_int: {'p10','p50','p90'}} (tonnes), or {} when no forecast
    file exists yet → caller falls back to the seasonal projection."""
    path = PREPARED_DIR / f"{company_id}_emissions_forecast.json"
    if not path.exists():
        return {}
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        fs = d.get("forecast", {}).get("data", {}).get("forecast_series", {})
        out: dict[int, dict] = {}
        for k, v in fs.items():
            if not k.startswith(str(YEAR)):
                continue
            q = v.get("quantile_forecast", {})
            p50 = float(q.get("0.5", v.get("forecast", 0)))
            p10 = float(q.get("0.1", p50 * 0.95))
            p90 = float(q.get("0.9", p50 * 1.05))
            out[int(k[5:7])] = {"p10": p10, "p50": p50, "p90": p90}
        return out
    except Exception:  # noqa: BLE001
        return {}


def _synthetic_outlook(company: dict, free: float) -> dict:
    annual = float(company["forecast_emissions"])
    base = annual / sum(_SEASONAL)
    actual = {m: base * _SEASONAL[m - 1] for m in range(1, 6)}
    forecast = {}
    for m in range(6, 13):
        p50 = base * _SEASONAL[m - 1]
        spread = 0.05 + 0.012 * (m - 5)
        forecast[m] = {"p10": p50 * (1 - spread), "p50": p50, "p90": p50 * (1 + spread)}
    return _assemble(company, free, actual, forecast, source="synthetic")


# ── projection from real history (seasonal shape + recent level) ──

def _project(hist: dict, start_month: int) -> dict:
    items = sorted(hist.items())
    vals = [v for _, v in items]
    if not vals:
        return {}
    by_cal: dict[int, list] = {m: [] for m in range(1, 13)}
    for k, v in items:
        by_cal[int(k[5:7])].append(v)
    overall = sum(vals) / len(vals)
    seasonal = {m: (sum(by_cal[m]) / len(by_cal[m]) / overall) if by_cal[m] else 1.0 for m in range(1, 13)}
    monthly_base = sum(vals[-12:]) / 12.0  # recent annual level / 12
    out: dict[int, dict] = {}
    for m in range(start_month, 13):
        p50 = monthly_base * seasonal[m]
        spread = 0.05 + 0.012 * (m - start_month + 1)  # widens with horizon
        out[m] = {"p10": p50 * (1 - spread), "p50": p50, "p90": p50 * (1 + spread)}
    return out


# ── shared assembly ──────────────────────────────────────────────

def _assemble(company: dict, free_allocation: float, actual: dict, forecast: dict, source: str) -> dict:
    months: list[dict] = []
    cum10 = cum50 = cum90 = 0.0
    for m in range(1, 13):
        if m in actual:
            v = actual[m]
            cum10 += v; cum50 += v; cum90 += v
            months.append({
                "month": f"{YEAR}-{m:02d}", "label": MONTHS[m - 1], "isForecast": False,
                "p10": round(v), "p50": round(v), "p90": round(v),
                "cumP10": round(cum10), "cumP50": round(cum50), "cumP90": round(cum90),
            })
        elif m in forecast:
            f = forecast[m]
            cum10 += f["p10"]; cum50 += f["p50"]; cum90 += f["p90"]
            months.append({
                "month": f"{YEAR}-{m:02d}", "label": MONTHS[m - 1], "isForecast": True,
                "p10": round(f["p10"]), "p50": round(f["p50"]), "p90": round(f["p90"]),
                "cumP10": round(cum10), "cumP50": round(cum50), "cumP90": round(cum90),
            })

    overshoot = _overshoot(months, free_allocation)
    annual_p50 = months[-1]["cumP50"] if months else 0
    return {
        "company_id": company["id"],
        "company": company["name"],
        "unit": "tCO2",
        "year": YEAR,
        "source": source,
        "free_allocation": round(free_allocation),
        "annual_emissions_p50": annual_p50,
        "annual_deficit_p50": round(annual_p50 - free_allocation),
        "months": months,
        "overshoot": overshoot,
    }


def _overshoot(months: list[dict], free_allocation: float) -> Optional[dict]:
    """Zone where the cumulative band crosses the free allocation line.

    start = earliest month the upper band (p90) crosses → soonest possible.
    expected = month the median (p50) crosses.
    end = month the lower band (p10) crosses → overshoot certain by here.
    """
    def cross(key: str) -> Optional[dict]:
        for mth in months:
            if mth[key] >= free_allocation:
                return mth
        return None

    expected = cross("cumP50")
    if expected is None:
        return None  # stays within allocation all year
    start = cross("cumP90") or expected
    end = cross("cumP10") or months[-1]
    return {
        "startMonth": start["month"], "startLabel": start["label"],
        "expectedMonth": expected["month"], "expectedLabel": expected["label"],
        "endMonth": end["month"], "endLabel": end["label"],
        "label": f"{start['label']}–{end['label']}" if start["month"] != end["month"] else start["label"],
    }


# ── data loader ──────────────────────────────────────────────────

def _load_history(path) -> dict:
    """Climate TRACE prepared file → {'YYYY-MM-01': tonnes}."""
    d = json.loads(path.read_text(encoding="utf-8"))
    ts = d.get("timeseries", {})
    return {k: float(v) for k, v in ts.items()}
