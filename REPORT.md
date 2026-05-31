# CarbonEdge — Forecasting AI (Sybilion)

## Team

- **Mansur Bibulatov** — Decision Agent Architect
- **Mashood Saya Ryed** — Frontend Developer
- **Florian Zainzinger** — Backend Developer
- **Albin Eiter** - Data Engineer

---

**Track:** Forecasting AI (Sybilion)

---

## TL;DR

CarbonEdge is a EUA procurement decision agent built on the Sybilion probabilistic forecasting API. It takes EUA certificate price forecasts with confidence bands and driver importance scores, as well as customer-provided carbon dioxide emission forecasts, and produces concrete procurement recommendations: how many allowances to buy, and crucially, when to buy them.

---

## Project Background: EU Allowances (EUAs)

EU Allowances (EUAs) are tradable permits that grant the holder the right to emit one tonne of CO₂. They are the core instrument of the EU Emissions Trading System (EU ETS), the world's largest carbon market, covering over 10,000 installations across energy, industry, and aviation. Companies receive a limited number of free allowances or must purchase them at auction or on the secondary market. If a company emits more CO₂ than its allowances cover, it must buy additional ones — or face heavy penalties. Since 2021, EUA prices have ranged from €30 to €100+ per tonne, making allowance procurement a multi-million-euro cost driver for affected companies.

---

## Problem

European companies spend millions on EU ETS carbon allowances and reduction projects, but they decide based on backward-looking compliance reports, not forward-looking probabilistic forecasts. The gap between a Sybilion forecast (a number with confidence bands and driver attributions) and an actual procurement decision is where the work sits:

- **When** is the cheapest time to buy EUA certificates given the price forecast and its uncertainty?
- **Where** is the right place to buy EUA certificates - on the private market or at auction?
- **How** does the decision change when a regulatory shock (ETS reform acceleration, CBAM phase-in) hits mid-year?

---

## Approach

How does your solution work? 3–5 bullets is enough.

- **Probabilistic forecast ingestion**: Submits monthly EU ETS price time series to the Sybilion API, receives point forecasts with quantile bands and ranked external driver importance scores.
- **Customer-specific procurement strategy**: Uses the Sybilion forecast to determine the optimal time to buy EUA certificates, taking into account the customer's CO₂ emission forecast and their specific procurement strategy.
- **Forward-looking MAC curve**: Ranks all reduction options by forecasted cost-per-ton using the Sybilion EUA price forecast — when prices rise, previously unviable options (e.g. H₂ blending at €65/ton) become economical.
- **Confidence-aware budget allocator**: Splits a fixed reduction budget across time buckets (NOW / Month 2 / Month 3 / Reserve), weighting each allocation by the forecast's confidence band width.
- **Adaptive scenario engine**: Applies regulatory shifts (ETS reform, CBAM acceleration, energy price crash) to the forecast, recalculates all decision streams, and surfaces a before/after delta with quantified savings from adapting.
- **Data sources**: Real facility-level CO₂ emissions from Climate TRACE v5.5.0 (14 sectors, ~2,160 installations worldwide), EU ETS historical prices (2021–2026).

A small diagram or architecture sketch in `extras/` helps but is not required.

---

## How to run it

The exact commands a stranger would need to reproduce your work:

### 1. Set up Backend

```sh
# Navigate to project root
cd zero_one_hackathon

# Create and activate virtual environment
python -m venv .venv

# Windows (PowerShell / CMD):
.venv\Scripts\activate

# macOS / Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
```

Open `.env` and insert your Sybilion API token:
```
SYBILION_API_TOKEN="your-token-here"
OPENAI_API_TOKEN=""   # optional
```

**Start the backend:**
```sh
uvicorn src.api.main:app --reload
```

→ API running on **http://localhost:8000**
→ Interactive docs: **http://localhost:8000/docs**

---

### 2. Set Up Frontend

> ⚠️ Start in a **new terminal** (backend must keep running).

```sh
cd zero_one_hackathon/frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

→ Frontend running on **http://localhost:5173**

---

Note that for this project a `Sybilion` API key is **required**. Optionally, you can use an `OpenAI` API key for improved keyword search. The keys must be put in an `.env` file in the root directory. You can find a template in `.env.example`.

---

## Results

The numbers. This is the section the jury reads most carefully.

### Backtest Design

We ran a **rolling walk-forward backtest** over the full EUA monthly price history (2015-04 → 2026-05, 134 months). At each evaluation point the decision agent receives a forecast, runs its 5-layer enhancement pipeline (regime, EPU, drivers, structural context, industrial demand), and produces a procurement plan via CVaR optimization. Realized costs are computed from the actual prices that materialized at each horizon and compared against five baselines:

| Baseline | Description |
|----------|-------------|
| Buy-all-at-spot | Purchase 100% of allowances at today's spot price |
| Equal thirds | Split purchases evenly across spot, M3, and M6 |
| Random walk | Forecast using random-walk-with-drift from past prices |
| Mean reversion | Anchor forecast to trailing 6-month moving average |
| Always H6 | Buy 100% at the 6-month horizon (extreme back-load) |

Statistical significance is assessed via the **Diebold-Mariano test** with Newey-West HAC standard errors (the literature standard for forecast evaluation, Diebold & Mariano 1995). H₀: agent and baseline have equal expected cost. p < 0.05 means the agent's cost difference is statistically distinguishable from the baseline.

We evaluate two forecast modes to separate **architecture quality** from **forecast quality**:

### Oracle (perfect-foresight upper bound)

The agent receives actual future prices as the forecast mean (plus calibrated noise). This answers: *if we knew the future, would the decision logic make good choices?*

| vs | Realized Savings | DM p-value | Significant? |
|----|-----------------|------------|-------------|
| Spot | **EUR +28.3M** | 0.0518 | borderline |
| Equal thirds | **EUR +837K** | 0.0278 | ✓ |
| Random walk | **EUR +768K** | 0.0237 | ✓ |
| Mean reversion | **EUR +900K** | 0.0225 | ✓ |
| Always H6 | **EUR +937K** | 0.0249 | ✓ |

- **4 of 5 baselines** are Diebold-Mariano significant at 5% level
- 8 FREEZE events (regime RED → emergency 25% lump sum)
- 5 distinct procurement strategies used (FREEZE, LUMP_SUM, FRONT_LOAD, EQUAL_SPLIT, LADDER)

### Naive (random-walk, actual operation mode)

The agent forecasts using a random-walk-with-drift from prices strictly before the evaluation date — no future leakage. This is what the system would produce in production without Sybilion.

| vs | Realized Savings | DM p-value | Significant? |
|----|-----------------|------------|-------------|
| Spot | **EUR +25.2M** | 0.0981 | no |
| Equal thirds | **EUR +771K** | 0.0575 | borderline |
| Random walk | **EUR +698K** | 0.0518 | borderline |
| Mean reversion | **EUR +830K** | 0.0459 | ✓ |
| Always H6 | **EUR +871K** | 0.0520 | borderline |

- Only **1 of 5 baselines** reaches DM significance at 5% (mean reversion)
- 8 FREEZE events (same PSY bubble detection — unaffected by forecast mode)
- Only 2 distinct strategies used (FREEZE, FRONT_LOAD) — less exploration than oracle

### Gap Analysis

| | Oracle | Naive | Delta |
|---|--------|-------|-------|
| Total savings vs spot | EUR +28.3M | EUR +25.2M | EUR -3.1M (**-11%**) |
| DM-significant baselines | 4/5 | 1/5 | Forecast error cost |
| FREEZE events | 8 | 8 | PSY bubble detection unaffected |
| Strategy diversity | 5 types | 2 types | Oracle explores more regimes |

The EUR 3.1M gap (11%) between oracle and naive is **purely forecast noise** — the architecture is identical. The naive agent still saves EUR 25.2M vs spot, but the lack of forecast direction means it defaults to FRONT_LOAD/FREEZE rather than exploring the full strategy space. This confirms that **the agent architecture is sound** (oracle proves it) and that **better forecasts directly translate to better decisions**.

### Single-Point Decision with Real Sybilion Forecast

Running the agent on a cached Sybilion forecast:

- **Forecast**: flat-to-slightly-down (75.5–75.7 across 6 months), but with widening uncertainty (M6 p05–p95 spans EUR 39.7)
- **Sybilion backtest MAPE**: 4.16%
- **Enhancement layers**: Regime GREEN, EPU CRISIS (1.80× volatility), Drivers BULLISH (+0.30), Structural BUY (84 Mt shortage), Composite +0.31 (MEDIUM BULL)
- **Result**: FRONT_LOAD strategy — 40% at spot (EUR 79.59), rest spread across M3 and M6. Total expected cost EUR 6.54M vs EUR 6.37M all-at-spot. The premium reflects the structural shortage signal overriding the flat Sybilion median — the agent is paying more now to avoid the risk of higher prices later in a tightening market.
- **Mean shift applied**: +9.9% (structural +6.8%, drivers +3.0%, demand +0.1%)

---

### Where the data came from

EU ETS historical prices (ICE/EEX, 2015–2026, 134 monthly observations). Climate TRACE v5.5.0 facility-level emissions data (public dataset, 2,160 installations worldwide, ~30,864 companies). Sybilion forecast submitted via `api.sybilion.dev` with 6-month horizon and full rolling-window backtest.

---

## What worked

### Niche and exciting focus

We believe that we managed to target a niche market with our agent. To the best of our knowledge, there are no other tools that focus solely on EUA procurement. Also, the potential market is huge, including all companies that are subject to the EU ETS. Additionally, the market is expected to grow significantly as the EU reduces the number of free allowances and increases the price of carbon. In 2021, we saw a whole new indutry fall under the EU ETS, namely the aviation industry. We believe that there is immense potential in this market and that our agent could be a valuable tool for companies that need to procure EUAs.

## What didn't work

### On hold: The Marketplace

We initially wanted to build a marketplace application for trading EUAs, powered by Sybilion's forecasts. However, we discovered that under Austrian law, EUAs are classified as financial products (similar to stocks), which would have triggered regulatory compliance requirements (licensing, reporting, etc.). We would have needed significantly more time to research whether the marketplace idea could be implemented compliantly — or if it would require legal partnerships, regulatory exemptions, or a different jurisdiction altogether. The decision agent architecture (CarbonEdge) remains the core deliverable that can integrate into such a marketplace once the legal path is clear. The idea is definetly something that we could explore in the future.

---

### Sybilion API frequency limitation

We initially tried to use a dataset comprisd of a daily time series.However, the Sybilion API only accepts `"monthly"` as the `frequency` value. `"daily"` and `"weekly"` are reserved in the schema but not yet supported — the API will reject them with a 422 validation error (`forecast_request_v1.py:44-48`).

**Implication for daily datasets:** If the source data (e.g., daily EUA prices, daily company emission readings) is collected at daily granularity, it must be **aggregated to monthly** before submission. A reasonable approach is to compute the **monthly average** (or monthly closing/last-observation) for each calendar month, reducing the daily series to one observation per month. This also means the resulting monthly series must still contain at least **60 observations** (5 years of monthly history) to meet Sybilion's minimum requirement.

**Possible update:** If Sybilion adds `"daily"` support in a future API version (`pipeline_version: v2`+), we could switch to daily granularity for finer-grained forecasts. Until then, daily→monthly aggregation is the required pre-processing step.

---

### Sybilion API Response Time

**Problem**: The Sybilion API is too slow for us to do a comprehensive backtest of the 5-layer agent. Unfortunately, we did not have the time to run a full backtest of the agent including a **non-cached** request to Sybilion. We only ran a backtest with a **cached** request to Sybilion. In general, we used caching as a workaround for the slow response time of the API. We think other teams were experiencing this as well.

**Solution**: We decided to cache the response from the API. This way, we do not have to wait for the API to respond every time we want to get a response from the API. Customers would have to wait once for the API to return. Then, the cached response can be used for further analysis, until it is deemed that an update is necessary.

### Project Time Allocation

We spent a lot of time on discussing potential ideas and possible use cases for the Sybilion API. Unfortunately, this led to the fact that we only started with the implementation after about half of the hackathon had already passed. This meant that we had to work really hard to get everything done in the remaining time.

---

## What you'd do with another 36 hours

### Review the marketplace idea

As mentioned in the section above, we would like to revisit the marketplace idea to see if it can be implemented compliantly. This would involve researching the legal requirements for trading EUAs in Austria and potentially partnering with a legal expert to ensure compliance. The idea behind the marketplace is to provide a plattform for companies to trade EUAs with each other. Sybilion's forecasts would be an incentive for companies to use the marketplace, as they would be able to make more informed decisions about when to buy and sell EUAs.

---

### Use a model for selecting relevant keywords

Currently, we select keywords based on the type of company and the type of indusrty. We do provide LLM integration when picking the right keywords. However, we believe that we could improve this by training a model to select the right keywords based on similar data from other companies of the same indusrty. This step would require a big dataset of companies and their corresponding keywords, which we did not have access to during the hackathon. We were not sure about the impact of this approach, especially because other teams had reported issues with respect to keywords. Therefore, we decided to shift our focus elsewhere, but it is definetly something that can be explored in the future.

---

### Put a stronger emphasis on the drivers

An idea we had was to recursively obtain predictions for the drivers of previous forecasts to allow for a more precise base forecast. However, this is nontrivial, since

- time series data is needed to obtain a forecast,
- recursion may lead to unforeseen error propagation,
- cross-correlation between drivers is not taken into account,

Also, we believe that the API already does this internally, hence we are not sure about the benefits of doing it ourselves.

---

### CBAM Integration

The Carbon Border Adjustment Mechanism (CBAM) creates a direct link between EU ETS allowance prices and the cost of imported goods. We would like to extend the agent to manage **both** EUA and CBAM certificate procurement simultaneously. Since CBAM certificate prices track the weekly average of EU ETS closing prices, a unified forecast could optimize the timing for both purchases. This would be particularly valuable for companies that both produce domestically (needing EUAs) and import materials (needing CBAM certificates), allowing them to hedge their total carbon cost exposure in a single decision stream.

---

## Track-specific deliverables: 📈 Forecasting AI (Sybilion)
- [X] Working agent or application — not slideware
- [X] Backtest results: at least one historical scenario validating the decision logic
- [X] Driver-importance visualization included in demo
- [X] Agent is ready to adapt to a mid-run assumption shift on Sunday
- [X] Domain choice rationale stated above in "Problem"

---

## Credits & dependencies

- **Open-source libraries used** (with versions): sybilion, numpy≥1.24, pandas≥2.0, scipy≥1.10.0, openpyxl≥3.1, fastapi, uvicorn, pytest≥8.0.0
- **External APIs called**: Sybilion API (api.sybilion.dev), OpenAI API (optional, for keyword generation)
- **AI coding assistants used during the hackathon**: Claude Code
- **Datasets**: Climate TRACE v5.5.0 facility-level emissions data (public), EU ETS historical prices (ICE/EEX)

---

## A note on honesty

We have not yet added the possibility for companies to upload their own historical data. We felt like this was not important for a PoC, but it would of course be required in a real product.

---

*Submitted by team !!1337 for Zero One Hack_01, 31.05.2026.*
