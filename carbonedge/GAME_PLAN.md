# CarbonEdge — Game Plan v2

**Based on analysis of 9 arXiv papers:**
1. Bastianin et al. (2024) — What Drives the European Carbon Market? [2402.04828]
2. Ren et al. (2025) — Hybrid DL Carbon Price Forecasting [2511.04988]
3. Maciejowski & Leonelli (2025) — Drivers of EU Carbon Futures via Bayesian Networks [2505.10384]
4. Dai et al. (2020) — Impact of EPU on Volatility of European Carbon Market [2007.10564]
5. Friedrich et al. (2019) — Explosive Trend in EU ETS: Fundamentals or Speculation? [1906.10572]
6. Abate et al. (2021) — Contracts in Electricity Markets under EU ETS: Stochastic Programming [2104.15062]
7. Hong et al. (2026) — Enterprise Carbon Emissions via Causal Inference [2602.00775]
8. Chakraborty (2025) — EU ETS Trade Dynamics [2510.22341]
9. Salvagnin (2024) — Review of the EU ETS Literature: Bibliometric Perspective [2409.01739]

---

## What This Agent Does

A company says: "I must buy 10,000 EUA certificates this year." CarbonEdge answers:

> Buy 4,000 tons now (EUR 83/ton). Ladder 3,000 tons in month 4 (EUR 79-91 range). Reserve 3,000 tons for month 8 (EUR 76-95). Expected savings: EUR 12,400 vs buying all today. Confidence: NARROW (regime stable, EPU normal). Reasoning: coal demand rising (bullish driver → front-load), MSR absorbing 275 Mt/yr (structural tightening), Sybilion bands tightening (confidence increasing). CAUTION: if EPU index crosses 150, freeze purchases and re-evaluate.

This is a PROCUREMENT DECISION AGENT, not a market timing tool.

---

## Architecture: Forecast Enhancement + Procurement Optimization

```
                        SYBILION FORECAST ENGINE
                        (point forecast + CI bands
                         + driver importance + backtest)
                                |
                                v
        +-----------------------------------------------+
        |         ENHANCEMENT LAYER                       |
        |  (The 9 papers feed THIS layer — they adjust    |
        |   Sybilion's output, don't compete with it)     |
        |                                                |
        |  A. Regime Detection (Friedrich 2019)           |
        |     - PSY bubble test → flag explosive regimes  |
        |     - CUSUM on forecast residuals → bias detect |
        |     - FOCuS on raw price → structural breaks    |
        |     Output: GREEN / YELLOW / RED stability     |
        |                                                |
        |  B. EPU Volatility Modulator (Dai 2020)         |
        |     - European EPU index → volatility forecast  |
        |     - Global EPU → stronger effect              |
        |     Output: volatility_amplifier (0.5x-2.0x)   |
        |                                                |
        |  C. Driver Filter (Maciejowski & Leonelli 2025) |
        |     - Coal, MSCI Energy → #1/#2 daily drivers   |
        |     - Gas/coal fuel-switch ratio → modulation   |
        |     Output: which Sybilion drivers to weight    |
        |                                                |
        |  D. Structural Context (Bastianin 2024)         |
        |     - Cap schedule + emissions + MSR balance    |
        |     - PP+/PP- (price pressure monitoring)       |
        |     - DPI (demand pressure index)               |
        |     Output: structural backdrop for reasoning   |
        +-----------------------------------------------+
                                |
                                v  (adjusted forecast bands)
        +-----------------------------------------------+
        |         PROCUREMENT OPTIMIZER                   |
        |  (Abate 2021 — CVaR stochastic programming)     |
        |                                                |
        |  Input:  adjusted_forecast_bands                |
        |          total_tons_needed: 10,000              |
        |          risk_tolerance: 0.95 (CVaR alpha)      |
        |          budget_eur: 1,000,000                  |
        |          purchase_windows: [now, m3, m6, m9]    |
        |                                                |
        |  Output: buy_plan = [                           |
        |    {horizon: now,  tons: 4000, eur: 83},        |
        |    {horizon: m4,   tons: 3000, eur: 79-91},    |
        |    {horizon: m8,   tons: 3000, eur: 76-95},    |
        |  ]                                             |
        |  expected_cost_each: EUR 826,000                |
        |  expected_savings: EUR 12,400 vs spot           |
        +-----------------------------------------------+
```

### Why this ISN'T 3 competing forecasts

**Old (wrong) approach:**
```
FUNDAMENTAL → BUY    ┐
SYBILION    → WAIT    ├→ ensemble → ???  (fistfight)
REGIME      → FREEZE  ┘
```

**Correct approach:**
```
SYBILION → forecast bands ──→ ENHANCEMENT → adjusted bands ──→ OPTIMIZER → buy plan
```

The enhancement layer doesn't say "BUY" or "DEFER". It says:
- "The regime is stable → trust Sybilion's bands" (narrow CI)
- "EPU is spiking → widen Sybilion's bands by 1.5x" (wider CI → ladder more)
- "Coal is rising → front-load purchases" (bias toward early buying)
- "MSR is absorbing 275 Mt → structural backdrop is tightening" (context in reasoning text)

The procurement optimizer then takes the adjusted bands and computes the optimal purchase schedule.

---

## Enhancement Layer — Detailed Design

### A. Regime Detection (Friedrich 2019 + existing FOCuS/CUSUM)

```
Input:  Sybilion forecast, historical prices, EPU index
Output: regime = GREEN | YELLOW | RED
        confidence_multiplier = 1.0 | 1.5 | 3.0

GREEN  → trust Sybilion bands, use narrow CI for optimization
YELLOW → widen Sybilion bands 1.5x, increase ladder steps
RED    → widen Sybilion bands 3.0x, recommend FREEZE + re-evaluate
```

Methods from Friedrich 2019:
- PSY (Phillips-Shi-Yu) bubble test: explosive root in price → RED
- Time-varying coefficient regression: structural instability → YELLOW
- Crash odds prediction: probability of -20% move within 3 months

Existing components to keep:
- FOCuS on raw price (structural breaks in volatility)
- CUSUM on forecast residuals (systematic bias detection)

### B. EPU Volatility Modulator (Dai 2020)

```
Input:  European EPU index (news-based, Baker-Bloom-Davis)
        Global EPU index
Output: volatility_multiplier (0.8x to 2.0x)

EPU < 100  → normal: multiplier = 1.0
EPU 100-150 → elevated: multiplier = 1.3
EPU > 150   → crisis: multiplier = 1.8
EPU spike (+2std above 12m rolling mean) → trigger BUY_NOW advisory
```

Key finding from Dai et al.: Global EPU is a STRONGER predictor of EUA volatility
than European EPU. Both exacerbate LONG-TERM volatility (GARCH-MIDAS long-run component).

### C. Driver Filter (Maciejowski & Leonelli 2025)

```
Input:  Daily coal API2, TTF gas, MSCI Europe Energy, Sybilion driver_importance
Output: driver_weights → which Sybilion horizon-scores to amplify

Coal rising + MSCI Energy rising  →  front-load purchases
Coal falling + MSCI Energy falling →  back-load purchases
Gas/coal ratio > 1.5x median       →  fuel-switch bearish, defer
Gas/coal ratio < 0.5x median       →  fuel-switch bullish, accelerate
```

Key finding: 95%+ of EUA-relevant info is CONTEMPORANEOUS — these drivers don't
predict future moves, they tell you whether the CURRENT environment supports
Sybilion's forecast. Use them as a REALITY CHECK, not a competing forecast.

### D. Structural Context (Bastianin 2024)

```
Input:  Cap schedule, verified emissions (latest known year), MSR model
Output: structural_balance (surplus/shortage in Mt)
        pp_plus, pp_minus (price pressure indicators)
        dpi (demand pressure index)
        narrative text for reasoning

Cap 2026 = 1,183 Mt, Ems(2024) = 1,034 Mt, MSR intake ~287 Mt
→ Effective balance = -137 Mt (SHORTAGE)
→ Structural backdrop: TIGHTENING (cap declining 93 Mt/yr, MSR absorbing)
```

Role: NOT a timing signal. Provides the "story" behind the recommendation.
The text "MSR is absorbing 275 Mt/yr from the market" appears in the reasoning
output, not as a trading rule. The optimizer uses adjusted Sybilion bands for
position sizing; the structural context explains WHY the optimizer front-loads.

---

## Procurement Optimizer (Abate 2021 — CVaR Model)

### Problem Formulation

```
Given:
  - Adjusted forecast: price ~ N(mu_h, sigma_h^2) for each horizon h ∈ {1..12}
  - Total quantity needed: Q tons
  - Purchase windows: W = {now, m3, m6, m9, m12}
  - Risk tolerance: alpha = 0.95 (5% worst-case)

Find:
  - Purchase plan: q_w for each window w ∈ W, sum(q_w) = Q
  - That minimizes: expected total cost + lambda * CVaR(cost)

Subject to:
  - Budget constraint: sum(q_w * p_w_upper) < available_budget
  - Minimum front-load: q_now >= 0 (none forced)
```

### Decision Logic (Abate et al. 2021 §3)

```
1. For each window w, extract Sybilion bands: [mu_w, ci_low_w, ci_high_w]
2. Apply enhancement adjustments:
   - Regime multiplier → sigma_w *= confidence_multiplier
   - EPU multiplier     → sigma_w *= volatility_multiplier
   - Driver direction   → mu_bias (shift mean up/down by 0.5 * sigma)
3. Run CVaR optimization:
   - Draw 10,000 monte-carlo paths from adjusted distributions
   - For each path, compute total procurement cost
   - Minimize: (1-lambda) * mean_cost + lambda * CVaR_alpha(cost)
   - CVaR_alpha = average cost in worst (1-alpha)% of paths
4. Output purchase plan with expected cost, savings vs spot, and worst-case bound
```

### Laddering Heuristic (fallback when optimizer is heavy)

```
When bands are WIDE (coefficient of variation > 0.3):
  q_now = 0.40 * Q      # Buy 40% now (lock in)
  q_m3  = 0.30 * Q      # Ladder 30% at month 3
  q_m6  = 0.30 * Q      # Reserve 30% for month 6

When bands are NARROW (CV < 0.15):
  If trend UP   →  q_now = 0.70 * Q, ladder rest
  If trend DOWN →  q_now = 0.20 * Q, back-load rest
  If trend FLAT →  q_now = Q (buy all, no timing benefit)

When REGIME = RED:
  q_now = 0.25 * Q      # Minimal buy to avoid compliance risk
  FREEZE rest until regime clears
```

---

## Files — What Exists, What to Build

```
carbonedge/                          STATUS
  fundamental/
    cap_schedule.py                  EXISTS (fixed bugs, 2013-2030)
    msr_model.py                     EXISTS (fixed bugs, sequential stepping)
    data_sources.py                  EXISTS (fixed filters, GB post-Brexit)
    chow_lin.py                      EXISTS (warnings added)
    balance_model.py                 EXISTS (critical bugs fixed)
    driver_monitor.py                EXISTS (coal/MSCI/gas ratio)
    __init__.py                      EXISTS

  decision_agent.py                  REFACTOR — remove competing forecast logic
  regime_detector.py                 EXISTS — KEEP (FOCuS + CUSUM)

  enhancement/                       NEW MODULE
    epu_modulator.py                 NEW — Dai 2020 EPU → volatility multiplier
    regime_enhancer.py               NEW — Friedrich 2019 bubble test
    driver_filter.py                 NEW — Maciejowski 2025 driver weights
    structural_context.py            NEW — Bastianin 2024 balance story

  procurement/                       NEW MODULE
    optimizer.py                     NEW — CVaR stochastic programming (Abate 2021)
    ladder_rules.py                  NEW — Heuristic fallback ladder

  main.py                            REFACTOR — wire enhancement → procurement
  output.py                          REFACTOR — show adjusted bands + buy plan
```

---

## Evaluation Criteria (from hackathon brief)

| Criterion | How We Address It |
|-----------|-------------------|
| **Decision change** | CVaR optimizer produces concrete buy plan, not just BUY/DEFER. Expected cost savings in EUR vs buying all at spot. |
| **Visible reasoning** | Output shows: regime status (why bands widened), EPU level (volatility amplifier), driver state (front/back-load bias), structural context (MSR tightening story). NOT a black box. |
| **Adaptive behavior** | When EPU spikes → volatility_multiplier increases → optimizer back-loads → output explains "EPU surged to 180, volatility expected to rise, deferring purchases." When regime flips RED → FREEZE + re-evaluate advisory. |
| **Backtest discipline** | Validate optimizer against historical Sybilion backtest data. Show: "Optimal ladder saved EUR X vs buying all at spot over Y historical years." |
| **Forecast changes decision** | Before: "Sybilion says EUR 83 in 6 months → guess." After: "Sybilion says EUR 83 in 6 months + EPU normal + regime GREEN + coal bullish → buy 40% now, ladder rest. Expected savings EUR 12,400." |

---

## Implementation Order

### Step 1: Enhancement Layer (what we do now)
1. Write `epu_modulator.py` — fetch EPU index, compute multiplier
2. Write `regime_enhancer.py` — wire Friedrich bubble detection + existing FOCuS/CUSUM
3. Wire enhancement into `decision_agent.py` as band adjusters (not override signals)

### Step 2: Procurement Optimizer
4. Write `procurement/optimizer.py` — CVaR monte-carlo optimization
5. Write `procurement/ladder_rules.py` — heuristic fallback
6. Wire optimizer into `decision_agent.py`

### Step 3: Output & Demo
7. Refactor `output.py` — show adjusted bands, EPU state, regime, buy plan
8. Refactor `main.py` — pull input (tons_needed, budget) from config or CLI
9. Demo script: show agent adapting to EPU spike mid-run

---

## Key Design Rules (from papers + postmortem)

1. **Sybilion is the forecast. Everything else ENHANCES it.** No alternative forecast. No competing "BUY vs WAIT" signals. Enhancement produces adjusted confidence bands; the optimizer acts on those bands.

2. **Regime detection is not a buy/sell rule.** It's a CONFIDENCE ADJUSTER. GREEN → trust Sybilion. YELLOW → widen bands 1.5x. RED → widen 3x + advisory.

3. **Fundamental model = reasoning text, not signal.** The cap-emissions-MSR balance explains WHY we front-load or back-load. It does not override the optimizer.

4. **The output is a procurement plan, not a forecast.** The user sees: "Buy X tons now at ~EUR Y, X tons in month 3 at ~EUR Z, expected savings = EUR W." That's what a compliance buyer actually needs.

5. **Adaptation is the differentiator.** When EPU spikes mid-demo, the agent visibly shifts from "buy 40% now" to "hold, EPU crisis, re-evaluate." This is the Sunday demo capability.
