"""
Core Supply-Demand Balance Model.

Implements the fundamental direction model from:
  Bastianin, Mirto, Qin, Rossini (2024) — "What drives the European carbon market?
  Macroeconomic factors and forecasts." arXiv:2402.04828

The core insight (Bastianin et al., 2024, §1-2): verified emissions and EUA
prices are driven by three forces — (i) regulatory supply (cap + MSR),
(ii) economic activity (business cycle), (iii) transition demand (renewables).
These can be captured with a simple supply-demand balance.

§5.3 Market Monitoring Tools (Bastianin et al. 2024, eq. 7-8):
  DPI(t)  = Ems_hat(t+12) - Ems_hat(t+1)         (Demand Pressure Index)
  PP+(t)  = (1/12) \u03a3_{h=1}^{12} I[R_hat_{t+h|t} > max(R_t ... R_{t-11})]
  PP-(t)  = (1/12) \u03a3_{h=1}^{12} I[R_hat_{t+h|t} < min(R_t ... R_{t-11})]
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np

from .cap_schedule import CapSchedule, build_cap_schedule
from .data_sources import EtsData, get_annual_emissions
from .msr_model import MSRModel, _M

logger = logging.getLogger(__name__)

# TNAC end of 2024 from EC C/2025/3180 (May 2025 communication)
TNAC_2024 = 1_148_049_585
# MSR holdings end of 2024 from EC C/2025/3180
MSR_HOLDINGS_2024 = 1_895_500_000

# Configurable thresholds (heuristics from paper studies)
SENSITIVITY_SIGMA_MT = 50.0       # balance range for BUY/HOLD/DEFER boundary
PP_DOMINANCE_THRESHOLD = 0.2      # PP+ - PP- gap for UPWARD/DOWNWARD
DPI_TIGHTENING_MT = 20.0          # DPI threshold for TIGHTENING
DPI_LOOSENING_MT = -20.0          # DPI threshold for LOOSENING
MIN_SAMPLES_FOR_STD = 3           # minimum balance years to compute std dev
DATA_COMPLETENESS_RATIO = 0.70    # most-recent-year / penultimate-year must be > this


@dataclass
class PricePressure:
    """
    Bastianin et al. (2024), eq. 7-8.

    PP⁺: fraction of forecast horizons where predicted price exceeds 12-month max.
    PP⁻: fraction where predicted price falls below 12-month min.
    """
    pp_plus: float           # 0.0 to 1.0, upward price pressure
    pp_minus: float          # 0.0 to 1.0, downward price pressure
    max_12m: float           # 12-month historical max
    min_12m: float           # 12-month historical min
    forecast_points: List[float]  # forecast values across horizons 1-12

    @property
    def dominant(self) -> str:
        """Which pressure dominates?"""
        gap = self.pp_plus - self.pp_minus
        if gap > PP_DOMINANCE_THRESHOLD:
            return "UPWARD"
        if gap < -PP_DOMINANCE_THRESHOLD:
            return "DOWNWARD"
        return "BALANCED"


@dataclass
class DemandPressure:
    """
    Bastianin et al. (2024), §5.3:
    DPI = difference between 12-month and 1-month ahead verified emission forecasts.
    Negative DPI = expectations of loosening market conditions.
    """
    dpi: float               # 12m forecast - 1m forecast (Mt)
    ems_forecast_1m: float   # verified emissions forecast, 1 month ahead
    ems_forecast_12m: float  # verified emissions forecast, 12 months ahead

    @property
    def direction(self) -> str:
        """Market signal from DPI."""
        if self.dpi < DPI_LOOSENING_MT:
            return "LOOSENING"    # emissions declining -> DEFER
        if self.dpi > DPI_TIGHTENING_MT:
            return "TIGHTENING"   # emissions rising -> BUY
        return "STABLE"


@dataclass
class BalanceSignal:
    """Output of the fundamental balance model for a given month."""
    year: int
    month: int
    date_key: str
    cap_mt: float
    verified_emissions_mt: float
    msr_intake_mt: float
    msr_release_mt: float
    market_balance_mt: float         # cap - emissions - intake + release
    balance_z_score: float
    signal: str                      # BUY / DEFER / HOLD
    signal_strength: float           # -1.0 (strong BUY) to +1.0 (strong DEFER)
    tnac_million: float
    msr_holdings_million: float
    price_pressure: Optional[PricePressure] = None
    demand_pressure: Optional[DemandPressure] = None

    @property
    def is_shortage(self) -> bool:
        return self.market_balance_mt < 0

    @property
    def display(self) -> str:
        base = (
            f"{self.date_key} | Cap={self.cap_mt:.0f}Mt "
            f"Ems={self.verified_emissions_mt:.0f}Mt "
            f"Balance={self.market_balance_mt:+.0f}Mt "
            f"> {self.signal}"
        )
        if self.price_pressure:
            base += f" | PP+={self.price_pressure.pp_plus:.2f} PP-={self.price_pressure.pp_minus:.2f}"
        return base


def compute_price_pressure(
    forecast_values: List[float],
    historical_prices: List[float],
    window: int = 12,
) -> PricePressure:
    """
    Bastianin et al. (2024), eq. 7-8.

    Parameters
    ----------
    forecast_values : predicted prices at horizons 1..H (use H=12)
    historical_prices : most recent `window` historical prices
    window : lookback window (default 12 months)
    """
    if not forecast_values or len(historical_prices) < window:
        return PricePressure(
            pp_plus=0.0, pp_minus=0.0,
            max_12m=max(historical_prices) if historical_prices else float("nan"),
            min_12m=min(historical_prices) if historical_prices else float("nan"),
            forecast_points=forecast_values or [],
        )

    recent = historical_prices[-window:]
    max_12m = max(recent)
    min_12m = min(recent)

    # eq. 7: PP⁺ = fraction of horizons where forecast > max_12m
    h_max = min(len(forecast_values), window)
    pp_plus = sum(1 for v in forecast_values[:h_max] if v > max_12m) / h_max

    # eq. 8: PP⁻ = fraction of horizons where forecast < min_12m
    pp_minus = sum(1 for v in forecast_values[:h_max] if v < min_12m) / h_max

    return PricePressure(
        pp_plus=pp_plus,
        pp_minus=pp_minus,
        max_12m=max_12m,
        min_12m=min_12m,
        forecast_points=forecast_values[:h_max],
    )


def compute_demand_pressure(
    ems_forecast_1m: float,
    ems_forecast_12m: float,
) -> DemandPressure:
    """
    Bastianin et al. (2024), §5.3:
    DPI = difference between 12-month and 1-month ahead verified emission forecasts.
    """
    return DemandPressure(
        dpi=ems_forecast_12m - ems_forecast_1m,
        ems_forecast_1m=ems_forecast_1m,
        ems_forecast_12m=ems_forecast_12m,
    )


@dataclass
class FundamentalModel:
    """
    The core supply-demand balance model.

    References
    ----------
    Bastianin et al. (2024) §4-5 — BVAR(1) + 1 PCA factor, market monitoring
    Maciejowski & Leonelli (2025) §4 — coal, MSCI Energy, gas/coal are key drivers
    EU Directive 2023/959 — cap schedule, MSR rules
    EC C/2025/3180 — TNAC communication (May 2025)
    """
    cap_schedule: CapSchedule
    emissions_data: EtsData
    msr_model: MSRModel = field(default_factory=lambda: MSRModel(
        tnac=TNAC_2024,
        msr_holdings=MSR_HOLDINGS_2024,
    ))
    sensitivity_sigma_mt: float = SENSITIVITY_SIGMA_MT

    _annual_emissions_mt: Dict[int, float] = field(default_factory=dict)
    _balance_history: Dict[int, float] = field(default_factory=dict)

    def __post_init__(self):
        self._annual_emissions_mt = get_annual_emissions(self.emissions_data)
        # Data quality: remove the most recent year if it appears incomplete
        self._strip_incomplete_year()
        self._balance_history = self._compute_balance_history()

    def _strip_incomplete_year(self):
        """Remove the most recent year if emissions are suspiciously
        far from the penultimate year (likely partial or double-counted reporting)."""
        years = sorted(self._annual_emissions_mt)
        if len(years) < 2:
            return
        latest = years[-1]
        penultimate = years[-2]
        pen_val = max(self._annual_emissions_mt[penultimate], 1.0)
        ratio = self._annual_emissions_mt[latest] / pen_val
        if ratio < DATA_COMPLETENESS_RATIO or ratio > (2.0 - DATA_COMPLETENESS_RATIO):
            import warnings
            msg = (
                f"Stripping year {latest} from emissions data: "
                f"emissions={self._annual_emissions_mt[latest]:.0f}Mt, "
                f"ratio vs {penultimate}={pen_val:.0f}Mt: {ratio:.2f} "
                f"(threshold: [{DATA_COMPLETENESS_RATIO}, {2.0 - DATA_COMPLETENESS_RATIO}])"
            )
            warnings.warn(msg)
            logger.warning(msg)
            del self._annual_emissions_mt[latest]

    def _compute_balance_history(self) -> Dict[int, float]:
        """Compute cap - emissions for each year where both are known.
        Does NOT include MSR effects (MSR is applied in evaluate()).
        Z-score uses this for consistency."""
        balances = {}
        cap_years = self.cap_schedule.years
        for year in sorted(self._annual_emissions_mt):
            cap = cap_years.get(year)
            if cap is not None:
                balances[year] = cap - self._annual_emissions_mt[year]
        return balances

    @property
    def latest_verified_year(self) -> Optional[int]:
        return max(self._annual_emissions_mt) if self._annual_emissions_mt else None

    @property
    def historical_balance_std(self) -> float:
        if len(self._balance_history) < MIN_SAMPLES_FOR_STD:
            return self.sensitivity_sigma_mt
        return float(np.std(list(self._balance_history.values())))

    def _warmup_msr_to_year(self, year: int):
        """Step the MSR model sequentially from initial year to year-1.
        Required because MSR is stateful — single-year jumps produce wrong TNAC."""
        self.msr_model.reset()
        if year <= self.msr_model.initial_year:
            return
        cap_years = self.cap_schedule.years
        for y in range(self.msr_model.initial_year, year):
            cap_mt_y = cap_years.get(y)
            ems_mt_y = self._annual_emissions_mt.get(y)
            if cap_mt_y is None:
                continue
            if ems_mt_y is None:
                ems_mt_y = self._annual_emissions_mt.get(max(self._annual_emissions_mt), 0)
                if ems_mt_y == 0:
                    import warnings
                    msg = (
                        f"MSR warmup: no emissions data for year {y}, "
                        "using 0 (balance will be cap-positive)"
                    )
                    warnings.warn(msg)
                    logger.warning(msg)
                else:
                    logger.debug(
                        "MSR warmup year %d: no emissions on file, using latest=%dMt",
                        y, ems_mt_y,
                    )
            self.msr_model.step(y, cap_mt_y * _M, ems_mt_y * _M)
        logger.debug(
            "MSR warmup complete: stepped %d -> %d, TNAC=%.0fM, holdings=%.0fM",
            self.msr_model.initial_year, year - 1,
            self.msr_model.tnac / _M, self.msr_model.msr_holdings / _M,
        )

    def evaluate(
        self,
        year: int,
        month: int = 1,
        forecast_prices: Optional[List[float]] = None,
        historical_prices: Optional[List[float]] = None,
        ems_forecast_1m: Optional[float] = None,
        ems_forecast_12m: Optional[float] = None,
    ) -> BalanceSignal:
        """
        Evaluate for a given month with optional price pressure and demand pressure.

        Parameters
        ----------
        year, month : evaluation date
        forecast_prices : Sybilion forecast values for horizons 1..12 (for PP+/PP-)
        historical_prices : last N months of actual prices (for PP+/PP- 12m window)
        ems_forecast_1m : verified emissions forecast 1 month ahead (for DPI)
        ems_forecast_12m : verified emissions forecast 12 months ahead (for DPI)
        """
        date_key = f"{year}-{month:02d}"
        cap_mt = self.cap_schedule.cap_mt(year)

        # Use latest verified emissions known at evaluation time
        available_years = sorted(self._annual_emissions_mt)
        if not available_years:
            raise ValueError(
                "No emissions data loaded. Call load_ets_csv() and "
                "pass EtsData to FundamentalModel."
            )
        past_years = [y for y in available_years if y < year]
        if not past_years:
            raise ValueError(
                f"No emissions data available before evaluation year {year}. "
                f"Available years: {available_years}. "
                "Cannot evaluate without historical emissions."
            )
        latest_ems_year = max(past_years)
        verified_mt = self._annual_emissions_mt[latest_ems_year]
        # MSR was not active before 2019 — use simplified balance
        if year < 2019:
            msr_intake_mt = 0.0
            msr_release_mt = 0.0
            balance_mt = cap_mt - verified_mt
            tnac_million = 0.0
            msr_holdings_million = 0.0
        else:
            # Warm up MSR from initial state to year-1 (sequential stepping)
            self._warmup_msr_to_year(year)
            cap_allowances = cap_mt * _M
            ems_allowances = verified_mt * _M
            msr_state = self.msr_model.step(year, cap_allowances, ems_allowances)
            msr_intake_mt = msr_state.intake / _M
            msr_release_mt = msr_state.release / _M
            balance_mt = cap_mt - verified_mt - msr_intake_mt + msr_release_mt
            tnac_million = msr_state.tnac / _M
            msr_holdings_million = msr_state.msr_holdings / _M

        # Z-score computed from pre-MSR balance (cap - emissions) for consistency
        # with _balance_history, which excludes MSR effects.
        pre_msr_balance = cap_mt - verified_mt
        z_score = 0.0
        if len(self._balance_history) >= MIN_SAMPLES_FOR_STD and self.historical_balance_std > 0:
            z_score = (pre_msr_balance - np.mean(list(self._balance_history.values()))) / self.historical_balance_std

        sigma = self.sensitivity_sigma_mt
        if balance_mt <= -sigma:
            signal = "BUY"
            signal_strength = max(-1.0, balance_mt / sigma)
        elif balance_mt >= sigma:
            signal = "DEFER"
            signal_strength = min(1.0, balance_mt / sigma)
        else:
            signal = "HOLD"
            signal_strength = max(-1.0, min(1.0, balance_mt / sigma))

        pp = None
        if forecast_prices and historical_prices:
            pp = compute_price_pressure(forecast_prices, historical_prices)

        dp = None
        if ems_forecast_1m is not None and ems_forecast_12m is not None:
            dp = compute_demand_pressure(ems_forecast_1m, ems_forecast_12m)

        return BalanceSignal(
            year=year,
            month=month,
            date_key=date_key,
            cap_mt=cap_mt,
            verified_emissions_mt=verified_mt,
            msr_intake_mt=msr_intake_mt,
            msr_release_mt=msr_release_mt,
            market_balance_mt=balance_mt,
            balance_z_score=z_score,
            signal=signal,
            signal_strength=signal_strength,
            tnac_million=tnac_million,
            msr_holdings_million=msr_holdings_million,
            price_pressure=pp,
            demand_pressure=dp,
        )

    def evaluate_range(
        self, start_year: int, end_year: int, month: int = 1
    ) -> List[BalanceSignal]:
        return [self.evaluate(y, month) for y in range(start_year, end_year + 1)]

    def summary(self, year: Optional[int] = None) -> Dict:
        if year is None:
            year = datetime.now().year
        sig = self.evaluate(year)
        caps = self.cap_schedule.years
        cap_years = sorted(caps)
        start = cap_years[0]
        end = cap_years[-1]
        return {
            "current_year": year,
            "latest_verified_year": self.latest_verified_year,
            "signal": sig.signal,
            "signal_strength": round(sig.signal_strength, 3),
            "market_balance_mt": round(sig.market_balance_mt, 1),
            "cap_mt": round(sig.cap_mt, 1),
            "latest_verified_emissions_mt": round(sig.verified_emissions_mt, 1),
            "msr_intake_mt": round(sig.msr_intake_mt, 1),
            "tnac_million": round(sig.tnac_million, 1),
            "msr_holdings_million": round(sig.msr_holdings_million, 1),
            "cap_start": caps[start],
            "cap_end": caps[end],
            "cumulative_cap_reduction_mt": round(caps[start] - caps[end], 1),
            "annual_cap_reduction_rate_mt_per_year": round(
                (caps[start] - caps[end]) / (end - start), 1
            ),
        }
