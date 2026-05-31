"""Finish/resume Sybilion forecasts (jobs can take >10 min to settle).

Modes:
  --eua-only [--job-id ID]   Fetch the already-submitted EUA job and save cache + artifact.
  --heidelberg-only          Submit the Heidelberg emissions job, poll long, save artifact.

Saving:
  EUA        -> data/prepared/cache_<hash>.json  (engine/adapter cache, wrapper format)
             -> data/prepared/eua_price_forecast.json
  Heidelberg -> data/prepared/_emissions_cache/cache_<hash>.json (isolated, no glob collision)
             -> data/prepared/heidelberg_emissions_forecast.json
"""

import argparse
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

EUA_JOB_DEFAULT = "b5913ab6-db09-4f51-af7e-67145ade0cef"
EUA_KEYWORDS = None  # wrapper/engine default
HB_KEYWORDS = [
    "cement production", "clinker output", "construction demand",
    "industrial emissions", "EU ETS compliance", "carbon leakage",
    "alternative fuels cement", "building materials", "infrastructure spending",
]


def _token() -> str:
    tok = os.environ.get("SYBILION_API_TOKEN") or os.environ.get("SYBILION_API_KEY")
    if not tok:
        env = ROOT / ".env"
        if env.exists():
            for line in env.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("SYBILION_API_TOKEN"):
                    tok = line.partition("=")[2].strip().strip('"')
    return (tok or "").strip().strip('"')


def _eua_series() -> pd.Series:
    raw = json.loads(EUA_PRICES.read_text(encoding="utf-8"))
    return pd.Series({pd.Timestamp(k): float(v) for k, v in raw.items()}).sort_index()


def _hb_series() -> pd.Series:
    rows = {}
    with HEIDELBERG.open(newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            rows[pd.Timestamp(r["date"])] = float(r["co2_emissions_kt"])
    return pd.Series(rows).sort_index()


def _fetch_artifacts(client, job_id):
    def grab(name):
        try:
            return json.loads(client.get_forecast_artifact(job_id, name))
        except Exception:
            return None
    forecast = grab("forecast.json")
    signals = grab("external_signals.json") or {}
    backtest = grab("backtest_metrics.json")
    return forecast, signals, backtest


def _save(forecast, signals, backtest, series, keywords, horizon, cache_dir, named, target, **meta):
    from src.sybilion.client import ForecastArtifacts, SybilionWrapper
    arts = ForecastArtifacts(forecast, signals, backtest)
    w = SybilionWrapper(api_token=None, cache_dir=str(cache_dir))  # only for _cache_key + _save_cache
    kws = keywords if keywords is not None else __import__(
        "src.sybilion.keywords", fromlist=["select_keywords"]
    ).select_keywords(target="eua_price", max_keywords=16)
    key = w._cache_key(series, kws, horizon)
    w._save_cache(key, arts)
    named.write_text(json.dumps({
        "target": target, "mode": "live",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "forecast": forecast, "signals": signals, "backtest": backtest, **meta,
    }, indent=2), encoding="utf-8")
    print(f"  saved cache_{key}.json in {cache_dir.name}/ and {named.name}")
    fs = (forecast or {}).get("data", {}).get("forecast_series", {})
    months = sorted(fs)
    if months:
        q = fs[months[0]].get("quantile_forecast", {})
        print(f"  forecast months={len(months)} quantile_keys({len(q)})={sorted(q.keys())}")


def eua_only(job_id):
    from sybilion import Client
    c = Client(token=_token())
    j = c.get_forecast(job_id)
    print(f"EUA job {job_id}: settled={j.settled} status={getattr(j,'status',None)} cost={getattr(j,'eur_cents_final',None)}c")
    if not j.settled:
        print("  not settled yet — re-run later.")
        return 1
    f, s, b = _fetch_artifacts(c, job_id)
    _save(f, s, b, _eua_series(), EUA_KEYWORDS, 6, PREPARED, PREPARED / "eua_price_forecast.json", "eua_price")
    return 0


def heidelberg_only():
    from src.sybilion.client import SybilionWrapper
    hb = _hb_series()
    print(f"Heidelberg series: {len(hb)} months {hb.index.min().date()}..{hb.index.max().date()}")
    w = SybilionWrapper(api_token=_token(), cache_dir=str(PREPARED / "_emissions_cache"))
    print(f"  mode: {w.mode} — submitting + polling (timeout 2400s)...")
    arts = w.submit_and_wait(
        hb, keywords=HB_KEYWORDS, horizon=12,
        title="Heidelberg Materials Monthly CO2 Emissions (Scope 1, EU ETS)",
        description=(
            "Monthly CO2 emissions in kilotonnes for Heidelberg Materials cement plants under the "
            "EU ETS. Data based on annual reports and EU ETS trajectory, disaggregated to monthly resolution."
        ),
        max_wait=2400, poll_interval=15,
    )
    (PREPARED / "heidelberg_emissions_forecast.json").write_text(json.dumps({
        "target": "emissions", "company": "heidelberg", "unit": "kt_co2", "mode": w.mode,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "forecast": arts.forecast, "signals": arts.signals, "backtest": arts.backtest,
    }, indent=2), encoding="utf-8")
    fs = arts.forecast.get("data", {}).get("forecast_series", {})
    print(f"  saved heidelberg_emissions_forecast.json — {len(fs)} months")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--eua-only", action="store_true")
    ap.add_argument("--heidelberg-only", action="store_true")
    ap.add_argument("--job-id", default=EUA_JOB_DEFAULT)
    a = ap.parse_args()
    if a.eua_only:
        raise SystemExit(eua_only(a.job_id))
    if a.heidelberg_only:
        raise SystemExit(heidelberg_only())
    print("specify --eua-only or --heidelberg-only")
    raise SystemExit(2)
