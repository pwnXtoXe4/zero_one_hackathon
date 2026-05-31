"""Company emissions outlook for the CarbonEdge timeline.

Combines year-to-date actual monthly emissions with the forward Sybilion
emissions forecast (p10/p50/p90), builds the CUMULATIVE band over calendar
2026, and locates the overshoot zone where cumulative emissions cross the
free allocation. Heidelberg uses a real Sybilion forecast; the synthetic demo
firms get a clearly-labelled illustrative path derived from their annual figure.

All values are tonnes CO2 (the forecast file is in kt and is converted here).
"""

import csv
import json
from typing import Optional

from src.api.services import PREPARED_DIR, RAW_DIR, company_service

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
YEAR = 2026
LATEST_ACTUAL_MONTH = 5  # actuals available through May 2026

_HB_FORECAST = PREPARED_DIR / "heidelberg_emissions_forecast.json"
_HB_CSV = RAW_DIR / "synthetic" / "heidelberg_materials_monthly_emissions.csv"
# Mild cement seasonality (low in winter, peak late summer) for synthetic firms.
_SEASONAL = [0.86, 0.84, 0.95, 1.02, 1.05, 1.07, 1.08, 1.09, 1.05, 1.04, 0.99, 0.96]


def emissions_outlook(company_id: str) -> Optional[dict]:
    company = company_service.get_company(company_id)
    if company is None:
        return None
    free_allocation = float(company["free_allocation"])
    if company_id == "heidelberg" and _HB_FORECAST.exists():
        return _heidelberg_outlook(company, free_allocation)
    return _synthetic_outlook(company, free_allocation)


# ── builders ─────────────────────────────────────────────────────

def _heidelberg_outlook(company: dict, free_allocation: float) -> dict:
    actual = _hb_actuals_2026()  # {month_idx: tonnes}
    fc = json.loads(_HB_FORECAST.read_text(encoding="utf-8"))
    fs = fc.get("forecast", {}).get("data", {}).get("forecast_series", {})
    forecast: dict[int, dict] = {}
    for date_key, pt in fs.items():
        if not date_key.startswith(str(YEAR)):
            continue
        mo = int(date_key[5:7])
        q = pt.get("quantile_forecast", {})
        p50 = float(q.get("0.50", pt.get("forecast", 0.0))) * 1000.0
        p10 = float(q.get("0.10", p50 / 1000 * 0.9)) * 1000.0
        p90 = float(q.get("0.90", p50 / 1000 * 1.1)) * 1000.0
        forecast[mo] = {"p10": p10, "p50": p50, "p90": p90}
    return _assemble(company, free_allocation, actual, forecast, source="sybilion")


def _synthetic_outlook(company: dict, free_allocation: float) -> dict:
    annual = float(company["forecast_emissions"])
    base = annual / sum(_SEASONAL)
    actual = {m: base * _SEASONAL[m - 1] for m in range(1, LATEST_ACTUAL_MONTH + 1)}
    forecast: dict[int, dict] = {}
    for m in range(LATEST_ACTUAL_MONTH + 1, 13):
        p50 = base * _SEASONAL[m - 1]
        spread = 0.05 + 0.012 * (m - LATEST_ACTUAL_MONTH)  # widens with horizon
        forecast[m] = {"p10": p50 * (1 - spread), "p50": p50, "p90": p50 * (1 + spread)}
    return _assemble(company, free_allocation, actual, forecast, source="synthetic")


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

    start = earliest month the upper band (p90) crosses → soonest possible overshoot.
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


def _hb_actuals_2026() -> dict:
    out: dict[int, float] = {}
    with _HB_CSV.open(newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            d = r["date"]
            if d.startswith(str(YEAR)):
                out[int(d[5:7])] = float(r["co2_emissions_kt"]) * 1000.0
    return out
