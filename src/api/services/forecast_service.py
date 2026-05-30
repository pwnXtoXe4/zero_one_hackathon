"""Forecast endpoints: request template + Sybilion submission.

Bridges the incoming Sybilion request body to the existing
``src/sybilion/client.py`` wrapper, which expects a pandas Series.
Falls back to a mock response when the SDK or token is unavailable.
"""

import json
import os
from typing import Any

from src.api.services import PREPARED_DIR

_REQUEST_TEMPLATE_FILE = PREPARED_DIR / "eua_forecast_request.json"


def get_request_template() -> dict:
    """Return the prepared Sybilion forecast request template as-is."""
    if not _REQUEST_TEMPLATE_FILE.exists():
        raise FileNotFoundError(f"Request template not found: {_REQUEST_TEMPLATE_FILE}")
    with _REQUEST_TEMPLATE_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def submit_to_sybilion(body: dict[str, Any]) -> dict:
    """Submit a forecast request to Sybilion via the existing wrapper.

    Returns a mock response when the SDK import fails or the token is missing.
    """
    token = os.environ.get("SYBILION_API_TOKEN")

    try:
        import pandas as pd

        from src.sybilion.client import HAS_SDK, SybilionWrapper
    except ImportError:
        return _mock_response(body, "Sybilion SDK or its dependencies unavailable")

    if not HAS_SDK or not token:
        return _mock_response(body, "Sybilion API token missing or SDK unavailable")

    timeseries = body.get("timeseries")
    if not timeseries:
        raise ValueError("Request body must include a non-empty 'timeseries' map.")

    series = pd.Series(
        {pd.Timestamp(k): float(v) for k, v in timeseries.items()}
    ).sort_index()

    metadata = body.get("timeseries_metadata", {})
    keywords = metadata.get("keywords") or None
    horizon = int(body.get("soft_horizon", 6))

    wrapper = SybilionWrapper(api_token=token)
    artifacts = wrapper.submit_and_wait(
        series,
        keywords=keywords,
        horizon=horizon,
        title=metadata.get("title", "Carbon Forecast"),
        description=metadata.get("description", "Monthly carbon market time series"),
    )

    return {
        "status": "ok",
        "mode": wrapper.mode,
        "forecast": artifacts.forecast,
        "signals": artifacts.signals,
        "backtest": artifacts.backtest,
    }


def _mock_response(body: dict, message: str) -> dict:
    return {
        "status": "mock",
        "message": message,
        "input": body,
    }
