"""
CarbonEdge — Run from real Sybilion forecast artifacts.

Usage: python run_carbonedge.py [--scenario ets_reform|cbam|energy_crash]
"""

import json
import sys
from pathlib import Path

BASE = Path(__file__).parent

# Artifact files from job 5a43f269
FORECAST_PATH = BASE / "forecast_artifact.json"
SIGNALS_PATH = BASE / "external_signals_artifact.json"
METRICS_PATH = BASE / "backtest_metrics_artifact.json"
REPORT_PATH = BASE / "carbonedge_strategy_report.txt"

# ---- Real forecast data from Sybilion job 5a43f269 ----
FORECAST_DATA = {
    "version": "1.1",
    "data": {
        "forecast_horizon": 6,
        "forecast_start": "2026-06-01",
        "forecast_end": "2026-11-01",
        "last_valid_data_index": "2026-05-01",
        "forecast_series": {
            "2026-06-01": {"forecast": 75.477663, "quantile_forecast": {
                "0.05": 70.325993, "0.10": 70.815191, "0.15": 70.815191,
                "0.20": 72.034354, "0.25": 73.007866, "0.30": 73.468011,
                "0.35": 73.468011, "0.40": 74.150273, "0.45": 74.95489,
                "0.50": 75.477663, "0.55": 76.000437, "0.60": 76.805053,
                "0.65": 77.487316, "0.70": 77.487316, "0.75": 77.947461,
                "0.80": 78.920973, "0.85": 80.140136, "0.90": 80.140136,
                "0.95": 80.629333
            }},
            "2026-07-01": {"forecast": 75.003588, "quantile_forecast": {
                "0.05": 66.306707, "0.10": 67.176451, "0.15": 68.232739,
                "0.20": 69.215533, "0.25": 71.645035, "0.30": 72.471937,
                "0.35": 72.471937, "0.40": 73.601729, "0.45": 74.41753,
                "0.50": 75.003588, "0.55": 75.589647, "0.60": 76.405447,
                "0.65": 77.53524, "0.70": 77.53524, "0.75": 78.362142,
                "0.80": 80.791644, "0.85": 81.774438, "0.90": 82.830726,
                "0.95": 83.700469
            }},
            "2026-08-01": {"forecast": 74.693107, "quantile_forecast": {
                "0.05": 62.909862, "0.10": 64.963162, "0.15": 65.814659,
                "0.20": 66.839838, "0.25": 69.483176, "0.30": 71.235878,
                "0.35": 71.235878, "0.40": 72.410679, "0.45": 73.995183,
                "0.50": 74.693107, "0.55": 75.391031, "0.60": 76.975534,
                "0.65": 78.150335, "0.70": 78.150335, "0.75": 79.903037,
                "0.80": 82.546375, "0.85": 83.571555, "0.90": 84.423052,
                "0.95": 86.476352
            }},
            "2026-09-01": {"forecast": 74.618708, "quantile_forecast": {
                "0.05": 60.973746, "0.10": 62.894379, "0.15": 63.91498,
                "0.20": 64.856114, "0.25": 68.4102, "0.30": 69.90202,
                "0.35": 70.038447, "0.40": 71.105321, "0.45": 73.785064,
                "0.50": 74.618708, "0.55": 75.452353, "0.60": 78.132095,
                "0.65": 79.19897, "0.70": 79.335397, "0.75": 80.827217,
                "0.80": 84.381303, "0.85": 85.322437, "0.90": 86.343038,
                "0.95": 88.263671
            }},
            "2026-10-01": {"forecast": 74.535683, "quantile_forecast": {
                "0.05": 57.94186, "0.10": 59.894586, "0.15": 62.002746,
                "0.20": 63.049214, "0.25": 66.529968, "0.30": 67.903085,
                "0.35": 69.336125, "0.40": 70.334732, "0.45": 73.717134,
                "0.50": 74.535683, "0.55": 75.354232, "0.60": 78.736635,
                "0.65": 79.735242, "0.70": 81.168282, "0.75": 82.541399,
                "0.80": 86.022152, "0.85": 87.068621, "0.90": 89.176781,
                "0.95": 91.129507
            }},
            "2026-11-01": {"forecast": 74.672587, "quantile_forecast": {
                "0.05": 50.580844, "0.10": 56.174158, "0.15": 59.295661,
                "0.20": 60.939186, "0.25": 64.157081, "0.30": 65.829226,
                "0.35": 67.760898, "0.40": 68.712507, "0.45": 73.701668,
                "0.50": 74.672587, "0.55": 75.643506, "0.60": 80.632667,
                "0.65": 81.584276, "0.70": 83.515948, "0.75": 85.188093,
                "0.80": 88.405988, "0.85": 90.049513, "0.90": 93.171017,
                "0.95": 98.76433
            }},
        }
    }
}

EXTERNAL_SIGNALS_DATA = {
    "version": "1.1",
    "data": {
        "43c05b30-1319-90e8-a979-e0ec6acd17da": {
            "driver_name": "Carbon pricing in Europe",
            "importance": {"overall": {"mean": 23.41, "min": 23.41, "max": 23.41}},
            "direction": {"overall": {"mean": 0.98, "min": 0.98, "max": 0.98}},
        },
        "0994767b-5c95-6ccd-0307-2db00a5fd0e3": {
            "driver_name": "Energy - Finland",
            "importance": {"overall": {"mean": 92.59, "min": 92.59, "max": 92.59}},
            "direction": {"overall": {"mean": 0.82, "min": 0.82, "max": 0.82}},
        },
        "0db3e662-b27d-a8a6-c244-e92907e25405": {
            "driver_name": "Commodities - World",
            "importance": {"overall": {"mean": 80.87, "min": 80.87, "max": 80.87}},
            "direction": {"overall": {"mean": 0.68, "min": 0.68, "max": 0.68}},
        },
        "4c86a36a-dc76-7f68-f8d3-982965da4708": {
            "driver_name": "Energy - World",
            "importance": {"overall": {"mean": 79.33, "min": 67.40, "max": 91.26}},
            "direction": {"overall": {"mean": -0.30, "min": -0.39, "max": -0.20}},
        },
        "7c4c2cc6-f36a-8484-a322-2f217a4e260b": {
            "driver_name": "Energy - Qatar",
            "importance": {"overall": {"mean": 97.00, "min": 97.00, "max": 97.00}},
            "direction": {"overall": {"mean": 0.06, "min": 0.06, "max": 0.06}},
        },
        "ab9c8040-7055-9556-cb79-6aac4d6001d1": {
            "driver_name": "EU trade value/volume indices",
            "importance": {"overall": {"mean": 84.82, "min": 84.82, "max": 84.82}},
            "direction": {"overall": {"mean": 0.84, "min": 0.84, "max": 0.84}},
        },
        "364b3c25-180a-baee-7eb1-2d16714340a7": {
            "driver_name": "Energy - United States",
            "importance": {"overall": {"mean": 100.0, "min": 100.0, "max": 100.0}},
            "direction": {"overall": {"mean": -0.16, "min": -0.16, "max": -0.16}},
        },
        "07b04245-1fa9-21c4-a543-fe3d382f3b09": {
            "driver_name": "Equities - World",
            "importance": {"overall": {"mean": 50.78, "min": 50.78, "max": 50.78}},
            "direction": {"overall": {"mean": 0.61, "min": 0.61, "max": 0.61}},
        },
        "2813b473-5b74-995f-d76b-5ebc511e2d37": {
            "driver_name": "HICP - Administered prices in Europe",
            "importance": {"overall": {"mean": 54.60, "min": 54.60, "max": 54.60}},
            "direction": {"overall": {"mean": 0.21, "min": 0.21, "max": 0.21}},
        },
    }
}

BACKTEST_METRICS_DATA = {
    "version": "1.1",
    "data": {
        "6m": {"metrics": {"MAE": 4.10, "MAPE": 5.54, "MASE": 1.54, "RMSE": 4.10, "RMSSE": 1.20}},
        "12m": {"metrics": {"MAE": 4.10, "MAPE": 5.54, "MASE": 1.54, "RMSE": 4.10, "RMSSE": 1.20}},
        "24m": {"metrics": {"MAE": 4.10, "MAPE": 5.54, "MASE": 1.54, "RMSE": 4.10, "RMSSE": 1.20}},
        "60m": {"metrics": {"MAE": 4.10, "MAPE": 5.54, "MASE": 1.54, "RMSE": 4.10, "RMSSE": 1.20}},
    }
}


def save_artifacts():
    """Save the real Sybilion data to JSON files for the pipeline to consume."""
    with open(FORECAST_PATH, "w") as f:
        json.dump(FORECAST_DATA, f, indent=2)
    with open(SIGNALS_PATH, "w") as f:
        json.dump(EXTERNAL_SIGNALS_DATA, f, indent=2)
    with open(METRICS_PATH, "w") as f:
        json.dump(BACKTEST_METRICS_DATA, f, indent=2)
    print("Artifact files saved.")


def run(scenario: str = None):
    save_artifacts()

    # Load historical prices for regime detection backtest
    prices_path = BASE / "eu_ets_monthly_prices.json"
    historical_prices = []
    if prices_path.exists():
        with open(prices_path) as f:
            import json as _json
            ts = _json.load(f)
            historical_prices = [float(v) for _, v in sorted(ts.items())]

    from zero_one_hackathon.carbonedge.main import run_carbonedge_with_forecast

    report = run_carbonedge_with_forecast(
        forecast_json_path=str(FORECAST_PATH),
        scenario=scenario,
        external_signals_path=str(SIGNALS_PATH),
        backtest_metrics_path=str(METRICS_PATH),
        historical_prices=historical_prices,
    )

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)

    print(report)
    print(f"\nReport saved to {REPORT_PATH}")


if __name__ == "__main__":
    scenario = sys.argv[2] if len(sys.argv) > 2 and sys.argv[1] == "--scenario" else None
    run(scenario)
