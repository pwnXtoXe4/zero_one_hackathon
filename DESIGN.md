# Design Choices & Possible Updates

## Sybilion API frequency limitation

The Sybilion API only accepts `"monthly"` as the `frequency` value. `"daily"` and `"weekly"` are reserved in the schema but not yet supported — the API will reject them with a 422 validation error (`forecast_request_v1.py:44-48`).

**Implication for daily datasets:** If the source data (e.g., daily EUA prices, daily company emission readings) is collected at daily granularity, it must be **aggregated to monthly** before submission. A reasonable approach is to compute the **monthly average** (or monthly closing/last-observation) for each calendar month, reducing the daily series to one observation per month. This also means the resulting monthly series must still contain at least **60 observations** (5 years of monthly history) to meet Sybilion's minimum requirement.

**Possible update:** If Sybilion adds `"daily"` support in a future API version (`pipeline_version: v2`+), we could switch to daily granularity for finer-grained forecasts. Until then, daily→monthly aggregation is the required pre-processing step.
