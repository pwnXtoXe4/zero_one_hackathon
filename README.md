# CarbonEdge — EUA Carbon Procurement Decision Platform

> Decision engine for carbon allowance procurement under EU ETS constraints.
> Combines real Climate-TRACE emissions data, EEX auction calendars, Sybilion
> forecasts, and ETS policy overlays to generate adaptive procurement strategies.

---

## Quick Start

### Prerequisites

- **Python 3.10+** (`python --version`)
- **Node.js 18+** (`node --version`)
- **Sybilion API Token** (required)
- **OpenAI API Token** (optional, for keyword LLM integration)

### 1. Set Up Backend

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

## Quick Health Check

| Component | URL | Expected Result |
|---|---|---|
| Backend Health | http://localhost:8000/health | `{"status": "ok"}` |
| API Docs | http://localhost:8000/docs | OpenAPI Swagger UI |
| Frontend | http://localhost:5173 | CarbonEdge Dashboard |

---

## Project Structure

```
zero_one_hackathon/
├── src/
│   ├── api/              # FastAPI backend (main.py = entry point)
│   ├── engine/           # Decision engine (agent.py)
│   ├── data/             # JSON/CSV data files (no DB needed!)
│   └── carbonedge/       # Advanced procurement logic
├── frontend/             # React + Vite + TypeScript dashboard
│   ├── src/
│   │   ├── components/   # UI components (charts, panels, …)
│   │   ├── data/         # Types, API client, mock data
│   │   └── lib/          # Utilities
│   └── package.json
├── .env                  # API keys (do not commit!)
└── requirements.txt      # Python dependencies
```

---

## Important Notes

- **No database** — all data comes from JSON/CSV files in `src/data/`
- **Sybilion API base URL:** `https://api.sybilion.dev` (NOT `mcp.sybilion.dev`!)
- **Restart backend** after changes to Python files (`agent.py`, `emissions_service.py`, …)
- **Frontend** uses Vite HMR — changes reload automatically in the browser
- **`forecastMode`** in the frontend shows `mock` or `live` (depending on whether real Sybilion forecasts are available)

---

## Backend API

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/companies` | All companies |
| GET | `/companies/{id}` | Single company |
| GET | `/companies/{id}/position` | Long/short position |
| GET | `/market/eua-prices` | EUA price history (chart format) |
| GET | `/market/futures?limit=500` | Carbon futures |
| GET | `/market/sell-offers` | Mock seller offers |
| GET | `/market/auctions` | EEX auction calendar |
| GET | `/market/auctions/next` | Next upcoming auction |
| GET | `/forecasts/request-template` | Sybilion request template |
| POST | `/forecasts/sybilion` | Submit forecast to Sybilion |
| POST | `/decisions/run` | Run decision engine |
| POST | `/decisions/scenario` | Scenario simulation |

---

## Architecture Overview

```
┌──────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Frontend   │────▶│   FastAPI API    │────▶│  Decision Engine│
│  React+Vite  │◀────│   (src/api/)     │◀────│  carbonedge/    │
└──────────────┘     └────────┬─────────┘     └─────────────────┘
                              │
                    ┌─────────┴──────────┐
                    │   Data Sources     │
                    │  • Climate-TRACE   │
                    │  • EEX Calendar    │
                    │  • Sybilion API    │
                    │  • Policy Overlay  │
                    └────────────────────┘
```

### Data Flow

1. **Emissions data** — Climate-TRACE history + Sybilion 6-month forecast (p10/p50/p90)
2. **Auction calendar** — Real EEX 2026 volumes (CAP3, DE, PL), real cadence
3. **Price drivers** — Sybilion signals (macro) + ETS policy overlay (MSR, CBAM, cap cut)
4. **Decision engine** — Detects regime (BUY/HOLD/LADDER), computes procurement strategy
5. **Scenario shocks** — MSR shock, price spike, volume halt → adaptive re-route

---

## Development

### Restart backend
```sh
# In backend terminal: Ctrl+C, then:
uvicorn src.api.main:app --reload
```

### Check frontend build
```sh
cd frontend
npx tsc --noEmit     # TypeScript type check
npm run build         # Production build
```

### Run tests
```sh
pytest                # Backend tests
```

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `ModuleNotFoundError` | Did you forget to activate `.venv\Scripts\activate`? |
| Frontend loads no data | Is backend running? Check `http://localhost:8000/health` |
| `forecastMode: mock` | No Sybilion forecasts yet — call `/forecasts/sybilion` first |
| Encoding errors (Windows) | Set `PYTHONIOENCODING=utf-8` before running Python scripts |
| Sybilion API timeout | Forecasts take ~15 min — set timeout to ≥1500s |
