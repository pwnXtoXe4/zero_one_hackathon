"""
CarbonEdge -- Daily-Data Backtest Engine

Uses carbon_emission_futures_data.csv (2,849 daily rows, 2015–2026)
to run the procurement backtest at higher temporal resolution.

Resampling
----------
Daily prices are resampled to monthly decision points (last business day
of each month). This preserves the monthly procurement cadence (horizons
1, 3, 6 months) while benefiting from:
  - More accurate spot prices (actual daily close vs monthly aggregate)
  - Higher-granularity regime detection (PSY bubble on daily data)
  - Potentially more test windows via shorter warmup / smaller step

Typical output with default settings:
  - 48-month warmup, 1-month step: ~87 test windows (vs 25 with monthly)
  - 36-month warmup, 1-month step: ~99 test windows

References
----------
- Diebold & Mariano (1995) — DM test with NW HAC
- Bastianin et al. (2024) — expanding-window protocol on monthly EUA
- Friedrich et al. (2019) — PSY bubble test on EU ETS data
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from .backtest import (
    BacktestResult,
    StatisticalSummary,
    _diebold_mariano,
    _newey_west_hac,
    format_backtest_report,
    run_backtest,
)
from .config import CARBON_EXPOSURE

logger = logging.getLogger(__name__)

_DAILY_CSV_PATH = Path(__file__).resolve().parents[1] / "data" / "raw" / "carbon_emission_futures_data.csv"
_ICAP_CSV_PATH = Path(__file__).resolve().parents[1] / "data" / "eu_ets_daily_prices.csv"


@dataclass
class DailyBacktestMeta:
    """Metadata about a daily-data backtest run."""
    source_file: str
    daily_rows: int
    date_from: str
    date_to: str
    monthly_points: int
    warmup_months: int
    step_months: int
    test_windows: int


def load_daily_prices(csv_path: Optional[Path] = None) -> List[Tuple[str, float]]:
    """Load daily carbon futures from CSV, return chronological (date, price).

    The CSV is reverse-chronological (newest first) — we reverse it.
    UTF-8 BOM is handled via encoding='utf-8-sig'.
    """
    path = csv_path or _DAILY_CSV_PATH
    rows: List[Tuple[str, float]] = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            date_str = row["Date"].strip()
            try:
                price = float(row["Price"].replace(",", ""))
            except (ValueError, KeyError):
                continue
            rows.append((date_str, price))
    rows.reverse()  # chronological order
    return rows


def _load_icap_daily_prices(path: Path = _ICAP_CSV_PATH) -> List[Tuple[str, float]]:
    """Load ICAP daily EU ETS auction prices (2010-2018, EUR).

    The ICAP file is a multi-jurisdiction wide CSV with two header rows;
    the EU ETS primary-auction price lives in column 9 ("Primary Market"
    under the "European Union Emissions Trading System (until 2018)"
    section). Date format is YYYY-MM-DD. Returns chronological [(date, price)].
    """
    import csv
    rows: List[Tuple[str, float]] = []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        next(reader, None)  # skip section row
        next(reader, None)  # skip field row
        for r in reader:
            if len(r) < 10:
                continue
            date_str = r[0].strip()
            price_str = r[9].strip()
            if not date_str or price_str in ("", "-"):
                continue
            try:
                price = float(price_str)
            except ValueError:
                continue
            rows.append((date_str, price))
    rows.sort()
    return rows


def load_extended_daily_prices(
    icap_path: Path = _ICAP_CSV_PATH,
    investing_path: Path = _DAILY_CSV_PATH,
    splice_date: str = "2015-04-30",
) -> List[Tuple[str, float]]:
    """Splice ICAP (2010-2015) + investing futures (2015-2026) for a continuous
    daily EUA price series back to 2010-01-05.

    Notes
    -----
    * Both series are denominated in EUR/tCO2e.
    * The ICAP series is primary-auction spot; the investing series is front-
      month futures. Mean basis in the 2015-2018 overlap is +5.2% (contango),
      stdev 0.9 EUR. This small level shift at the splice point is acceptable
      for backtesting because every evaluation window uses prices internally
      consistently — only windows that straddle the splice see the basis.
    * Dates from `splice_date` onward come from `investing_path`. Dates
      strictly before come from `icap_path`.
    """
    icap = _load_icap_daily_prices(icap_path)
    inv = load_daily_prices(investing_path)
    # Reformat investing dates to YYYY-MM-DD for consistent ordering
    inv_norm: List[Tuple[str, float]] = []
    for date_str, price in inv:
        dt = datetime.strptime(date_str, "%m/%d/%Y")
        inv_norm.append((dt.strftime("%Y-%m-%d"), price))

    # Split: ICAP < splice_date; investing >= splice_date.
    early = [(d, p) for d, p in icap if d < splice_date]
    late = [(d, p) for d, p in inv_norm if d >= splice_date]
    merged = early + late
    merged.sort()
    # De-duplicate any same-day collisions (keep the later source as the more
    # liquid feed)
    seen: Dict[str, float] = {}
    for d, p in merged:
        seen[d] = p
    out = sorted(seen.items())

    # Re-emit dates in the same MM/DD/YYYY format the rest of the pipeline
    # expects (resample_to_monthly / resample_to_weekly use strptime %m/%d/%Y).
    formatted: List[Tuple[str, float]] = []
    for d, p in out:
        dt = datetime.strptime(d, "%Y-%m-%d")
        formatted.append((dt.strftime("%m/%d/%Y"), p))
    return formatted


def resample_to_weekly(
    daily: List[Tuple[str, float]],
    method: str = "last",
) -> Dict[str, float]:
    """Resample daily data to weekly decision points (last trading day of ISO week).

    Parameters
    ----------
    daily : (date_str, price) chronological list
    method : 'last' -> last trading day of ISO week; 'first' -> first

    Returns
    -------
    {YYYY-MM-DD: price} dict with the chosen trading day's date as the key.
    The date is the *actual* trading day picked (not Friday by convention) so
    monthly downstream lookups stay consistent.
    """
    week_data: Dict[str, List[Tuple[str, float]]] = {}
    for date_str, price in daily:
        dt = datetime.strptime(date_str, "%m/%d/%Y")
        iso_year, iso_week, _ = dt.isocalendar()
        key = f"{iso_year}-W{iso_week:02d}"
        week_data.setdefault(key, []).append((dt, price))

    result: Dict[str, float] = {}
    for week_key, entries in sorted(week_data.items()):
        entries.sort(key=lambda x: x[0])
        chosen = entries[0] if method == "first" else entries[-1]
        date_key = chosen[0].strftime("%Y-%m-%d")
        result[date_key] = chosen[1]
    return result


def resample_to_monthly(
    daily: List[Tuple[str, float]],
    method: str = "last",
) -> Dict[str, float]:
    """Resample daily data to monthly decision points.

    Parameters
    ----------
    daily : (date_str, price) chronological list
    method : 'last' → last trading day of month; 'first' → first trading day

    Returns
    -------
    {YYYY-MM-DD: price} dict with one entry per calendar month.
    """
    month_data: Dict[str, List[Tuple[str, float]]] = {}
    for date_str, price in daily:
        dt = datetime.strptime(date_str, "%m/%d/%Y")
        key = dt.strftime("%Y-%m")  # e.g. "2021-03"
        month_data.setdefault(key, []).append((date_str, price))

    result: Dict[str, float] = {}
    for month_key, entries in sorted(month_data.items()):
        entries.sort(key=lambda x: x[0])
        if method == "first":
            chosen = entries[0]
        else:
            chosen = entries[-1]  # last trading day
        # Use first day of month as the key (matching existing monthly format)
        date_key = f"{month_key}-01"
        result[date_key] = chosen[1]

    return result


def run_backtest_weekly(
    csv_path: Optional[Path] = None,
    resample_method: str = "last",
    warmup_months: int = 48,
    step_weeks: int = 1,
    forecast_mode: str = "naive",
    seed: int = 42,
    **kwargs,
) -> Tuple[BacktestResult, DailyBacktestMeta]:
    """Run end-to-end backtest at WEEKLY evaluation cadence.

    The decision agent still reasons about MONTHLY forecast horizons (1, 3,
    6 months ahead), because that's the granularity Sybilion produces. But
    we re-evaluate the agent every `step_weeks` weeks, giving ~12x the
    number of test windows that a monthly backtest produces over the same
    span. Statistical power scales with sqrt(n_windows) after Newey-West
    accounts for the (high) autocorrelation between adjacent weeks.

    Parameters
    ----------
    csv_path : path to carbon_emission_futures_data.csv (auto-detected)
    resample_method : 'last' or 'first' day of ISO week
    warmup_months : minimum *months* of history before first evaluation
    step_weeks : weeks between evaluation windows (default 1)
    forecast_mode : 'naive' (only mode supported for weekly -- oracle is
        calibrated to monthly Sybilion artifacts)
    seed : random seed
    **kwargs : passed to run_backtest()

    Returns
    -------
    (BacktestResult, DailyBacktestMeta)
    """
    if forecast_mode != "naive":
        raise ValueError(
            f"run_backtest_weekly only supports forecast_mode='naive'; "
            f"oracle is monthly-only."
        )
    weekly_per_month = 52.143 / 12.0   # = 4.345
    daily = load_daily_prices(csv_path)
    prices = resample_to_weekly(daily, method=resample_method)

    if not prices:
        raise ValueError("No weekly data after resampling daily CSV")

    sorted_dates = sorted(prices.keys())
    warmup_ticks = int(round(warmup_months * weekly_per_month))
    eval_indices = list(range(warmup_ticks, len(sorted_dates) - 1, step_weeks))

    meta = DailyBacktestMeta(
        source_file=str(csv_path or _DAILY_CSV_PATH),
        daily_rows=len(daily),
        date_from=daily[0][0] if daily else "N/A",
        date_to=daily[-1][0] if daily else "N/A",
        monthly_points=len(prices),    # named monthly_points but it's weekly here
        warmup_months=warmup_months,
        step_months=step_weeks,        # named step_months but it's weeks here
        test_windows=len(eval_indices),
    )

    logger.info(
        "Weekly backtest: %d daily rows -> %d weekly points -> %d test windows "
        "(warmup=%d mo, step=%d wk, cadence=%.3f wk/mo)",
        meta.daily_rows, meta.monthly_points, meta.test_windows,
        warmup_months, step_weeks, weekly_per_month,
    )

    result = run_backtest(
        prices=prices,
        seed=seed,
        forecast_mode=forecast_mode,
        warmup_ticks=warmup_ticks,
        step_ticks=step_weeks,
        min_windows=max(6, step_weeks * 4),
        cadence_ticks_per_month=weekly_per_month,
        **kwargs,
    )
    return result, meta


def run_backtest_daily(
    csv_path: Optional[Path] = None,
    resample_method: str = "last",
    warmup_months: int = 48,
    step_months: int = 1,
    forecast_mode: str = "naive",
    seed: int = 42,
    use_asymptotic_psy: bool = False,
    psy_n_simulations: Optional[int] = None,
    **kwargs,
) -> Tuple[BacktestResult, DailyBacktestMeta]:
    """Run end-to-end backtest on daily-resampled data.

    Parameters
    ----------
    csv_path : path to carbon_emission_futures_data.csv (auto-detected)
    resample_method : 'last' or 'first' day of month
    warmup_months : minimum months before first evaluation (default 48)
    step_months : months between evaluation windows (default 1, was 3)
    forecast_mode : 'naive' (honest out-of-sample) or 'oracle'
    seed : random seed
    use_asymptotic_psy : if True, skip PSY bootstrap and use asymptotic
        critical values from PSY (2015) Table 1. Fast but ~5% size distortion.
    psy_n_simulations : override default bootstrap sim count (2000).
        Lower to 500-1000 for faster first-run precompute.
    **kwargs : passed to run_backtest() (epu_modulator, fundamental_model, etc.)

    Returns
    -------
    (BacktestResult, DailyBacktestMeta) — backtest results + metadata.
    """
    daily = load_daily_prices(csv_path)
    prices = resample_to_monthly(daily, method=resample_method)

    if not prices:
        raise ValueError("No monthly data after resampling daily CSV")

    sorted_dates = sorted(prices.keys())
    eval_indices = list(range(warmup_months, len(sorted_dates) - 1, step_months))

    meta = DailyBacktestMeta(
        source_file=str(csv_path or _DAILY_CSV_PATH),
        daily_rows=len(daily),
        date_from=daily[0][0] if daily else "N/A",
        date_to=daily[-1][0] if daily else "N/A",
        monthly_points=len(prices),
        warmup_months=warmup_months,
        step_months=step_months,
        test_windows=len(eval_indices),
    )

    logger.info(
        "Daily backtest: %d daily rows -> %d monthly points -> %d test windows "
        "(warmup=%d mo, step=%d mo)",
        meta.daily_rows, meta.monthly_points, meta.test_windows,
        warmup_months, step_months,
    )

    # ---- Pre-compute PSY critical values for all window sizes ----
    if not use_asymptotic_psy:
        from .enhancement.psy_bubble import precompute_critical_values, PSY_N_SIMULATIONS
        try:
            T_values = [idx + 1 for idx in eval_indices]
            n_sim = psy_n_simulations or PSY_N_SIMULATIONS
            logger.info(
                "Daily backtest: pre-computing PSY critical values for %d T values "
                "(n_sim=%d)",
                len(set(T_values)), n_sim,
            )
            precompute_critical_values(
                T_values=T_values,
                min_window=24,
                n_simulations=n_sim,
                seed=seed,
            )
        except Exception as exc:
            logger.warning(
                "PSY precompute failed (%s), falling back to asymptotic critical values. "
                "Bubble detection will be approximate (~5%% size distortion vs bootstrap).",
                exc,
            )

    result = run_backtest(
        prices=prices,
        seed=seed,
        forecast_mode=forecast_mode,
        warmup_months=warmup_months,
        step_months=step_months,
        min_windows=max(6, step_months * 3),
        use_asymptotic_psy=use_asymptotic_psy,
        psy_n_simulations=psy_n_simulations,
        **kwargs,
    )

    return result, meta


def format_daily_report(result: BacktestResult, meta: DailyBacktestMeta) -> str:
    """Generate a report compatible with format_backtest_report(), plus metadata."""
    # Build a prices dict from result for format_backtest_report
    if result.windows:
        prices = {w.evaluation_date: w.spot_price for w in result.windows}
    else:
        prices = {}
    report = format_backtest_report(result, prices)

    meta_lines = [
        "",
        "=" * 72,
        "  DAILY-DATA BACKTEST META",
        "=" * 72,
        f"  Source:         {meta.source_file}",
        f"  Daily rows:     {meta.daily_rows}",
        f"  Date range:     {meta.date_from} → {meta.date_to}",
        f"  Monthly points: {meta.monthly_points}",
        f"  Warmup months:  {meta.warmup_months}",
        f"  Step months:    {meta.step_months}",
        f"  Test windows:   {meta.test_windows}",
        "",
    ]

    return "\n".join(meta_lines) + "\n" + report


# ---------------------------------------------------------------------------
# Quick-launch entry point
# ---------------------------------------------------------------------------
def main():
    """Run the daily-data backtest and print the report."""
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    result, meta = run_backtest_daily(
        warmup_months=48,
        step_months=1,
        forecast_mode="naive",
        use_asymptotic_psy=True,
    )
    print(format_daily_report(result, meta))


if __name__ == "__main__":
    main()
