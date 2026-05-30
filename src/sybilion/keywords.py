"""Domain-specific keyword sets for carbon market forecasting."""

# Layer 1 — Regulatory (structural policy drivers)
REGULATORY_KEYWORDS = [
    "EU ETS reform",
    "CBAM implementation",
    "Fit for 55",
    "carbon border tax",
    "emissions trading system cap",
    "carbon price floor",
]

# Layer 2 — Market (trading and investment signals)
MARKET_KEYWORDS = [
    "carbon credit supply shortage",
    "PPA price index",
    "renewable energy auction results",
    "green premium",
    "voluntary carbon offset price",
    "EU allowance futures",
]

# Layer 3 — Technology (cost curve inflection points)
TECHNOLOGY_KEYWORDS = [
    "green hydrogen cost curve",
    "battery storage deployment",
    "direct air capture scale-up",
    "solar LCOE trend",
    "wind energy cost reduction",
]

# Layer 4 — Macro (economic cycle effects)
MACRO_KEYWORDS = [
    "industrial production index",
    "natural gas price forecast",
    "energy crisis",
    "natural gas storage level",
    "recession probability",
    "eurozone GDP growth",
]

ALL_KEYWORDS = (
    REGULATORY_KEYWORDS
    + MARKET_KEYWORDS
    + TECHNOLOGY_KEYWORDS
    + MACRO_KEYWORDS
)


def select_keywords(
    focus: str = "carbon_market",
    horizon: int = 6,
    max_keywords: int = 12,
) -> list[str]:
    """Select keyword subset based on focus area and forecast horizon.

    Short horizons: emphasize recent market signals.
    Long horizons: emphasize regulatory and structural drivers.
    """
    if focus == "carbon_market":
        if horizon <= 3:
            pool = REGULATORY_KEYWORDS[:2] + MARKET_KEYWORDS + MACRO_KEYWORDS[:2]
        else:
            pool = REGULATORY_KEYWORDS + MARKET_KEYWORDS[:3] + MACRO_KEYWORDS[:3]
    elif focus == "emissions_trajectory":
        pool = TECHNOLOGY_KEYWORDS + MACRO_KEYWORDS[:2] + MARKET_KEYWORDS[:2]
    else:
        pool = ALL_KEYWORDS

    return pool[:max_keywords]
