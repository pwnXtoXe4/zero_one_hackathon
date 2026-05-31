# CarbonEdge — Project Context for Claude Code

## What This Project Is

CarbonEdge is a 36h hackathon project (Zero One Hackathon). A CO2/EUA procurement intelligence platform that uses the **Sybilion probabilistic forecasting API** to help EU-ETS companies decide when and how to buy carbon certificates.

## Team Roles

| Role | Owner | Status |
|------|-------|--------|
| Backend Infrastructure | Florian Zainzinger | ✅ DONE |
| Decision Engine (carbonedge/) | Florian Zainzinger | ✅ DONE |
| Frontend | Another teammate | ✅ Active development |
| Data (company emissions) | Florian Zainzinger | ✅ 30,864 companies loaded |

## Current Repo State (updated 31.05.2026)

### ✅ Backend (src/api/)

| What | Where |
|------|-------|
| FastAPI backend (CORS open, 13 endpoints) | `src/api/main.py` |
| Health, companies, position routes | `src/api/routes/` |
| Market data routes (prices, futures, offers, auctions) | `src/api/routes/market.py` |
| Forecast routes (template + Sybilion submission) | `src/api/routes/forecasts.py` |
| Decision adapter (tries importing engine, falls back to mock) | `src/api/services/decision_adapter.py` |
| Service layer (file loading, CSV parsing, position calc) | `src/api/services/` |
| Sybilion API wrapper (caching + mock fallback) | `src/sybilion/client.py` |

### ✅ Decision Engine (carbonedge/)

| Layer | File | What it does |
|-------|------|-------------|
| Main entry point | `carbonedge/main.py` | CLI: loads data, builds forecast request, runs pipeline |
| Decision agent orchestrator | `carbonedge/decision_agent.py` | Wires all 5 layers → EnhancedDecision with procurement plan |
| Config + Company Profile | `carbonedge/config.py` | COMPANY_PROFILE, EMISSION_SOURCES, MAC_CONFIG |
| Sybilion client wrapper | `carbonedge/sybilion_client.py` | Builds requests, parses responses (real Sybilion format) |
| Mock forecast generator | `carbonedge/sybilion_client.py` | generate_mock_forecast() for testing |
| Output formatter | `carbonedge/output.py` | format_full_decision(), format_adaptive_delta() |
| Regime detector (FOCuS + CUSUM) | `carbonedge/regime_detector.py` | Online changepoint detection for structural breaks |
| MAC Curve builder | `carbonedge/mac_curve.py` | Marginal Abatement Cost curve |
| Budget allocator | `carbonedge/budget_allocator.py` | Distributes reduction budget across options |
| Adaptive scenario shifts | `carbonedge/adaptive.py` | ETS reform, CBAM, energy crash recalculations |
| Fundamental model | `carbonedge/fundamental/` | Cap schedule, MSR model, balance model, driver monitor |
| **Layer 1: Regime Enhancer** | `carbonedge/enhancement/regime_enhancer.py` | GREEN/YELLOW/RED confidence multipliers |
| **Layer 2: EPU Modulator** | `carbonedge/enhancement/epu_modulator.py` | Economic Policy Uncertainty → volatility multiplier |
| **Layer 3: Driver Filter** | `carbonedge/enhancement/driver_filter.py` | Coal/MSCI Energy/Gas ratio → front/back-load bias |
| **Layer 4: Structural Context** | `carbonedge/enhancement/structural_context.py` | Cap-emissions-MSR balance → narrative context |
| **Layer 5: Demand Signal** (NEW) | `carbonedge/enhancement/demand_signal.py` | 30,864 company emissions → demand_pressure (-1..+1) |
| **Company Risk Layer** (NEW) | `carbonedge/enhancement/company_risk.py` | Per-sector/size risk profiles → CVaR lambda override |
| Procurement optimizer (CVaR) | `carbonedge/procurement/optimizer.py` | Monte Carlo + scipy SLSQP → buy plan |
| Ladder rules (fallback) | `carbonedge/procurement/ladder_rules.py` | Heuristic ladder when optimizer fails |
| Tests | `carbonedge/tests/` | test_contracts.py, test_crosshair.py |

### Pipeline Architecture (5 Layers)

```
Sybilion Forecast
       │
       ▼
Layer 1: Regime     → confidence_multiplier (GREEN/YELLOW/RED)
Layer 2: EPU        → volatility_multiplier (NORMAL/ELEVATED/CRISIS)
Layer 3: Driver     → front/back-load bias (-0.3..+0.3)
Layer 4: Structural → narrative context (cap-emissions-MSR balance)
Layer 5: Demand     → demand_pressure (-1..+1) from 30K companies
       │
Company Risk Layer  → risk_lambda override (0.15-0.50 per sector/size)
       │
       ▼
CVaR Optimizer → Procurement Plan (tons × window × EUR)
```

## Data Audit (ehrlich: was ist echt, was ist Mock)

| Element | Status | Quelle |
|---------|:---:|--------|
| EUA-Preishistorie (67 Monate) | 🟢 echt | `data/raw/eua_prices_monthly.json` |
| Carbon Futures (2849 rows, 2015-2026) | 🟢 echt | `data/raw/carbon_emission_futures_data.csv` |
| Carbon Futures monthly mean/median | 🟢 echt | `data/prepared/carbon_futures_monthly_*.json` |
| 30,864 Company Emissions (2021-2026) | 🟢 echt | `data/prepared/all_companies_co2_timeseries.json` (Climate TRACE v5.5, 62MB) |
| 6 Individual Company CSVs | 🟢 echt | `data/raw/*.csv` (Salzgitter, Lengerich, Deuna, Nordzucker, Uxheim, Adolf) |
| Heidelberg Materials Emissions | 🟡 synth. Monatsauflösung | `data/raw/synthetic/heidelberg_materials_monthly_emissions.csv` (echte Firma, monatliche Disaggregation synthetisch) |
| Sybilion Forecast Request Template | 🟢 echt | `data/prepared/eua_forecast_request.json` |
| Backend Companies (greenchem, alpine_paper, voest_steel) | 🔴 synthetisch | `data/mock/companies.json` (statische Zahlen, keine echten Emissionen) |
| Auction Calendar | 🔴 Mock | `data/mock/auction_calendar.json` (kein echter EEX-Kalender) |
| Sell Offers (OTC) | 🔴 Mock | `data/mock/sell_offers.json` |
| Inter-Firmen-Trade-Daten | ⚫ existiert nicht | Nicht öffentlich verfügbar (Union Registry zeigt das nicht) |

## Tech Stack

- **Language:** Python 3.11+
- **Backend:** FastAPI + Uvicorn
- **Decision Engine:** numpy, scipy (for CVaR optimizer)
- **Optional:** pandas, openpyxl (for EPU data), changepoint_online (for FOCuS)
- **Data:** JSON files + CSV (NO database)
- **Forecasting:** Sybilion API (api.sybilion.dev)
- **No Docker, no ORM, no auth**

## Sybilion Integration (Critical)

- **Correct API endpoint:** `https://api.sybilion.dev`
- **Auth header:** `Authorization: Bearer <token>`
- **Token env var:** `SYBILION_API_TOKEN`
- **DO NOT use:** `mcp.sybilion.dev` — MCP proxy has user-mapping bugs
- **Account:** `e909b765`, Tier 4, hackathon grant ~€10,000 (expires June 1 2026)
- Sybilion liefert volle p05–p95 Quantile (19 pro Monat) — KEIN Aufweiten nötig

## Known Gaps (was noch fehlt)

1. **Backend-Engine-Brücke fehlt:** `src/engine/agent.py` existiert nicht. Der `decision_adapter.py` sucht danach und gibt `mock_engine_not_connected` zurück. Die Pipeline in `carbonedge/` ist standalone per CLI nutzbar, aber nicht über die API-Endpoints `/decisions/run` und `/decisions/scenario` erreichbar.

2. **Emissions-Forecast nicht verdrahtet:** Heidelberg Materials hat 137 Monate echte/synthetische Emissionsdaten + einen Sybilion-Forecast. Aber der Forecast ist nicht an eine im Frontend auswählbare Firma gekoppelt.

3. **EUA-Preis-Forecast veraltet:** Der gecachte EUA-Forecast hat nur p10/p50/p90. Sollte neu gezogen werden für volle p05–p95 wie der Emissions-Forecast.

4. **Frontend zeigt unverbundene Karten:** Keine Kausalkette zwischen Emissions-Verlauf → Überschreitungs-Zeitpunkt → Defizit → Kaufplan. Fehlende Timeline-Visualisierung.

5. **requirements.txt hat Merge-Conflict-Marker** (<<<<<<< / ======= / >>>>>>>). Muss bereinigt werden.

## How to Run Backend

```bash
pip install -r requirements.txt
uvicorn src.api.main:app --reload
# Docs at http://localhost:8000/docs
```

## How to Run Decision Engine (CLI)

```bash
# Without forecast (prepares request for Sybilion):
python -m carbonedge.main

# With forecast artifact:
python -m carbonedge.main --forecast path/to/forecast.json

# With scenario shift:
python -m carbonedge.main --forecast forecast.json --scenario ets_reform

# With external signals + backtest:
python -m carbonedge.main --forecast forecast.json --external-signals signals.json --backtest-metrics backtest.json
```
