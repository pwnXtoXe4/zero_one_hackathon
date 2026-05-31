"""Forecast Heidelberg Materials monthly emissions via Sybilion (12-month horizon)
and print the annualised p10/p50/p90 — used to size the company's free allocation.

    python scripts/check_emissions.py
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from src.sybilion.client import SybilionWrapper  # noqa: E402
from src.sybilion.keywords import select_keywords  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SERIES = ROOT / "data/prepared/synthetic/heidelberg_materials_monthly_emissions.json"


def main() -> None:
    data = json.loads(SERIES.read_text(encoding="utf-8"))
    ts = data["timeseries"]
    print("points:", len(ts), "| unit:", data["unit"], "| last:", sorted(ts)[-1], ts[sorted(ts)[-1]])

    s = pd.Series({pd.Timestamp(k): float(v) for k, v in ts.items()}).sort_index()
    token = os.environ.get("SYBILION_API_TOKEN") or os.environ.get("SYBILION_API_KEY")
    w = SybilionWrapper(api_token=token)
    art = w.submit_and_wait(
        s, keywords=select_keywords(focus="emissions_trajectory", horizon=12), horizon=12,
        title="Heidelberg Materials monthly CO2 emissions",
        description="Monthly Scope 1+2 CO2 emissions (kt) for Heidelberg Materials cement operations.",
    )
    print("mode:", w.mode)
    fs = art.forecast["data"]["forecast_series"]
    months = sorted(fs)

    def q(m, k):
        return fs[m].get("quantile_forecast", {}).get(k, fs[m]["forecast"])

    p50 = [q(m, "0.5") for m in months]
    p10 = [q(m, "0.1") for m in months]
    p90 = [q(m, "0.9") for m in months]
    print("horizon months:", [m[:7] for m in months])
    print("monthly p50 (kt):", [round(x) for x in p50])
    print(f"ANNUAL forecast (t):  p10={round(sum(p10)*1000):,}  p50={round(sum(p50)*1000):,}  p90={round(sum(p90)*1000):,}")


if __name__ == "__main__":
    main()
