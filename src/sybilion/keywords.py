"""Domain-specific keyword sets for carbon market forecasting.

Two forecast targets:
  1. EUA certificate price — what drives the price of CO₂ allowances
  2. Company CO₂ emissions — what drives a company's emissions output

The emissions keywords combine:
  - General CO₂ terms (always included)
  - Sector-specific terms (selected by company type)

Max 20 keywords per API request, each ≤ 255 bytes.
"""

# ═══════════════════════════════════════════════════════════
# EUA CERTIFICATE PRICE — drivers of allowance price
# ═══════════════════════════════════════════════════════════

EUA_PRICE_DIRECT = [
    "EUA futures price",
    "EU ETS allowance price",
    "carbon allowance",
]

EUA_PRICE_REGULATORY = [
    "EU ETS reform",
    "CBAM implementation",
    "Fit for 55",
    "emissions trading system cap",
    "carbon price floor",
]

EUA_PRICE_MARKET = [
    "carbon credit supply shortage",
    "EU allowance futures",
    "renewable energy auction results",
    "voluntary carbon offset price",
]

EUA_PRICE_MACRO = [
    "industrial production index",
    "natural gas price",
    "coal price",
    "eurozone GDP growth",
    "energy crisis",
]

EUA_PRICE_KEYWORDS = (
    EUA_PRICE_DIRECT
    + EUA_PRICE_REGULATORY
    + EUA_PRICE_MARKET[:2]
    + EUA_PRICE_MACRO[:3]
)


# ═══════════════════════════════════════════════════════════
# COMPANY CO₂ EMISSIONS
# ═══════════════════════════════════════════════════════════

# General CO₂ keywords — ALWAYS included for any company type
EMISSIONS_GENERAL = [
    "CO2 emissions",
    "greenhouse gas emissions",
    "carbon footprint",
    "Scope 1 emissions",
    "Scope 2 emissions",
    "EU ETS compliance",
]

# Sector-specific keyword sets — combined with EMISSIONS_GENERAL
EMISSIONS_SECTORS = {
    "cement": {
        "label": "Cement",
        "keywords": [
            "cement production",
            "clinker output",
            "construction demand",
            "alternative fuels cement",
            "carbon capture cement",
            "building materials",
            "infrastructure spending",
            "real estate construction",
            "cement capacity utilization",
        ],
    },
    "steel": {
        "label": "Steel",
        "keywords": [
            "steel production",
            "blast furnace",
            "scrap steel demand",
            "iron ore",
            "hot rolled coil",
            "automotive steel",
            "construction steel",
            "electric arc furnace",
            "steel capacity utilization",
        ],
    },
    "chemicals": {
        "label": "Chemicals & Petrochemicals",
        "keywords": [
            "chemical production",
            "petrochemicals",
            "ethylene demand",
            "natural gas feedstock",
            "plastics demand",
            "polymer prices",
            "pharmaceutical production",
            "fertilizer demand",
            "chemical capacity utilization",
        ],
    },
    "refinery": {
        "label": "Oil Refinery",
        "keywords": [
            "refinery utilization",
            "crude oil processing",
            "diesel demand",
            "gasoline production",
            "jet fuel demand",
            "refinery margins",
            "fuel oil demand",
            "refining capacity",
            "biofuel blending",
        ],
    },
    "pulp_paper": {
        "label": "Pulp & Paper",
        "keywords": [
            "paper production",
            "pulp output",
            "packaging demand",
            "corrugated board",
            "recycled paper",
            "biomass energy paper",
            "printing paper demand",
            "tissue production",
            "paper capacity utilization",
        ],
    },
    "glass": {
        "label": "Glass & Ceramics",
        "keywords": [
            "glass production",
            "flat glass demand",
            "container glass",
            "ceramic manufacturing",
            "furnace energy consumption",
            "construction glass demand",
            "automotive glass",
            "glass recycling",
            "glass capacity utilization",
        ],
    },
    "aluminum": {
        "label": "Aluminum",
        "keywords": [
            "aluminum smelting",
            "primary aluminum",
            "alumina production",
            "bauxite",
            "aluminum demand",
            "electricity intensive production",
            "automotive aluminum",
            "aluminum recycling",
            "aluminum capacity utilization",
        ],
    },
    "aviation": {
        "label": "Aviation",
        "keywords": [
            "aviation emissions",
            "flight volume",
            "jet fuel consumption",
            "passenger traffic",
            "cargo flights",
            "airline capacity",
            "sustainable aviation fuel",
            "airport operations",
            "aviation fuel demand",
        ],
    },
    "maritime": {
        "label": "Maritime Shipping",
        "keywords": [
            "maritime shipping emissions",
            "container shipping volume",
            "bunker fuel consumption",
            "port activity",
            "freight tonnage",
            "shipping routes",
            "LNG marine fuel",
            "vessel utilization",
            "maritime capacity",
        ],
    },
}


def get_company_types() -> dict[str, dict]:
    """Return all predefined company types for frontend buttons."""
    return EMISSIONS_SECTORS


def select_keywords(
    target: str = "eua_price",
    sector: str = "cement",
    custom_keywords: list[str] | None = None,
    max_keywords: int = 20,
) -> list[str]:
    """Select keyword subset for a specific forecast target.

    Args:
        target: "eua_price" or "emissions"
        sector: company type key (e.g. "cement", "steel") for emissions target
        custom_keywords: user-provided keywords (replaces sector keywords)
        max_keywords: maximum keywords to return (API limit: 20)

    Returns:
        List of keywords ready for the Sybilion API.
    """
    if target == "eua_price":
        return EUA_PRICE_KEYWORDS[:max_keywords]

    if target == "emissions":
        if custom_keywords:
            # User entered a custom company type — prepend general keywords
            pool = EMISSIONS_GENERAL + custom_keywords
        else:
            # Predefined sector — combine general + sector keywords
            sector_data = EMISSIONS_SECTORS.get(sector, EMISSIONS_SECTORS["cement"])
            pool = EMISSIONS_GENERAL + sector_data["keywords"]

        return pool[:max_keywords]

    # Fallback
    return EUA_PRICE_KEYWORDS[:max_keywords]
