"""
Minimal Crosshair symbolic execution tests for CarbonEdge core functions.

Crosshair verifies postconditions for ALL possible input values within
the type domain, finding counterexamples that regular unit tests miss.

Run: python -m crosshair check zero_one_hackathon.carbonedge.tests.test_crosshair
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))


# ---------------------------------------------------------------------------
# 1. Optimizer: fractions sum-to-one invariant
# ---------------------------------------------------------------------------
def _fractions_sum_to_one(total_tons: int, bias: float) -> bool:
    """Postcondition: allocated tons == total_tons for all bias in [-0.5, 1.0]"""
    from carbonedge.procurement.optimizer import optimize_procurement
    if total_tons <= 0 or total_tons > 500_000:
        return True  # precondition: skip degenerate inputs
    if bias < -1.0 or bias > 1.0:
        return True
    mu = {1: 80.0, 3: 82.0, 6: 85.0}
    sigma = {1: 5.0, 3: 8.0, 6: 12.0}
    plan = optimize_procurement(mu, sigma, total_tons, [1, 3, 6], 80.0,
                                front_load_bias=bias)
    allocated = sum(w.tons for w in plan.windows)
    return allocated == total_tons


# ---------------------------------------------------------------------------
# 2. Optimizer: positive bias → NOW > 33%
# ---------------------------------------------------------------------------
def _positive_bias_front_loads(total_tons: int, bias: float) -> bool:
    """Postcondition: positive bias allocates more to NOW than equal third"""
    from carbonedge.procurement.optimizer import optimize_procurement
    if total_tons < 3000 or total_tons > 500_000:
        return True
    if bias <= 0.0 or bias > 0.8:
        return True
    mu = {1: 80.0, 3: 82.0, 6: 85.0}
    sigma = {1: 5.0, 3: 8.0, 6: 12.0}
    plan = optimize_procurement(mu, sigma, total_tons, [1, 3, 6], 80.0,
                                front_load_bias=bias)
    now_fraction = plan.windows[0].tons / total_tons
    return now_fraction > 1.0 / len(plan.windows)  # must exceed equal fraction


# ---------------------------------------------------------------------------
# 3. Decision: RED regime always FREEZE
# ---------------------------------------------------------------------------
def _red_regime_always_freezes(total_tons: int) -> bool:
    """Postcondition: RED regime produces FREEZE with <= 25% bundle"""
    from carbonedge.decision_agent import make_procurement_decision
    from carbonedge.enhancement.driver_filter import DriverBias
    from carbonedge.enhancement.regime_enhancer import RegimeBand
    from carbonedge.sybilion_client import ForecastResult
    if total_tons < 1 or total_tons > 500_000:
        return True
    fc = ForecastResult(target_name="test")
    fc.current_value = 80.0
    fc.forecast_points = {1: {"value": 82, "low": 75, "high": 89}}
    rb = RegimeBand(
        level="RED", multiplier=3.0,
        focus_triggered=True, cusum_triggered=False,
        bubble_risk=False, advisory="test",
    )
    db = DriverBias(
        bias=0.0, signal="NEUTRAL",
        coal_rising=False, energy_rising=False,
        fuel_switch_bearish=False, reasoning="test",
    )
    plan = make_procurement_decision(fc, 80.0, total_tons, rb, None, db)
    return plan.strategy == "FREEZE" and plan.windows[0].tons <= max(total_tons // 4, 1)


# ---------------------------------------------------------------------------
# 4. Allocation: budget never exceeded
# ---------------------------------------------------------------------------
def _budget_never_exceeded(budget: int) -> bool:
    """Postcondition: total allocated <= budget (including reserve)"""
    from carbonedge.budget_allocator import allocate_budget
    from carbonedge.mac_curve import build_mac_curve
    if budget <= 0 or budget > 100_000_000:
        return True
    mac = build_mac_curve(current_ets_price=80.0)
    plan = allocate_budget(mac, budget=budget)
    spent = sum(b.budget_eur for b in plan.buckets)
    return spent <= budget


# ---------------------------------------------------------------------------
# 5. Driver filter: bias always in range [-0.5, 0.5]
# ---------------------------------------------------------------------------
def _driver_bias_always_in_range(
    coal_monthly_return: float, energy_monthly_return: float, gas_ratio: float
) -> bool:
    """Postcondition: driver bias clamped to [-0.5, 0.5]"""
    from carbonedge.enhancement.driver_filter import DriverFilter, BIAS_FRONT_LOAD, BIAS_BACK_LOAD
    from carbonedge.fundamental.driver_monitor import DriverMonitor, DriverState
    # Clamp inputs to realistic ranges for symbolic exploration
    if abs(coal_monthly_return) > 2.0 or abs(energy_monthly_return) > 2.0:
        return True
    if gas_ratio <= 0 or gas_ratio > 20:
        return True
    monitor = DriverMonitor(lookback=22)
    # Seed with enough history to compute a return
    for i in range(24):
        monitor.update(
            date=f"2020-{i+1:02d}-01",
            coal_price=100.0, energy_index=1500.0, gas_price=300.0,
        )
    # Now add the test point
    coal_price = 100 * (1 + coal_monthly_return)
    energy_idx = 1500 * (1 + energy_monthly_return)
    gas_price = coal_price * gas_ratio
    state = monitor.update(
        date="2025-01-01", coal_price=coal_price,
        energy_index=energy_idx, gas_price=gas_price,
    )
    df = DriverFilter(monitor)
    result = df.evaluate()
    return -0.5 <= result.bias <= 0.5


# ---------------------------------------------------------------------------
# Run with crosshair: python -m crosshair check <this_file>
# For quick pytest-style check: python <this_file>
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    total, passed, failed = 0, 0, 0

    # Manually sample across the input space
    test_cases = {
        _fractions_sum_to_one: [(t, b) for t in [10, 100, 1000, 10000, 80000, 100000]
                               for b in [-0.5, -0.3, -0.15, 0.0, 0.15, 0.20, 0.30, 0.50, 0.7]],
        _positive_bias_front_loads: [(t, b) for t in [10000, 80000, 100000]
                                      for b in [0.15, 0.20, 0.30, 0.50, 0.7]],
        _red_regime_always_freezes: [(t,) for t in [10, 1000, 80000, 100000]],
        _budget_never_exceeded: [(b,) for b in [0, 1000, 100000, 1000000, 10000000]],
        _driver_bias_always_in_range: [
            (0.05, 0.05, 3.0), (-0.05, -0.05, 3.0), (0.01, 0.01, 6.0),
            (-0.01, -0.01, 0.4), (0.20, -0.10, 3.0), (0.0, 0.0, 3.0),
        ],
    }
    for fn, cases in test_cases.items():
        total += 1
        try:
            for args in cases:
                assert fn(*args), f"{fn.__name__}{args} returned False"
            print(f"  PASS {fn.__name__} ({len(cases)} combos)")
            passed += 1
        except Exception as e:
            print(f"  FAIL {fn.__name__}: {e}")
            failed += 1

    print(f"\n{passed}/{total} passed, {failed} failed")
