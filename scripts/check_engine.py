"""Manual smoke test for the decision engine. Run from repo root:

    python scripts/check_engine.py

With SYBILION_API_TOKEN unset it uses the mock-from-real forecast (fast);
with it set it exercises the live Sybilion path (and caches the result).
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.api.services import company_service  # noqa: E402
from src.engine.agent import CarbonEdgeAgent, ScenarioManager  # noqa: E402


def main() -> None:
    company = company_service.get_company("greenchem")
    position = company_service.compute_position(company)
    print("position:", position)

    agent = CarbonEdgeAgent()
    base = agent.run(company=company, position=position)
    print("\nforecastMode:", base["forecastMode"], "| currentPrice:", base["currentPrice"])
    print("plan.action:", base["plan"]["action"], "| headline:", base["plan"]["headline"])
    print("plan.channelMix:", base["plan"]["channelMix"])
    print("plan.expectedTotal:", base["plan"]["expectedTotal"],
          "| savedVsYearEnd:", base["plan"]["savingsVsYearEnd"])
    print("channels:", [(c["key"], c["rank"], c["recommendedVolume"], c["effCost"]) for c in base["channels"]])
    print("auctions targeted:", [(a["label"], a["targetVolume"], a["expectedClearing"]) for a in base["auctions"] if a["targetVolume"]])
    print("tranches:", [(t["channel"], t["volume"], t["status"]) for t in base["plan"]["tranches"]])
    print("forecast p50:", [p["p50"] for p in base["forecast"]])
    print("drivers:", [(d["name"], d["importance"]) for d in base["drivers"]])

    sm = ScenarioManager(agent)
    scen = sm.run_scenario(company=company, position=position, forecast=None, event="msr_auction_cut")
    print("\n--- MSR SHOCK ---")
    print("mixBefore:", scen["diff"]["mixBefore"])
    print("mixAfter :", scen["diff"]["mixAfter"])
    print("shocked action:", scen["shocked"]["plan"]["action"], "| savedByAdapting:", scen["diff"]["savingsFromAdapting"])
    print("shocked channels:", [(c["key"], c["rank"], c["recommendedVolume"]) for c in scen["shocked"]["channels"]])

    # sanity assertions
    assert base["plan"]["deficitVolume"] > 0
    assert sum(m["volume"] for m in base["plan"]["channelMix"]) > 0
    assert len(base["forecast"]) == 6
    print("\nOK — engine produced a complete, valid decision payload.")


if __name__ == "__main__":
    main()
