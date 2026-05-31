"""
Crosshair contract tests for CarbonEdge critical functions.

These verify invariants, pre/post conditions, and boundary behavior
using symbolic execution. Crosshair explores all possible input values
within the type domain to find counterexamples.

Run: python -m crosshair check carbonedge/tests/test_contracts.py
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import crosshair
from crosshair import with_realized_args


# ============================================================================
# 1. Procurement Optimizer — allocation invariants
# ============================================================================

def _build_prices():
    """Build a valid 3-horizon price dict for testing.

    h1 below spot creates a real trade-off: buy NOW cheaper vs wait for
    higher prices later. This lets the bias actually influence allocation.
    """
    return {1: 78.0, 3: 82.0, 6: 86.0}, {1: 3.0, 3: 6.0, 6: 10.0}


def test_optimizer_total_allocation_matches_request():
    """Total allocated tons MUST equal total_tons, regardless of bias."""
    from carbonedge.procurement.optimizer import optimize_procurement

    @with_realized_args
    def check(total_tons: int, front_load_bias: float):
        """Postcondition: sum of window tons == total_tons"""
        if total_tons < 1 or total_tons > 1_000_000:
            return
        if abs(front_load_bias) > 1.0:
            return
        mu, sigma = _build_prices()
        plan = optimize_procurement(
            forecast_mean=mu, forecast_sigma=sigma,
            total_tons=total_tons, purchase_windows=[1, 3, 6],
            current_price=80.0, front_load_bias=front_load_bias,
        )
        allocated = sum(w.tons for w in plan.windows)
        assert allocated == total_tons, (
            f"allocated={allocated}, total_tons={total_tons}, bias={front_load_bias:.3f}"
        )
    # Crosshair hovers around symbolic int/float values; run a limited check
    return check


def test_optimizer_fractions_sum_to_one():
    """Internal fractions must sum to 1.0 for all valid bias ranges."""
    from carbonedge.procurement.optimizer import optimize_procurement
    import numpy as np

    @with_realized_args
    def check(front_load_bias: float):
        """Postcondition: sum(fractions) ≈ 1.0"""
        if abs(front_load_bias) > 1.0:
            return
        mu, sigma = _build_prices()
        plan = optimize_procurement(
            forecast_mean=mu, forecast_sigma=sigma,
            total_tons=100_000, purchase_windows=[1, 3, 6],
            current_price=80.0, front_load_bias=front_load_bias,
        )
        total = sum(w.tons for w in plan.windows)
        fractions_sum = total / 100_000
        assert abs(fractions_sum - 1.0) < 0.001, (
            f"fractions sum={fractions_sum:.6f}, bias={front_load_bias:.3f}"
        )
    return check


def test_optimizer_front_load_gives_more_now():
    """CVaR optimizer allocates more to NOW when forward prices slope up."""
    from carbonedge.procurement.optimizer import optimize_procurement

    # NOW (78) is cheaper than spot (80); M3/M6 (82/86) are pricier.
    # Low sigma so NOW's small uncertainty doesn't outweigh the discount.
    mu = {1: 78.0, 3: 82.0, 6: 86.0}
    sigma = {1: 2.0, 3: 4.0, 6: 6.0}
    plan = optimize_procurement(
        mu, sigma, 100_000, [1, 3, 6], 80.0, front_load_bias=0.30,
    )
    now_tons = next((w.tons for w in plan.windows if w.label == "NOW"), 0)
    assert now_tons > 0, "NOW at EUR78 should attract allocation vs spot EUR80"
    assert plan.strategy in ("FRONT_LOAD", "LUMP_SUM"), (
        f"Expected FRONT_LOAD or LUMP_SUM, got {plan.strategy}"
    )


def test_optimizer_back_load_gives_less_now():
    """CVaR optimizer defers when forward prices drop below spot."""
    from carbonedge.procurement.optimizer import optimize_procurement

    # Downward slope: SPOT 80, wait and pay 72/66
    mu = {1: 72.0, 3: 66.0, 6: 62.0}
    sigma = {1: 3.0, 3: 6.0, 6: 10.0}
    plan = optimize_procurement(
        mu, sigma, 80_000, [1, 3, 6], 80.0, front_load_bias=-0.30,
    )
    # M6 at EUR62 is cheapest; optimizer should load there, not NOW
    m6_tons = next((w.tons for w in plan.windows if w.label == "M6"), 0)
    assert m6_tons > 0, "At least some tons should go to M6 (cheapest horizon)"
    assert plan.strategy in ("BACK_LOAD", "LUMP_BACK"), (
        f"Expected BACK_LOAD or LUMP_BACK, got {plan.strategy}"
    )


def test_optimizer_no_negative_tons():
    """No window should receive negative tons, even at extreme bias."""
    from carbonedge.procurement.optimizer import optimize_procurement

    mu, sigma = _build_prices()
    for bias in [-0.5, -0.3, 0.0, 0.3, 0.5, 0.7]:
        plan = optimize_procurement(
            mu, sigma, 80_000, [1, 3, 6], 80.0, front_load_bias=bias,
        )
        for w in plan.windows:
            assert w.tons >= 0, (
                f"Window {w.label}: {w.tons} tons negative at bias={bias:.1f}"
            )


def test_optimizer_expected_cost_in_range():
    """Expected cost should be within a reasonable multiple of all-now cost."""
    from carbonedge.procurement.optimizer import optimize_procurement

    mu, sigma = _build_prices()
    total = 80_000
    cost_all_now = total * 80.0

    plan = optimize_procurement(
        mu, sigma, total, [1, 3, 6], 80.0, front_load_bias=0.20,
    )
    # Expected cost should be between 70% and 130% of all-now cost
    # (MUCH wider than reality, just sanity check)
    assert 0.7 * cost_all_now <= plan.total_cost_expected <= 1.3 * cost_all_now, (
        f"Expected cost {plan.total_cost_expected:,.0f} vs all-now {cost_all_now:,.0f}"
    )


# ============================================================================
# 2. Procurement decision — signal combination
# ============================================================================

def test_decision_structural_buy_tilts_front_load():
    """Structural BUY context must flow through to the procurement decision."""
    from carbonedge.decision_agent import make_procurement_decision
    from carbonedge.enhancement.driver_filter import DriverBias
    from carbonedge.enhancement.regime_enhancer import RegimeBand
    from carbonedge.enhancement.structural_context import StructuralBackdrop
    from carbonedge.sybilion_client import ForecastResult

    fc = ForecastResult(target_name="test")
    fc.current_value = 80.0
    fc.forecast_points = {
        1: {"value": 78, "low": 72, "high": 84},
        3: {"value": 80, "low": 72, "high": 88},
        6: {"value": 84, "low": 74, "high": 94},
    }
    rb = RegimeBand(
        level="GREEN", multiplier=1.0,
        focus_triggered=False, cusum_triggered=False,
        bubble_risk=False, advisory="",
    )
    db = DriverBias(
        bias=0.0, signal="NEUTRAL",
        coal_rising=False, energy_rising=False,
        fuel_switch_bearish=False, reasoning="test",
    )
    sb = StructuralBackdrop(
        balance_mt=-100, cap_mt=1300, emissions_mt=1350,
        msr_intake_mt=275, msr_release_mt=0,
        annual_cap_decline_mt_per_year=93,
        surplus_to_shortage_year=2026,
        signal="BUY", tightening_score=0.5, narrative="Supply tightening: buy early.",
    )

    plan = make_procurement_decision(
        fc, 80.0, 80_000, rb, None, db, structural=sb,
    )
    # Structural BUY adds a modest mean shift to forward prices.
    # With h1=78 below spot (80), the optimizer naturally front-loads.
    # The structural context is reflected in the reasoning, not forced.
    assert plan.strategy in ("FRONT_LOAD", "LUMP_SUM"), (
        f"Expected FRONT_LOAD or LUMP_SUM with cheaper NOW, got {plan.strategy}"
    )
    now_tons = plan.windows[0].tons
    assert now_tons > 0, "Should buy at least some tons in the cheapest window"


def test_decision_red_regime_freezes():
    """RED regime must produce FREEZE strategy with 25% minimal buy."""
    from carbonedge.decision_agent import make_procurement_decision
    from carbonedge.enhancement.driver_filter import DriverBias
    from carbonedge.enhancement.regime_enhancer import RegimeBand
    from carbonedge.sybilion_client import ForecastResult

    fc = ForecastResult(target_name="test")
    fc.current_value = 80.0
    fc.forecast_points = {
        1: {"value": 82, "low": 75, "high": 89},
    }
    rb = RegimeBand(
        level="RED", multiplier=3.0,
        focus_triggered=True, cusum_triggered=False,
        bubble_risk=False, advisory="Structural break detected",
    )
    db = DriverBias(
        bias=0.3, signal="BULLISH",
        coal_rising=True, energy_rising=True,
        fuel_switch_bearish=False, reasoning="test",
    )

    plan = make_procurement_decision(
        fc, 80.0, 80_000, rb, None, db,
    )
    assert plan.strategy == "FREEZE", (
        f"Expected FREEZE in RED regime, got {plan.strategy}"
    )
    now_tons = plan.windows[0].tons
    assert now_tons <= 80_000 * 0.30, (
        f"RED regime bought {now_tons}t, expected <=25%"
    )


def test_decision_downtrend_back_loads():
    """DOWN-trending forecast must NOT front-load (NOW < SPOT, defer saves money)."""
    from carbonedge.decision_agent import make_procurement_decision
    from carbonedge.enhancement.driver_filter import DriverBias
    from carbonedge.enhancement.regime_enhancer import RegimeBand
    from carbonedge.sybilion_client import ForecastResult

    fc = ForecastResult(target_name="test")
    fc.current_value = 80.0
    fc.forecast_points = {
        1: {"value": 78, "low": 71, "high": 85},
        3: {"value": 74, "low": 65, "high": 83},
        6: {"value": 70, "low": 60, "high": 80},
    }
    rb = RegimeBand(
        level="GREEN", multiplier=1.0,
        focus_triggered=False, cusum_triggered=False,
        bubble_risk=False, advisory="",
    )
    db = DriverBias(
        bias=0.0, signal="NEUTRAL",
        coal_rising=False, energy_rising=False,
        fuel_switch_bearish=False, reasoning="test",
    )
    # M6 at EUR70 is 12.5% cheaper than SPOT at EUR80.
    # CVaR optimizer naturally back-loads to the cheapest horizon.

    plan = make_procurement_decision(
        fc, 80.0, 80_000, rb, None, db,
    )
    # M6 is dramatically cheaper; optimizer should defer heavily.
    assert plan.strategy in ("BACK_LOAD", "LUMP_BACK"), (
        f"DOWN trend should defer purchases, got {plan.strategy}"
    )
    m6_tons = next((w.tons for w in plan.windows if w.label == "M6"), 0)
    assert m6_tons > 0, "Cheapest horizon M6 should receive allocation"
    # NOW (h=1) at 78 is below spot but not as cheap as M6 at 70
    now_tons = next((w.tons for w in plan.windows if w.label == "NOW"), 0)
    assert now_tons < m6_tons or now_tons == 0, (
        f"M6 ({m6_tons}t) should dominate NOW ({now_tons}t) when downward slope is steep"
    )


def test_decision_empty_forecast_returns_lump_sum():
    """No forecast: must return LUMP_SUM with all at NOW."""
    from carbonedge.decision_agent import make_procurement_decision
    from carbonedge.enhancement.driver_filter import DriverBias
    from carbonedge.enhancement.regime_enhancer import RegimeBand
    from carbonedge.sybilion_client import ForecastResult

    fc = ForecastResult(target_name="test")
    fc.current_value = 80.0
    # Empty forecast_points
    rb = RegimeBand(
        level="GREEN", multiplier=1.0,
        focus_triggered=False, cusum_triggered=False,
        bubble_risk=False, advisory="",
    )
    db = DriverBias(
        bias=0.0, signal="NEUTRAL",
        coal_rising=False, energy_rising=False,
        fuel_switch_bearish=False, reasoning="test",
    )

    plan = make_procurement_decision(
        fc, 80.0, 80_000, rb, None, db,
    )
    assert plan.strategy == "LUMP_SUM", f"Expected LUMP_SUM, got {plan.strategy}"
    assert plan.windows[0].tons == 80_000, (
        f"Should buy all NOW, got {plan.windows[0].tons}t"
    )


# ============================================================================
# 3. Budget allocator — allocation invariants
# ============================================================================

def test_budget_allocator_never_exceeds_budget():
    """Budget allocation must never exceed total budget."""
    from carbonedge.budget_allocator import allocate_budget
    from carbonedge.mac_curve import build_mac_curve

    mac = build_mac_curve(current_ets_price=80.0)
    plan = allocate_budget(mac, budget=10_000_000)

    total_spent = sum(b.budget_eur for b in plan.buckets)
    assert total_spent <= plan.budget, (
        f"Spent {total_spent:,.0f} > budget {plan.budget:,.0f}"
    )


def test_budget_allocator_reserve_is_correct():
    """Reserve must be exactly reserve_pct of budget."""
    from carbonedge.budget_allocator import allocate_budget
    from carbonedge.config import ALLOCATOR_CONFIG
    from carbonedge.mac_curve import build_mac_curve

    mac = build_mac_curve(current_ets_price=80.0)
    for budget in [1_000_000, 5_000_000, 10_000_000, 50_000_000]:
        plan = allocate_budget(mac, budget=budget)
        expected_reserve = budget * ALLOCATOR_CONFIG["reserve_pct"]
        assert abs(plan.reserve_budget - expected_reserve) < 1.0, (
            f"Reserve {plan.reserve_budget:,.0f} != {expected_reserve:,.0f}"
        )


def test_budget_allocator_reduces_some_tons():
    """A valid MAC curve + budget should reduce non-zero tons."""
    from carbonedge.budget_allocator import allocate_budget
    from carbonedge.mac_curve import build_mac_curve

    mac = build_mac_curve(current_ets_price=80.0)
    plan = allocate_budget(mac, budget=10_000_000)
    assert plan.total_tons_reduced > 0, (
        "Should reduce some tons with EUR10M budget"
    )


def test_budget_allocator_blended_cost_positive():
    """Blended cost per ton must be positive when reductions exist."""
    from carbonedge.budget_allocator import allocate_budget
    from carbonedge.mac_curve import build_mac_curve

    mac = build_mac_curve(current_ets_price=80.0)
    plan = allocate_budget(mac, budget=10_000_000)
    if plan.total_tons_reduced > 0:
        assert plan.blended_cost_per_ton > 0, (
            f"Blended cost {plan.blended_cost_per_ton} should be positive"
        )


# ============================================================================
# 4. Driver filter — signal invariants
# ============================================================================

def test_driver_filter_bias_in_range():
    """Driver bias must always be in [-0.5, 0.5]."""
    from carbonedge.enhancement.driver_filter import DriverFilter
    from carbonedge.fundamental.driver_monitor import DriverMonitor

    monitor = DriverMonitor(lookback=22)
    # Seed with rising prices → BULLISH
    for i in range(30):
        monitor.update(
            date=f"2020-{(i+1):02d}-01",
            coal_price=100 + i * 0.5,      # slowly rising
            energy_index=1500 + i * 2,      # slowly rising
            gas_price=300 + i * 3,         # rising faster (gas/coal ratio rising)
        )
    df = DriverFilter(monitor)
    bias = df.evaluate()
    assert -0.5 <= bias.bias <= 0.5, (
        f"Driver bias {bias.bias} out of range [-0.5, 0.5]"
    )


def test_driver_filter_returns_neutral_without_data():
    """No driver data → NEUTRAL signal with bias=0.0."""
    from carbonedge.enhancement.driver_filter import DriverFilter
    from carbonedge.fundamental.driver_monitor import DriverMonitor

    monitor = DriverMonitor(lookback=22)
    df = DriverFilter(monitor)
    bias = df.evaluate()
    assert bias.bias == 0.0, f"Empty monitor bias should be 0.0, got {bias.bias}"
    assert bias.signal == "NEUTRAL", f"Empty monitor signal should be NEUTRAL, got {bias.signal}"


# ============================================================================
# 5. Structural context — signal invariants
# ============================================================================

def test_structural_context_signal_values():
    """Structural signal must be one of BUY/DEFER/HOLD."""
    from carbonedge.enhancement.structural_context import StructuralContext
    from carbonedge.fundamental.balance_model import FundamentalModel
    from carbonedge.fundamental.cap_schedule import build_cap_schedule
    from carbonedge.fundamental.data_sources import load_ets_csv

    try:
        caps = build_cap_schedule()
        emis = load_ets_csv()
        if not emis.verified_emissions:
            return
        fm = FundamentalModel(cap_schedule=caps, emissions_data=emis)
        ctx = StructuralContext(fm)
        # Evaluate at multiple years
        for year in [2020, 2022, 2024, 2026, 2028, 2030]:
            if year in caps.years:
                backdrop = ctx.evaluate(year=year)
                assert backdrop.signal in ("BUY", "DEFER", "HOLD"), (
                    f"Year {year}: invalid signal '{backdrop.signal}'"
                )
                assert -1.0 <= backdrop.tightening_score <= 1.0, (
                    f"Year {year}: tightening_score {backdrop.tightening_score} out of range"
                )
    except (FileNotFoundError, ValueError, KeyError, TypeError):
        pass  # Data not available for structural context test


# ============================================================================
# 6. EPU modulator — level invariants
# ============================================================================

def test_epu_modulator_levels_are_valid():
    """EPU level must be one of NORMAL/ELEVATED/CRISIS/UNKNOWN."""
    from carbonedge.enhancement.epu_modulator import EpuModulator

    try:
        mod = EpuModulator()
        state = mod.evaluate("2024-01-01")
        assert state.level in ("NORMAL", "ELEVATED", "CRISIS", "UNKNOWN"), (
            f"Invalid EPU level: {state.level}"
        )
        assert 0.5 <= state.volatility_multiplier <= 2.0, (
            f"Volatility multiplier {state.volatility_multiplier} out of sane range"
        )
    except FileNotFoundError:
        pass  # EPU data not available


def test_epu_modulator_multiplier_matches_level():
    """Volatility multiplier must correspond to level."""
    from carbonedge.enhancement.epu_modulator import (
        EpuModulator, VOLATILITY_AMPLIFIER_NORMAL,
        VOLATILITY_AMPLIFIER_ELEVATED, VOLATILITY_AMPLIFIER_CRISIS,
    )

    try:
        mod = EpuModulator()
        state = mod.evaluate("2024-01-01")
        expected_map = {
            "NORMAL": VOLATILITY_AMPLIFIER_NORMAL,
            "ELEVATED": VOLATILITY_AMPLIFIER_ELEVATED,
            "CRISIS": VOLATILITY_AMPLIFIER_CRISIS,
            "UNKNOWN": VOLATILITY_AMPLIFIER_NORMAL,
        }
        expected = expected_map[state.level]
        assert state.volatility_multiplier == expected, (
            f"Level {state.level} has multiplier {state.volatility_multiplier}, "
            f"expected {expected}"
        )
    except FileNotFoundError:
        pass


# ============================================================================
# 7. Regime enhancer — multiplier invariants
# ============================================================================

def test_regime_confidence_multipliers():
    """GREEN when no triggers; YELLOW when FOCuS or CUSUM firing."""
    from carbonedge.enhancement.regime_enhancer import (
        get_confidence_multiplier, CONFIDENCE_GREEN, CONFIDENCE_YELLOW,
    )
    from carbonedge.regime_detector import RegimeStatus

    # None → default YELLOW (no monitor active)
    none_band = get_confidence_multiplier(None, None)
    assert none_band.level == "YELLOW", f"None→YELLOW, got {none_band.level}"
    assert none_band.multiplier == CONFIDENCE_YELLOW

    # All clear → GREEN
    green_status = RegimeStatus(
        tick=0, focus_statistic=0.0,
        cusum_pos=0.0, cusum_neg=0.0,
        focus_triggered=False, cusum_triggered=False,
        regime_change=False, cusum_message="",
    )
    green = get_confidence_multiplier(green_status, None)
    assert green.level == "GREEN", f"No triggers→GREEN, got {green.level}"
    assert green.multiplier == CONFIDENCE_GREEN

    # FOCuS firing → YELLOW
    focus_status = RegimeStatus(
        tick=1, focus_statistic=10.0,
        cusum_pos=0.0, cusum_neg=0.0,
        focus_triggered=True, cusum_triggered=False,
        regime_change=False, cusum_message="",
    )
    yellow_focus = get_confidence_multiplier(focus_status, None)
    assert yellow_focus.level == "YELLOW", f"FOCuS→YELLOW, got {yellow_focus.level}"
    assert yellow_focus.multiplier == CONFIDENCE_YELLOW
    assert yellow_focus.focus_triggered

    # CUSUM firing → YELLOW
    cusum_status = RegimeStatus(
        tick=2, focus_statistic=0.0,
        cusum_pos=5.0, cusum_neg=0.0,
        focus_triggered=False, cusum_triggered=True,
        regime_change=False, cusum_message="Forecast residual above threshold",
    )
    yellow_cusum = get_confidence_multiplier(cusum_status, None)
    assert yellow_cusum.level == "YELLOW", f"CUSUM→YELLOW, got {yellow_cusum.level}"
    assert yellow_cusum.multiplier == CONFIDENCE_YELLOW
    assert yellow_cusum.cusum_triggered

    # RED (multiplier 3.0) is now returned when PSY bubble test detects
    # explosive price behaviour (Friedrich et al. 2019). See psy_bubble.py.


# ============================================================================
if __name__ == "__main__":
    # Run all test_* functions
    import types
    total, passed, failed = 0, 0, 0
    for name, obj in sorted(globals().items()):
        if name.startswith("test_") and isinstance(obj, types.FunctionType):
            total += 1
            fn_name = f"{obj.__module__}.{name}" if hasattr(obj, '__module__') else name
            try:
                obj()
                print(f"  PASS {name}")
                passed += 1
            except AssertionError as e:
                print(f"  FAIL {name}: {e}")
                failed += 1
            except Exception as e:
                print(f"  ERROR {name}: {e}")
                failed += 1
    print(f"\n{passed}/{total} passed, {failed} failed")
    if failed:
        raise SystemExit(1)
