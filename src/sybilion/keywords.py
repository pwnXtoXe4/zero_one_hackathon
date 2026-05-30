"""Domain-specific keyword sets for carbon market forecasting.

Two forecast targets:
  1. EUA certificate price — what drives the price of CO₂ allowances
  2. Company CO₂ emissions — what drives a company's emissions output

The emissions keywords combine:
  - General CO₂ terms (always included)
  - Sector-specific terms (selected by company type)
  - LLM-generated terms (for custom company types)

Max 20 keywords per API request, each ≤ 255 bytes.
"""

import os
import json
import re
from typing import Optional

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


def get_keywords_for_company(
    company_type: str,
    max_keywords: int = 20,
    llm_provider: str = "openai",
    llm_api_key: Optional[str] = None,
) -> list[str]:
    """Get keywords for any company type — predefined or custom via LLM.

    This is the main function the frontend should call. It:
    1. Checks if company_type matches a predefined sector
    2. If yes, returns the hardcoded keywords
    3. If no, calls the LLM to generate keywords for the custom type
    4. Combines with general CO₂ keywords

    Args:
        company_type: The company type (e.g. "cement", "Textile Manufacturing")
        max_keywords: Maximum keywords to return (API limit: 20)
        llm_provider: "openai" or "anthropic" (used for custom types only)
        llm_api_key: Optional API key for the LLM provider

    Returns:
        Combined list of general + sector/LLM keywords.
    """
    # Check if it's a predefined sector key
    if company_type.lower() in EMISSIONS_SECTORS:
        return select_keywords(
            target="emissions",
            sector=company_type.lower(),
            max_keywords=max_keywords,
        )

    # Also check against sector labels (e.g. user typed "Cement" instead of "cement")
    for key, sector_data in EMISSIONS_SECTORS.items():
        if company_type.lower() == sector_data["label"].lower():
            return select_keywords(
                target="emissions",
                sector=key,
                max_keywords=max_keywords,
            )

    # Not predefined — generate via LLM
    llm_keywords = generate_keywords_llm(
        company_type=company_type,
        provider=llm_provider,
        api_key=llm_api_key,
    )

    return select_keywords(
        target="emissions",
        custom_keywords=llm_keywords,
        max_keywords=max_keywords,
    )

    # Fallback
    return EUA_PRICE_KEYWORDS[:max_keywords]


# ═══════════════════════════════════════════════════════════
# LLM KEYWORD GENERATION
# ═══════════════════════════════════════════════════════════

_LLM_KEYWORD_PROMPT = """You are helping a carbon emissions forecasting tool find the right keywords for a company's CO₂ emissions time series.

The user will tell you their company type (e.g. "Textile Manufacturing", "Food Processing", "Data Centers").
Return exactly 9 keywords that describe factors influencing that company's CO₂ emissions output.

Rules:
- Each keyword must be 1-4 words, lowercase.
- Focus on production activity, energy sources, sector demand drivers, and capacity factors.
- Include at least one keyword about capacity utilization or production volume.
- Do NOT include generic terms like "CO2 emissions" or "climate change" — those are added separately.
- Return ONLY a JSON array of 9 strings, nothing else.

Example for "Textile Manufacturing":
["textile production volume", "fabric demand", "cotton processing energy", "dyeing energy consumption", "packaging textile demand", "recycled fiber usage", "garment manufacturing", "textile capacity utilization", "synthetic fiber production"]
Example for "Aluminium Production":
["aluminium price", "aluminium demand", "bauxite", "alumina", "smelting costs", "electricity prices", "energy-intensive production", "Chinese industrial demand", "construction activity", "automotive demand", "inventories", "production cuts", "sanctions", "trade flows", "freight costs", "macroeconomic indicators"]

Company type: {company_type}"""


def generate_keywords_llm(
    company_type: str,
    provider: str = "alibaba",
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> list[str]:
    """Generate sector-specific keywords via LLM for a custom company type.

    Args:
        company_type: Free-text description of the company type
            (e.g. "Textile Manufacturing", "Food Processing").
        provider: LLM provider — "alibaba", "openai", or "anthropic".
        api_key: API key. Falls back to ALIBABA_API_KEY, OPENAI_API_KEY,
            or ANTHROPIC_API_KEY env var.
        model: Model name. Defaults to qwen-plus (Alibaba), gpt-4o-mini
            (OpenAI), or claude-sonnet-4-6 (Anthropic).

    Returns:
        List of 9 keyword strings.

    Raises:
        ValueError: If no API key is available or response is invalid.
        ConnectionError: If the LLM API call fails.
    """
    if provider == "alibaba":
        key = api_key or os.environ.get("ALIBABA_API_KEY") or os.environ.get("ALIBABA_API_TOKEN")
        if not key:
            raise ValueError("No Alibaba API key. Set ALIBABA_API_KEY or pass api_key=")
        return _generate_alibaba(company_type, key, model or "qwen-plus")

    if provider == "openai":
        key = api_key or os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_TOKEN")
        if not key:
            raise ValueError("No OpenAI API key. Set OPENAI_API_KEY or pass api_key=")
        return _generate_openai(company_type, key, model or "gpt-4o-mini")

    if provider == "anthropic":
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise ValueError("No Anthropic API key. Set ANTHROPIC_API_KEY or pass api_key=")
        return _generate_anthropic(company_type, key, model or "claude-sonnet-4-6")

    raise ValueError(f"Unknown provider: {provider}. Use 'alibaba', 'openai', or 'anthropic'.")


def _generate_openai(company_type: str, api_key: str, model: str) -> list[str]:
    """Call OpenAI API to generate keywords."""
    return _generate_openai_compat(
        company_type, api_key, model,
        url="https://api.openai.com/v1/chat/completions",
    )


def _generate_alibaba(company_type: str, api_key: str, model: str) -> list[str]:
    """Call Alibaba DashScope (Qwen) via OpenAI-compatible endpoint."""
    return _generate_openai_compat(
        company_type, api_key, model,
        url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions",
    )


def _generate_openai_compat(
    company_type: str, api_key: str, model: str, url: str
) -> list[str]:
    """Call any OpenAI-compatible API to generate keywords."""
    import urllib.request
    import urllib.error

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    body = json.dumps({
        "model": model,
        "messages": [
            {"role": "user", "content": _LLM_KEYWORD_PROMPT.format(company_type=company_type)}
        ],
        "temperature": 0.7,
        "max_tokens": 300,
    }).encode()

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise ConnectionError(f"OpenAI API error {e.code}: {e.read().decode()}")
    except urllib.error.URLError as e:
        raise ConnectionError(f"OpenAI API connection failed: {e.reason}")

    content = result["choices"][0]["message"]["content"].strip()
    return _parse_keywords(content)


def _generate_anthropic(company_type: str, api_key: str, model: str) -> list[str]:
    """Call Anthropic API to generate keywords."""
    import urllib.request
    import urllib.error

    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }
    body = json.dumps({
        "model": model,
        "max_tokens": 300,
        "messages": [
            {"role": "user", "content": _LLM_KEYWORD_PROMPT.format(company_type=company_type)}
        ],
    }).encode()

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise ConnectionError(f"Anthropic API error {e.code}: {e.read().decode()}")
    except urllib.error.URLError as e:
        raise ConnectionError(f"Anthropic API connection failed: {e.reason}")

    content = result["content"][0]["text"].strip()
    return _parse_keywords(content)


def _parse_keywords(content: str) -> list[str]:
    """Extract keyword list from LLM response.

    Handles:
    - Raw JSON array: ["kw1", "kw2", ...]
    - JSON in code blocks: ```json [...] ```
    - Numbered lists: 1. kw1\n2. kw2\n...
    - Comma-separated: kw1, kw2, kw3
    """
    # Try JSON array (possibly wrapped in code blocks)
    json_match = re.search(r'```(?:json)?\s*\n?(\[.*?\])\s*\n?```', content, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try raw JSON array
    json_match = re.search(r'\[[\s\S]*?\]', content)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    # Try numbered list: "1. keyword\n2. keyword..."
    items = re.findall(r'\d+\.\s*(.+)', content)
    if items:
        return [item.strip().strip('"').strip("'") for item in items]

    # Try comma-separated or newline-separated
    # Remove bullet points and leading numbers
    cleaned = re.sub(r'^[\s\-\*•\d.]+', '', content, flags=re.MULTILINE)
    items = [item.strip().strip('"').strip("'") for item in re.split(r'[,;\n]', cleaned)]
    items = [item for item in items if item and len(item) > 2]

    return items[:9]
