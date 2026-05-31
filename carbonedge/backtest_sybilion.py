"""
Backtest the CarbonEdge decision agent using the real Sybilion forecast
from forecast_job/. Does NOT call the Sybilion API.

Usage:
    python -m carbonedge.backtest_sybilion
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from .config import CARBON_EXPOSURE, COMPANY_PROFILE
from .decision_agent import (
    build_enhancement_pipeline,
    compute_layer_composite,
    make_procurement_decision,
)
from .enhancement.driver_filter import DriverBias
from .enhancement.regime_enhancer import RegimeBand
from .fundamental.balance_model import FundamentalModel
from .fundamental.cap_schedule import build_cap_schedule
from .fundamental.data_sources import load_ets_csv
from .fundamental.driver_monitor import DriverMonitor
from .mac_curve import build_mac_curve
from .regime_detector import RegimeMonitor
from .sybilion_client import ForecastResult, parse_forecast_response

logger = logging.getLogger(__name__)

FORECAST_JOB = Path(__file__).resolve().parents[1] / "forecast_job"


def load_sybilion_forecast() -> ForecastResult:
    """Parse the Sybilion forecast from forecast_job/ into a ForecastResult."""
    forecast_path = FORECAST_JOB / "forecast.json"
    signals_path = FORECAST_JOB / "external_signals.json"
    backtest_path = FORECAST_JOB / "backtest_metrics.json"

    with open(forecast_path) as f:
        forecast_raw = json.load(f)

    external_signals = None
    if signals_path.exists():
        with open(signals_path) as f:
            external_signals = json.load(f)

    backtest_metrics = None
    if backtest_path.exists():
        with open(backtest_path) as f:
            backtest_metrics = json.load(f)

    # The input.json has the actual timeseries; the last value is the current price
    input_path = FORECAST_JOB / "input.json"
    with open(input_path) as f:
        input_raw = json.load(f)
    ts = input_raw.get("timeseries", {})
    last_date = max(ts.keys())
    current_price = ts[last_date]

    forecast = parse_forecast_response(
        forecast_raw, "eu_ets_price",
        external_signals=external_signals,
        backtest_metrics=backtest_metrics,
        reference_date=datetime.strptime(last_date, "%Y-%m-%d"),
    )
    forecast.current_value = current_price
    return forecast


def load_historical_prices() -> Dict[str, float]:
    """Load the EUA monthly price timeseries from input.json."""
    input_path = FORECAST_JOB / "input.json"
    with open(input_path) as f:
        raw = json.load(f)
    return raw.get("timeseries", {})


def build_driver_monitor_from_prices(
    historical_prices: List[float],
    ts_data: Dict[str, float],
) -> DriverMonitor:
    """Warm-start a DriverMonitor from EUA price history."""
    monitor = DriverMonitor()
    if not historical_prices:
        return monitor
    sorted_dates = sorted(ts_data.keys())
    for date_key in sorted_dates[-min(24, len(sorted_dates)):]:
        price = ts_data[date_key]
        coal = max(1.0, price * 1.4)
        energy = max(1.0, price * 1.2)
        gas = coal
        monitor.update_monthly(date_key, coal, energy, gas)
    return monitor


def run_single_decision(
    forecast: ForecastResult,
    current_price: float,
    historical_prices: List[float],
    ts_data: Dict[str, float],
    evaluation_date: str = "",
) -> Dict:
    """Run the full decision pipeline at a single evaluation point."""
    allowances_needed = CARBON_EXPOSURE["eu_ets_allowances_needed_annually"]

    # Regime monitor
    regime_monitor = RegimeMonitor()
    naive_forecasts = [historical_prices[0]] + historical_prices[:-1]
    for price, naive_fc in zip(historical_prices, naive_forecasts):
        regime_monitor.update(price, naive_fc)

    # Fundamental model
    fundamental_model = None
    try:
        cap = build_cap_schedule()
        ets_data = load_ets_csv()
        fundamental_model = FundamentalModel(cap, ets_data)
    except (FileNotFoundError, ValueError, KeyError, ImportError) as e:
        logger.warning("Fundamental model not loaded: %s", e)

    # Driver monitor
    driver_monitor = build_driver_monitor_from_prices(historical_prices, ts_data)

    # Company risk profile
    risk_profile = None
    try:
        from .enhancement.company_risk import CompanyRiskLayer
        risk_layer = CompanyRiskLayer()
        risk_profile = risk_layer.get_profile("steel", "large")
    except Exception as e:
        logger.warning("Company risk layer not available: %s", e)

    # MAC curve
    mac = build_mac_curve(current_ets_price=current_price)

    # Enhancement pipeline
    regime, epu, driver_bias, structural, demand = build_enhancement_pipeline(
        forecast, current_price, regime_monitor, historical_prices,
        fundamental_model, driver_monitor, evaluation_date=evaluation_date,
    )

    # Composite score
    composite = compute_layer_composite(structural, driver_bias, epu, demand)

    # Procurement decision
    procurement = make_procurement_decision(
        forecast, current_price, allowances_needed,
        regime, epu, driver_bias, structural,
        demand=demand, risk_profile=risk_profile,
        historical_prices=historical_prices,
    )

    # Budget allocation
    from .budget_allocator import allocate_budget
    reduction_plan = allocate_budget(
        mac_curve=mac, budget=COMPANY_PROFILE["annual_reduction_budget_eur"],
        ets_price=current_price,
    )

    return {
        "evaluation_date": evaluation_date or datetime.now().strftime("%Y-%m-%d"),
        "current_price": current_price,
        "forecast_trend": forecast.trend,
        "band_width_ratio": forecast.band_width_ratio,
        "backtest_mape": forecast.backtest_accuracy,
        "forecast_points": {
            f"M{h}": {
                "value": fp["value"],
                "low": fp["low"],
                "high": fp["high"],
            }
            for h, fp in sorted(forecast.forecast_points.items())
        },
        "regime": {
            "level": regime.level,
            "multiplier": regime.multiplier,
            "focus_triggered": regime.focus_triggered,
            "cusum_triggered": regime.cusum_triggered,
            "bubble_risk": regime.bubble_risk,
            "advisory": regime.advisory,
        },
        "epu": {
            "level": epu.level if epu else "N/A",
            "value": epu.epu_value if epu else None,
            "z_score": epu.z_score if epu else None,
            "volatility_multiplier": epu.volatility_multiplier if epu else 1.0,
            "spike": epu.spike if epu else False,
        } if epu else None,
        "driver_bias": {
            "signal": driver_bias.signal,
            "bias": driver_bias.bias,
            "reasoning": driver_bias.reasoning,
        },
        "structural": {
            "signal": structural.signal if structural else "N/A",
            "tightening_score": structural.tightening_score if structural else None,
            "balance_mt": structural.balance_mt if structural else None,
            "narrative": structural.narrative if structural else "N/A",
        } if structural else None,
        "demand": {
            "demand_pressure": demand.demand_pressure if demand else None,
            "composite_index": demand.composite_index if demand else None,
            "reasoning": demand.reasoning if demand else "N/A",
        } if demand else None,
        "composite_score": composite,
        "procurement": {
            "strategy": procurement.strategy,
            "total_tons": procurement.total_tons,
            "total_cost_expected": procurement.total_cost_expected,
            "cost_if_all_now": procurement.cost_if_all_now,
            "expected_savings": procurement.expected_savings,
            "windows": [
                {
                    "label": w.label,
                    "horizon": w.horizon,
                    "tons": w.tons,
                    "expected_price": w.expected_price,
                    "cost_expected": w.cost_expected,
                }
                for w in procurement.windows
            ],
            "diagnostics": procurement.diagnostics or {},
        },
        "budget_allocation": {
            "total_tons_reduced": reduction_plan.total_tons_reduced,
            "blended_cost_per_ton": reduction_plan.blended_cost_per_ton,
            "reserve_budget": reduction_plan.reserve_budget,
        },
        "alerts": _build_alerts(regime, epu, driver_bias, structural, demand, procurement, reduction_plan),
    }


def _build_alerts(regime, epu, driver_bias, structural, demand, procurement, reduction_plan) -> List[str]:
    alerts = []
    if regime.level != "GREEN":
        alerts.append(f"[REGIME] {regime.level}: {regime.advisory}")
    if regime.focus_triggered:
        alerts.append("[FOCuS] Structural break detected in ETS price volatility.")
    if regime.cusum_triggered:
        alerts.append("[CUSUM] Forecast residuals show systematic bias.")
    if regime.bubble_risk:
        alerts.append("[BUBBLE] Explosive price behaviour detected.")
    if epu:
        epu_advisory = f"EPU: {epu.epu_value:.0f} ({epu.level}), z-score: {epu.z_score:+.1f}"
        if epu.spike:
            epu_advisory += " | SPIKE: >2 sigma above mean"
        alerts.append(f"[EPU] {epu_advisory}")
    alerts.append(f"[DRIVERS] {driver_bias.reasoning}")
    if structural:
        alerts.append(f"[STRUCTURAL] {structural.narrative}")
    if demand:
        alerts.append(f"[DEMAND] {demand.reasoning}")
    alerts.append(
        f"[PROCUREMENT] {procurement.strategy}: {procurement.total_tons:,} tons, "
        f"expected cost EUR{procurement.total_cost_expected:,.0f}, "
        f"savings EUR{procurement.expected_savings:+,.0f} vs spot."
    )
    alerts.append(
        f"[BUDGET] EUR{COMPANY_PROFILE['annual_reduction_budget_eur']:,.0f} allocated: "
        f"{reduction_plan.total_tons_reduced:,.0f} tons reduced "
        f"@ EUR{reduction_plan.blended_cost_per_ton:.0f}/ton. "
        f"EUR{reduction_plan.reserve_budget:,.0f} held in reserve."
    )
    return alerts


def print_decision_report(decision: Dict):
    """Pretty-print the decision report."""
    print("=" * 80)
    print("  CARBONEDGE -- DECISION AGENT BACKTEST (Sybilion Forecast)")
    print("=" * 80)
    print(f"  Evaluation date: {decision['evaluation_date']}")
    print(f"  Current spot price: EUR {decision['current_price']:.2f}/ton")
    print(f"  Forecast backtest MAPE: {decision['backtest_mape']:.2f}%" if decision['backtest_mape'] else "  Forecast backtest MAPE: n/a")
    print()

    # Forecast
    print("  --- SYBILION FORECAST (6-month) ---")
    print(f"  Trend: {decision['forecast_trend']} | Band width ratio: {decision['band_width_ratio']:.3f}")
    for label, fp in sorted(decision["forecast_points"].items()):
        print(f"    {label}: EUR {fp['value']:.2f}  [p10: {fp['low']:.2f} -- p90: {fp['high']:.2f}]")
    print()

    # Enhancement layers
    print("  --- ENHANCEMENT LAYERS ---")
    r = decision["regime"]
    print(f"  [1] Regime: {r['level']} | multiplier: {r['multiplier']:.2f}x | focus={r['focus_triggered']} cusum={r['cusum_triggered']} bubble={r['bubble_risk']}")
    print(f"      Advisory: {r['advisory']}")

    epu = decision["epu"]
    if epu:
        print(f"  [2] EPU: {epu['level']} | value={epu['value']:.0f} | z={epu['z_score']:+.2f} | vol_mult={epu['volatility_multiplier']:.2f}x | spike={epu['spike']}")
    else:
        print("  [2] EPU: N/A")

    d = decision["driver_bias"]
    print(f"  [3] Driver: {d['signal']} | bias={d['bias']:+.3f}")
    print(f"      {d['reasoning']}")

    s = decision["structural"]
    if s:
        print(f"  [4] Structural: {s['signal']} | tightening={s['tightening_score']:+.3f} | balance={s['balance_mt']:+.0f} Mt")
        print(f"      {s['narrative']}")
    else:
        print("  [4] Structural: N/A")

    dm = decision["demand"]
    if dm:
        print(f"  [5] Demand: pressure={dm['demand_pressure']:+.3f} | index={dm['composite_index']:.3f}")
        print(f"      {dm['reasoning']}")
    else:
        print("  [5] Demand: N/A")

    print(f"  [~] Composite score: {decision['composite_score']:+.3f}")
    print()

    # Procurement plan
    p = decision["procurement"]
    print("  --- PROCUREMENT PLAN ---")
    print(f"  Strategy: {p['strategy']}")
    print(f"  Total tons: {p['total_tons']:,}")
    print(f"  Cost if all at spot: EUR {p['cost_if_all_now']:,.0f}")
    print(f"  Expected cost:       EUR {p['total_cost_expected']:,.0f}")
    print(f"  Expected savings:    EUR {p['expected_savings']:+,.0f}")
    print()
    print(f"  {'Window':<10} {'Horizon':>8} {'Tons':>8} {'Price EUR':>10} {'Cost EUR':>14}")
    print(f"  {'-'*52}")
    for w in p["windows"]:
        print(f"  {w['label']:<10} M{w['horizon']:>7} {w['tons']:>8,} EUR {w['expected_price']:>8.2f} EUR {w['cost_expected']:>12,.0f}")
    print()

    # Diagnostics
    diag = p.get("diagnostics", {})
    if diag:
        print("  --- OPTIMIZER DIAGNOSTICS ---")
        print(f"  Mean shift: {diag.get('total_mean_shift', 0)*100:+.1f}%")
        print(f"    driver_shift:   {diag.get('driver_shift', 0)*100:+.2f}%")
        print(f"    structural_shift: {diag.get('structural_shift', 0)*100:+.2f}%")
        print(f"    demand_shift:   {diag.get('demand_shift', 0)*100:+.2f}%")
        print(f"  Trend guard active: {diag.get('trend_guard_active', False)}")
        if diag.get('trend_log_return') is not None:
            print(f"  Trailing 6m log-return: {diag['trend_log_return']*100:+.2f}%")
        print(f"  CVaR risk lambda: {diag.get('risk_lambda', 0.0):.3f}")
        print(f"  Constraints: min_spot={diag.get('min_spot', 0):.2f} max_spot={diag.get('max_spot', 1):.2f} max_back={diag.get('max_back', 1):.2f} max_single={diag.get('max_single', 1):.2f}")
        if diag.get("constraint_reasons"):
            for reason in diag["constraint_reasons"]:
                print(f"    -> {reason}")
        print()

    # Budget allocation
    b = decision["budget_allocation"]
    print("  --- BUDGET ALLOCATION (Reduction) ---")
    print(f"  Tons reduced: {b['total_tons_reduced']:,.0f}")
    print(f"  Blended cost: EUR {b['blended_cost_per_ton']:.0f}/ton")
    print(f"  Reserve: EUR {b['reserve_budget']:,.0f}")
    print()

    # Alerts
    print("  --- ALERTS ---")
    for alert in decision["alerts"]:
        print(f"  {alert}")
    print()
    print("=" * 80)


def run_rolling_backtest(ts_data: Dict[str, float], forecast: ForecastResult, current_price: float):
    """
    Walk-forward backtest using the Sybilion forecast structure.

    For each evaluation point, we build a forecast from historical data
    (calibrated to the Sybilion band structure), run the decision agent,
    and compare realized cost vs spot baseline.

    This uses the existing backtest.run_backtest infrastructure but plugs
    in the Sybilion-calibrated forecast.
    """
    from .backtest import (
        BacktestResult, BacktestWindow, DecisionTrace,
        _build_regime_monitor, _determine_trend,
        _realized_prices_by_horizon, _realized_cost_for_plan,
        format_backtest_report, format_trace_report,
        BACKTEST_WINDOW_MONTHS, BACKTEST_STEP_MONTHS, BACKTEST_MIN_WINDOWS,
    )
    from .forecast_baselines import (
        baseline_cost_spot, baseline_cost_equal_thirds,
        baseline_cost_random_walk, baseline_cost_mean_reversion,
        baseline_cost_always_horizon_6, make_random_walk_forecast,
    )

    sorted_dates = sorted(ts_data.keys())
    allowances_needed = CARBON_EXPOSURE["eu_ets_allowances_needed_annually"]
    warmup = BACKTEST_WINDOW_MONTHS
    step = BACKTEST_STEP_MONTHS
    min_w = BACKTEST_MIN_WINDOWS

    if len(sorted_dates) < warmup + min_w:
        print(f"  Not enough data: need {warmup + min_w} months, have {len(sorted_dates)}")
        return None

    eval_indices = list(range(warmup, len(sorted_dates) - 1, step))
    print(f"\n  Rolling backtest: {len(eval_indices)} windows (warmup={warmup}, step={step})")

    # Extract Sybilion band calibration
    syb_points = forecast.forecast_points  # {1: {value, low, high}, 3: ..., 6: ...}
    if not syb_points:
        print("  No Sybilion forecast points for calibration")
        return None

    # Calibrate band widening from Sybilion's actual quantiles
    syb_bands = {}
    for h, fp in syb_points.items():
        syb_bands[h] = (fp["high"] - fp["low"]) / fp["value"] if fp["value"] > 0 else 0.1

    horizons = [1, 3, 6]
    rng = np.random.default_rng(42)

    result = BacktestResult(forecast_mode="sybilion_calibrated", step_months=step)

    for window_num, eval_idx in enumerate(eval_indices, 1):
        eval_date = sorted_dates[eval_idx]
        spot_price = ts_data[eval_date]
        hist_start = max(0, eval_idx - warmup)
        hist_prices = [ts_data[d] for d in sorted_dates[:eval_idx + 1]]
        trend = _determine_trend(hist_prices)
        regime_monitor = _build_regime_monitor([ts_data[d] for d in sorted_dates[hist_start:eval_idx + 1]])

        # Build Sybilion-calibrated forecast for this window
        fc_result = ForecastResult(target_name=f"sybilion_calibrated_{eval_date}")
        fc_result.current_value = spot_price

        # Scale Sybilion's forecast structure to current spot
        # Sybilion forecast was at ~75.6 EUR; scale bands proportionally
        syb_spot = current_price  # ~79.59
        scale = spot_price / syb_spot if syb_spot > 0 else 1.0

        for h in horizons:
            if h not in syb_points:
                continue
            syb = syb_points[h]
            scaled_value = syb["value"] * scale
            # Add calibrated noise (MAPE-level)
            mape = forecast.backtest_accuracy / 100.0 if forecast.backtest_accuracy else 0.04
            noise = rng.normal(0, scaled_value * mape)
            fc_value = scaled_value + noise

            scaled_low = syb["low"] * scale + rng.normal(0, scaled_value * mape * 0.5)
            scaled_high = syb["high"] * scale + rng.normal(0, scaled_value * mape * 0.5)

            fc_result.forecast_points[h] = {
                "value": round(fc_value, 2),
                "low": round(scaled_low, 2),
                "high": round(scaled_high, 2),
            }

        fc_result.backtest_accuracy = forecast.backtest_accuracy
        fc_result.driver_importance = forecast.driver_importance

        # MAC curve
        mac = build_mac_curve(current_ets_price=spot_price)

        # Driver monitor
        window_prices = {d: ts_data[d] for d in sorted_dates[:eval_idx + 1]}
        window_dates = sorted_dates[:eval_idx + 1]
        from .backtest import _seed_driver_monitor
        window_driver = _seed_driver_monitor(window_prices, window_dates)

        # Run decision agent
        try:
            decision = run_decision_agent(
                ets_forecast=fc_result,
                mac_curve=mac,
                budget=COMPANY_PROFILE["annual_reduction_budget_eur"],
                current_ets_price=spot_price,
                allowances_needed=allowances_needed,
                regime_monitor=regime_monitor,
                historical_prices=hist_prices,
                fundamental_model=None,
                driver_monitor=window_driver,
                evaluation_date=eval_date,
            )
        except Exception as exc:
            import warnings
            warnings.warn(f"Backtest window {eval_date} failed: {exc}")
            logger.exception("Backtest window %s failed", eval_date)
            continue

        procurement = decision.procurement

        # Realized costs
        realized_by_h = _realized_prices_by_horizon(sorted_dates, ts_data, eval_idx, horizons)
        realized_agent = _realized_cost_for_plan(procurement, spot_price, realized_by_h)
        realized_spot = baseline_cost_spot(spot_price, allowances_needed)
        realized_equal_thirds = baseline_cost_equal_thirds(realized_by_h, allowances_needed, horizons=horizons)

        past_prices_for_rw = [ts_data[d] for d in sorted_dates[:eval_idx + 1]]
        realized_random_walk = baseline_cost_random_walk(
            past_prices_for_rw, spot_price, realized_by_h, allowances_needed, horizons,
        )
        realized_mr = baseline_cost_mean_reversion(
            past_prices_for_rw, spot_price, realized_by_h, allowances_needed, horizons,
        )
        realized_always_6 = baseline_cost_always_horizon_6(realized_by_h, allowances_needed)

        savings_spot = realized_spot - realized_agent
        savings_equal_thirds = realized_equal_thirds - realized_agent if realized_equal_thirds is not None else None
        savings_rw = realized_random_walk - realized_agent if realized_random_walk is not None else None
        savings_mr = realized_mr - realized_agent if realized_mr is not None else None
        savings_a6 = realized_always_6 - realized_agent if realized_always_6 is not None else None

        # Trace
        diag = procurement.diagnostics or {}
        alloc_breakdown = {}
        for w in procurement.windows:
            key = "SPOT" if w.label == "SPOT" else f"h{w.horizon}"
            alloc_breakdown[key] = alloc_breakdown.get(key, 0) + int(w.tons)

        trace = DecisionTrace(
            eval_date=eval_date, spot_price=float(spot_price),
            trailing_6mo_log_return=diag.get("trend_log_return"),
            trend_guard_active=bool(diag.get("trend_guard_active", False)),
            regime_level=decision.regime.level,
            regime_multiplier=decision.regime.multiplier,
            epu_level=decision.epu.level if decision.epu else "N/A",
            epu_value=decision.epu.epu_value if decision.epu else float("nan"),
            epu_spike=bool(decision.epu.spike) if decision.epu else False,
            epu_volatility_multiplier=decision.epu.volatility_multiplier if decision.epu else 1.0,
            driver_signal=decision.driver_bias.signal,
            driver_bias=decision.driver_bias.bias,
            structural_signal=decision.structural.signal if decision.structural else "N/A",
            structural_tightening_score=decision.structural.tightening_score if decision.structural else float("nan"),
            structural_inflection_year=decision.structural.surplus_to_shortage_year if decision.structural else 0,
            demand_pressure=decision.demand.demand_pressure if decision.demand else float("nan"),
            driver_shift=float(diag.get("driver_shift", 0.0)),
            structural_shift=float(diag.get("structural_shift", 0.0)),
            demand_shift=float(diag.get("demand_shift", 0.0)),
            total_mean_shift=float(diag.get("total_mean_shift", 0.0)),
            min_spot=float(diag.get("min_spot", 0.0)),
            max_spot=float(diag.get("max_spot", 1.0)),
            max_back=float(diag.get("max_back", 1.0)),
            max_single=float(diag.get("max_single", 1.0)),
            constraint_reasons=list(diag.get("constraint_reasons", [])),
            composite_score=float(diag.get("composite_score", 0.0)),
            strategy=procurement.strategy,
            allocation=alloc_breakdown,
        )

        window = BacktestWindow(
            evaluation_date=eval_date, spot_price=spot_price,
            allowances_needed=allowances_needed,
            procurement_strategy=procurement.strategy,
            total_cost_expected=procurement.total_cost_expected,
            realized_cost_agent=realized_agent,
            realized_cost_spot=realized_spot,
            realized_cost_equal_thirds=realized_equal_thirds,
            realized_cost_random_walk=realized_random_walk,
            realized_cost_mean_reversion=realized_mr,
            realized_cost_always_6=realized_always_6,
            savings_vs_spot=savings_spot,
            savings_vs_equal_thirds=savings_equal_thirds,
            savings_vs_random_walk=savings_rw,
            savings_vs_mean_reversion=savings_mr,
            savings_vs_always_6=savings_a6,
            regime_level=decision.regime.level,
            epu_level=decision.epu.level if decision.epu else "N/A",
            epu_value=decision.epu.epu_value if decision.epu else float("nan"),
            forecast_months=len(fc_result.forecast_points),
            band_width_ratio=fc_result.band_width_ratio,
            windows_detail=[
                {"label": w.label, "tons": w.tons, "price": w.expected_price}
                for w in procurement.windows
            ],
            trace=trace,
        )
        result.windows.append(window)

    # Aggregate
    result.total_windows = len(result.windows)
    if result.total_windows == 0:
        print("  No windows survived")
        return result

    result.windows_won = sum(1 for w in result.windows if w.savings_vs_spot > 0)
    result.windows_lost = sum(1 for w in result.windows if w.savings_vs_spot < 0)
    result.win_rate = result.windows_won / result.total_windows

    savings_list = [w.savings_vs_spot for w in result.windows]
    result.total_savings_eur = sum(savings_list)
    result.avg_savings_eur = result.total_savings_eur / result.total_windows
    result.max_savings_eur = max(savings_list)
    result.max_loss_eur = min(savings_list)

    for w in result.windows:
        result.strategy_counts[w.procurement_strategy] = result.strategy_counts.get(w.procurement_strategy, 0) + 1
        result.regime_breakdown[w.regime_level] = result.regime_breakdown.get(w.regime_level, 0) + 1

    # Statistical tests
    from .backtest import _paired_stats
    agent_costs = [w.realized_cost_agent for w in result.windows]
    spot_costs = [w.realized_cost_spot for w in result.windows]
    result.stats_vs_spot = _paired_stats(agent_costs, spot_costs, "buy_all_at_spot")

    equal_thirds_pairs = [
        (w.realized_cost_agent, w.realized_cost_equal_thirds)
        for w in result.windows if w.realized_cost_equal_thirds is not None
    ]
    if equal_thirds_pairs:
        result.stats_vs_equal_thirds = _paired_stats(
            [p[0] for p in equal_thirds_pairs], [p[1] for p in equal_thirds_pairs], "equal_thirds_1_3_6"
        )

    rw_pairs = [
        (w.realized_cost_agent, w.realized_cost_random_walk)
        for w in result.windows if w.realized_cost_random_walk is not None
    ]
    if rw_pairs:
        result.stats_vs_random_walk = _paired_stats(
            [p[0] for p in rw_pairs], [p[1] for p in rw_pairs], "random_walk_forecast"
        )

    mr_pairs = [
        (w.realized_cost_agent, w.realized_cost_mean_reversion)
        for w in result.windows if w.realized_cost_mean_reversion is not None
    ]
    if mr_pairs:
        result.stats_vs_mean_reversion = _paired_stats(
            [p[0] for p in mr_pairs], [p[1] for p in mr_pairs], "mean_reversion_vs_MA"
        )

    a6_pairs = [
        (w.realized_cost_agent, w.realized_cost_always_6)
        for w in result.windows if w.realized_cost_always_6 is not None
    ]
    if a6_pairs:
        result.stats_vs_always_6 = _paired_stats(
            [p[0] for p in a6_pairs], [p[1] for p in a6_pairs], "always_horizon_6"
        )

    return result


if __name__ == "__main__":
    configure_logging = None
    try:
        from .logging_setup import configure_logging as _cl
        configure_logging = _cl
    except ImportError:
        pass

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["single", "rolling", "both"], default="both",
                        help="Run single Sybilion forecast decision, rolling backtest, or both")
    parser.add_argument("--log-level", default="WARNING")
    args = parser.parse_args()

    if configure_logging:
        configure_logging(level=args.log_level)
    else:
        logging.basicConfig(level=getattr(logging, args.log_level, logging.WARNING))

    # Load data
    ts_data = load_historical_prices()
    sorted_dates = sorted(ts_data.keys())
    last_date = max(sorted_dates)
    current_price = ts_data[last_date]
    historical_prices = [ts_data[d] for d in sorted_dates]

    # Load Sybilion forecast
    forecast = load_sybilion_forecast()

    print(f"\n  Data: {len(ts_data)} monthly EUA prices ({sorted_dates[0]} -> {last_date})")
    print(f"  Current spot: EUR {current_price:.2f}/ton ({last_date})")
    print(f"  Sybilion forecast: {len(forecast.forecast_points)} points, trend={forecast.trend}")
    print(f"  Sybilion backtest MAPE: {forecast.backtest_accuracy:.2f}%" if forecast.backtest_accuracy else "  Sybilion backtest MAPE: n/a")
    print(f"  Band width ratio: {forecast.band_width_ratio:.3f}")

    if args.mode in ("single", "both"):
        print("\n" + "=" * 80)
        print("  PART 1: Single Decision with Sybilion Forecast")
        print("=" * 80)
        decision = run_single_decision(
            forecast, current_price, historical_prices, ts_data,
            evaluation_date=last_date,
        )
        print_decision_report(decision)

        # Save to file
        out_path = FORECAST_JOB / "decision_output.json"
        with open(out_path, "w") as f:
            json.dump(decision, f, indent=2, default=str)
        print(f"  Decision saved to {out_path}")

    if args.mode in ("rolling", "both"):
        print("\n" + "=" * 80)
        print("  PART 2: Rolling Backtest (Sybilion-Calibrated)")
        print("=" * 80)
        bt_result = run_rolling_backtest(ts_data, forecast, current_price)
        if bt_result:
            report = format_backtest_report(bt_result, ts_data)
            print(report)

            print()
            trace_report = format_trace_report(bt_result)
            print(trace_report)

            # Save backtest
            bt_path = FORECAST_JOB / "backtest_result.json"
            bt_serializable = {
                "total_windows": bt_result.total_windows,
                "forecast_mode": bt_result.forecast_mode,
                "step_months": bt_result.step_months,
                "windows_won": bt_result.windows_won,
                "windows_lost": bt_result.windows_lost,
                "win_rate": bt_result.win_rate,
                "total_savings_eur": bt_result.total_savings_eur,
                "avg_savings_eur": bt_result.avg_savings_eur,
                "max_savings_eur": bt_result.max_savings_eur,
                "max_loss_eur": bt_result.max_loss_eur,
                "strategy_counts": bt_result.strategy_counts,
                "regime_breakdown": bt_result.regime_breakdown,
                "windows": [
                    {
                        "evaluation_date": w.evaluation_date,
                        "spot_price": w.spot_price,
                        "procurement_strategy": w.procurement_strategy,
                        "realized_cost_agent": w.realized_cost_agent,
                        "realized_cost_spot": w.realized_cost_spot,
                        "savings_vs_spot": w.savings_vs_spot,
                        "savings_vs_equal_thirds": w.savings_vs_equal_thirds,
                        "savings_vs_random_walk": w.savings_vs_random_walk,
                        "savings_vs_mean_reversion": w.savings_vs_mean_reversion,
                        "savings_vs_always_6": w.savings_vs_always_6,
                        "regime_level": w.regime_level,
                        "windows_detail": w.windows_detail,
                    }
                    for w in bt_result.windows
                ],
            }
            with open(bt_path, "w") as f:
                json.dump(bt_serializable, f, indent=2)
            print(f"\n  Backtest saved to {bt_path}")
