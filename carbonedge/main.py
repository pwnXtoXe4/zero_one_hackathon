"""
CarbonEdge -- Main Entry Point

Usage:
    python -m carbonedge.main

Flow:
    1. Load EU ETS price data
    2. Validate time series
    3. Prepare Sybilion forecast request
    4. Build MAC curve from company profile
    5. Run decision agent
    6. Print formatted strategy report
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import (
    CARBON_EXPOSURE,
    COMPANY_PROFILE,
    DATA_DIR,
    EMISSION_SOURCES,
    FORECAST_TARGETS,
    ReductionOption,
    load_timeseries,
)
from .logging_setup import configure_logging

logger = logging.getLogger(__name__)
from .fundamental.balance_model import FundamentalModel, BalanceSignal
from .fundamental.cap_schedule import build_cap_schedule
from .fundamental.data_sources import load_ets_csv, load_monthly_prices, EtsData
from .fundamental.driver_monitor import DriverMonitor, DriverState
from .mac_curve import MACCurve, build_mac_curve, mac_summary
from .decision_agent import EnhancedDecision, run_decision_agent

from .adaptive import (
    ACCELERATED_ETS_REFORM,
    CBAM_ACCELERATION,
    ENERGY_PRICE_CRASH,
    AdaptiveDelta,
    ScenarioShift,
    recalculate_after_shift,
)
from .output import (
    format_full_decision,
    format_adaptive_delta,
)
from .regime_detector import RegimeMonitor
from .sybilion_client import (
    ForecastResult,
    build_forecast_request,
    parse_forecast_response,
    validate_timeseries,
)


def load_ets_data() -> Dict[str, float]:
    """Load the EU ETS monthly price data."""
    target = FORECAST_TARGETS["eu_ets_price"]
    logger.info("Loading ETS time series from %s", target["input_file"])
    data = load_timeseries(target["input_file"])
    if not data:
        logger.error("No data in %s", target["input_file"])
        sys.exit(1)
    logger.info(
        "Loaded %d ETS points (range %s -> %s)",
        len(data),
        min(data.keys()),
        max(data.keys()),
    )
    return data


def build_sybilion_request(ts_data: Dict[str, float]) -> Dict[str, Any]:
    """Build a Sybilion forecast request for the EU ETS price series."""
    target = FORECAST_TARGETS["eu_ets_price"]

    valid, msg = validate_timeseries(ts_data)
    if not valid:
        logger.error("Sybilion request validation failed: %s", msg)
        sys.exit(1)
    logger.debug("Timeseries validation OK (%s)", msg)

    request = build_forecast_request(
        timeseries=ts_data,
        title=target["title"],
        description=target["description"],
        keywords=target["keywords"],
        soft_horizon=6,
        backtest=True,
        hard_horizon=3,
        recency_factor=0.7,
        categories=[25, 46, 40, 12, 17, 30, 47, 45, 2, 23],
        regions=[3, 276, 250, 616, 528],
        driver_limit=1000,
    )

    logger.info(
        "Built Sybilion request: %d points, horizon=%d, backtest=%s, keywords=%d",
        len(ts_data),
        request["soft_horizon"],
        request["backtest"],
        len(request["timeseries_metadata"]["keywords"]),
    )
    print(f"[v] Validated {len(ts_data)} data points (back to {min(ts_data.keys())})")
    return request


def get_current_ets_price(ts_data: Dict[str, float]) -> float:
    """Get the latest ETS price from the time series."""
    latest = max(ts_data.keys())
    return float(ts_data[latest])


def main():
    """
    CarbonEdge -- Full Pipeline

    This is the entry point used by the opencode agent to:
      1. Prepare data for Sybilion
      2. Build the decision model
      3. After receiving a forecast, generate the strategy report
    """
    print("+==================================================+")
    print("|   CarbonEdge -- CO2 Reduction Decision Agent      |")
    print("+==================================================+")
    print()

    # ------------------------------------------------------------------
    # Phase 1: Load & validate data
    # ------------------------------------------------------------------
    print("[1/4] Loading EU ETS price data...")
    ts_data = load_ets_data()
    current_price = get_current_ets_price(ts_data)
    print(f"      Latest price: EUR{current_price:.2f}/ton ({max(ts_data.keys())})")

    request = build_sybilion_request(ts_data)

    # ------------------------------------------------------------------
    # Phase 2: Prepare forecast request (for agent to submit via MCP)
    # ------------------------------------------------------------------
    print("\n[2/4] Sybilion Forecast Request prepared:")
    print(f"      Points: {len(ts_data)} | Horizon: {request['soft_horizon']} months | Backtest: {request['backtest']}")
    print(f"      Keywords: {', '.join(request['timeseries_metadata']['keywords'])}")

    # Write request to file for the agent to use with sybilion_validate -> sybilion_submit
    request_path = DATA_DIR / "forecast_request_ets.json"
    with open(request_path, "w") as f:
        json.dump(request, f, indent=2)
    print(f"      -> Request saved to {request_path}")

    # ------------------------------------------------------------------
    # Phase 3: Build initial MAC curve & decision model
    # ------------------------------------------------------------------
    print("\n[3/4] Building MAC curve & decision model...")
    mac = build_mac_curve(current_ets_price=current_price)
    print(f"      Options: {len(mac)} | Viable tons: {mac.total_potential_tons:,.0f}")

    print("\n" + mac_summary(mac))

    # ------------------------------------------------------------------
    # Phase 4: Wait for Sybilion forecast, then run agent
    # ------------------------------------------------------------------
    print("\n[4/4] Awaiting Sybilion forecast...")
    print(f"      Run: sybilion_validate_forecast_data with the request at {request_path}")
    print(f"      Then: sybilion_submit_forecast to get a job_id")
    print(f"      Then: sybilion_get_forecast to poll until completed")
    print(f"      Then: sybilion_get_forecast_chart for visualization")
    print()
    print("      After receiving the forecast response, run:")
    print("      ---------------------------------------")
    print("      run_carbonedge_with_forecast(forecast_json_path)")
    print("      ---------------------------------------")
    print()

    return request, mac, current_price


def run_carbonedge_with_forecast(
    forecast_json_path: str,
    scenario: Optional[str] = None,
    external_signals_path: Optional[str] = None,
    backtest_metrics_path: Optional[str] = None,
    historical_prices: Optional[List[float]] = None,
) -> str:
    """
    Process a Sybilion forecast response and generate the full decision report.

    Parameters
    ----------
    forecast_json_path : path to forecast.json artifact
    scenario : optional scenario shift name ("ets_reform", "cbam", "energy_crash")
    external_signals_path : path to external_signals.json artifact
    backtest_metrics_path : path to backtest_metrics.json artifact
    historical_prices : optional list of historical prices for regime detection backtest

    Returns
    -------
    Formatted strategy report as a string.
    """
    logger.info(
        "run_carbonedge_with_forecast(forecast=%s, scenario=%s, ext=%s, backtest=%s)",
        forecast_json_path, scenario, external_signals_path, backtest_metrics_path,
    )

    # Load data
    ts_data = load_ets_data()
    current_price = get_current_ets_price(ts_data)
    logger.info("Current spot price: EUR %.2f/ton", current_price)

    # Parse forecast
    logger.debug("Reading forecast artifact %s", forecast_json_path)
    with open(forecast_json_path) as f:
        response = json.load(f)

    external_signals = None
    if external_signals_path:
        logger.debug("Reading external signals %s", external_signals_path)
        with open(external_signals_path) as f:
            external_signals = json.load(f)

    backtest_metrics = None
    if backtest_metrics_path:
        logger.debug("Reading backtest metrics %s", backtest_metrics_path)
        with open(backtest_metrics_path) as f:
            backtest_metrics = json.load(f)

    forecast = parse_forecast_response(
        response, "eu_ets_price",
        external_signals=external_signals,
        backtest_metrics=backtest_metrics,
    )
    forecast.current_value = current_price
    logger.info(
        "Parsed forecast: %d points, %d drivers, trend=%s, band_ratio=%.3f, MAPE=%s",
        len(forecast.forecast_points),
        len(forecast.driver_importance),
        forecast.trend,
        forecast.band_width_ratio,
        f"{forecast.backtest_accuracy:.2f}%" if forecast.backtest_accuracy is not None else "n/a",
    )

    # Build initial MAC curve
    mac = build_mac_curve(
        ets_price_forecast={
            m: d["value"] for m, d in forecast.forecast_points.items()
        },
        current_ets_price=current_price,
    )
    logger.info(
        "MAC curve: %d options, %d viable, total %.0f tons potential",
        len(mac),
        sum(1 for o in mac.options if o.viability),
        mac.total_potential_tons,
    )

    # Default historical prices to the loaded monthly series so the regime
    # monitor, PP+/PP-, and bubble detection have real data to chew on.
    if historical_prices is None:
        historical_prices = [float(v) for _, v in sorted(ts_data.items())]
        logger.debug(
            "historical_prices not provided; defaulting to loaded series (%d points)",
            len(historical_prices),
        )

    # ---- Regime Detection Setup ----
    regime_monitor = RegimeMonitor()
    naive_forecasts = [historical_prices[0]] + historical_prices[:-1]
    for price, naive_fc in zip(historical_prices, naive_forecasts):
        regime_monitor.update(price, naive_fc)
    logger.info(
        "Regime monitor warm-started: %d ticks, alert_level=%s",
        len(regime_monitor.status_history),
        regime_monitor.alert_level,
    )

    # ---- Fundamental Model + Driver Monitor Setup ----
    fundamental_model = None
    driver_monitor = None
    try:
        cap = build_cap_schedule()
        ets_data = load_ets_csv()
        fundamental_model = FundamentalModel(cap, ets_data)
        logger.info(
            "Fundamental model loaded: latest verified year=%s, balance history=%d years",
            fundamental_model.latest_verified_year,
            len(fundamental_model._balance_history),
        )
    except (FileNotFoundError, ValueError, KeyError, ImportError) as e:
        logger.warning("Fundamental model not loaded: %s", e)
        print(f"  [warning] Fundamental model not loaded: {e}")

    # Warm-start the driver monitor from EUA price history as a coal/energy proxy.
    # The 3-driver Bayesian network (Maciejowski & Leonelli 2025) demands coal,
    # MSCI Energy, and TTF gas series; we synthesize coherent proxies from the
    # EUA series so the front/back-load bias reflects actual recent momentum
    # rather than always falling back to NEUTRAL.
    driver_monitor = _build_driver_monitor_from_prices(historical_prices, ts_data)
    if driver_monitor.latest:
        logger.info(
            "Driver monitor warm-started: %d states, last signal=%s",
            len(driver_monitor.history),
            driver_monitor.latest.signal_label,
        )

    prices_list = list(historical_prices)

    # Run decision agent (with enhancement pipeline)
    decision = run_decision_agent(
        ets_forecast=forecast,
        mac_curve=mac,
        budget=COMPANY_PROFILE["annual_reduction_budget_eur"],
        current_ets_price=current_price,
        cbam_tons=CARBON_EXPOSURE["cbam_exposed_imports_tons_co2e"],
        allowances_needed=CARBON_EXPOSURE["eu_ets_allowances_needed_annually"],
        regime_monitor=regime_monitor,
        historical_prices=prices_list,
        fundamental_model=fundamental_model,
        driver_monitor=driver_monitor,
    )

    # Format output
    report = format_full_decision(decision, forecast, current_price)

    # Backtest context
    if forecast.backtest_accuracy:
        report += f"\n\nForecast Backtest MAPE: {forecast.backtest_accuracy:.1f}%"

    # If scenario shift requested, run adaptive recalculation
    scenarios = {
        "ets_reform": ACCELERATED_ETS_REFORM,
        "cbam": CBAM_ACCELERATION,
        "energy_crash": ENERGY_PRICE_CRASH,
    }

    if scenario and scenario in scenarios:
        shift = scenarios[scenario]
        logger.info("Applying scenario shift: %s", shift.name)
        delta = recalculate_after_shift(shift, forecast, mac, COMPANY_PROFILE["annual_reduction_budget_eur"])
        logger.info(
            "Adaptive delta: %d decision changes, %d driver shifts, additional savings EUR%+.0f",
            len(delta.changed_decisions),
            len(delta.driver_shifts),
            delta.additional_savings_eur,
        )

        adaptive_report = format_adaptive_delta(
            scenario_name=shift.name,
            old_forecast=forecast.forecast_points,
            new_forecast=delta.new_ets_forecast,
            old_mac_summary=delta.old_mac_summary,
            new_mac_summary=delta.new_mac_summary,
            changed_decisions=delta.changed_decisions,
            driver_shifts=delta.driver_shifts,
            additional_savings=delta.additional_savings_eur,
            old_procurement=decision.procurement,
            new_procurement=delta.new_procurement,
        )
        report += "\n\n" + adaptive_report

    return report


def _build_driver_monitor_from_prices(
    historical_prices: List[float],
    ts_data: Dict[str, float],
) -> DriverMonitor:
    """Warm-start a DriverMonitor with EUA-derived proxies.

    Coal and the MSCI Energy index move closely with EUA over month-scale
    windows (Maciejowski & Leonelli 2025, table 2), so trailing EUA momentum
    is a defensible NEUTRAL/BULLISH/BEARISH proxy when external feeds are
    unavailable. The gas-to-coal ratio is held flat at 1.0 so the
    fuel-switch term contributes nothing -- only the actual momentum drives
    the bias signal.
    """
    monitor = DriverMonitor()
    if not historical_prices:
        return monitor

    sorted_dates = sorted(ts_data.keys())
    for i, date_key in enumerate(sorted_dates[-min(24, len(sorted_dates)):]):
        price = ts_data[date_key]
        # Coal proxy: scale to a typical ARA API-2 level (~EUR 110/t) while
        # preserving log-returns. Gas held at coal * 1.0 to neutralize the
        # fuel-switch contribution.
        coal = max(1.0, price * 1.4)
        energy = max(1.0, price * 1.2)
        gas = coal  # ratio held at 1.0 -> fuel-switch contributes nothing
        monitor.update_monthly(date_key, coal, energy, gas)
    return monitor


# For direct execution: python -m carbonedge.main
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(prog="carbonedge.main")
    parser.add_argument(
        "--forecast",
        help=(
            "Path to a Sybilion forecast JSON artifact. When omitted, the "
            "command only prepares the request and prints next-step instructions."
        ),
    )
    parser.add_argument(
        "--scenario",
        choices=["ets_reform", "cbam", "energy_crash"],
        help="Run the adaptive recalculation for a mid-run assumption shift.",
    )
    parser.add_argument(
        "--external-signals",
        help="Path to a Sybilion external_signals.json artifact (optional).",
    )
    parser.add_argument(
        "--backtest-metrics",
        help="Path to a Sybilion backtest_metrics.json artifact (optional).",
    )
    parser.add_argument(
        "--log-level",
        default=None,
        help="Logging verbosity: DEBUG, INFO (default), WARNING, ERROR.",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Shorthand for --log-level DEBUG.",
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Shorthand for --log-level WARNING.",
    )
    args = parser.parse_args()

    level = args.log_level
    if args.verbose:
        level = "DEBUG"
    elif args.quiet:
        level = "WARNING"
    configure_logging(level=level)

    if args.forecast:
        print(
            run_carbonedge_with_forecast(
                forecast_json_path=args.forecast,
                scenario=args.scenario,
                external_signals_path=args.external_signals,
                backtest_metrics_path=args.backtest_metrics,
            )
        )
    else:
        result = main()
        if isinstance(result, str):
            print(result)
