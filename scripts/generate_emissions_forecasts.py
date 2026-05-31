"""Generate REAL Sybilion ~6-month emissions forecasts for each company and cache them.

Each company has ~61 months of REAL Climate TRACE history (>= 60 -> valid for a
4-6 month Sybilion horizon). Output per company:
    data/prepared/<company_id>_emissions_forecast.json   (real p10/p50/p90)

emissions_service._sybilion_forward() reads these automatically; until they
exist it falls back to the seasonal projection (honestly labelled).

Run (token via env var SYBILION_API_TOKEN or SYBILION_API_KEY):
    python scripts/generate_emissions_forecasts.py
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

try:  # make Windows consoles tolerate any unicode the SDK / data may print
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PREP = ROOT / "data" / "prepared"

from src.sybilion.client import HAS_SDK, SybilionWrapper  # noqa: E402

try:
    from src.sybilion.keywords import select_keywords  # noqa: E402
except Exception:  # noqa: BLE001
    select_keywords = None

# company_id -> (history file, sector key for keyword selection)
COMPANIES = {
    "salzgitter_steel": ("large_steel_salzgitter.json", "steel"),
    "lengerich_cement": ("large_cement_lengerich.json", "cement"),
    "deuna_cement": ("medium_cement_deuna.json", "cement"),
    "nordzucker_food": ("medium_food_nordzucker.json", "food"),
    "uxheim_cement": ("small_cement_uxheim.json", "cement"),
}

# No predefined "food" sector in keywords.py -> supply sugar/food-specific terms.
FOOD_KEYWORDS = [
    "sugar production", "sugar beet harvest", "food processing",
    "campaign season energy", "natural gas food industry", "boiler fuel consumption",
    "beet sugar output", "factory capacity utilization",
]


def _series(fn: str) -> pd.Series:
    d = json.loads((PREP / fn).read_text(encoding="utf-8"))
    return pd.Series({pd.Timestamp(k): float(v) for k, v in d["timeseries"].items()}).sort_index()


def _keywords(sector: str):
    if select_keywords is None:
        return None
    try:
        if sector == "food":
            return select_keywords(target="emissions", custom_keywords=FOOD_KEYWORDS, max_keywords=16)
        return select_keywords(target="emissions", sector=sector, max_keywords=16)
    except Exception:  # noqa: BLE001
        return None


def main() -> int:
    token = os.environ.get("SYBILION_API_TOKEN") or os.environ.get("SYBILION_API_KEY")
    print(f"HAS_SDK={HAS_SDK} | token={bool(token)}", flush=True)
    if not (HAS_SDK and token):
        print("ABORT: no SDK or token -> would only mock. Set SYBILION_API_TOKEN and retry.", flush=True)
        return 1

    ok = 0
    for cid, (fn, sector) in COMPANIES.items():
        try:
            s = _series(fn)
            kw = _keywords(sector)
            print(f"\n[{cid}] sector={sector} | {len(s)} pts "
                  f"{s.index.min().date()}..{s.index.max().date()} | submitting (horizon=6)...", flush=True)
            w = SybilionWrapper(api_token=token, cache_dir=str(PREP))
            art = w.submit_and_wait(
                s, keywords=kw, horizon=6,
                title=f"Monthly CO2 emissions - {cid}",
                description="Monthly facility CO2 emissions (tonnes), Climate TRACE v5.5 history.",
                max_wait=1500, poll_interval=15,  # these jobs settle in ~10-15 min
            )
            out = {
                "target": "emissions", "company_id": cid, "sector": sector, "mode": w.mode,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "forecast": art.forecast, "signals": art.signals, "backtest": art.backtest,
            }
            (PREP / f"{cid}_emissions_forecast.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
            fs = art.forecast.get("data", {}).get("forecast_series", {})
            ms = sorted(fs)
            q = fs[ms[0]].get("quantile_forecast", {}) if ms else {}
            print(f"  OK saved {cid}_emissions_forecast.json | mode={w.mode} | "
                  f"months={len(ms)} | quantiles={len(q)}", flush=True)
            ok += 1
        except Exception as e:  # noqa: BLE001
            print(f"  FAIL {cid}: {repr(e)[:200]}", flush=True)
    print(f"\nDONE ({ok}/{len(COMPANIES)} succeeded)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
