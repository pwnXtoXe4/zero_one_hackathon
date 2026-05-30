"""
EPU Volatility Modulator

Dai et al. (2020) "The impact of economic policy uncertainties on the
volatility of European carbon market" (arXiv:2007.10564) shows:
  - GARCH-MIDAS model: EPU -> long-run volatility of EUA
  - Global EPU is a STRONGER predictor than European EPU
  - EPU exacerbates long-term volatility component

Data source: policyuncertainty.com — European News-Based EPU Index
(loaded from Europe_Policy_Uncertainty_Data.xlsx if available,
falls back to built-in 2015-2025 hardcoded series).
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

EPU_NORMAL = 100.0
EPU_ELEVATED = 150.0
EPU_CRISIS = 250.0
VOLATILITY_AMPLIFIER_NORMAL = 1.0
VOLATILITY_AMPLIFIER_ELEVATED = 1.3
VOLATILITY_AMPLIFIER_CRISIS = 1.8
EPU_SPIKE_SIGMA = 2.0


def _load_epu_data() -> Dict[str, float]:
    """Load European News-Based EPU Index from Excel file.
    Searches: (1) CARBONEDGE_DATA_DIR env, (2) project-relative data/,
    (3) user's Downloads as last resort."""
    import os

    search_paths = []

    env_dir = os.environ.get("CARBONEDGE_DATA_DIR")
    if env_dir:
        search_paths.append(Path(env_dir) / "Europe_Policy_Uncertainty_Data.xlsx")

    here = Path(__file__).resolve()
    # Project-root data/ first (canonical), then carbonedge/data/ as fallback.
    search_paths.append(here.parents[2] / "data" / "Europe_Policy_Uncertainty_Data.xlsx")
    search_paths.append(here.parents[1] / "data" / "Europe_Policy_Uncertainty_Data.xlsx")

    search_paths.append(Path.home() / "Downloads" / "Firefox" / "Europe_Policy_Uncertainty_Data.xlsx")

    excel_path = None
    for p in search_paths:
        if p.exists():
            excel_path = p
            logger.debug("EPU data loaded from %s", excel_path)
            break

    if excel_path is None:
        logger.error("EPU data file missing from all candidates: %s", search_paths)
        raise FileNotFoundError(
            "EPU data file not found. Searched: " + ", ".join(str(p) for p in search_paths) + ". "
            "Set CARBONEDGE_DATA_DIR env var or place Europe_Policy_Uncertainty_Data.xlsx "
            "in the project data/ directory. Download from https://www.policyuncertainty.com/europe_monthly.html"
        )

    import pandas as pd
    df = pd.read_excel(excel_path)
    df = df[pd.to_numeric(df["Year"], errors="coerce").notna()].copy()
    df = df[df["Month"].notna()].copy()
    df["Year"] = df["Year"].astype(int)
    df["Month"] = df["Month"].astype(int)

    result: Dict[str, float] = {}
    for _, row in df.iterrows():
        key = f"{int(row['Year'])}-{int(row['Month']):02d}"
        result[key] = float(row["European_News_Index"])
    return result


@dataclass
class EpuState:
    """Snapshot of EPU volatility assessment."""
    date: str
    epu_value: float
    epu_12m_mean: float
    epu_12m_std: float
    z_score: float
    volatility_multiplier: float
    level: str  # NORMAL, ELEVATED, CRISIS
    spike: bool  # >2 sigma above 12m mean


@dataclass
class EpuModulator:
    """
    Monitors EPU index and outputs a volatility multiplier.
    From Dai et al. (2020): EPU -> long-run EUA volatility.

    The multiplier is applied to Sybilion's confidence band width:
      adjusted_sigma = original_sigma * volatility_multiplier
    """
    _history: List[EpuState] = field(default_factory=list)

    def evaluate(self, date_str: str, epu_value: Optional[float] = None) -> EpuState:
        data: Dict[str, float] = {}
        if epu_value is None:
            date_key = date_str[:7]  # "YYYY-MM"
            data = _load_epu_data()
            epu_value = data.get(date_key)
            if epu_value is None and data:
                # Use most recent available month when current month not in data
                latest_key = max(data.keys())
                epu_value = data[latest_key]
                logger.info(
                    "EPU: requested %s not in data, falling back to latest %s=%.0f",
                    date_key, latest_key, epu_value,
                )
                date_key = latest_key
            if epu_value is None:
                logger.warning("EPU evaluate(%s): no value resolvable -> UNKNOWN state", date_str)
                return EpuState(
                    date=date_str, epu_value=float("nan"),
                    epu_12m_mean=float("nan"), epu_12m_std=float("nan"),
                    z_score=0.0, volatility_multiplier=1.0,
                    level="UNKNOWN", spike=False,
                )
        else:
            date_key = date_str[:7]

        # 12-month trailing baseline: prefer running history (warm-started by
        # backtests or repeated evaluate() calls); otherwise sample 12 months
        # ending just before date_key from the loaded data file.
        history_values = np.array([h.epu_value for h in self._history[-12:]])
        n_hist = len(history_values)
        if n_hist >= 6:
            mean_12m = float(np.mean(history_values))
            std_12m = max(float(np.std(history_values)), 15.0)
        elif data:
            prior_keys = sorted(k for k in data if k < date_key)[-12:]
            if len(prior_keys) >= 6:
                prior_vals = np.array([data[k] for k in prior_keys])
                mean_12m = float(np.mean(prior_vals))
                std_12m = max(float(np.std(prior_vals)), 15.0)
            else:
                mean_12m = EPU_NORMAL
                std_12m = 30.0
        else:
            mean_12m = EPU_NORMAL
            std_12m = 30.0
        z_score = (epu_value - mean_12m) / std_12m

        if epu_value > EPU_CRISIS:
            multiplier = VOLATILITY_AMPLIFIER_CRISIS
            level = "CRISIS"
        elif epu_value > EPU_ELEVATED:
            multiplier = VOLATILITY_AMPLIFIER_ELEVATED
            level = "ELEVATED"
        else:
            multiplier = VOLATILITY_AMPLIFIER_NORMAL
            level = "NORMAL"

        spike = z_score > EPU_SPIKE_SIGMA

        state = EpuState(
            date=date_str,
            epu_value=epu_value,
            epu_12m_mean=mean_12m,
            epu_12m_std=std_12m,
            z_score=z_score,
            volatility_multiplier=multiplier,
            level=level,
            spike=spike,
        )
        self._history.append(state)
        return state

    @property
    def latest(self) -> Optional[EpuState]:
        return self._history[-1] if self._history else None

    def reset(self):
        """Clear rolling history for backtest window isolation."""
        self._history = []
