"""Generate REAL Sybilion forecasts and cache them for the backend + frontend.

Produces two forecasts:
  1. EUA price (6-month horizon)   -> data/prepared/cache_<hash>.json   (engine/adapter cache)
                                    -> data/prepared/eua_price_forecast.json (named artifact)
  2. Heidelberg emissions (12-mo)  -> data/prepared/heidelberg_emissions_forecast.json

Run from the repo root with the venv python:
    SYBILION_API_TOKEN=... python scripts/generate_forecasts.py
The token is also read from a .env file if present.
"""

import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PREPARED = ROOT / "data" / "prepared"
EUA_PRICES = ROOT / "data" / "raw" / "eua_prices_monthly.json"
HEIDELBERG = ROOT / "data" / "raw" / "synthetic" / "heidelberg_materials_monthly_emissions.csv"


def _load_token() -> str | None:
    tok = os.environ.get("SYBILION_API_TOKEN") or os.environ.get("SYBILION_API_KEY")
    if tok:
        return tok.strip().strip('"')
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("SYBILION_API_TOKEN"):
                _, _, val = line.partition("=")
                return val.strip().strip('"')
    return None


def _eua_series() -> pd.Series:
    raw = json.loads(EUA_PRICES.read_text(encoding="utf-8"))
    return pd.Series({pd.Timestamp(k): float(v) for k, v in raw.items()}).sort_index()


def _heidelberg_series() -> pd.Series:
    rows = {}
    with HEIDELBERG.open(newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            rows[pd.Timestamp(r["date"])] = float(r["co2_emissions_kt"])
    return pd.Series(rows).sort_index()


def _artifact_dict(artifacts, mode: str, target: str, **extra) -> dict:
    return {
        "target": target,
        "mode": mode,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "forecast": artifacts.forecast,
        "signals": artifacts.signals,
        "backtest": artifacts.backtest,
        **extra,
    }


def _summarise(artifacts, label: str) -> None:
    fs = artifacts.forecast.get("data", {}).get("forecast_series", {})
    months = sorted(fs.keys())
    print(f"  [{label}] {len(months)} forecast months: {months[:1]}..{months[-1:]}")
    if months:
        q = fs[months[0]].get("quantile_forecast", {})
        print(f"  [{label}] quantile keys ({len(q)}): {sorted(q.keys())}")
        print(f"  [{label}] first month p50: {fs[months[0]].get('forecast')}")
    drivers = artifacts.signals.get("data", {})
    print(f"  [{label}] drivers: {len(drivers)} -> {list(drivers)[:5]}")


def main() -> int:
    from src.sybilion.client import HAS_SDK, SybilionWrapper

    token = _load_token()
    print(f"SDK available: {HAS_SDK} | token present: {bool(token)}")
    if not (HAS_SDK and token):
        print("WARNING: running in MOCK mode (no SDK or token).")

    # ── 1. EUA price forecast (6-month) ──────────────────────────────
    print("\n[1/2] EUA price forecast (horizon=6)...")
    eua = _eua_series()
    print(f"  series: {len(eua)} months {eua.index.min().date()}..{eua.index.max().date()}")
    w_price = SybilionWrapper(api_token=token, cache_dir=str(PREPARED))
    print(f"  mode: {w_price.mode}")
    art_price = w_price.submit_and_wait(
        eua,
        keywords=None,  # wrapper default == engine default -> cache key reproducible
        horizon=6,
        title="EU ETS EUA Carbon Allowance Price (EUR per tCO2)",
        description=(
            "Monthly closing prices of European Union Allowance (EUA) carbon permits under the "
            "EU Emissions Trading System. Prices in EUR per tonne of CO2 equivalent."
        ),
    )
    _summarise(art_price, "EUA")
    (PREPARED / "eua_price_forecast.json").write_text(
        json.dumps(_artifact_dict(art_price, w_price.mode, "eua_price"), indent=2),
        encoding="utf-8",
    )
    print(f"  saved -> {PREPARED / 'eua_price_forecast.json'}")
    caches = sorted(PREPARED.glob("cache_*.json"))
    print(f"  engine cache files in prepared/: {[c.name for c in caches]}")

    # ── 2. Heidelberg emissions forecast (12-month) ──────────────────
    print("\n[2/2] Heidelberg Materials emissions forecast (horizon=12)...")
    hb = _heidelberg_series()
    print(f"  series: {len(hb)} months {hb.index.min().date()}..{hb.index.max().date()}")
    # Separate cache dir so the emissions cache never collides with the price
    # cache the decision adapter globs in data/prepared.
    w_em = SybilionWrapper(api_token=token, cache_dir=str(PREPARED / "_emissions_cache"))
    art_em = w_em.submit_and_wait(
        hb,
        keywords=[
            "cement production", "clinker output", "construction demand",
            "industrial emissions", "EU ETS compliance", "carbon leakage",
            "alternative fuels cement", "building materials", "infrastructure spending",
        ],
        horizon=12,
        title="Heidelberg Materials Monthly CO2 Emissions (Scope 1, EU ETS)",
        description=(
            "Monthly CO2 emissions in kilotonnes for Heidelberg Materials cement plants under the "
            "EU ETS. Data based on annual reports and EU ETS trajectory, disaggregated to monthly "
            "resolution."
        ),
    )
    _summarise(art_em, "HEIDELBERG")
    (PREPARED / "heidelberg_emissions_forecast.json").write_text(
        json.dumps(
            _artifact_dict(art_em, w_em.mode, "emissions", company="heidelberg", unit="kt_co2"),
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"  saved -> {PREPARED / 'heidelberg_emissions_forecast.json'}")

    print("\nDONE.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
