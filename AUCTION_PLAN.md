# CarbonEdge — Execution Optimizer Plan (integriert mit Florians Backend)

> **Reframe:** Aus „BUY/WAIT/LADDER" + OTC-Match wird ein **Procurement-/Execution-Optimizer**, der pro Tranche entscheidet **Kanal (Auktion / Spot / RFQ / OTC) + Tag + Maximalpreis** — gegroundet auf Sybilions monatlichem EUA-Forecast (Band + Treiber), re-routet unter Shocks.
>
> **Hackathon-Hebel (Sybilion-Jury):** Decision change · Visible reasoning · Adaptiv beim Mid-Run-Shock.
> **Demo-Shock:** **MSR kürzt Auktionsvolumen 20 %** → Primärmarkt dünn → Agent routet von Auktion auf Spot/RFQ und zieht vor.

---

## 0. STATUS — was schon da ist (Florians Backend, Repo `zero_one_hackathon`)

Florian hat die komplette Infra + Daten + Sybilion-Anbindung gebaut. **Die Decision-Engine ist die bewusst freigelassene Andockstelle — genau dort kommt unsere Arbeit rein.**

| Schon fertig ✅ | Wo |
|---|---|
| FastAPI, 13 Endpoints, CORS offen | `src/api/` |
| Sybilion-Wrapper (Cache + Mock-Fallback) | `src/sybilion/client.py` |
| Keyword-Sets (4 Layer) | `src/sybilion/keywords.py` |
| **3 Firmen — `greenchem` = unser Demo-Profil** (485k/400k/20k → SHORT 65k) | `data/mock/companies.json` |
| Auktionskalender (5 Einträge Juni 2026, CAP3/DE/PL, mit `expected_clearing_price`) | `data/mock/auction_calendar.json` |
| 4 Verkäuferangebote (OTC/Broker, mit `counterparty_rating`) | `data/mock/sell_offers.json` |
| **Echte EUA-Monatspreise Jan 2021–Mai 2026 (65–67 Punkte)** | `data/raw/eua_prices_monthly.json` |
| Tägliche Carbon-Futures 2015–2026 | `data/raw/carbon_emission_futures_data.csv` |
| Fertiger Sybilion-Request (`soft_horizon: 6`) | `data/prepared/eua_forecast_request.json` |

| Noch offen ❌ | Wer |
|---|---|
| **Decision-Engine `src/engine/`** | **WIR** |
| Frontend an Backend anbinden | Frontend liegt in Repo `zero_one_hack_01` (s. §7) |

**Sybilion-Konto:** e909b765, Tier 4, ~€10k Grant — **läuft 01.06.2026 ab** (also nur noch ~heute/morgen). Real-Call früh machen + cachen. Braucht `pip install pandas` + `SYBILION_API_TOKEN`.

---

## 1. WICHTIGE RANDBEDINGUNGEN (durch die Daten gesetzt)

- **Horizont = 6 Monate** (nicht 12!). Sybilion verlangt ≥120 Punkte für 7–12 Monate; wir haben nur 65 → **6-Monats-Forecast ist die korrekte, datengedeckte Wahl.** Auktionskalender (Juni 2026) und Forecast-Start (Juni 2026) passen zusammen.
- **Sybilion ist monatlich, nicht pro Auktionstag.** Tagesgenauer Clearing-Preis kommt aus unserem **deterministischen Auktions-Mikromodell** (§4) auf Basis des Monatsniveaus. → Das *ist* die „substantielle eigene Logik", die das Briefing verlangt. Im Demo offen so sagen.
- **`expected_clearing_price` in der JSON ist hardcoded** → unsere Engine **leitet ihn aus dem Forecast ab** (damit er unter Shocks mitwandert); JSON-Wert nur als Fallback.

---

## 2. Architektur — Datenfluss

```
[FastAPI Backend — DA]                         [ENGINE — WIR bauen src/engine/]
 /companies, /companies/{id}/position  ─┐
 /market/eua-prices  ───────────────────┤
 /market/auctions, /market/sell-offers ─┤
 /forecasts/sybilion (Wrapper+Cache) ───┘──►  CarbonEdgeAgent.run(company, position, forecast, src)
                                                   │
   POST /decisions/run  ───────────────────────────┤   1) Position → Defizit (SHORT-Menge)
   POST /decisions/scenario ────────────────────────┤   2) Clearing-Mikromodell pro (Kanal,Tag)
        (event = msr_auction_cut)                    │   3) Execution-Optimizer (greedy, risk-adj.)
                                                      │   4) ExecutionPlan + Baselines + Rationale
                                                      ▼
   ScenarioManager.run_scenario(... event ...)  ──► MSR-Transform → Re-Run → Vorher/Nachher-Delta
```

**Der Adapter `src/api/services/decision_adapter.py` erwartet exakt:**
```python
from src.engine.agent import CarbonEdgeAgent, ScenarioManager
CarbonEdgeAgent().run(company, position, forecast, forecast_source) -> decision: dict
ScenarioManager(agent).run_scenario(company, position, forecast, event, forecast_source) -> result: dict
```
Sobald `src/engine/agent.py` mit dieser Signatur existiert, schalten `/decisions/run` und `/decisions/scenario` automatisch von `mock_engine_not_connected` auf echt. **Kein Backend-Code muss geändert werden** (außer: MSR-Event zur Liste hinzufügen, s. §6).

**Hinweis zum `forecast`-Shape:** Adapter liefert bei `sybilion` `{status,mode,forecast,signals,backtest}`, bei `cache` `{forecast,signals,backtest}`. Engine muss beide normalisieren (einfach `forecast.get("forecast", forecast)`).

---

## 3. Datenmodell (in `src/engine/`)

```python
@dataclass
class Channel:
    key: str            # "AUCTION" | "SPOT" | "RFQ" | "OTC"
    spread_to_spot: float   # €/t vs. Sekundär-Spot: AUCTION ~-0.05, SPOT +0.03, RFQ +0.15, OTC +0.10
    fee_per_t: float
    fill_prob: float        # SPOT 1.0, AUCTION ~0.8, RFQ 0.95, OTC ~0.9
    min_lot: float
    max_lot_per_event: float

@dataclass
class SupplyEvent:           # konkrete Kaufgelegenheit
    date: date; channel: str
    available_volume: float  # Auktion: volume×Teilnahmeanteil ; Spot: groß ; OTC/RFQ: aus sell_offers
    counterparty_rating: float = 1.0
    expected_price: float = 0.0; price_low: float = 0.0; price_high: float = 0.0

@dataclass
class Allocation:
    date: date; channel: str; volume: float
    expected_price: float; max_bid: float | None
    eff_cost: float; reason: str
```
- **Auktion-Events** ← `/market/auctions` (auction_date, volume, auction_type).
- **OTC/RFQ-Events** ← `/market/sell-offers` (settlement_method OTC→OTC, BROKER→RFQ; volume, price_per_eua, valid_until, counterparty_rating).
- **Spot** = synthetisches kontinuierliches Event je Monat aus Forecast-p50 + halber Spread, fill_prob 1.0.

---

## 4. Clearing-Preis-Mikromodell

Für Event an Tag `d` in Monat `m`:
```
spot_m        = interpolate(forecast.p50, d)            # linear in/zwischen Monaten
low_m, high_m = interpolate(p10/0.1, d), interpolate(p90/0.9, d)
tilt          = driver_tilt(signals, horizon=d)         # kleiner ± aus Σ(direction*importance)
expected_price = spot_m*(1+tilt) + ch.spread_to_spot + ch.fee_per_t
price_low/high = low_m/high_m + ch.spread_to_spot
```
Sybilion-`forecast_series` liefert je Monat `quantile_forecast {0.1,0.5,0.9}` → genau die Bänder. Treiber aus `external_signals.json` (`importance` je month_1/3/6).

---

## 5. Execution-Optimizer (greedy & transparent)

```python
for e in events:
    ch = channels[e.channel]
    e.eff_cost = (e.expected_price
        + risk_aversion * (e.price_high - e.expected_price)        # breites Band → "warten" teurer
        + timing_penalty(e.date, compliance_deadline)              # carry + Deadline-Druck steigend
        + counterparty_penalty(1 - e.counterparty_rating)          # OTC-Gegenparteirisiko
        - availability_bonus(ch.fill_prob))                        # Auktions-Fill-Risiko
events.sort(key=eff_cost)
remaining = deficit; plan = []
for e in events:
    if remaining <= 0: break
    take = min(remaining, e.available_volume*ch.fill_prob, ch.max_lot_per_event)
    if take >= ch.min_lot:
        plan.append(Allocation(... max_bid = e.price_high if AUCTION else None ...))
        remaining -= take
apply_band_overlay(plan)         # breites Band nahe Horizont → Front-Load deckeln + Reserve
return build_decision(plan, remaining, baselines)
```
- **Baselines** für €-Ersparnis: „alles jetzt am Spot" und „alles am Jahresende/Deadline".
- Breites Band laddert automatisch; schmal & steigend zieht vor.

---

## 6. MSR-Shock (Sonntag-Highlight) — `event = "msr_auction_cut"`

1. Backend: in `decision_adapter.SCENARIO_EVENTS` `"msr_auction_cut"` ergänzen (1 Zeile).
2. `ScenarioManager.run_scenario`:
   - **Auktions-`available_volume` × 0.8** für betroffene Tage.
   - Forecast-Band: p50 leicht ↑ / Band leicht enger — **deterministischer Transform auf dem gecachten Forecast** (kein neuer API-Call → bühnensicher).
   - Optimizer neu → weniger Auktionskapazität → mehr Volumen auf **SPOT/RFQ**, **frühere** Tage, höhere Max-Bids.
3. Rückgabe `{event, baseline, shocked, diff}` mit Kanal-Mix vorher/nachher, Timing-Shift, **Mehrkosten bei Nicht-Anpassung vs. Anpassung**.

---

## 7. Engine-Output-Schema (Frontend-Vertrag)

```jsonc
// /decisions/run  → decision
{
  "headline": "Beschaffe 65.000 EUA: 25k Auktion (Di), 15k RFQ, 25k warten",
  "deficit": 65000, "confidence": "medium",
  "channel_comparison": [
    {"channel":"AUCTION","eff_cost":70.1,"expected_price":69.8,"fill_prob":0.8,"available":29000,"recommended_volume":25000,"reason":"..."},
    {"channel":"SPOT","...":"..."}, {"channel":"RFQ","...":"..."}, {"channel":"OTC","...":"..."}
  ],
  "execution_plan": [
    {"date":"2026-06-02","channel":"AUCTION","volume":25000,"expected_price":69.8,"max_bid":71.2,"reason":"..."}
  ],
  "auction_strategy": [{"auction_id":"cap3-2026-06-02","target_volume":25000,"max_bid":71.2,"expected_clearing":69.8,"reason":"..."}],
  "costs": {"expected_total":..,"worst_case":..,"vs_buy_all_now":..,"vs_year_end":..},
  "drivers": [{"name":"EU ETS reform","importance_now":0.25,"importance_late":0.45,"direction":1,"trend":"INCREASING"}],
  "triggers": ["Wenn Spot > €72 vor Auktion → vorziehen", "Wenn Produktion sinkt → letzte Tranche stornieren"]
}
// /decisions/scenario → { "event":"msr_auction_cut", "baseline":<decision>, "shocked":<decision>,
//   "diff": {"channel_mix_before":{...},"channel_mix_after":{...},"timing_shift_days":-14,
//            "extra_cost_if_no_adapt":210000,"savings_from_adapting":120000,"narrative":"..."} }
```

---

## 8. Frontend-Anbindung (Repo `zero_one_hack_01/frontend`)

`src/data/api.ts` ist sauberer Swap-Point. Statt Mock → FastAPI (`http://localhost:8000`):
| UI braucht | Endpoint |
|---|---|
| Firmen / Position | `/companies` · `/companies/{id}/position` |
| Preis-Historie | `/market/eua-prices` |
| Forecast (Band+Treiber) | `/forecasts/sybilion` (POST request-template) oder Cache |
| **ExecutionPlan / Empfehlung** | `POST /decisions/run {company_id}` |
| **Shock (vorher/nachher)** | `POST /decisions/scenario {company_id, event:"msr_auction_cut"}` |
| Auktionen / Angebote | `/market/auctions` · `/market/sell-offers` |

**Komponenten:** `RecommendationCard` → ExecutionPlan-Headline · `SmartMatchFeed`/`OrderBook` → „OTC = ein Kanal" · `TimingLadder` → **ExecutionPlanTimeline** (kanal-farbige Tranchen) · **NEU** `ChannelComparison` + `AuctionCalendar` · `scenario.tsx` Shock-Enum `'none'|'msr'`.

---

## 9. ⚠️ Offene Team-Entscheidung: ZWEI Repos

- **Backend + Daten + Sybilion + Design-Doc** liegen in `zero_one_hackathon` (Florians Repo, in CLAUDE.md als kanonisch behandelt).
- **Frontend** liegt in `zero_one_hack_01` (Klon des offiziellen Templates).
- **Abgabe braucht EINE Repo-URL.** → Empfehlung: Frontend nach `zero_one_hackathon` ziehen und dieses als Submission-Repo nutzen. **Früh entscheiden**, sonst Merge-Stress am Sonntagmorgen.
- Der Memory-Markt-Python-Agent in `zero_one_hack_01/sybilion/agent/` ist jetzt **obsolet** (Florians Sybilion-Client ersetzt ihn) — nicht weiterbauen, nur als Referenz.

---

## 10. Dateien, die WIR anlegen (`zero_one_hackathon/src/engine/`)

```
src/engine/
├── __init__.py
├── channels.py            # Channel-Defs + Clearing-Mikromodell (§3/§4)
├── auction_source.py      # /market/auctions + sell-offers → SupplyEvent-Liste
├── optimizer.py           # Execution-Optimizer (§5)
├── agent.py               # CarbonEdgeAgent.run(...) + ScenarioManager.run_scenario(...) (§2/§7)
└── shock.py               # MSR-Transform (§6)
```
+ 1 Zeile in `decision_adapter.py` (`msr_auction_cut` in `SCENARIO_EVENTS`).

---

## 11. Zeitplan (Sa Abend → So 10:00), nach Impact/Risiko

| Phase | Zeit | Inhalt | Warum |
|---|---|---|---|
| 0 | 0,5h | `pip install pandas`, Token setzen, Backend hochfahren, `/forecasts/sybilion` **einmal live** → Cache | Grant läuft 01.06 ab → jetzt cachen, bühnensicher |
| 1 | 2,5h | `src/engine/`: channels + clearing + optimizer → `CarbonEdgeAgent.run` liefert echten Plan über `/decisions/run` | **die Substanz, die bewertet wird — Zeit schützen** |
| 2 | 1,5h | `ScenarioManager` + `msr_auction_cut` → `/decisions/scenario` Vorher/Nachher | Jury-Highlight |
| 3 | 2h | Frontend an Backend: ChannelComparison + AuctionCalendar + ExecutionPlanTimeline | sichtbarer Mehrwert |
| 4 | 0,5h | Repo-Konsolidierung (Frontend → `zero_one_hackathon`) | Abgabe braucht 1 URL |
| 5 | 1h | Backtest 2022-Spike (Stretch) + Politur + 2-Min-Video + Submission-Report | Abgabe |

**Risiken:** Optimizer-Zeit nicht vom Frontend-Umbau fressen lassen. Shock = deterministischer Transform auf Cache (kein Live-Call). Forecast früh cachen, da Grant abläuft.

---

## 12. Ignorieren
ChatGPTs MiFID-/MTF-/Regulierungs-Block ist Hackathon-irrelevant (wir sind Decision-Support, kein Handelsplatz). Nur bei echtem Startup relevant.
