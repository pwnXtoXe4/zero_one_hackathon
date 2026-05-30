# CarbonEdge — CO₂ Reduction Decision Agent on Probabilistic Forecasting

## 1. Executive Summary

**CarbonEdge** is a decision agent that helps companies reduce CO₂ emissions **cost-effectively** by using probabilistic forecasts to answer three questions:

1. **When** is the cheapest time to make emissions-intensive purchases or run high-emission processes?
2. **Where** should reduction investments go first — based on forecasted impact, not last year's emission reports?
3. **How much** carbon credit / allowance to buy now vs. later, given probabilistic price trajectories and regulatory shifts?

Most carbon management tools are **backward-looking**: they measure last quarter's emissions and generate compliance reports. CarbonEdge is **forward-looking**: it uses probabilistic forecasts to make emissions reduction decisions that respect both cost constraints and uncertainty — because the cheapest ton of CO₂ reduced is the one you reduce *at the right time, in the right place*.

---

## 2. The Problem

### The Compliance Trap

Companies are drowning in carbon data but starving for carbon **decisions**:

- **ESG reports look backward.** They tell you what you emitted last year, not what to do differently next month.
- **Carbon prices are volatile.** EU ETS allowance prices swung from €50 to €100+ per ton in the past two years. Buying allowances at the wrong time costs millions.
- **Reduction budgets are fixed, but costs aren't.** A company might have €2M to spend on reductions this year — but when should they buy solar PPAs? When should they purchase offsets? When should they schedule maintenance that reduces emissions?
- **CBAM is coming.** The EU Carbon Border Adjustment Mechanism (phased in from 2026) will tax imported goods based on embedded carbon. Companies that haven't modeled their exposure probabilistically will overpay or underprepare.
- **Competitive pressure is real.** Companies with lower carbon intensity get better financing rates, win ESG-mandated procurement contracts, and face lower regulatory risk. This is a **competitive race**, not a compliance checkbox.

### The Cost of Not Deciding

| Scenario | Naive Approach | Cost of Being Wrong |
|---|---|---|
| EU ETS allowance timing | Buy all needed allowances at fiscal year start | €20-50/ton swing = €500K-2M on a 100K ton portfolio |
| PPA (Power Purchase Agreement) signing | Sign when salesperson calls | Locking in at €80/MWh vs. waiting for €55/MWh = €500K/year overcommitment |
| Carbon offset purchase timing | Buy offsets reactively at year-end | Year-end offset prices can spike 30-40% in Q4 compliance rush |
| Reduction investment prioritization | Invest in easiest reductions first (low-hanging fruit) | Missing forecasted high-impact areas → 2-3× higher cost per ton reduced |
| CBAM exposure | Assume flat tariff rate | CBAM certificate price tracks EU ETS — a €30 swing per ton of embedded carbon = massive import cost surprises |

---

## 3. System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    SYBILION API                               │
│                                                               │
│  Input:  Historical emissions / carbon price / energy          │
│          consumption time series + contextual keywords          │
│          ("EU ETS reform", "CBAM phase-in", "renewable         │
│           capacity expansion", "carbon tax legislation", ...)   │
│                                                               │
│  Output:                                                      │
│    • Probabilistic forecast (monthly outcome bands)            │
│      — for emissions trajectory, carbon price, energy cost     │
│    • External driver importance scores per horizon             │
│    • Historical backtest accuracy data                         │
└──────────────────────────┬──────────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────┐
│              CARBONEDGE DECISION AGENT                          │
│                                                               │
│  ┌─────────────────┐  ┌──────────────────┐  ┌──────────────┐ │
│  │ Marginal Abate- │  │ Carbon Market    │  │ Investment   │ │
│  │ ment Cost       │  │ Timing Engine    │  │ Optimizer    │ │
│  │ (MAC) Curve     │  │                  │  │              │ │
│  │                 │  │ • EU ETS allow-  │  │ • Reduction  │ │
│  │ • Ranks all     │  │   ance timing    │  │   project    │ │
│  │   reduction     │  │ • Offset market  │  │   sequencing │ │
│  │   options by    │  │   timing         │  │ • Budget     │ │
│  │   cost-per-ton  │  │ • CBAM cert      │  │   allocation │ │
│  │   • Forecasts   │  │   price timing   │  │   across     │ │
│  │   future MAC    │  │ • Confidence-    │  │   projects   │ │
│  │   shape with    │  │   band-aware     │  │ • ROI under  │ │
│  │   Sybilion data │  │   buy/wait logic │  │   uncertainty│ │
│  └────────┬────────┘  └────────┬─────────┘  └──────┬───────┘ │
│           └────────────────────┘                    │         │
│                            ▼                        │         │
│              ┌───────────────────────────┐           │         │
│              │  Compliance & Reporting   │◄──────────┘         │
│              │  Engine                   │                      │
│              │  • CBAM exposure calc     │                      │
│              │  • ESG target tracking    │                      │
│              │  • Regulatory timeline    │                      │
│              └───────────────────────────┘                      │
└──────────────────────────┬──────────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                    DECISION OUTPUT                            │
│                                                               │
│  For each decision area:                                      │
│    → Action: BUY / WAIT / INVEST / DEFER / RESEQUENCE         │
│    → Timing: Immediate / This quarter / Next fiscal year      │
│    → Volume: How many allowances / offsets / tons to reduce   │
│    → Confidence: High / Medium / Low (with band visualization)│
│    → Cost impact: Expected savings vs. naive baseline         │
│    → Emissions impact: Tons CO₂e reduced, trajectory change   │
│    → Reasoning: Top 3 drivers, backtest support, MAC curve    │
│      position, regulatory timeline alignment                   │
└──────────────────────────────────────────────────────────────┘
```

---

## 4. Decision Logic — How the Agent Thinks

### 4.1 Three Parallel Decision Streams

CarbonEdge runs three decision streams simultaneously, each consuming different Sybilion forecasts:

#### Stream A: Carbon Market Timing (When to Buy)

Forecasts: EU ETS allowance price, voluntary carbon offset price, CBAM certificate price

```
Decision Logic:
┌─────────────────────────────────────────────────────────────┐
│ If forecast price trajectory is UPWARD + confidence narrow:  │
│   → BUY NOW (lock in current price, forward-purchase)        │
│                                                              │
│ If forecast price trajectory is DOWNWARD + confidence narrow:│
│   → WAIT (buy closer to compliance deadline, save 10-20%)   │
│                                                              │
│ If forecast band is WIDE (high uncertainty):                 │
│   → LADDER (buy 40% now, 30% at month 3, 30% at month 6)    │
│   → Sets price trigger alerts above/below band               │
│                                                              │
│ If driver "regulatory tightening" importance is INCREASING:  │
│   → Tilt earlier — structural price floor is rising           │
└─────────────────────────────────────────────────────────────┘
```

#### Stream B: Marginal Abatement Cost Optimization (Where to Cut)

Forecasts: Company emissions by source, energy prices, renewable cost curves

```
Decision Logic:
┌─────────────────────────────────────────────────────────────┐
│ Build forward-looking MAC curve (not static):               │
│                                                              │
│ 1. Rank all reduction options by forecasted cost-per-ton    │
│    (not current cost — forecasted, including energy price    │
│     trajectories and technology cost curves)                  │
│                                                              │
│ 2. Identify "window opportunities":                          │
│    - Solar PPA becomes cheaper than grid in month 4-6        │
│    - Process optimization ROI improves when production       │
│      forecast drops (lower opportunity cost of downtime)     │
│    - Fleet electrification total cost crosses ICE threshold  │
│      in month 8                                              │
│                                                              │
│ 3. Allocate reduction budget across time, not just projects: │
│    - Month 1-2: Low-cost operational changes (€20/ton)       │
│    - Month 3-5: PPA signing when renewable price dips        │
│    - Month 6-8: Capital investment when financing favorable  │
│    - Month 9-12: Offset purchases if trajectory off-target   │
└─────────────────────────────────────────────────────────────┘
```

#### Stream C: Production Scheduling (When to Emit)

Forecasts: Grid carbon intensity, renewable availability, production demand

```
Decision Logic:
┌─────────────────────────────────────────────────────────────┐
│ For companies with flexible production schedules:           │
│                                                              │
│ • Shift high-emission processes to low-carbon-grid hours    │
│   (Sybilion forecasts grid carbon intensity by month)        │
│ • Schedule maintenance/emissions-reducing upgrades when:    │
│   - Production demand forecast is LOW (less revenue impact)  │
│   - Grid carbon intensity is HIGH anyway (max reduction      │
│     impact per unit of efficiency gain)                      │
│ • Pre-purchase raw materials before carbon-intensive         │
│   production runs if CBAM / carbon price forecast is rising  │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 The Confidence-Aware Budget Allocator

The most distinctive feature: CarbonEdge doesn't just recommend actions — it recommends **how to split a fixed reduction budget** across time and options, based on forecast confidence.

```
Input: €2M annual reduction budget
       Sybilion forecast: EU ETS price trajectory, renewable PPA pricing
       Company: 500K tons CO₂e/year, target 15% reduction

Output — Budget Allocation:
┌─────────────────────────────────────────────────────────────┐
│                                                            │
│  NOW (€600K — 30%):                                        │
│    • Buy 8,000 EU ETS allowances at €68/ton = €544K       │
│      WHY: Forecast trajectory UP, confidence NARROW         │
│           [€72-78/ton by month 3, backtest acc: 74%]       │
│    • Quick operational audit = €56K                        │
│                                                            │
│  MONTH 3 (€800K — 40%):                                    │
│    • Sign 5-year solar PPA = €750K (locked at €52/MWh)    │
│      WHY: Renewable price forecast dips in month 2-3       │
│           Confidence MEDIUM — use option clause to exit    │
│           if grid price drops below €45/MWh                │
│    • Process optimization implementation = €50K            │
│                                                            │
│  MONTH 6 (€400K — 20%):                                    │
│    • Fleet electrification phase 1 = €350K                 │
│      WHY: TCO crossover point reached in month 5-6         │
│           Confidence WIDE [month 8-12 band is large]       │
│           → Only phase 1, reassess before phase 2          │
│    • Monitoring + recalibration = €50K                     │
│                                                            │
│  RESERVE (€200K — 10%):                                    │
│    • Hold for year-end offset purchases ONLY if trajectory │
│      shows we're off-target                                │
│    • Trigger: If mid-year emissions > 85% of target, deploy│
│      into high-quality removal credits                      │
│                                                            │
│  EXPECTED OUTCOME:                                          │
│    • 78K tons CO₂e reduced (15.6% of baseline)             │
│    • Blended cost: €25.6/ton (vs. industry avg €38/ton)    │
│    • vs. naive approach (buy everything now): saves €180K  │
└─────────────────────────────────────────────────────────────┘
```

### 4.3 Driver-Importance Translation

The Sybilion API returns driver importance scores per horizon. CarbonEdge translates these into domain-specific signals:

| Driver | What It Means for the Company | Decision Impact |
|---|---|---|
| "EU ETS reform" importance ↑ | Regulatory supply squeeze coming — allowance prices structurally higher | Accelerate allowance purchases, increase reduction target |
| "Renewable capacity expansion" importance ↑ | Grid getting cleaner over time — some reductions happen naturally | Defer some capital investments, let grid decarbonization do part of the work |
| "CBAM phase-in" importance ↑ | Import costs rising for carbon-intensive inputs | Pre-purchase materials, qualify alternative low-carbon suppliers |
| "Natural gas price" importance ↑ | Energy cost volatility affecting reduction ROI | Prioritize energy efficiency (always pays), defer fuel-switch decisions |
| "Carbon removal technology" importance ↑ | Voluntary market maturing — credit quality improving | Wait to buy offsets, quality/price ratio improving |

---

## 5. Time Series & Data Requirements

### 5.1 Primary Time Series (Sybilion API Input)

| Data | Source | Minimum Points |
|---|---|---|
| Company monthly CO₂e emissions (by source) | Internal data / ERP | 40-120 |
| EU ETS allowance monthly price | ICE / EEX exchange data | 60+ (publicly available since 2005) |
| Monthly grid carbon intensity (by region) | Ember Climate / ENTSO-E | 40+ |
| Monthly renewable energy cost (solar/wind LCOE) | IRENA / BloombergNEF | 40+ |
| Voluntary carbon offset price index | Ecosystem Marketplace / Trove Research | 40+ |

### 5.2 Contextual Keywords

| Layer | Keywords | Purpose |
|---|---|---|
| **Regulatory** | "EU ETS reform", "CBAM implementation", "Fit for 55", "carbon border tax", "SEC climate disclosure" | Regulatory trajectory drives structural price shifts |
| **Market** | "renewable energy auction", "carbon credit supply shortage", "green premium", "PPA price index" | Market timing signals |
| **Technology** | "direct air capture scale-up", "green hydrogen cost curve", "battery storage deployment", "SMR licensing" | Technology cost curve inflection points |
| **Macro** | "recession probability", "industrial production index", "energy crisis", "natural gas storage level" | Economic cycle effects on emissions and prices |
| **Competitive** | "sectoral decarbonization target", "Scope 3 reporting mandate", "ESG fund flows" | Peer pressure and competitive dynamics |

### 5.3 Company Configuration (Static/Semi-Static)

```yaml
company:
  name: "European Manufacturing Corp"
  baseline_emissions_tons_co2e: 500000
  reduction_target_pct: 15
  target_year: 2027
  annual_reduction_budget_eur: 2000000

  emission_sources:
    - id: SCOPE_1_COMBUSTION
      tons_co2e_per_year: 180000
      reduction_options:
        - { name: "Boiler efficiency upgrade", cost_per_ton: 25, max_reduction_pct: 8 }
        - { name: "Natural gas → hydrogen blend", cost_per_ton: 65, max_reduction_pct: 15 }
        - { name: "Process electrification", cost_per_ton: 45, max_reduction_pct: 12 }

    - id: SCOPE_2_ELECTRICITY
      tons_co2e_per_year: 200000
      reduction_options:
        - { name: "Solar PPA", cost_per_ton: 30, max_reduction_pct: 25 }
        - { name: "Wind PPA", cost_per_ton: 28, max_reduction_pct: 20 }
        - { name: "Energy efficiency", cost_per_ton: 15, max_reduction_pct: 10 }

    - id: SCOPE_3_SUPPLIERS
      tons_co2e_per_year: 120000
      reduction_options:
        - { name: "Supplier engagement program", cost_per_ton: 40, max_reduction_pct: 5 }
        - { name: "Alternative low-carbon materials", cost_per_ton: 55, max_reduction_pct: 8 }

  carbon_exposure:
    eu_ets_allowances_needed_annually: 80000
    cbam_exposed_imports_tons_co2e: 30000
    voluntary_offset_purchases_annually: 10000
```

---

## 6. Example: Full Decision Flow

### Scenario: Mid-Sized European Manufacturer Planning Annual Carbon Strategy

**Sybilion API Input:**
- Time series: 60 months of EU ETS prices, company emissions by source, grid carbon intensity
- Keywords: `"EU ETS reform"`, `"CBAM phase-in"`, `"renewable energy auction results"`, `"natural gas price forecast"`, `"industrial production index"`

**Sybilion API Output (example):**
```json
{
  "forecast": {
    "eu_ets_price": {
      "month_1": { "value": 68, "confidence_band": [62, 74] },
      "month_3": { "value": 76, "confidence_band": [68, 88] },
      "month_6": { "value": 82, "confidence_band": [58, 110] },
      "month_12": { "value": 90, "confidence_band": [55, 130] }
    },
    "company_emissions_trajectory": {
      "month_6": { "value": 485000, "confidence_band": [460000, 510000] },
      "month_12": { "value": 470000, "confidence_band": [420000, 520000] }
    }
  },
  "drivers": [
    { "name": "EU ETS reform", "importance_m1": 0.25, "importance_m3": 0.40, "importance_m6": 0.45 },
    { "name": "Natural gas price forecast", "importance_m1": 0.30, "importance_m3": 0.20, "importance_m6": 0.10 },
    { "name": "CBAM phase-in", "importance_m1": 0.10, "importance_m3": 0.15, "importance_m6": 0.25 },
    { "name": "Renewable energy auction results", "importance_m1": 0.15, "importance_m3": 0.22, "importance_m6": 0.18 }
  ],
  "backtest": { "historical_accuracy": 0.71, "similar_regime_accuracy": 0.65 }
}
```

**CarbonEdge Decision Agent Output:**

```
══════════════════════════════════════════════════════════
  CARBONEDGE — ANNUAL CARBON STRATEGY RECOMMENDATIONS
  Company: European Manufacturing Corp
  Baseline: 500,000 tons CO₂e | Target: 15% reduction
  Budget: €2,000,000
  Generated: 2026-06-15
══════════════════════════════════════════════════════════

⚠️  KEY FINDING: Act Now on Allowances — Wait on Capital

─── STREAM A: CARBON MARKET TIMING ───────────────────────

EU ETS ALLOWANCE PURCHASES:
  → ACTION: BUY 60% NOW, LADDER REMAINDER
  → REASONING:
    • Price trajectory UPWARD: €68 → €90 (12-month forecast)
    • Month 1-3 confidence NARROW [€62-88] → high confidence in rise
    • Month 6+ confidence WIDE [€55-130] → too uncertain for full purchase
    • "EU ETS reform" driver importance INCREASING (0.25→0.45)
      → structural price floor rising, not cyclical
    • Backtest accuracy: 65% in this regime — moderate

  QUANTITIES:
    • Now:   48,000 allowances × €68 = €3,264,000
    • Month 3: 16,000 allowances (if price < €80)
    • Month 6: 16,000 allowances (re-evaluate based on band position)

  EXPECTED SAVINGS vs. buying all at year-end: €800K-1.2M

─── STREAM B: REDUCTION INVESTMENT OPTIMIZATION ──────────

DYNAMIC MAC CURVE — FORWARD-LOOKING RANKING:

  Rank  Option                    € per ton   Timing
  ────  ─────────────────────     ─────────   ──────
   1.   Energy efficiency          €15        NOW (always positive ROI)
   2.   Boiler efficiency upgrade  €25        NOW (low capex, fast payback)
   3.   Solar PPA                  €30        MONTH 3 (price dip forecast)
   4.   Wind PPA                   €28        MONTH 3 (auction results favorable)
   5.   Process electrification    €45        MONTH 6 (wait for gas price clarity)
   6.   Supplier engagement        €40        MONTH 6 (needs lead time)
   7.   H2 blend                   €65        DEFER (too expensive, technology immature)

  BUDGET ALLOCATION:
  ┌─────────────────────────────────────────────────────┐
  │ NOW (€520K):                                        │
  │   • Energy efficiency program: €150K (20K tons)     │
  │   • Boiler upgrade: €180K (14.4K tons)              │
  │   • EU ETS forward purchase (40%): €190K            │
  │                                                     │
  │ MONTH 3 (€880K):                                    │
  │   • Solar PPA signing: €600K (lock 5yr @ €52/MWh)  │
  │     WHY: Renewable auction driver rising (0.15→0.22)│
  │            PPA prices forecast to dip in Q3          │
  │   • Wind PPA option contract: €150K                 │
  │   • EU ETS tranche 2 (if price < €80): €130K        │
  │                                                     │
  │ MONTH 6 (€400K):                                    │
  │   • Process electrification phase 1: €250K          │
  │     WHY: Gas price importance declining (0.30→0.10) │
  │            → clearer picture for fuel-switch ROI     │
  │   • Supplier engagement launch: €100K               │
  │   • EU ETS tranche 3: €50K                          │
  │                                                     │
  │ RESERVE (€200K):                                    │
  │   • Offset purchases if trajectory off-target        │
  │   • Trigger: emissions > 440K tons at month 9        │
  └─────────────────────────────────────────────────────┘

  PROJECTED OUTCOME:
    • 82K tons CO₂e reduced (16.4% — exceeds 15% target)
    • Blended cost: €24.4/ton (vs. industry avg €38/ton)
    • vs. naive approach: saves €210K

─── STREAM C: PRODUCTION SCHEDULING ──────────────────────

  → RECOMMENDATION: Schedule boiler maintenance in Month 4
  → REASONING:
    • Production demand forecast dips in month 4 (from internal data)
    • Grid carbon intensity is FORECASTED to peak in month 4
      (summer cooling demand strains grid)
    • Maintenance during this period maximizes emission reduction
      impact AND minimizes production disruption
    • Estimated additional reduction: 2,500 tons CO₂e

─── CBAM EXPOSURE ANALYSIS ───────────────────────────────

  → CURRENT EXPOSURE: 30,000 tons CO₂e in imported materials
  → CBAM CERTIFICATE PRICE FORECAST: Tracks EU ETS (€68→€90)
  → EXPOSED COST: €2.04M → €2.7M over next 12 months
  → RECOMMENDATION:
    • Pre-qualify 2 low-carbon alternative suppliers (Month 1-3)
    • Pre-purchase 6 months of carbon-intensive raw materials
      before CBAM certificate price rises
    • Savings potential: €180-350K if alternative suppliers qualify

─── MONITORING TRIGGERS ──────────────────────────────────

  🔍 If EU ETS price exceeds €88 before month 3 → accelerate purchases
  🔍 If EU ETS price drops below €60 → defer purchases, buy spot
  🔍 If "CBAM phase-in" driver importance exceeds 0.30 → escalate supplier switching
  🔍 If emissions trajectory upper bound exceeds 440K tons at month 6 → deploy reserve into offsets
  🔍 Re-evaluate full allocation in 90 days

─── DRIVER IMPORTANCE ACROSS HORIZONS ────────────────────

  EU ETS Reform:       ██████████████░░  0.25→0.45  ↑ INCREASING
  Natural Gas Price:   ████████░░░░░░░░  0.30→0.10  ↓ DECLINING
  CBAM Phase-In:       ████░░░░░░░░░░░░  0.10→0.25  ↑ INCREASING
  Renewable Auctions:  █████░░░░░░░░░░░  0.15→0.18  → STABLE

  KEY INSIGHT: "EU ETS reform" and "CBAM" are structural drivers
  that grow in importance — this is NOT a cyclical price movement.
  Delaying all purchases is risky; the floor is rising.
══════════════════════════════════════════════════════════
```

---

## 7. Adaptive Behavior — The Sunday Live Demo

### The Challenge Scenario

**Jury introduces mid-run assumption shift:** *"The EU has just announced an accelerated ETS reform — the emissions cap will be cut 20% faster than planned, starting next quarter. Carbon analysts project allowance prices could spike to €120/ton within 6 months."*

### How CarbonEdge Adapts

```
══════════════════════════════════════════════════════════
  ⚠️  REGULATORY SHIFT DETECTED — RECALCULATING STRATEGY
  Trigger: EU ETS cap cut accelerated 20% (effective next quarter)
══════════════════════════════════════════════════════════

DRIVER IMPORTANCE SHIFTS:

  "EU ETS reform":     0.45 → 0.72  ⚠️ DOMINANT
  "CBAM phase-in":     0.25 → 0.35  ↑ (CBAM tracks ETS)
  "Natural gas price":  0.10 → 0.05  ↓ (less relevant now)
  "Renewable auctions": 0.18 → 0.22  → (more valuable as offset)

CHANGED DECISIONS:

  ALLOWANCE PURCHASES:
    BEFORE: Buy 60% now, ladder remainder
    NOW:    Buy 80% IMMEDIATELY, all remaining by month 2
    WHY:    Price forecast revised: €68 → €120 (was €90)
            Confidence band NARROWED after policy confirmation
            Structural floor rising faster than anticipated
            Additional cost of waiting: €2.1M on remaining 32K allowances

  REDUCTION INVESTMENTS:
    BEFORE: Solar PPA in month 3, electrification in month 6
    NOW:    Solar PPA IMMEDIATELY, electrification moved to month 4
    WHY:    Every ton reduced internally saves €120 (new ETS price)
            Previously saved €90 — ROI on ALL reduction projects improved
            MAC curve re-ranked: H2 blend now viable at €65/ton
            (was too expensive at €90 ETS, economical at €120)

    NEW MAC CURVE RANKING:
     1. Energy efficiency        €15/ton  (saves €120) → ROI: 700%
     2. Boiler efficiency        €25/ton  (saves €120) → ROI: 380%
     3. Wind PPA                 €28/ton  (saves €120) → ROI: 329%
     4. Solar PPA                €30/ton  (saves €120) → ROI: 300%
     5. Supplier engagement      €40/ton  (saves €120) → ROI: 200%
     6. Process electrification  €45/ton  (saves €120) → ROI: 167%
     7. H2 blend                 €65/ton  (saves €120) → ROI: 85% ← NOW VIABLE

  BUDGET REALLOCATION:
    • Shift €200K from reserve → immediate allowance purchase
    • Accelerate solar PPA signing (lock price before renewable demand surge)
    • Add H2 blend feasibility study to month 4 pipeline

  CBAM STRATEGY:
    BEFORE: Pre-qualify suppliers over 3 months
    NOW:    Emergency supplier qualification — complete in 6 weeks
    WHY:    CBAM certificate price tracks revised ETS → €120/ton exposure
            Each month of delay = €300K additional import cost

REVISED OUTCOME:
    • Projected reduction: 95K tons (19% — exceeds 15% target by 4pp)
    • Blended cost: €26.8/ton (up from €24.4 due to accelerated timeline)
    • vs. NAIVE approach (did nothing different): SAVES €3.4M
    • vs. OLD strategy (if we hadn't adapted): SAVES additional €1.2M
══════════════════════════════════════════════════════════
```

**Why this demo works:** The jury sees a complete strategy, a dramatic assumption shift, and a recalculated plan that:
1. Changes the **timing** of every action (accelerates everything)
2. Changes the **ranking** of reduction options (H2 blend becomes viable)
3. Changes the **budget allocation** (dips into reserve, shifts priorities)
4. Shows **exactly why** (driver importance shifts, revised price forecasts, recalculated ROI)
5. Quantifies the **value of adapting** (€1.2M saved vs. not updating the plan)

---

## 8. Technical Implementation Plan (36h Scope)

### Day 1 — Foundation (Hours 0-12)

| Task | Details |
|---|---|
| **Define company profile** | Create a realistic mid-sized manufacturer with 3 emission sources, 7 reduction options, €2M budget |
| **Source time series data** | EU ETS prices (ICE/EEX public data), grid carbon intensity (Ember/ENTSO-E), company emissions (synthetic but realistic) |
| **Build Sybilion API integration** | Send time series + keywords, receive forecasts for ETS price, emissions trajectory, grid intensity |
| **Build MAC curve engine** | Static first: rank reduction options by cost-per-ton. Then: forward-looking with energy price forecasts |
| **Validate first forecast** | Understand driver scores — does "EU ETS reform" importance correlate with actual policy events? |

### Day 2 — Decision Agent (Hours 12-24)

| Task | Details |
|---|---|
| **Implement budget allocator** | Split fixed budget across time and options based on forecast confidence and severity |
| **Build carbon market timing logic** | Buy/wait/ladder logic based on price trajectory + confidence band |
| **Implement CBAM exposure calculator** | Link ETS price forecast to import cost exposure, trigger supplier switching |
| **Build production scheduler** | Match maintenance windows to low-demand, high-carbon-intensity periods |
| **Backtest validation** | Run against 2022-2023 ETS price spike — would the agent have recommended buying early? |
| **Build structured output** | Formatted decision cards with reasoning, cost estimates, triggers |

### Day 3 — Adaptive + UI (Hours 24-36)

| Task | Details |
|---|---|
| **Implement adaptive recalculator** | Detect assumption/regulatory shifts, re-run all three streams, show before/after |
| **Build visualization** | MAC curve, confidence band chart, driver importance over horizon, budget allocation timeline |
| **Stress-test with scenarios** | Feed: ETS price spike, CBAM acceleration, renewable price crash, gas crisis |
| **Write summary document** | Key technical challenges, solutions, architecture decisions |

---

## 9. Stretch Goals

1. **Portfolio optimization** — when multiple reduction options compete for the same budget, solve as a knapsack problem with probabilistic returns
2. **Scope 3 propagation** — model how supplier emissions forecasts cascade through the supply chain, triggering upstream reduction investments
3. **Real-time ESG score simulator** — show how each decision affects the company's ESG rating and cost of capital
4. **Scenario comparison dashboard** — side-by-side: aggressive vs. conservative reduction strategies under the same forecast
5. **Leonardo GPU stress-testing** — run 1,000+ regulatory scenarios (different ETS reform speeds, CBAM rates, carbon tax introductions) to find where the strategy breaks

---

## 10. Why This Scores Well

| Jury Dimension | How CarbonEdge Delivers |
|---|---|
| **Decision change** | The agent's recommendations are fundamentally different from "measure emissions and set a target." It produces time-phased budget allocations, confidence-aware purchase timing, and dynamically-ranked reduction options. A naive baseline ("buy all allowances now, invest in cheapest reductions first") would cost €200K-3M more. |
| **Visible reasoning** | Every recommendation includes: MAC curve ranking with forward-looking costs, confidence band visualization for carbon prices, driver importance shifts, backtest support, and explicit cost/emissions impact calculations. |
| **Adaptive behavior** | When regulatory assumptions shift, the agent recalculates: MAC curve re-ranks (options become viable/unviable), budget allocation changes, timing accelerates or defers. The before/after delta is explicit. |
| **Commercial impact** | Carbon management is a €200B+ market (ETS + voluntary + CBAM). Companies spend millions on allowances and reduction investments — timing and prioritization decisions directly affect the bottom line. |
| **Originality** | Most carbon tools are compliance/reporting platforms. A forward-looking decision agent with dynamic MAC curves, confidence-aware budget allocation, and regulatory-adaptive behavior is genuinely novel. |
| **Technical sophistication** | Three parallel decision streams, forward-looking MAC curve construction, confidence-band-aware budget optimization, scenario stress-testing, and backtest-validated logic. Not an LLM wrapper. |

---

## 11. Data Sources (All Public)

| Data Type | Source | URL |
|---|---|---|
| EU ETS allowance prices | ICE / EEX / Ember Climate | [ember-climate.org](https://ember-climate.org) |
| Grid carbon intensity | Ember / ENTSO-E | [ember-climate.org/data](https://ember-climate.org/data) |
| Renewable energy costs | IRENA | [irena.org/costs](https://www.irena.org/Energy-Transition/Technology/Costs) |
| Company emissions data | Internal ERP / CDP disclosures | Company-specific |
| CBAM methodology | European Commission | [taxation-customs.ec.europa.eu](https://taxation-customs.ec.europa.eu/carbon-border-adjustment-mechanism_en) |
| Voluntary carbon prices | Ecosystem Marketplace | [ecosystemmarketplace.com](https://www.ecosystemmarketplace.com) |
| Regulatory calendar | EU Official Journal | [eur-lex.europa.eu](https://eur-lex.europa.eu) |

---

## 12. Team Name & Positioning

- **Product name:** CarbonEdge
- **Tagline:** "Reduce smarter, not harder"
- **Hackathon positioning:** We don't measure your carbon. We tell you what to do about it — at the right time, at the right price.

---

## 13. Analysis of the Idea

### Strengths

1. **Direct alignment with the brief's philosophy.** The assignment explicitly states: *"Wide confidence bands are not noise to be ignored. They are the most decision-relevant part of the output, because they encode when not to act."* CarbonEdge's core innovation — the confidence-aware budget allocator — directly operationalizes this principle. When the carbon price forecast band is wide, the agent says "ladder your purchases, don't commit." When narrow, it says "buy now."

2. **Three independent decision streams = rich demo.** The jury sees three different types of decisions (market timing, investment prioritization, production scheduling) all responding to the same forecast. This demonstrates breadth without being unfocused.

3. **EU regulatory context = built-in urgency.** CBAM phasing in from 2026, ETS reform accelerating, ESG disclosure mandates tightening — there's a real, immediate business need. This isn't a hypothetical.

4. **MAC curve is a proven concept made forward-looking.** The Marginal Abatement Cost curve is a standard tool in carbon economics — but it's always static (based on current costs). Making it forward-looking using Sybilion's forecasts is a genuine innovation.

5. **Backtest validation is natural and compelling.** You can run the agent against the 2022 ETS price spike (€40 → €100) and show: "Here's what the agent would have recommended in January 2022 vs. what companies actually did." The savings are quantifiable.

6. **Adaptive behavior is dramatic.** A regulatory shift (ETS reform, CBAM acceleration) changes EVERYTHING — allowance timing, reduction rankings, budget allocation, supplier strategy. The before/after delta is large and easy to demonstrate.

### Weaknesses & Risks

1. **Company-specific data requirement.** Real emissions data is internal and confidential. For the hackathon, you'll need to create a realistic synthetic company profile. This is fine for a demo but could be challenged as "not real data."
   - **Mitigation:** Use publicly available CDP (Carbon Disclosure Project) data from real companies as the basis for your synthetic profile. It's anonymized-aggregate but realistic.

2. **Three streams may be too much for 36h.** Building MAC curves, market timing, AND production scheduling is ambitious.
   - **Mitigation:** Scope to two streams for MVP (market timing + MAC curve). Production scheduling is a stretch goal. The brief says "scoping is part of the technical sophistication."

3. **Carbon prices are influenced by policy, not just historical patterns.** The Sybilion API forecasts based on time series + keywords, but a sudden policy announcement (like the demo scenario) is inherently unpredictable.
   - **This is actually a strength for the demo** — it's exactly the kind of mid-run assumption shift the brief wants you to handle. The point is not that the agent predicted the policy change, but that it adapts sensibly when the forecast is updated.

4. **The "competitive" aspect is underdeveloped.** The brief mentions competitive dynamics, but the current design focuses on internal optimization.
   - **Mitigation:** Add a lightweight competitive layer — "Your carbon intensity per revenue is in the 60th percentile of your sector. Achieving the 15% reduction target moves you to the 40th percentile, qualifying for ESG-mandated procurement contracts worth an estimated €X."

5. **Keyword selection is critical and non-trivial.** The brief states: *"Keyword quality is critical."* Picking the wrong keywords for carbon forecasting will produce garbage forecasts.
   - **Mitigation:** Spend significant time in Day 1 on keyword research. Test multiple keyword sets against historical data to see which produces the most accurate backtest.

### Opportunity Assessment

| Dimension | Rating | Notes |
|---|---|---|
| Hackathon fit | ★★★★★ | 36h scope, clear demo, dramatic adaptive behavior |
| Originality | ★★★★☆ | Forward-looking MAC curve + confidence-aware budget allocation is novel. Carbon tools exist but are backward-looking. |
| Technical depth | ★★★★☆ | Three decision streams, MAC curve optimization, scenario engine. Could go deeper with portfolio optimization. |
| Business viability | ★★★★★ | Real pain point, willing buyers, growing regulatory pressure. Post-hackathon product is viable. |
| Data availability | ★★★☆☆ | ETS prices and grid intensity are public. Company emissions data requires synthetic construction. |
| Demo impact | ★★★★★ | The before/after adaptive demo is dramatic and easy to visualize. |

### Verdict

**CarbonEdge is a strong hackathon choice.** It scores highly on originality (forward-looking vs. backward-looking carbon tools), has a dramatic adaptive demo (regulatory shifts change everything), and the technical work is substantive (MAC curves, budget optimization, confidence-aware decision logic). The main risk is scope — three decision streams in 36h is tight. Recommend committing to two streams for MVP and making the third a stretch goal.

The idea also has genuine post-hackathon commercial potential — companies are actively looking for tools that go beyond compliance reporting to actual carbon decision support.
