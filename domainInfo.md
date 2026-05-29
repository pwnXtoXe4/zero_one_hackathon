<!-- Source: https://sybilion.dev/docs/ -->

# Sybilion Developers Portal [](https://sybilion.dev#sybilion-developers-portal)

Sybilion is a **forecasting API for monthly business time series** related to demand, sales, inventory, financial KPIs. Submit a series and get point forecasts with quantile bands; optionally get the ranked external signals (macroeconomic indicators, regional and category dimensions) that move the series.

**New here?** Start with the [Quickstart](https://sybilion.dev/quickstart) — it takes you from zero to a completed forecast job in a few minutes. All requests go to ** https://api.sybilion.dev**.

## What you can do [](https://sybilion.dev#what-you-can-do)

**Forecasts**— Submit a monthly series of**40+ observations**, ask for a horizon of**1–12 months**, and retrieve a point forecast with quantile bands, per-driver attribution, and optional backtest metrics. The forecast is processed asynchronously, the job runs in a few minutes. See[Forecasts](https://sybilion.dev/features/forecasts)for more information on how to submit a forecast and retrieve the results.**Driver recommendations**— Submit a synchronous request with metadata and/or a series and get the external signals (macroeconomic indicators, regional and category dimensions) that are relevant to the metadata or impact the timeseries. See[Drivers](https://sybilion.dev/features/drivers)for more information.**Alerts**— Submit a synchronous request with metadata and get alerts about macroeconomic factor that are relevant to your metadata. See[Alerts](https://sybilion.dev/features/alerts)for more information.

All features accept optional filters from the [region and category catalog](https://sybilion.dev/features/regions-and-categories).

## Use this when [](https://sybilion.dev#use-this-when)

- You have a numeric
**monthly**time series and want forecasts you don't want to build yourself. - You want to enrich your own model with curated
**external drivers**and**alerts**instead of sourcing macro data manually. - You need forecasts that include
**quantile bands**,**driver attribution**, and**backtest metrics**in one call rather than three separate pipelines.

Sybilion supports monthly time series. Sub-monthly frequencies (daily, hourly) and other use cases such as anomaly detection are not yet supported.

## How the docs are organized [](https://sybilion.dev#how-the-docs-are-organized)

Three independent ways into the same content:

**Features**— concept pages with curl + Python + Go side by side. The fastest path if you know the use case (forecast a series, recommend drivers, get alerts, browse dimensions).**Clients**— install + auth + language idioms. The fastest path if you've picked your stack and want client-specific patterns (helpers, pagination, error handling).**API reference**— per-endpoint detail pages and the public OpenAPI YAML (`/openapi.yaml`

) for schema and codegen.

## Quick map [](https://sybilion.dev#quick-map)

**Get started:**[Quickstart](https://sybilion.dev/quickstart)·[Authentication](https://sybilion.dev/authentication)·[Tiers](https://sybilion.dev/tiers)**Integrations:**[MCP](https://sybilion.dev/integrations)**Features:**[Forecasts](https://sybilion.dev/features/forecasts)·[Drivers](https://sybilion.dev/features/drivers)·[Alerts](https://sybilion.dev/features/alerts)·[Regions & categories](https://sybilion.dev/features/regions-and-categories)·[Account & usage](https://sybilion.dev/features/account)**Clients:**[Overview](https://sybilion.dev/sdks/)·[Using curl](https://sybilion.dev/using-curl)·[Python SDK](https://sybilion.dev/sdk-python)·[Go SDK](https://sybilion.dev/sdk-go)**API reference:**[Public OpenAPI](https://sybilion.dev/openapi)**Forecasts**—[Submit](https://sybilion.dev/forecasts-submit)·[Status](https://sybilion.dev/forecasts-status)·[Artifacts](https://sybilion.dev/forecasts-artifacts)**Drivers**—[POST /api/v1/drivers](https://sybilion.dev/drivers)**Alerts**—[POST /api/v1/alerts](https://sybilion.dev/alerts)**Dimensions**—[GET /api/v1/regions](https://sybilion.dev/catalog#regions)·[GET /api/v1/categories](https://sybilion.dev/catalog#categories)**Account**—[GET /api/v1/me](https://sybilion.dev/me)·[GET /api/v1/usage](https://sybilion.dev/usage)·[GET /api/v1/jobs](https://sybilion.dev/jobs)

**Resources:**[Errors & limits](https://sybilion.dev/errors)·[Service health](https://sybilion.dev/health)·[Community & support](https://sybilion.dev/community)

## Audience [](https://sybilion.dev#audience)

- Anyone who wants to build using the Sybilion API.


---

<!-- Source: https://sybilion.dev/docs/quickstart -->

# Quickstart [](https://sybilion.dev#quickstart)

This page helps you build a **complete forecast job** using the Sybilion API. All you need is a Sybilion account to get started. You can use Sybilion in three ways — **direct API calls** (curl or any HTTP client), our **Python and Go SDKs**, or via **MCP** to connect AI assistants like Claude or ChatGPT.

## 1. Sign up or sign in [](https://sybilion.dev#_1-sign-up-or-sign-in)

Create a new account or sign in at the Developers Portal:

## 2. Create an API key [](https://sybilion.dev#_2-create-an-api-key)

In the Developers Portal, navigate to **API keys** and create a new key.


Important:The full secret is shownonly once, at creation time. Copy it immediately — it starts with`sk_ops_…`

and cannot be retrieved again.

The examples in this guide all read from `$SYBILION_API_TOKEN`

. Set it in your shell/terminal using this command:

`export SYBILION_API_TOKEN="sk_ops_..."`


## 3. Pick a client [](https://sybilion.dev#_3-pick-a-client)

The base URL is ** https://api.sybilion.dev**. Choose the client that fits your stack:

```
# Already on most systems. To install if needed:
# macOS: brew install curl
# Debian/Ubuntu: sudo apt install -y curl
# Windows: winget install curl.curl
```


`pip install sybilion`


`go get go.sybilion.dev/sybilion@latest`


SDK packages: [Python — sybilion on PyPI](https://pypi.org/project/sybilion/) ·

[Go —](https://pkg.go.dev/go.sybilion.dev/sybilion).

`go.sybilion.dev/sybilion`

on pkg.go.dev## 4. Verify authentication — `GET /api/v1/me`

[](https://sybilion.dev#_4-verify-authentication-—-get-api-v1-me)

Call `GET /api/v1/me`

to confirm your key works and see your current balance and tier.

```
curl -sS \
-H "Authorization: Bearer $SYBILION_API_TOKEN" \
https://api.sybilion.dev/api/v1/me
```


```
import os
from sybilion import Client
c = Client(token=os.environ["SYBILION_API_TOKEN"])
me = c.me()
print(me.user_id, me.available_eur_cents, me.api_usage_tier)
```


```
package main
import (
"context"
"fmt"
"os"
"go.sybilion.dev/sybilion"
)
func main() {
c := sybilion.New(sybilion.Options{Token: os.Getenv("SYBILION_API_TOKEN")})
me, _, err := c.DefaultAPI().ApiV1MeGet(context.Background()).Execute()
if err != nil { panic(err) }
fmt.Println(me.GetUserId(), me.GetAvailableEurCents(), me.GetApiUsageTier())
}
```


A successful response looks like this:

```
{
"user_id": "1f2a8b3e-4c5d-46d7-9a01-2b3c4d5e6f70",
"balance_eur_cents": 1234,
"available_eur_cents": 1134,
"api_usage_tier": 1
}
```


`available_eur_cents`

is your spendable balance (balance minus any active holds). Monetary values are always integer**EUR cents**(`100`

=`€1.00`

).`api_usage_tier`

is your current[pricing tier](https://sybilion.dev/tiers).- A
means your token is missing or invalid — double-check the value you exported.`401`


See [GET /api/v1/me](https://sybilion.dev/me) for the full field references.

## 5. Submit a forecast — `POST /api/v1/forecasts`

[](https://sybilion.dev#_5-submit-a-forecast-—-post-api-v1-forecasts)

Save the body below as ** forecast_body.json**. This example uses the shortest possible horizon (

`soft_horizon: 1`

), which needs a minimum of **40**monthly observations. Your most recent data point cannot be older than 12 months. Replace the

`timeseries`

values with your own data.

Date format:Each key must be thefirst day of the monthin`YYYY-MM-DD`

format (e.g.`2024-06-01`

, not`2024-06-15`

). Any other day-of-month will be rejected.

```
{
"pipeline_version": "v1",
"frequency": "monthly",
"soft_horizon": 1,
"recency_factor": 0.5,
"timeseries_metadata": {
"title": "Monthly Widget Sales Europe",
"description": "Monthly unit sales of widgets in the European market.",
"keywords": ["widget", "sales", "europe", "consumer goods", "retail"]
},
"timeseries": {
"2021-12-01": 218.5,
"2022-01-01": 148.1,
"2022-02-01": 145.9,
"2022-03-01": 162.4,
"2022-04-01": 168.7,
"2022-05-01": 166.2,
"2022-06-01": 178.5,
"2022-07-01": 172.3,
"2022-08-01": 168.9,
"2022-09-01": 181.4,
"2022-10-01": 189.7,
"2022-11-01": 204.8,
"2022-12-01": 218.5,
"2023-01-01": 155.3,
"2023-02-01": 152.7,
"2023-03-01": 170.1,
"2023-04-01": 176.4,
"2023-05-01": 174.0,
"2023-06-01": 186.2,
"2023-07-01": 180.5,
"2023-08-01": 177.1,
"2023-09-01": 190.3,
"2023-10-01": 198.4,
"2023-11-01": 213.9,
"2023-12-01": 227.6,
"2024-01-01": 162.8,
"2024-02-01": 160.2,
"2024-03-01": 178.5,
"2024-04-01": 184.9,
"2024-05-01": 182.3,
"2024-06-01": 194.7,
"2024-07-01": 188.4,
"2024-08-01": 185.0,
"2024-09-01": 198.6,
"2024-10-01": 207.3,
"2024-11-01": 223.1,
"2024-12-01": 237.8,
"2025-01-01": 170.4,
"2025-02-01": 168.1,
"2025-03-01": 186.7
}
}
```


Then submit it:

```
curl -sS -X POST https://api.sybilion.dev/api/v1/forecasts \
-H "Authorization: Bearer $SYBILION_API_TOKEN" \
-H "Content-Type: application/json" \
-d @forecast_body.json
```


```
import json
import os
from sybilion import Client
c = Client(token=os.environ["SYBILION_API_TOKEN"])
with open("forecast_body.json", encoding="utf-8") as f:
body = json.load(f)
resp = c.submit_forecast(body)
print(resp.job_id, resp.poll_url)
```


```
package main
import (
"context"
"encoding/json"
"fmt"
"log"
"os"
"go.sybilion.dev/sybilion"
api "go.sybilion.dev/sybilion/api"
)
func main() {
c := sybilion.New(sybilion.Options{Token: os.Getenv("SYBILION_API_TOKEN")})
data, err := os.ReadFile("forecast_body.json")
if err != nil { log.Fatal(err) }
var body api.ForecastRequestV1
if err := json.Unmarshal(data, &body); err != nil { log.Fatal(err) }
resp, err := c.SubmitForecast(context.Background(), body)
if err != nil { log.Fatal(err) }
fmt.Println(resp.GetJobId(), resp.GetPollUrl())
}
```


A successful response is ** 202 Accepted**:

```
{
"job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
"poll_url": "/api/v1/forecasts/a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```


Copy the `job_id`

— you'll need it in the next step. See [POST /api/v1/forecasts](https://sybilion.dev/forecasts-submit) for the full field reference and validation rules.

## 6. Poll until completed [](https://sybilion.dev#_6-poll-until-completed)

Forecasts run asynchronously and typically take a few minutes. Keep checking the job status until `settled`

is `true`

.

```
JOB_ID="<paste-job-id>"
API="https://api.sybilion.dev"
until curl -sS -H "Authorization: Bearer $SYBILION_API_TOKEN" \
"$API/api/v1/forecasts/$JOB_ID" | grep -qE '"settled"[[:space:]]*:[[:space:]]*true'; do
sleep 2
done
curl -sS -H "Authorization: Bearer $SYBILION_API_TOKEN" \
"$API/api/v1/forecasts/$JOB_ID"
```


```
import os
from sybilion import Client
c = Client(token=os.environ["SYBILION_API_TOKEN"])
job = c.wait_forecast("<paste-job-id>", poll_s=2.0, timeout_s=3600.0)
print(job.status, job.artifacts)
```


```
package main
import (
"context"
"fmt"
"log"
"os"
"time"
"go.sybilion.dev/sybilion"
)
func main() {
c := sybilion.New(sybilion.Options{Token: os.Getenv("SYBILION_API_TOKEN")})
jobID := "<paste-job-id>"
job, err := c.WaitForecast(context.Background(), jobID, 2*time.Second)
if err != nil { log.Fatal(err) }
fmt.Println(job.GetStatus(), job.GetEurCentsFinal())
for _, a := range job.GetArtifacts() {
fmt.Println(" -", a.GetName())
}
}
```


Once `status`

is `completed`

, the response includes how much the forecast cost and an `artifacts`

array listing the files ready to download:

```
{
"job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
"status": "completed",
"settled": true,
"eur_cents_final": 3,
"artifacts": [
{ "name": "forecast.json", "href": "/api/v1/forecasts/a1b2c3d4-.../artifacts/forecast.json" },
{ "name": "external_signals.json", "href": "/api/v1/forecasts/a1b2c3d4-.../artifacts/external_signals.json" }
]
}
```


See [GET /api/v1/forecasts/:id](https://sybilion.dev/forecasts-status) for the full response shape.

## 7. Fetch artifacts [](https://sybilion.dev#_7-fetch-artifacts)

Download the forecast results using the artifact names from the `artifacts`

array above.

```
curl -sS \
-H "Authorization: Bearer $SYBILION_API_TOKEN" \
"https://api.sybilion.dev/api/v1/forecasts/$JOB_ID/artifacts/forecast.json"
```


```
import json
import os
from sybilion import Client
c = Client(token=os.environ["SYBILION_API_TOKEN"])
data = c.get_forecast_artifact("<paste-job-id>", "forecast.json")
forecast = json.loads(data)
print(forecast["data"]["forecast_series"])
```


```
package main
import (
"context"
"fmt"
"io"
"log"
"os"
"go.sybilion.dev/sybilion"
)
func main() {
c := sybilion.New(sybilion.Options{Token: os.Getenv("SYBILION_API_TOKEN")})
f, err := c.GetForecastArtifact(context.Background(), "<paste-job-id>", "forecast.json")
if err != nil { log.Fatal(err) }
defer f.Close()
body, _ := io.ReadAll(f)
fmt.Println(string(body))
}
```


The `forecast.json`

artifact looks like this (our example used `soft_horizon: 1`

, so there is one forecast point):

```
{
"version": "1.1",
"data": {
"forecast_horizon": 1,
"forecast_start": "2025-04-01",
"forecast_end": "2025-04-01",
"forecast_series": {
"2025-04-01": {
"forecast": 191.3
}
}
}
}
```


The `external_signals.json`

artifact is always present alongside `forecast.json`

and contains the ranked external drivers (macroeconomic indicators, regional and category signals) that influenced the forecast. See [Artifact download](https://sybilion.dev/forecasts-artifacts) for the full schema of all artifact files.

## Next steps [](https://sybilion.dev#next-steps)

**Explore more features**

[Drivers](https://sybilion.dev/features/drivers)— find the external signals that impact your series, without running a full forecast.[Alerts](https://sybilion.dev/features/alerts)— get info about macroeconomic events relevant to your data.[Regions & categories](https://sybilion.dev/features/regions-and-categories)— browse the dimension catalog to narrow your results.[Account & usage](https://sybilion.dev/features/account)— check your balance, tier, and charge history.

**Go deeper on forecasts**

[POST /api/v1/forecasts](https://sybilion.dev/forecasts-submit)— full validation rules, along with details on all fields.[Artifact download](https://sybilion.dev/forecasts-artifacts)— complete schema for`forecast.json`

,`external_signals.json`

, and backtest files.[Errors & limits](https://sybilion.dev/errors)— understand`402`

,`422`

,`429`

, and what each means for your integration.

**Connect and integrate**

[MCP integrations](https://sybilion.dev/integrations)— use the Sybilion API through Claude, ChatGPT, or TradingView Remix without writing code.[Python SDK](https://sybilion.dev/sdk-python)·[Go SDK](https://sybilion.dev/sdk-go)·[Using curl](https://sybilion.dev/using-curl)— language-specific patterns and helpers.[Tiers](https://sybilion.dev/tiers)— understand how pricing tiers work and when they change.

**Get help**

[Community & support](https://sybilion.dev/community)— Slack, Discord, or email. We're happy to help.


---

<!-- Source: https://sybilion.dev/docs/authentication -->

# Authentication [](https://sybilion.dev#authentication)

Every request to the Sybilion API must be authenticated. The method depends on how you're connecting.

| Method | Auth type | How? | Credentials |
|---|---|---|---|
| Direct API calls (curl, HTTP) | API key | `Authorization: Bearer` header |
|

[API keys](https://sybilion.dev/keys)in the Developers PortalMissing or invalid credentials return ** 401 Unauthorized**.

## Get an API key [](https://sybilion.dev#get-an-api-key)

In the Developers Portal, navigate to ** API keys** and create a new key.


Important:The full secret is shownonly once, at creation time. Copy it immediately — it starts with`sk_ops_…`

and cannot be retrieved again. Keys can be revoked at any time from the same page.

Store it in the `SYBILION_API_TOKEN`

environment variable:

`export SYBILION_API_TOKEN="sk_ops_..."`


## Direct HTTP / curl [](https://sybilion.dev#direct-http-curl)

Pass the key in the `Authorization`

header on every request:

```
curl -sS \
-H "Authorization: Bearer $SYBILION_API_TOKEN" \
https://api.sybilion.dev/api/v1/me
```


## SDKs (Python and Go) [](https://sybilion.dev#sdks-python-and-go)

All SDKs pick up `SYBILION_API_TOKEN`

automatically once it's set in your environment.

## MCP (Claude, ChatGPT, TradingView Remix) [](https://sybilion.dev#mcp-claude-chatgpt-tradingview-remix)

MCP integrations use **OAuth** — no API key is needed. The MCP client handles the full auth flow on your behalf, you just need to approve the access in a browser pop-up. See [MCP integrations](https://sybilion.dev/integrations) for setup instructions.


---

<!-- Source: https://sybilion.dev/docs/tiers -->

# Tiers [](https://sybilion.dev#tiers)

Every Sybilion account is on a **pricing tier**. Your tier controls how fast you can call the API (per-minute request budgets) and how many forecast jobs you can run in parallel. This page describes what each tier is for. Your current tier and its live limits are shown in the [Developers Portal Tiers Page](https://sybilion.dev/tiers).

## Available tiers [](https://sybilion.dev#available-tiers)

| Tier | Who it's for |
|---|---|
Free | New accounts trying the API. |
Starter | Active developers running small integrations. |
Pro | Teams running steady production workloads. |
Growth | High-volume integrations. |
Enterprise | Contracted customers with custom limits, SLAs, and support. |

## Moving between tiers [](https://sybilion.dev#moving-between-tiers)

Free, Starter, Pro, and Growth tiers **upgrade automatically** as you purchase more credits — you will be moved up to the next tier without any action needed on your part.

To get **Enterprise** tier, [contact us](https://sybilion.dev/cdn-cgi/l/email-protection#f98a8c8989968b8db98a809b9095909697d79a9694) with a brief description of your use case and expected volume.


---

<!-- Source: https://sybilion.dev/docs/integrations -->

# MCP integrations [](https://sybilion.dev#mcp-integrations)

The Sybilion MCP server exposes the full public API surface as tools that any MCP-compatible AI client can discover and call.

**MCP server URL:** `https://mcp.sybilion.dev/mcp`

**Authentication:** OAuth — the client handles the flow, you just need to approve access in your browser when requested.

Once connected, your AI client can submit forecasts, poll status, retrieve driver recommendations, and browse regions and categories. All through natural-language conversation backed by the actual API.

## ChatGPT [](https://sybilion.dev#chatgpt)

### Requirements [](https://sybilion.dev#requirements)

ChatGPT custom connectors require **Developer Mode** and a **Plus, Pro, Business, Enterprise, or Edu** plan. Business and above plans require an admin to enable Developer Mode for the organisation first.

### Setup [](https://sybilion.dev#setup)

- Open
**Settings → Apps & Connectors → Advanced settings**and enable**Developer Mode**. - Go to
**Settings → Connectors → Create**. - Fill in the connector:
**Name**:`Sybilion`

**Description**:`Submit forecasts, get driver recommendations, and browse the Sybilion API.`

**Connector URL**:`https://mcp.sybilion.dev/mcp`


- Click
**Create**. ChatGPT connects to the server and lists the advertised tools — you should see forecast, drivers, regions, categories, and account endpoints. - Complete the OAuth approval in the browser pop-up that follows.

### Using it [](https://sybilion.dev#using-it)

In any new chat, click **+** near the composer → **More** → select **Sybilion**. The connector is active for that conversation. Write-tool calls (forecast submit, driver recommend) require per-call approval unless you choose to remember approvals for the session.

### Example prompts [](https://sybilion.dev#example-prompts)

- "Using the Sybilion API, submit a 6-month forecast for this monthly data and tell me when the job settles."
- "Use the Sybilion API to recommend drivers for energy commodities in Europe and rank them by importance."
- "Check my Sybilion account balance and tell me if I have enough credit to run another forecast."

## Claude [](https://sybilion.dev#claude)

### Claude.ai and Claude Desktop [](https://sybilion.dev#claude-ai-and-claude-desktop)

Both the web UI and desktop app support remote MCP connectors.

**Individual accounts (Pro or Max):**

- Go to
[Customize → Connectors](https://claude.ai/customize/connectors). - Click
**+**→**Add custom connector**. - Enter the server URL:
`https://mcp.sybilion.dev/mcp`

- Click
**Add**, then complete the OAuth flow that opens in your browser. - Enable the connector per conversation via
**+**→**Connectors**in the chat composer.

**Team or Enterprise accounts:**

An Owner must first add the connector at [Organization settings → Connectors](https://claude.ai/admin-settings/connectors), then individual members connect to it from their own [Customize → Connectors](https://claude.ai/customize/connectors) page.

### Example prompts [](https://sybilion.dev#example-prompts-1)

Once the connector is active in a conversation:

- "Submit a monthly forecast for this data and poll until it settles."
- "Recommend drivers for Commodities (category 46) in Europe (region 3) with recency factor 0.7."
- "Show me my current balance and tier."

## TradingView Remix [](https://sybilion.dev#tradingview-remix)

[TradingView Remix: AI Chart Copilot](https://chromewebstore.google.com/detail/tradingview-remix-ai-char/fchmejnoncmdhlebgdgifdnehoibalnd) is a Chrome extension with a built-in MCP client. You can add the Sybilion MCP server so it calls the Sybilion API during chart analysis conversations.

### Setup [](https://sybilion.dev#setup-1)

- Install the
[TradingView Remix extension](https://chromewebstore.google.com/detail/tradingview-remix-ai-char/fchmejnoncmdhlebgdgifdnehoibalnd)from the Chrome Web Store and sign in. - Open TradingView, click the Remix icon to open the side panel.
- In the side panel, open
**Settings → MCP Servers**(or the equivalent MCP integration section). - Add a new MCP server:
**URL**:`https://mcp.sybilion.dev/mcp`

**Auth**: OAuth

- Approve the OAuth flow in the browser pop-up.
- Ask the extension to list available Sybilion tools to confirm the connection:
"List the tools available from the Sybilion MCP server."


### Example prompts [](https://sybilion.dev#example-prompts-2)

- "Using the Sybilion API, which drivers correlate most with this chart's commodity? Filter by the visible region."
- "Use the Sybilion API to submit a 6-month forecast for the series in this chart and show me the result when it settles."

TIP

Sybilion forecasts are async — the MCP tool polls until the job completes, then returns the result. Runs can take tens of seconds to a few minutes.

If the agent cannot retrieve forecast data

Some MCP clients pass tool arguments as a plain string instead of a structured dict. If the agent fails to retrieve a forecast or artifact, ask it to call the tool again with the correct argument structure:

| Tool | Required arguments |
|---|---|
`get_forecast` | `{ "job_id": "<uuid>" }` |
`get_forecast_chart` | `{ "job_id": "<uuid>" }` |
`get_forecast_artifact` | `{ "job_id": "<uuid>", "artifact_name": "<artifact_name>" }` |

## See also [](https://sybilion.dev#see-also)

[Quickstart](https://sybilion.dev/quickstart)— first forecast in five steps.[Authentication](https://sybilion.dev/authentication)— API keys vs session tokens.[Public OpenAPI](https://sybilion.dev/openapi)— full spec and schema reference.[Forecasts](https://sybilion.dev/features/forecasts)·[Drivers](https://sybilion.dev/features/drivers)— feature walkthroughs.


---

<!-- Source: https://sybilion.dev/docs/features/forecasts -->

# Forecasts [](https://sybilion.dev#forecasts)

A **forecast** is a model-generated projection of a monthly time series. Results include point estimates with quantile bands, per-driver attributions, and optional rolling-window backtest metrics. The Sybilion pipeline selects the most relevant macroeconomic signals, regional and category dimensions, and fits the best model for the series.

Forecast jobs are **asynchronous**. Submitting a request returns a `job_id`

immediately while the pipeline runs in the background, typically finishing within a few minutes. Poll the job status until it is completed, then download the resulting artifact files.

The full process:

**Submit**`POST /api/v1/forecasts`

with the time series and metadata to receive a`job_id`

.**Poll**`GET /api/v1/forecasts/{id}`

until`status: "completed"`

.**Download**the artifact files listed in the completed job response.

In this page, code examples are shown for curl, the Python SDK, and the Go SDK. For full validation rules and field-level reference, see [Forecast submission](https://sybilion.dev/forecasts-submit), [Forecast status](https://sybilion.dev/forecasts-status), and [Artifact download](https://sybilion.dev/forecasts-artifacts).

## Usa cases [](https://sybilion.dev#usa-cases)

- Forecasting a monthly series of
**40+**observations (more for longer horizons, see below). - Getting point forecasts with optional quantile bands over
**1 to 12**months. - Understanding which external drivers impact the series and by how much.
- Validating forecast quality with rolling backtest metrics.

To get driver recommendations synchronously without running a full forecast, use [Drivers](https://sybilion.dev/drivers) instead.

## Prepare data [](https://sybilion.dev#prepare-data)

The timeseries is submitted as a JSON object where each key is a date and the value is a numeric observation. Keys must follow the format `YYYY-MM-DD`

and must be the **first day of the month** — any other day-of-month is rejected. The most recent observation must fall within the past 12 months. The minimum number of observations depends on the forecast horizon (`soft_horizon`

or `hard_horizon`

, whichever is larger):

| Horizon (months) | Minimum observations |
|---|---|
| 1–3 | 40 |
| 4–6 | 60 |
| 7–12 | 120 |

We recommend storing the full request body in a JSON file. The file structure looks like this :

```
{
"pipeline_version": "v1",
"frequency": "monthly",
"recency_factor": 0.6,
"soft_horizon": 6,
"backtest": true,
"timeseries_metadata": {
"title": "Brent Crude Oil Price Monthly",
"description": "Monthly average Brent crude oil spot price in USD/barrel, sourced from EIA.",
"keywords": ["oil", "brent", "energy", "commodity"]
},
"timeseries": {
"2021-01-01": 57.64,
"2021-02-01": 65.02,
"2021-03-01": 67.24,
"...": "...",
"2025-10-01": 91.05,
"2025-11-01": 81.77,
"2025-12-01": 76.10
}
}
```


Save this as ** forecast_body.json** — the examples in the next step reference it by filename.

## Submit forecast job [](https://sybilion.dev#submit-forecast-job)

Required fields: `pipeline_version`

, `frequency`

, `recency_factor`

, `timeseries_metadata`

, `timeseries`

, and at least one of `soft_horizon`

or `hard_horizon`

.

```
curl -sS -X POST https://api.sybilion.dev/api/v1/forecasts \
-H "Authorization: Bearer $SYBILION_API_TOKEN" \
-H "Content-Type: application/json" \
-d @forecast_body.json
```


```
import json
import os
from sybilion import Client
client = Client(token=os.environ["SYBILION_API_TOKEN"])
with open("forecast_body.json", encoding="utf-8") as f:
body = json.load(f)
submit = client._api.api_v1_forecasts_post(forecast_request_v1=body)
print("job_id:", submit.job_id)
```


```
package main
import (
"context"
"encoding/json"
"fmt"
"log"
"os"
"go.sybilion.dev/sybilion"
api "go.sybilion.dev/sybilion/api"
)
func main() {
c := sybilion.New(sybilion.Options{Token: os.Getenv("SYBILION_API_TOKEN")})
data, err := os.ReadFile("forecast_body.json")
if err != nil { log.Fatal(err) }
var body api.ForecastRequestV1
if err := json.Unmarshal(data, &body); err != nil { log.Fatal(err) }
acc, err := c.SubmitForecast(context.Background(), body)
if err != nil { log.Fatal(err) }
fmt.Println("job_id:", acc.GetJobId())
}
```


A successful submission returns ** 202 Accepted**:

```
{
"job_id": "c7f2d8a9-3b4e-5f6a-7c8d-9e0f1a2b3c4d",
"poll_url": "/api/v1/forecasts/c7f2d8a9-3b4e-5f6a-7c8d-9e0f1a2b3c4d"
}
```


Copy the `job_id`

,it is needed to check the forecast job status and download artifacts. Validation errors return ** 422** with one

`{field, message}`

detail; see [Errors & limits](https://sybilion.dev/errors).

filters.limit

`filters.limit`

controls how many drivers the pipeline considers. A higher limit gives the pipeline more candidates to evaluate, which improves forecast quality but also increases the time the job takes to complete.

## Wait for job to complete [](https://sybilion.dev#wait-for-job-to-complete)

Forecasts typically take a few minutes. Poll `GET /api/v1/forecasts/{id}`

until `status`

is `completed`

. All SDKs provide a helper that handles polling automatically.

```
JOB_ID="c7f2d8a9-3b4e-5f6a-7c8d-9e0f1a2b3c4d"
until curl -sS -H "Authorization: Bearer $SYBILION_API_TOKEN" \
"https://api.sybilion.dev/api/v1/forecasts/$JOB_ID" \
| grep -q '"status":"completed"'; do
sleep 10
done
curl -sS -H "Authorization: Bearer $SYBILION_API_TOKEN" \
"https://api.sybilion.dev/api/v1/forecasts/$JOB_ID"
```


```
job = client.wait_forecast(submit.job_id, poll_s=10.0, timeout_s=3600.0)
print("status:", job.status, "cost (cents):", job.eur_cents_final)
for a in job.artifacts or []:
print(" -", a.name, a.size, "bytes")
```


```
ctx := context.Background()
job, err := c.WaitForecast(ctx, acc.GetJobId(), 10*time.Second)
if err != nil { log.Fatal(err) }
fmt.Println("status:", job.GetStatus(), "cost (cents):", job.GetEurCentsFinal())
for _, a := range job.GetArtifacts() {
fmt.Println(" -", a.GetName(), a.GetSize(), "bytes")
}
```


When `status`

is `completed`

, the response lists the artifact files ready to download:

```
{
"job_id": "c7f2d8a9-3b4e-5f6a-7c8d-9e0f1a2b3c4d",
"status": "completed",
"eur_cents_final": 5,
"artifacts": [
{
"name": "forecast.json",
"href": "/api/v1/forecasts/c7f2d8a9-3b4e-5f6a-7c8d-9e0f1a2b3c4d/artifacts/forecast.json",
"content_type": "application/json",
"size": 4096
},
{
"name": "external_signals.json",
"href": "/api/v1/forecasts/c7f2d8a9-3b4e-5f6a-7c8d-9e0f1a2b3c4d/artifacts/external_signals.json",
"content_type": "application/json",
"size": 2048
},
{
"name": "backtest_metrics.json",
"href": "/api/v1/forecasts/c7f2d8a9-3b4e-5f6a-7c8d-9e0f1a2b3c4d/artifacts/backtest_metrics.json",
"content_type": "application/json",
"size": 1280
},
{
"name": "backtest_trajectories.json",
"href": "/api/v1/forecasts/c7f2d8a9-3b4e-5f6a-7c8d-9e0f1a2b3c4d/artifacts/backtest_trajectories.json",
"content_type": "application/json",
"size": 8192
}
]
}
```


If `status`

is `failed`

or `canceled`

, the response includes a `pipeline_error`

object with a `code`

and a `detail`

field explaining what went wrong.

## Download artifacts [](https://sybilion.dev#download-artifacts)

Use the `name`

values from the `artifacts`

array above. Artifacts are available at `GET /api/v1/forecasts/{id}/artifacts/{name}`

.

| File | When present | Contents |
|---|---|---|
`forecast.json` | Always | Point forecasts and quantile bands for each horizon month. |
`external_signals.json` | Always | Ranked external drivers with importance, direction, and correlation scores. |
`backtest_metrics.json` | When `backtest: true` | Aggregated accuracy metrics (MAPE, RMSE) over rolling 6m / 12m / 24m / 60m windows. |
`backtest_trajectories.json` | When `backtest: true` | Per-fold actual vs forecast series for the last 12 months of history. |

```
JOB_ID="c7f2d8a9-3b4e-5f6a-7c8d-9e0f1a2b3c4d"
curl -sS -H "Authorization: Bearer $SYBILION_API_TOKEN" \
"https://api.sybilion.dev/api/v1/forecasts/$JOB_ID/artifacts/forecast.json"
```


```
import json
data = client.get_forecast_artifact(submit.job_id, "forecast.json")
forecast = json.loads(data)
print(forecast["data"]["forecast_series"])
```


```
import (
"io"
"net/http"
)
jobID := acc.GetJobId()
req, _ := http.NewRequestWithContext(ctx, "GET",
"https://api.sybilion.dev/api/v1/forecasts/"+jobID+"/artifacts/forecast.json",
nil,
)
req.Header.Set("Authorization", "Bearer "+os.Getenv("SYBILION_API_TOKEN"))
resp, err := http.DefaultClient.Do(req)
if err != nil { log.Fatal(err) }
defer resp.Body.Close()
buf, _ := io.ReadAll(resp.Body)
fmt.Println(string(buf))
```


Example `forecast.json`

response (6-month horizon, one point shown):

```
{
"version": "1.1",
"data": {
"forecast_horizon": 6,
"forecast_start": "2026-01-01",
"forecast_end": "2026-06-01",
"forecast_series": {
"2026-01-01": {
"forecast": 78.40,
"quantile_forecast": { "0.1": 68.2, "0.5": 78.4, "0.9": 89.1 }
},
"2026-02-01": {
"forecast": 79.15,
"quantile_forecast": { "0.1": 68.8, "0.5": 79.2, "0.9": 89.9 }
}
}
}
}
```


For the full schema of all artifact files, see [Artifact download](https://sybilion.dev/forecasts-artifacts).

For error codes, validation details, and the full JSON envelope, see [Forecast submission](https://sybilion.dev/forecasts-submit) and [Errors & limits](https://sybilion.dev/errors).

## Pricing [](https://sybilion.dev#pricing)

Billing applies **only on 2xx** responses. The cost includes a base fee plus a variable component that scales with the time the forecast job takes to complete.

A pre-charge hold is applied when the forecast job is successfully submitted. If there is not enough balance to satisfy the pre-charge hold, the operation is blocked.

## See also [](https://sybilion.dev#see-also)

- API reference:
[POST /api/v1/forecasts](https://sybilion.dev/forecasts-submit)·[GET /api/v1/forecasts/:id](https://sybilion.dev/forecasts-status)·[GET /api/v1/forecasts/:id/artifacts/:name](https://sybilion.dev/forecasts-artifacts). - Find valid filter ids:
[Regions & categories](https://sybilion.dev/regions-and-categories). - Clients:
[Using curl](https://sybilion.dev/using-curl)·[Python SDK](https://sybilion.dev/sdk-python)·[Go SDK](https://sybilion.dev/sdk-go).


---

<!-- Source: https://sybilion.dev/docs/features/drivers -->

# Drivers [](https://sybilion.dev#drivers)

**Drivers** are external macroeconomic signals identified by the Sybilion pipeline as the most relevant influences on a given time series. They quantify which signals shaped a projection and by how much, appearing as attributions in a forecast's `external_signals.json`

artifact.

Driver recommendations can also be retrieved independently, without running a full forecast. Submitting to `POST /api/v1/drivers`

returns a ranked list of drivers with importance and direction scores immediately without any polling.

Result quality of the drivers is driven by several key factors: the `keywords`

that embed domain knowledge into the driver selection, a `recency factor`

that shifts the news window used to augment the search, and `filters`

that narrow the candidate universe by region and category.

For the full request shape and per-field validation, see [POST /api/v1/drivers](https://sybilion.dev/drivers).

## Use cases [](https://sybilion.dev#use-cases)

- Getting
**driver recommendations**for suggestions or exploratory analysis. - Skipping the full forecast pipeline when only a ranked driver list with importance and direction is needed.
- Filtering by region or category to scope the recommendation universe.

For a forecast that also embeds driver attributions, submit a [forecast](https://sybilion.dev/forecasts) instead. Its `external_signals.json`

artifact carries the same kind of information.

## Pricing [](https://sybilion.dev#pricing)

Billing applies **only on 2xx** responses. The cost includes a base fee plus scales with how many result items are returned. The cost of the request is shown on the

[Developers Portal](https://sybilion.dev/billing)pricing page.

A pre-charge hold is applied based on the maximum number of drivers that can be returned. If the available balance cannot cover the hold, the operation is blocked.

## See also [](https://sybilion.dev#see-also)

- API reference:
[POST /api/v1/drivers](https://sybilion.dev/drivers). - Main feature that bundles driver attributions:
[Forecasts](https://sybilion.dev/forecasts). - Find valid filter ids:
[Regions & categories](https://sybilion.dev/regions-and-categories). - Clients:
[Using curl](https://sybilion.dev/using-curl)·[Python SDK](https://sybilion.dev/sdk-python)·[Go SDK](https://sybilion.dev/sdk-go).


---

<!-- Source: https://sybilion.dev/docs/features/alerts -->

# Alerts [](https://sybilion.dev#alerts)

An **alert** is a ranked list of macroeconomic events and shocks relevant to a given time series. Submit timeseries metadata (title, description, and keywords) and the engine returns the top matching events ordered by relevance, with trend direction, percentage change, and supporting news articles for each one.

For the full request shape and per-field validation, see [POST /api/v1/alerts](https://sybilion.dev/alerts).

## Use cases [](https://sybilion.dev#use-cases)

- Discovering
**what events or shocks are associated with a timeseries**. - Getting
**immediate results**for a recomendation system or exploratory analysis, without an async job. - Use of region or category to scope the alert universe.

## Pricing [](https://sybilion.dev#pricing)

Billing applies **only on 2xx**. The cost includes a base fee plus scales with the number of alert items the system returns. The cost of the request is shown on the

[Developers Portal](https://sybilion.dev/billing)pricing page.

A pre-charge hold is applied assuming the maximum number of alerts that can be returned, which is 100 when no result limit filter is defined. If there is not enough balance to satisfy the pre-charge hold, the operation is blocked.

## See also [](https://sybilion.dev#see-also)

- API reference:
[POST /api/v1/alerts](https://sybilion.dev/alerts). - Synchronous driver recommendations:
[Drivers](https://sybilion.dev/drivers). - Find valid filter ids:
[Regions & categories](https://sybilion.dev/regions-and-categories). - Clients:
[Using curl](https://sybilion.dev/using-curl)·[Python SDK](https://sybilion.dev/sdk-python)·[Go SDK](https://sybilion.dev/sdk-go).


---

<!-- Source: https://sybilion.dev/docs/features/regions-and-categories -->

# Regions & categories [](https://sybilion.dev#regions-categories)

Regions and categories are read-only catalogs that expose the integer ids accepted by the `filters`

object on [Forecasts](https://sybilion.dev/forecasts), [Drivers](https://sybilion.dev/drivers), and [Alerts](https://sybilion.dev/alerts). Use them to discover valid ids before building a filter or populating a picker.

**Regions** represent geographic dimensions: countries, sub-regions, or broader economic zones. Each entry carries an integer id, a name, and hierarchy metadata (parent, path, coordinates).

**Categories** represent thematic or sector dimensions: industry groups, commodity classes, or similar classifications. Each entry carries an integer id, a name, and optional classification codes.

Both lists are returned in full with no pagination, sorted by id in ascending order.

## Pricing [](https://sybilion.dev#pricing)

Authentication is required but these catalogs are **not billed**. Lookups do not consume credits.

## See also [](https://sybilion.dev#see-also)

- API reference with code examples:
[GET /api/v1/regions](https://sybilion.dev/catalog#regions)·[GET /api/v1/categories](https://sybilion.dev/catalog#categories). - These ids are used in filters on:
[Forecasts](https://sybilion.dev/forecasts)·[Drivers](https://sybilion.dev/drivers)·[Alerts](https://sybilion.dev/alerts). - Clients:
[Using curl](https://sybilion.dev/using-curl)·[Python SDK](https://sybilion.dev/sdk-python)·[Go SDK](https://sybilion.dev/sdk-go).


---

<!-- Source: https://sybilion.dev/docs/features/account -->

# Account & usage [](https://sybilion.dev#account-usage)

Your account exposes balance, credit grants, charge history, and async job summaries. All of it is read-only from the API; billing settings are managed separately in the Developers Portal.

Three resources cover this:

— balance, pricing tier, signup trial, and active credit grants.`GET /api/v1/me`

— paginated charge history, one row per billed event.`GET /api/v1/usage`

— paginated list of async jobs (forecasts).`GET /api/v1/jobs`


All monetary fields are integer **EUR cents** (`100`

= `€1.00`

). Top-ups, payment methods, and auto top-up settings are managed in the [Developers Portal](https://sybilion.dev/billing) — not via this API.

## Balance and available balance [](https://sybilion.dev#balance-and-available-balance)

Your account has two balance figures. The ledger total (`balance_eur_cents`

) reflects all top-ups and charges. The available balance (`available_eur_cents`

) is lower when async forecast jobs are running, because a hold is reserved until each job completes or fails.

## Credit grants [](https://sybilion.dev#credit-grants)

Credits are held as individual grants (signup trial, top-up, partner credit, and similar), each having its remaining balance, expiry date, and source. Grants are consumed in expiry order, soonest-to-expire first.

## Usage history [](https://sybilion.dev#usage-history)

Each billed event produces a row in the usage history, whether an async job settling or a call completing. The list is paginated and sortable, suitable for building usage reports or auditing spend.

## Job list [](https://sybilion.dev#job-list)

Async jobs (forecasts) can be listed with lightweight summaries: status, submission time, and final cost. For a single job's full state and artifacts, use [ GET /api/v1/forecasts/:id](https://sybilion.dev/forecasts-status).

## Top up balance [](https://sybilion.dev#top-up-balance)

Credit top-ups and payment methods are managed in the **Developers Portal**, there is no API to initiate a top-up or update payment details.

## See also [](https://sybilion.dev#see-also)

- API reference:
·`GET /api/v1/me`

·`GET /api/v1/usage`

.`GET /api/v1/jobs`

- Clients:
[Using curl](https://sybilion.dev/using-curl)·[Python SDK](https://sybilion.dev/sdk-python)·[Go SDK](https://sybilion.dev/sdk-go).


---

<!-- Source: https://sybilion.dev/docs/sdks/ -->

# Clients [](https://sybilion.dev#clients)

The Sybilion API is plain HTTP/JSON. Pick the client that fits your stack:

| Client | Install | Best for |
|---|---|---|
|

[Python SDK](https://sybilion.dev/sdk-python)`pip install sybilion`

`wait_forecast`

and pagination iterators.[Go SDK](https://sybilion.dev/sdk-go)`go get go.sybilion.dev/sybilion@latest`

`WaitForecast`

and error-unwrap helpers.All three clients hit the same endpoints with the same Bearer token. **Feature pages** in the [Features](https://sybilion.dev/features/forecasts) section show every use case in all three, side by side, so you can compare and switch tracks at any time.

## Auth & base URL [](https://sybilion.dev#auth-base-url)

- Pass your
**Bearer token**(an API key`sk_ops_…`

or a dashboard session token) into the client constructor or as the`Authorization: Bearer …`

header. - The default API origin is
. Override per-process with the`https://api.sybilion.dev`

`SYBILION_API_BASE_URL`

environment variable, or per-call via the constructor's`base_url`

(Python) /`Options.BaseURL`

(Go) / by substituting the URL (curl).

See [Authentication](https://sybilion.dev/authentication) for token types and where to get them.

## Picking a client [](https://sybilion.dev#picking-a-client)

**Just exploring or scripting?**[Using curl](https://sybilion.dev/using-curl)is enough — auth, pagination, polling, and artifact downloads in plain shell.**Production Python?**[Python SDK](https://sybilion.dev/sdk-python)— typed models, validation errors as exceptions, polling helpers.**Production Go?**[Go SDK](https://sybilion.dev/sdk-go)— context-aware polling, custom HTTP client injection, generated models.

You can use all three in the same project — for example, curl in CI smoke tests and the SDK in your service code.

## Versioning [](https://sybilion.dev#versioning)

Both SDKs use **SemVer** independently of the API server version. Pin to a tag for production builds. The wire contract itself is OpenAPI-versioned; breaking changes appear as new operations or new schema versions, not silent edits to existing ones.

## Package pages [](https://sybilion.dev#package-pages)

| Client | Package |
|---|---|
| Python SDK |
`sybilion` on PyPI |

`go.sybilion.dev/sybilion`

on pkg.go.devNeed a client for another language? Generate one from the public OpenAPI spec at ** https://api.sybilion.dev/openapi.yaml** with

[openapi-generator](https://openapi-generator.tech/)(this is exactly how the Python and Go SDKs are built).

## See also [](https://sybilion.dev#see-also)

[Features](https://sybilion.dev/features/forecasts)— every use case with curl + Python + Go side by side.[Quickstart](https://sybilion.dev/quickstart)— five steps to a completed forecast.[Community & support](https://sybilion.dev/community)— Slack, Discord, email.


---

<!-- Source: https://sybilion.dev/docs/using-curl -->

# Using curl [](https://sybilion.dev#using-curl)

The Sybilion API is plain HTTP/JSON. If you don't want a generated client — for shell scripts, prototypes, CI, or onboarding — these patterns get you the same coverage as the SDKs without any dependencies.

## Setup [](https://sybilion.dev#setup)

Export your API key once per shell:

`export SYBILION_API_TOKEN="sk_ops_..."`


The base URL is ** https://api.sybilion.dev**. To hit a non-production host, substitute the URL.

## Authentication header [](https://sybilion.dev#authentication-header)

Every authenticated request takes a Bearer token:

```
curl -sS -H "Authorization: Bearer $SYBILION_API_TOKEN" \
https://api.sybilion.dev/api/v1/me
```


A missing or invalid token returns ** 401 Unauthorized**. There is no separate "verify token" endpoint —

`GET /api/v1/me`

is the canonical health check (it also tells you balance, tier, and trial state in one call).See [Authentication](https://sybilion.dev/authentication) for the supported token types and how to get them.

## Paginated lists [](https://sybilion.dev#paginated-lists)

Listing endpoints (`/usage`

, `/jobs`

) share four query parameters:

| Param | Default | Notes |
|---|---|---|
`page` | `1` | 1-based. |
`limit` | `50` | Max per page.`200` |
`sort` | endpoint-specific | E.g. `created_at` , `id` . |
`order` | `desc` | `asc` or `desc` . |

The response wraps results in a `pagination`

object:

```
curl -sS -H "Authorization: Bearer $SYBILION_API_TOKEN" \
"https://api.sybilion.dev/api/v1/usage?page=1&limit=50&sort=created_at&order=desc"
```


To walk every page, increment `page`

until you've seen `pagination.total_pages`

pages.

## Polling an async job [](https://sybilion.dev#polling-an-async-job)

Forecasts return ** 202** with a

`job_id`

. Poll **until**

`GET /api/v1/forecasts/:id`

`settled`

is `true`

, then read `status`

and `artifacts`

:```
JOB_ID="<paste job_id>"
until curl -sS -H "Authorization: Bearer $SYBILION_API_TOKEN" \
"https://api.sybilion.dev/api/v1/forecasts/$JOB_ID" | grep -qE '"settled"[[:space:]]*:[[:space:]]*true'; do
sleep 2
done
curl -sS -H "Authorization: Bearer $SYBILION_API_TOKEN" \
"https://api.sybilion.dev/api/v1/forecasts/$JOB_ID"
```


The `grep`

check is a quick shell-only heuristic (it matches `"settled": true`

as text); in production code, parse the JSON and read `settled`

as a boolean so you cannot be misled by the same substring appearing elsewhere in the body.

Forecasts run for tens of seconds to a few minutes. Pick a poll interval (2–5 seconds is fine) and add a max-duration guard for production use.

## Reading the error envelope [](https://sybilion.dev#reading-the-error-envelope)

Every error response uses the same shape. For validation:

```
{
"error": "validation_failed",
"details": [{ "field": "soft_horizon", "message": "soft_horizon must be between 1 and 12" }]
}
```


Validation is **fail-fast** — only the first offending field is reported per call. Other errors use a shorter shape:

`{ "error": "insufficient credits" }`


Common patterns:

```
# Show HTTP status on non-2xx; otherwise print the body.
RES=$(curl -sS -w "\n%{http_code}" \
-H "Authorization: Bearer $SYBILION_API_TOKEN" \
https://api.sybilion.dev/api/v1/forecasts \
-d @forecast_body.json)
BODY=$(printf '%s' "$RES" | sed '$d')
CODE=$(printf '%s' "$RES" | tail -n1)
if [ "$CODE" -ge 400 ]; then
printf 'HTTP %s — body:\n' "$CODE"
printf '%s\n' "$BODY"
else
printf '%s\n' "$BODY"
fi
```


Full catalog of HTTP codes: [Errors & limits](https://sybilion.dev/errors).

## Downloading artifacts [](https://sybilion.dev#downloading-artifacts)

Forecast artifacts stream through the API at ** GET /api/v1/forecasts/:id/artifacts/:name** — there are no direct storage URLs. Use

`-o`

to save:```
JOB_ID="<paste job_id>"
for ART in forecast.json external_signals.json backtest_metrics.json; do
curl -sS -H "Authorization: Bearer $SYBILION_API_TOKEN" \
-o "$ART" \
"https://api.sybilion.dev/api/v1/forecasts/$JOB_ID/artifacts/$ART"
done
```


Inspect each file in your application or editor — they are JSON with a top-level `version`

and `data`

object.

Artifact responses can be large (up to **100 MiB** per file). Use `Range`

headers for partial reads — the API returns ** 206** when honoring a range. Full artifact contract:

[Artifact download](https://sybilion.dev/forecasts-artifacts).

## Idempotent retries [](https://sybilion.dev#idempotent-retries)

For synchronous billed calls (e.g. `POST /api/v1/drivers`

), pass a stable ** X-Request-ID** header on each retry to deduplicate billing on success:

```
REQ_ID=$(uuidgen)
curl -sS -X POST https://api.sybilion.dev/api/v1/drivers \
-H "Authorization: Bearer $SYBILION_API_TOKEN" \
-H "Content-Type: application/json" \
-H "X-Request-ID: $REQ_ID" \
-d @drivers_body.json
```


## Useful flags [](https://sybilion.dev#useful-flags)

| Flag | Why |
|---|---|
`-sS` | Silent + show errors. Hides progress bars without hiding real failures. |
`-w "\n%{http_code}\n"` | Append the HTTP status to the output for scripted handling. |
`-D -` | Dump response headers to stdout (useful for inspecting `Content-Type` , `Content-Length` ). |
`--fail-with-body` | Exit non-zero on `4xx` / `5xx` while still printing the body (curl 7.76+). |
`-o file` | Stream the body to disk (use for artifact downloads). |
`-H "Accept-Encoding: gzip"` | Lets the API gzip large list responses. |

## See also [](https://sybilion.dev#see-also)

[Quickstart](https://sybilion.dev/quickstart)— end-to-end walkthrough.- Feature pages with curl tabs:
[Forecasts](https://sybilion.dev/features/forecasts)·[Drivers](https://sybilion.dev/features/drivers)·[Regions & categories](https://sybilion.dev/features/regions-and-categories)·[Account & usage](https://sybilion.dev/features/account) [Errors & limits](https://sybilion.dev/errors)·[Authentication](https://sybilion.dev/authentication)


---

<!-- Source: https://sybilion.dev/docs/sdk-python -->

# Python SDK [](https://sybilion.dev#python-sdk)

The official Python SDK is published as ** sybilion** on PyPI. It ships two layers in one package:

— the hand-written wrapper exposed to users (`sybilion`

`Client`

, ergonomic methods, pagination iterators, exceptions).— the OpenAPI-generated low-level client. Accessible via`sybilion._api`

`client._api`

as an escape hatch for endpoints not yet wrapped.

This page documents the wrapper's idioms. For canonical use cases (forecasts, drivers, alerts, account, regions/categories), see the [Features](https://sybilion.dev/features/forecasts) section — every example there has a Python tab.

## Install [](https://sybilion.dev#install)

`pip install sybilion`


Requires **Python 3.10+**.

## Construct a client [](https://sybilion.dev#construct-a-client)

```
import os
from sybilion import Client
# Token read from the environment automatically:
client = Client()
# Or pass it explicitly:
client = Client(token=os.environ["SYBILION_API_TOKEN"])
me = client.me()
print(me.user_id, me.available_eur_cents)
```


When `token`

is omitted, `Client`

reads `SYBILION_API_TOKEN`

from the environment. If neither is provided it raises `ValueError`

. `Client`

also accepts an optional `base_url`

to override the default API origin.

### Base URL resolution [](https://sybilion.dev#base-url-resolution)

`Client(base_url=...)`

resolves the API origin in this order:

- Explicit
`base_url`

argument. `SYBILION_API_BASE_URL`

environment variable.- The compiled-in default (
`sybilion.DEFAULT_PUBLIC_API_BASE_URL`

, currently`https://api.sybilion.dev`

).

To verify the resolution at runtime:

```
from sybilion import resolve_api_base_url
print(resolve_api_base_url(None)) # what Client will use
```


## Wrapper methods [](https://sybilion.dev#wrapper-methods)

`Client`

exposes a method for every endpoint:

| Method | Endpoint |
|---|---|
`me()` | `GET /api/v1/me` |
`submit_forecast(request)` | `POST /api/v1/forecasts` |
`get_forecast(id)` | `GET /api/v1/forecasts/{id}` |
`get_forecast_artifact(id, name)` | `GET /api/v1/forecasts/{id}/artifacts/{name}` |
`wait_forecast(job_id, *, poll_s, timeout_s)` | polling helper |
`get_drivers(request)` | `POST /api/v1/drivers` |
`get_alerts(*, metadata, context_enriched, ...)` | `POST /api/v1/alerts` |
`list_jobs(*, page, limit, ...)` | `GET /api/v1/jobs` |
`iter_jobs_pages(*, limit, status, ...)` | pagination helper |
`get_usage(*, page, limit, ...)` | `GET /api/v1/usage` |
`iter_usage_pages(*, limit, ...)` | pagination helper |
`list_categories()` | `GET /api/v1/categories` |
`list_regions()` | `GET /api/v1/regions` |

For endpoints not yet covered, the underlying generated client is accessible as `client._api`

(a `DefaultApi`

instance). Method names mirror the OpenAPI operationId: `api_v1_me_get`

, `api_v1_forecasts_post`

, etc.

`wait_forecast`

— poll until settled [](https://sybilion.dev#wait-forecast-—-poll-until-settled)

```
submit = client.submit_forecast(body)
job = client.wait_forecast(
submit.job_id,
poll_s=2.0, # seconds between polls
timeout_s=3600.0, # max total wait
)
print(job.status, job.eur_cents_final)
for art in job.artifacts or []:
print(art.name, art.size)
```


Behaviour:

- Polls
`GET /api/v1/forecasts/{id}`

every`poll_s`

seconds. - Returns the response
**as soon as**— works for`settled == True`

`completed`

,`failed`

, and`canceled`

jobs. - Raises
`TimeoutError`

if the deadline is exceeded; the job continues running on the server and you can resume polling later.

Pick `poll_s`

based on your latency tolerance — 2–5 seconds is typical. The wrapper does not back off; if you need exponential backoff, call `client.get_forecast(id)`

in your own loop.

`get_alerts`

— synchronous alert detection [](https://sybilion.dev#get-alerts-—-synchronous-alert-detection)

`client.get_alerts`

calls `POST /api/v1/alerts`

and returns the result immediately — no polling required.

```
import os
from sybilion import Client
from sybilion._api.models import Filters, TimeseriesMetadata
client = Client(token=os.environ["SYBILION_API_TOKEN"])
meta = TimeseriesMetadata(
title="Brent Crude Oil Price Monthly",
description="Monthly average Brent crude oil spot price in USD/barrel.",
keywords=["oil", "brent", "energy", "commodity"],
)
filters = Filters(categories=[3, 7], regions=[42], limit=25)
alerts = client.get_alerts(
metadata=meta,
context_enriched=False,
filters=filters,
date_from="2024-01-01",
)
for alert in alerts:
print(alert["name"], alert["pct_change"], alert["trending"])
```


Parameters:

| Parameter | Type | Notes |
|---|---|---|
`metadata` | `TimeseriesMetadata` | Required. Title, description, keywords describing the series. |
`context_enriched` | `bool` | Required. Pass `True` if the metadata was already enriched upstream; `False` to let the engine enrich it. |
`filters` | `Filters | None` | Optional. Scope by category / region ids and cap item count with `limit` . |
`date_from` | `str | None` | Optional. Earliest date bound for alert events (`YYYY-MM-DD` ). |
`date_to` | `str | None` | Optional. Latest date bound for alert events (`YYYY-MM-DD` ). |

Returns a `list[dict]`

— each dict has `name`

, `pct_change`

, `trending`

, and a `news[]`

sub-list. See [POST /api/v1/alerts](https://sybilion.dev/alerts) for the full response shape.

## Pagination iterators [](https://sybilion.dev#pagination-iterators)

Two helpers walk paginated endpoints page-by-page so you don't have to track `page`

/ `total_pages`

yourself.

```
# All usage events (newest first by default).
for page in client.iter_usage_pages(limit=100, sort="created_at", order="desc"):
for ev in page.usage_events:
print(ev.id, ev.eur_cents_charged, ev.created_at)
# Only completed forecast jobs.
for page in client.iter_jobs_pages(limit=100, status="completed"):
for job in page.jobs:
print(job.job_id, job.status, job.eur_cents_final)
```


Each iterator stops automatically when `page == pagination.total_pages`

. Stop early with `break`

.

## Error handling [](https://sybilion.dev#error-handling)

Wrapper methods raise a plain `Exception`

whose message is the `error`

field from the API response body. If the body can't be parsed, the original `ApiException`

from the generated client is re-raised.

```
try:
job = client.submit_forecast(body)
except Exception as exc:
print("error:", exc)
```


When calling `client._api.*`

directly, the generated client raises typed exceptions:

```
from sybilion import (
ApiException,
BadRequestException,
UnauthorizedException,
UnprocessableEntityException,
ServiceException,
)
try:
job = client._api.api_v1_forecasts_post(forecast_request_v1=body)
except UnprocessableEntityException as exc:
# 422 — single validation detail in exc.body
print("validation failed:", exc.body)
except UnauthorizedException:
print("token rejected — refresh SYBILION_API_TOKEN")
except ApiException as exc:
print("HTTP", exc.status, exc.reason, exc.body)
```


| Exception | HTTP | When |
|---|---|---|
`BadRequestException` | `400` | Malformed JSON, invalid query params. |
`UnauthorizedException` | `401` | Missing or invalid token. |
`ForbiddenException` | `403` | Authenticated but not allowed. |
`NotFoundException` | `404` | Unknown id, or outside the visibility window. |
`ConflictException` | `409` | Job not yet completed (artifact downloads). |
`UnprocessableEntityException` | `422` | Validation failure — body has `error` + one `details[]` . |
`ServiceException` | `5xx` | Transient backend failure; retry with backoff. |
`ApiException` | other | Catch-all base class. |

Useful attributes on every `ApiException`

: `status`

(int), `reason`

(str), `body`

(raw bytes), `headers`

(dict).

For a `402`

(insufficient balance), the SDK raises `ApiException`

. Inspect `exc.status == 402`

and parse `exc.body`

for `error`

text. Surface this as "top up balance" in your UI.

## Custom configuration [](https://sybilion.dev#custom-configuration)

The generated client uses `urllib3`

under the hood. To override the default timeout or connection settings, build a `Configuration`

directly and access the generated API:

```
import os
from sybilion import resolve_api_base_url
from sybilion._api import ApiClient, Configuration, DefaultApi
cfg = Configuration(
host=resolve_api_base_url(None),
access_token=os.environ["SYBILION_API_TOKEN"],
)
cfg.retries = 3 # urllib3 retry policy
cfg.connection_pool_maxsize = 10 # parallel calls
raw_api = DefaultApi(ApiClient(cfg))
me = raw_api.api_v1_me_get()
```


Per-call timeouts can be passed via the underlying urllib3 request — see [the urllib3 docs](https://urllib3.readthedocs.io/) for the full surface.

## Versioning [](https://sybilion.dev#versioning)

The SDK uses **SemVer** independently of the API server version; minor releases stay backward-compatible, breaking changes bump the major. Pin to a tag (`sybilion==0.1.0`

) for production builds.

## See also [](https://sybilion.dev#see-also)

[Features](https://sybilion.dev/features/forecasts)— full use-case walkthroughs with Python tabs.[Alerts](https://sybilion.dev/features/alerts)·[Drivers](https://sybilion.dev/features/drivers)— synchronous endpoints with SDK wrappers.[Using curl](https://sybilion.dev/using-curl)and[Go SDK](https://sybilion.dev/sdk-go).- Package page:
.`sybilion`

on PyPI


---

<!-- Source: https://sybilion.dev/docs/sdk-go -->

# Go SDK [](https://sybilion.dev#go-sdk)

The official Go SDK is published as ** go.sybilion.dev/sybilion**. It ships two packages in one module:

at`sybilion`

`go.sybilion.dev/sybilion`

— the hand-written wrapper exposed to users (`New`

,`Options`

, direct methods,`WaitForecast`

, pagination callbacks, ...).at`sybilionapi`

`go.sybilion.dev/sybilion/api`

— the OpenAPI-generated low-level client and models. Exposed via`c.DefaultAPI()`

for endpoints not yet wrapped.

This page documents the wrapper's idioms. For canonical use cases (forecasts, drivers, alerts, account, regions/categories), see the [Features](https://sybilion.dev/features/forecasts) section — every example there has a Go tab.

## Install [](https://sybilion.dev#install)

`go get go.sybilion.dev/sybilion@latest`


Requires **Go 1.25+**.

## Construct a client [](https://sybilion.dev#construct-a-client)

```
package main
import (
"context"
"fmt"
"log"
"os"
"go.sybilion.dev/sybilion"
)
func main() {
// Token read from SYBILION_API_TOKEN automatically:
c := sybilion.New(sybilion.Options{})
// Or pass it explicitly:
c = sybilion.New(sybilion.Options{
Token: os.Getenv("SYBILION_API_TOKEN"),
})
me, err := c.Me(context.Background())
if err != nil {
log.Fatal(err)
}
fmt.Println(me.GetUserId(), me.GetAvailableEurCents())
}
```


When `Options.Token`

is empty, `New`

reads `SYBILION_API_TOKEN`

from the environment. If both are empty, the client makes unauthenticated requests (only `/health`

works).

`Options`

fields [](https://sybilion.dev#options-fields)

| Field | Default | Notes |
|---|---|---|
`Token` | empty | Bearer token. When empty, `SYBILION_API_TOKEN` env var is read. |
`BaseURL` | resolved at runtime | API origin without trailing slash. See resolution rules below. |
`HTTPClient` | `&http.Client{Timeout: 60 * time.Second}` | Inject your own for custom transports, retries, or different timeouts. |
`UserAgent` | generator default | Override to brand outgoing requests. |

### Base URL resolution [](https://sybilion.dev#base-url-resolution)

`Options.BaseURL`

is resolved in this order:

- Explicit
`Options.BaseURL`

. `SYBILION_API_BASE_URL`

environment variable (constant`sybilion.EnvSybilionAPIBaseURL`

).- The compiled-in default
`sybilion.DefaultPublicAPIBaseURL`

(currently`https://api.sybilion.dev`

).

Trailing slashes are stripped.

## Wrapper methods [](https://sybilion.dev#wrapper-methods)

`Client`

exposes a method for every endpoint:

| Method | Endpoint |
|---|---|
`Me(ctx)` | `GET /api/v1/me` |
`SubmitForecast(ctx, req)` | `POST /api/v1/forecasts` |
`GetForecast(ctx, id)` | `GET /api/v1/forecasts/{id}` |
`GetForecastArtifact(ctx, id, name)` | `GET /api/v1/forecasts/{id}/artifacts/{name}` |
`WaitForecast(ctx, jobID, poll)` | polling helper |
`GetDrivers(ctx, req)` | `POST /api/v1/drivers` |
`GetAlerts(ctx, req)` | `POST /api/v1/alerts` |
`ForEachJobsPage(ctx, sort, order, limit, fn)` | pagination helper |
`ForEachUsagePage(ctx, sort, order, limit, fn)` | pagination helper |
`ListCategories(ctx)` | `GET /api/v1/categories` |
`ListRegions(ctx)` | `GET /api/v1/regions` |

For endpoints not yet wrapped, `c.DefaultAPI()`

returns the `*sybilionapi.DefaultAPIService`

. Method names mirror the OpenAPI operationId: `ApiV1MeGet`

, `ApiV1ForecastsPost`

, `ApiV1ForecastsIdGet`

, `ApiV1RegionsGet`

, etc. The fluent builder returns `(*Model, *http.Response, error)`

from `Execute()`

.

`regions, _, err := c.DefaultAPI().ApiV1RegionsGet(ctx).Execute()`


`WaitForecast`

— poll until settled [](https://sybilion.dev#waitforecast-—-poll-until-settled)

```
import "time"
ctx := context.Background()
acc, err := c.SubmitForecast(ctx, *body)
if err != nil { log.Fatal(err) }
job, err := c.WaitForecast(ctx, acc.GetJobId(), 2*time.Second)
if err != nil { log.Fatal(err) }
fmt.Println(job.GetStatus(), job.GetEurCentsFinal())
for _, a := range job.GetArtifacts() {
fmt.Println(a.GetName(), a.GetSize())
}
```


Behaviour:

- Polls
`GET /api/v1/forecasts/{id}`

every`poll`

interval (no jitter, no backoff). - Returns the response
**as soon as**— works for`settled == true`

`completed`

,`failed`

, and`canceled`

jobs. - Honors
`ctx`

: cancel the context to stop polling. The wrapper returns`ctx.Err()`

.

For a hard wall-clock cap, wrap the call in `context.WithTimeout`

:

```
ctx, cancel := context.WithTimeout(context.Background(), 10*time.Minute)
defer cancel()
job, err := c.WaitForecast(ctx, acc.GetJobId(), 2*time.Second)
```


`c.Forecasts().Wait(ctx, jobID, poll)`

is an alias for `c.WaitForecast`

kept for backwards compatibility.

`GetAlerts`

— synchronous alert detection [](https://sybilion.dev#getalerts-—-synchronous-alert-detection)

`c.GetAlerts`

calls `POST /api/v1/alerts`

and returns the result immediately — no polling required.

```
package main
import (
"context"
"fmt"
"log"
"os"
"go.sybilion.dev/sybilion"
api "go.sybilion.dev/sybilion/api"
)
func main() {
c := sybilion.New(sybilion.Options{Token: os.Getenv("SYBILION_API_TOKEN")})
meta := api.NewTimeseriesMetadata("Brent Crude Oil Price Monthly")
meta.SetDescription("Monthly average Brent crude oil spot price in USD/barrel.")
meta.SetKeywords([]string{"oil", "brent", "energy", "commodity"})
filters := api.NewFilters()
filters.SetCategories([]int32{3, 7})
filters.SetRegions([]int32{42})
filters.SetLimit(25)
alerts, err := c.GetAlerts(context.Background(), sybilion.AlertsRequest{
Metadata: *meta,
ContextEnriched: false,
Filters: filters,
DateFrom: "2024-01-01",
})
if err != nil {
log.Fatal(err)
}
for _, a := range alerts {
fmt.Println(a.Name, a.PctChange, a.Trending)
}
}
```


`AlertsRequest`

fields:

| Field | Type | Notes |
|---|---|---|
`Metadata` | `api.TimeseriesMetadata` | Required. Title, description, keywords describing the series. |
`ContextEnriched` | `bool` | Required. Set to `true` if the metadata was already enriched upstream; `false` to let the engine enrich it. |
`Filters` | `*api.Filters` | Optional. Scope by category / region ids and cap item count with `SetLimit` . |
`DateFrom` | `string` | Optional. Earliest date bound for alert events (`YYYY-MM-DD` ). |
`DateTo` | `string` | Optional. Latest date bound for alert events (`YYYY-MM-DD` ). |

Returns `([]sybilion.AlertItem, error)`

. Each `AlertItem`

has `Name`

, `PctChange`

, `Trending`

, and `News []NewsItem`

. See [POST /api/v1/alerts](https://sybilion.dev/alerts) for the full response shape.

## Pagination callbacks [](https://sybilion.dev#pagination-callbacks)

`ForEachUsagePage`

and `ForEachJobsPage`

walk paginated endpoints page-by-page. The callback receives each page and returns `(continueNext bool, err error)`

— return `false`

to stop early.

```
// Walk all usage events.
err := c.ForEachUsagePage(ctx, "created_at", "desc", 50, func(ctx context.Context, page *api.ApiV1UsageGet200Response) (bool, error) {
for _, ev := range page.GetUsageEvents() {
fmt.Println(ev.GetId(), ev.GetEurCentsCharged())
}
return true, nil // continue to the next page
})
if err != nil { log.Fatal(err) }
// Walk completed jobs only.
err = c.ForEachJobsPage(ctx, "created_at", "desc", 50, func(ctx context.Context, page *api.ApiV1JobsGet200Response) (bool, error) {
for _, j := range page.GetJobs() {
fmt.Println(j.GetJobId(), j.GetStatus())
}
return true, nil
})
```


Iteration stops automatically when the last page is reached, or when the callback returns `false`

or a non-nil error.

## Error handling [](https://sybilion.dev#error-handling)

Wrapper methods return a plain `error`

whose message is the `error`

field from the API response body. If the body can't be parsed, the original `*api.GenericOpenAPIError`

is returned as-is.

```
me, err := c.Me(ctx)
if err != nil {
log.Fatal(err) // prints the API error message
}
```


When you need the HTTP status code — for example to branch on `402`

vs `422`

— use `DefaultAPI()`

directly, which returns `(*Model, *http.Response, error)`

:

```
resp, httpResp, err := c.DefaultAPI().ApiV1ForecastsPost(ctx).
ForecastRequestV1(*body).
Execute()
if err != nil {
log.Printf("status=%d body=%s", httpResp.StatusCode, ...)
}
_ = resp
```


## Custom HTTP client [](https://sybilion.dev#custom-http-client)

Inject any `*http.Client`

to replace timeouts, transport, retries, or proxies:

```
import (
"crypto/tls"
"net/http"
"os"
"time"
"go.sybilion.dev/sybilion"
)
httpc := &http.Client{
Timeout: 30 * time.Second,
Transport: &http.Transport{
TLSClientConfig: &tls.Config{MinVersion: tls.VersionTLS12},
MaxIdleConns: 50,
IdleConnTimeout: 90 * time.Second,
},
}
c := sybilion.New(sybilion.Options{
Token: os.Getenv("SYBILION_API_TOKEN"),
HTTPClient: httpc,
UserAgent: "my-app/1.0",
})
```


For per-call cancellation and timeouts, use `context.WithTimeout`

/ `context.WithCancel`

instead of mutating the `*http.Client`

.

## Versioning [](https://sybilion.dev#versioning)

The SDK uses **SemVer** independently of the API server version; minor releases stay backward-compatible, breaking changes bump the major. Pin to a tag (`go get go.sybilion.dev/`

) for production builds.[[email protected]](https://sybilion.dev/cdn-cgi/l/email-protection)

## See also [](https://sybilion.dev#see-also)

[Features](https://sybilion.dev/features/forecasts)— full use-case walkthroughs with Go tabs.[Alerts](https://sybilion.dev/features/alerts)·[Drivers](https://sybilion.dev/features/drivers)— synchronous endpoints with SDK wrappers.[Using curl](https://sybilion.dev/using-curl)and[Python SDK](https://sybilion.dev/sdk-python).- Package page:
.`go.sybilion.dev/sybilion`

on pkg.go.dev


---

<!-- Source: https://sybilion.dev/docs/openapi -->

# Public OpenAPI [](https://sybilion.dev#public-openapi)

The API publishes a single **public** OpenAPI 3 document at ** https://api.sybilion.dev/docs**.

The document covers the full integrator-facing surface: every path, parameter, and schema available to third-party clients. Dashboard-only operations are excluded and not part of this API.

Use the YAML for client generation, contract tests, and offline reference.


---

<!-- Source: https://sybilion.dev/docs/me -->

`GET /api/v1/me`

[](https://sybilion.dev#get-api-v1-me)

Read-only snapshot of the authenticated user. Use this to display balance, current pricing tier, and trial status. All monetary fields are integer **EUR cents** (`100`

cents = `€1.00`

). Manage account settings such as auto top-up in the [Developers Portal](https://sybilion.dev/billing) — they are exposed read-only here for reference.

## Call the endpoint [](https://sybilion.dev#call-the-endpoint)

```
curl -sS -H "Authorization: Bearer $SYBILION_API_TOKEN" \
https://api.sybilion.dev/api/v1/me
```


```
import os
from sybilion import Client
client = Client(token=os.environ["SYBILION_API_TOKEN"])
me = client.me()
trial_left = me.signup_trial.remaining_eur_cents if me.signup_trial else 0
print(
"tier:", me.api_usage_tier,
"balance:", me.available_eur_cents,
"trial_left:", trial_left,
)
```


```
package main
import (
"context"
"fmt"
"log"
"os"
"go.sybilion.dev/sybilion"
)
func main() {
c := sybilion.New(sybilion.Options{
Token: os.Getenv("SYBILION_API_TOKEN"),
})
me, err := c.Me(context.Background())
if err != nil {
log.Fatal(err)
}
fmt.Printf("tier=%d balance=%d\n",
me.GetApiUsageTier(), me.GetAvailableEurCents())
}
```


## Response [](https://sybilion.dev#response)

```
{
"user_id": "1f2a8b3e-4c5d-46d7-9a01-2b3c4d5e6f70",
"balance_eur_cents": 1234,
"available_eur_cents": 1134,
"api_usage_tier": 1,
"lifetime_paid_cents": 5000,
"payment_count": 1,
"has_ever_paid": true,
"euro_tranches": [
{
"id": "9c8d7e6f-1a2b-3c4d-5e6f-7a8b9c0d1e2f",
"source": "stripe",
"initial_eur_cents": 5000,
"remaining_eur_cents": 3865,
"expires_at": "2027-04-30T10:05:00Z",
"created_at": "2026-04-30T10:05:00Z"
}
],
"signup_trial": {
"granted_at": "2026-04-15T10:00:00Z",
"initial_eur_cents": 100,
"remaining_eur_cents": 0,
"expires_at": "2026-04-30T10:00:00Z"
},
"auto_recharge": {
"enabled": false,
"below_eur_cents": 0,
"target_eur_cents": 0,
"monthly_cap_cents": 0,
"meter_cents": 0,
"has_stripe_customer": true,
"meter_month": null
}
}
```


## Field reference [](https://sybilion.dev#field-reference)

### Top-level [](https://sybilion.dev#top-level)

| Field | Meaning |
|---|---|
`user_id` | Stable UUID for the caller. |
`balance_eur_cents` | Ledger balance in EUR cents (top-ups, charges, refunds, grants). |
`available_eur_cents` | `balance_eur_cents` minus active holds for in-flight async jobs, in EUR cents. |
`api_usage_tier` | Your current pricing tier level. Drives rate-limit and concurrency caps — see
|

`lifetime_paid_cents`

`payment_count`

`has_ever_paid`

`true`

once your first top-up settles.When async forecast jobs are running, holds reserve part of the balance until each job **settles** or **fails**; then `available_eur_cents`

moves back toward `balance_eur_cents`

.

`euro_tranches[]`

[](https://sybilion.dev#euro-tranches)

Active grants that still have a positive balance and have not expired (`remaining_eur_cents > 0`

AND `expires_at > now()`

). Tranches are consumed in `expires_at ASC`

order.

| Field | Meaning |
|---|---|
`id` | UUID of the grant. |
`source` | One of `signup_trial` , `stripe` , `partner` , `legacy` . Other labels may appear for custom grants. |
`initial_eur_cents` | Amount initially granted in the tranche, in EUR cents. |
`remaining_eur_cents` | Amount left after charges and holds, in EUR cents. |
`expires_at` | RFC3339 timestamp. Always present — every tranche has an expiry (top-ups are typically valid for 1 year). |
`created_at` | RFC3339 timestamp the grant was inserted. |

`signup_trial`

[](https://sybilion.dev#signup-trial)

Present **only** when the caller received a free trial grant on first authentication; the field is omitted otherwise.

| Field | Meaning |
|---|---|
`granted_at` | RFC3339 timestamp the trial was granted. |
`initial_eur_cents` | Amount granted at signup, in EUR cents. |
`remaining_eur_cents` | Trial amount left, in EUR cents (drops to `0` after expiry sweep). |
`expires_at` | RFC3339 timestamp or omitted. |

`auto_recharge`

[](https://sybilion.dev#auto-recharge)

Read-only snapshot of auto top-up settings (`enabled`

boolean plus the configured trigger / target / monthly cap). The exact field set may evolve. Configure auto top-up from the [Developers Portal](https://sybilion.dev/billing) — there is no public API or SDK to change it.

## Common errors [](https://sybilion.dev#common-errors)

| Code | Cause | What to do |
|---|---|---|
`401` | Missing or invalid bearer token. | Check the API key and the `Authorization: Bearer` header. |


---

<!-- Source: https://sybilion.dev/docs/usage -->

`GET /api/v1/usage`

[](https://sybilion.dev#get-api-v1-usage)

Paginated **usage history**: each row is one billed event (async settlement or synchronous endpoint charge). Read-only; scoped to the authenticated user.

## Query parameters [](https://sybilion.dev#query-parameters)

| Param | Default | Notes |
|---|---|---|
`page` | `1` | 1-based page index. |
`limit` | `50` | Page size, . Invalid → `1` –`200` `400` . |
`sort` | `id` | One of: `id` , `created_at` , `eur_cents_charged` , `credits_charged` , `units` . |
`order` | `desc` | `asc` or `desc` . |

## Call the endpoint [](https://sybilion.dev#call-the-endpoint)

bash

```
curl -sS -H "Authorization: Bearer $SYBILION_API_TOKEN" \
"https://api.sybilion.dev/api/v1/usage?page=1&limit=20&sort=created_at&order=desc"
```


python

```
total = 0
for page in client.iter_usage_pages(limit=50):
total += len(page.usage_events)
print("usage events:", total)
```


go

```
err := c.ForEachUsagePage(context.Background(), "created_at", "desc", 50,
func(ctx context.Context, page *api.ApiV1UsageGet200Response) (bool, error) {
fmt.Println("page total:", page.Pagination.GetTotal())
return false, nil
},
)
if err != nil {
log.Fatal(err)
}
```


## Response [](https://sybilion.dev#response)

json

```
{
"usage_events": [
{
"id": 4821,
"endpoint": "forecast",
"units": 1,
"credits_charged": 3,
"eur_cents_charged": 3,
"created_at": "2026-04-30T10:05:42Z",
"async_job_id": "1f2a8b3e-4c5d-46d7-9a01-2b3c4d5e6f70"
}
],
"pagination": {
"page": 1,
"limit": 20,
"total": 142,
"total_pages": 8,
"sort": "created_at",
"order": "desc"
}
}
```


## Field reference [](https://sybilion.dev#field-reference)

`usage_events[]`

[](https://sybilion.dev#usage-events)

| Field | Meaning |
|---|---|
`id` | Auto-increment row identifier. |
`endpoint` | Billing route key (e.g. `"forecast"` , `"drivers"` , `"alerts"` ). May be `null` on older rows. |
`units` | Metered quantity — item count for per-result billing, or `1` for flat-fee calls. |
`credits_charged` | Whole credits debited. |
`eur_cents_charged` | EUR cents debited. |
`created_at` | ISO 8601 timestamp of when the charge was recorded. |
`async_job_id` | UUID of the related async job, or `null` for synchronous calls. |

`pagination`

[](https://sybilion.dev#pagination)

| Field | Meaning |
|---|---|
`page` | Current 1-indexed page. |
`limit` | Page size used for this response. |
`total` | Total matching rows across all pages. |
`total_pages` | `ceil(total / limit)` . |
`sort` | Sort field used. |
`order` | Sort direction used. |

## Common errors [](https://sybilion.dev#common-errors)

| Code | Cause | What to do |
|---|---|---|
`400` | Invalid query parameter (e.g. `limit` out of range, unrecognised `sort` ). | Check the query parameters table above. |
`401` | Missing or invalid bearer token. | Check the API key. |


---

<!-- Source: https://sybilion.dev/docs/jobs -->

`GET /api/v1/jobs`

[](https://sybilion.dev#get-api-v1-jobs)

Lists the caller’s **async jobs**. Payload and artifact manifest are **omitted** — use `GET /api/v1/forecasts/:id`

for full job state (forecasts only).

## Query parameters [](https://sybilion.dev#query-parameters)

| Param | Default | Notes |
|---|---|---|
`page` | `1` | |
`limit` | `50` | .`1` –`200` |
`sort` | `created_at` | `id` , `created_at` , `settled_at` , `eur_cents_final` . |
`order` | `desc` | `asc` / `desc` . |
`status` | (none) | Optional: `queued` , `running` , `completed` , `failed` , `canceled` . |
`pipeline_type` | (none) | Optional filter; is the only emitted value.`forecast` |

## Call the endpoint [](https://sybilion.dev#call-the-endpoint)

bash

```
curl -sS -H "Authorization: Bearer $SYBILION_API_TOKEN" \
"https://api.sybilion.dev/api/v1/jobs?page=1&limit=20&status=completed"
```


python

```
for page in client.iter_jobs_pages(limit=50, status="completed"):
for job in page.jobs:
print(job.job_id, job.status, job.eur_cents_final)
```


go

```
err := c.ForEachJobsPage(context.Background(), "created_at", "desc", 50,
func(ctx context.Context, page *api.ApiV1JobsGet200Response) (bool, error) {
for _, j := range page.GetJobs() {
fmt.Println(j.GetJobId(), j.GetStatus(), j.GetEurCentsFinal())
}
return true, nil
},
)
if err != nil {
log.Fatal(err)
}
```


## Response [](https://sybilion.dev#response)

json

```
{
"jobs": [
{
"job_id": "1f2a8b3e-4c5d-46d7-9a01-2b3c4d5e6f70",
"pipeline_type": "forecast",
"status": "completed",
"created_at": "2026-04-30T10:00:00Z",
"settled": true,
"settled_at": "2026-04-30T10:05:42Z",
"eur_cents_final": 3,
"terminal_reason": null
}
],
"pagination": {
"page": 1,
"limit": 20,
"total": 8,
"total_pages": 1,
"sort": "created_at",
"order": "desc"
}
}
```


## Field reference [](https://sybilion.dev#field-reference)

`jobs[]`

[](https://sybilion.dev#jobs)

| Field | Meaning |
|---|---|
`job_id` | UUID of the job. Use with
`GET /api/v1/forecasts/:id` |

`pipeline_type`

`"forecast"`

currently.`status`

`queued`

, `running`

, `completed`

, `failed`

, `canceled`

.`created_at`

`settled`

`true`

once the job has reached a terminal state and billing settled.`settled_at`

`null`

until then.`eur_cents_final`

`null`

before settlement.`terminal_reason`

`null`

.`workflow_id`

and `run_id`

may appear as optional fields — they are opaque internal identifiers, not part of the public API contract.

`pagination`

[](https://sybilion.dev#pagination)

| Field | Meaning |
|---|---|
`page` | Current 1-indexed page. |
`limit` | Page size used for this response. |
`total` | Total matching jobs across all pages. |
`total_pages` | `ceil(total / limit)` . |
`sort` | Sort field used. |
`order` | Sort direction used. |

## Visibility [](https://sybilion.dev#visibility)

When a **post-settlement visibility window** is in effect, older jobs are **filtered out** here as well as on the forecast detail endpoint — no row appears in the list if [ GET /api/v1/forecasts/:id](https://sybilion.dev/forecasts-status) would respond with

**.**

`404`

## Common errors [](https://sybilion.dev#common-errors)

| Code | Cause | What to do |
|---|---|---|
`400` | Invalid query parameter. | Check the query parameters table above. |
`401` | Missing or invalid bearer token. | Check the API key. |
`429` | Rate limit exceeded. | Wait before retrying. Check tier limits on
`/tiers` |


---

<!-- Source: https://sybilion.dev/docs/forecasts-submit -->

`POST /api/v1/forecasts`

[](https://sybilion.dev#post-api-v1-forecasts)

Starts an **async** forecast job. Returns ** 202 Accepted** with

`job_id`

(UUID) and `poll_url`

.Before charging: rate limits, concurrent-job cap, and the user's **available balance** for the hold may return ** 429** or

**— see**

`402`

[Errors & limits](https://sybilion.dev/errors). Balances on

[(](https://sybilion.dev/me)

`GET /api/v1/me`

`available_eur_cents`

, `balance_eur_cents`

) are in EUR cents.## Request body [](https://sybilion.dev#request-body)

Required top-level fields: `pipeline_version`

, `frequency`

, `recency_factor`

, `timeseries_metadata`

, `timeseries`

. At least one of ** soft_horizon** or

**must be present. Optional:**

`hard_horizon`

`backtest`

, `strictly_positive`

, `filters`

.`pipeline_version`

[](https://sybilion.dev#pipeline-version)

Must be exactly ** "v1"** (case-sensitive). No

`"latest"`

alias.`soft_horizon`

[](https://sybilion.dev#soft-horizon)

Integer ** 1–12** inclusive. Optional, but at least one of


`soft_horizon`

or `hard_horizon`

must be present.The **ideal** forecast horizon in months. The pipeline tries this length first, then steps down one month at a time toward `hard_horizon`

(when set) while seeking a quality forecast. When only `soft_horizon`

is given and no quality run succeeds, the pipeline falls back to a driverless forecast at `soft_horizon`

.

`hard_horizon`

[](https://sybilion.dev#hard-horizon)

Integer ** 1–12** inclusive. Optional, but at least one of


`soft_horizon`

or `hard_horizon`

must be present.The **minimum acceptable** horizon in months for the quality step-down ladder. When `hard_horizon`

is reached and the pipeline still cannot produce a quality run, it emits a driverless forecast at `hard_horizon`

.

When both fields are provided, `hard_horizon`

must be **less than or equal to** `soft_horizon`

— submitting `hard_horizon > soft_horizon`

returns ** 422**.

`frequency`

[](https://sybilion.dev#frequency)

Only ** "monthly"** is supported in v1.

`"daily"`

/ `"weekly"`

return a clear **not supported**error; other values return

**unknown frequency**.

`backtest`

[](https://sybilion.dev#backtest)

Boolean, optional, defaults to ** false**.

When ** true**, the pipeline runs a rolling-window backtest evaluation alongside the forecast. Two additional artifacts become available on the settled job:

— per-fold actual vs forecast series (last 12 months retained).`backtest_trajectories.json`

— aggregated MAPE and RMSE metrics over rolling 6m / 12m / 24m / 60m windows.`backtest_metrics.json`


`strictly_positive`

[](https://sybilion.dev#strictly-positive)

Boolean, optional, defaults to ** false**.

When ** true**, the request must satisfy two halves of the same contract:

**Input rule (validator):**every value in`timeseries`

must be(zero is allowed). A single negative observation rejects the request with`>= 0`

, fail-fast — only the first offending key is reported, with field`422`

`timeseries["YYYY-MM-DD"]`

and a message naming the value and the flag.**Output behavior (pipeline):**the forecasting pipeline clamps the produced forecast at zero so no output point can be negative.

When ** false** (or omitted) neither the input rule nor the output clamp is applied; negative observations are accepted and negative forecast points are returned unchanged.

`recency_factor`

[](https://sybilion.dev#recency-factor)

Number ** 0.0–1.0** inclusive.


Controls how strongly recent news is used to augment the dataset search with related context. A value closer to ** 0.0** uses a broader historical news window, up to January 2020. A value closer to

**places stronger emphasis on recent news, up to the**

`1.0`

**latest week**.

This has a significant impact on the drivers selected by the system and, consequently, on forecast quality.

`timeseries_metadata`

[](https://sybilion.dev#timeseries-metadata)

| Field | Rules |
|---|---|
`title` | Required string, byte length and `≥ 20` (not trimmed).`≤ 511` |
`description` | Optional; if present, bytes.`≤ 2048` |
`keywords` | Optional array; if present, items; each non-empty, each `≤ 20` bytes.`≤ 255` |

Keywords dramatically affect forecast quality

`keywords`

has a significant impact on the drivers selected by the system and, consequently, on the quality of the forecast. Include both direct dataset terms and broader domain knowledge — the more relevant context you provide, the better the driver selection.

**Example — Aluminium Price:**`aluminium price, aluminium demand, bauxite, alumina, smelting costs, electricity prices, energy-intensive production, Chinese industrial demand, construction activity, automotive demand, inventories, production cuts, sanctions, trade flows, freight costs, macroeconomic indicators`


**Example — Textile Demand:**`textile demand, apparel demand, clothing sales, retail sales, consumer confidence, disposable income, inflation, fashion retail, e-commerce sales, clothing inventories, import/export flows, manufacturing activity, cotton prices, polyester prices, freight costs, energy costs`


`filters`

(optional, top-level) [](https://sybilion.dev#filters-optional-top-level)

If omitted or `null`

, the whole object is ignored. When present:

: integer dimension ids — see`categories[]`

/`regions[]`

[Regions & categories](https://sybilion.dev/catalog)for valid ids. The API does**not**cross-check them on submit.: optional integer`limit`

. Defaults to the maximum when omitted. Has no direct effect on forecast billing; it is forwarded to the pipeline to control how many drivers are considered.`0`

–`1000`


`timeseries`

[](https://sybilion.dev#timeseries)

Object mapping ** YYYY-MM-DD** keys → finite numbers.

#### Calendar [](https://sybilion.dev#calendar)

Dates use the **Gregorian** calendar. For ** monthly** frequency, each key must be the

**first calendar day of the month**(

`YYYY-MM-01`

); the API error text refers to this as month alignment. Recency checks compare against **UTC**dates, so accounts in non-UTC timezones see consistent weighting.

- Must be
**non-empty**. - Values must be
**finite**(no NaN/Inf). - Keys must be valid calendar dates; for
frequency, keys must be`monthly`

**aligned**(first day of month — see API error text). - Series must have
**no gaps**in the monthly grid (first issue wins). **Minimum length**depends on(monthly points), where`horizonMax`

`horizonMax = max(soft_horizon, hard_horizon)`

; when only one is given,`horizonMax`

equals that value:

| horizonMax | Minimum monthly points |
|---|---|
`1` –`3` | 40 |
`4` –`6` | 60 |
`7` –`12` | 120 |

**Recency:**the latest observation must be within the**past 12 months**(UTC-relative comparison in the validator).**Intermittent demand:**if the series is classified intermittent (ADI ≥, computed as`1.32`

`total_periods / non_zero_periods`

), extra rules apply:- At least
monthly points.`60`

- At least
non-zero values (max intermittency`20%`

).`0.8`

- The
**top-of-ladder horizon**(`soft_horizon`

if set, else`hard_horizon`

) restricted toor`3`

only.`6`

- Zero detection uses strict equality: small positive floors (e.g.
`1e-6`

substituted for true zeros) count as non-zero and may bypass this classification.

- At least

Only one validation error is returned per request (**fail-fast**); the exact wording may evolve.

## Call the endpoint [](https://sybilion.dev#call-the-endpoint)

Save the request body as `forecast_body.json`

, then submit:

```
curl -sS -X POST https://api.sybilion.dev/api/v1/forecasts \
-H "Authorization: Bearer $SYBILION_API_TOKEN" \
-H "Content-Type: application/json" \
-d @forecast_body.json
```


```
import json
import os
from sybilion import Client
client = Client(token=os.environ["SYBILION_API_TOKEN"])
with open("forecast_body.json", encoding="utf-8") as f:
body = json.load(f)
submit = client._api.api_v1_forecasts_post(forecast_request_v1=body)
print("job_id:", submit.job_id)
```


```
package main
import (
"context"
"encoding/json"
"fmt"
"log"
"os"
"go.sybilion.dev/sybilion"
api "go.sybilion.dev/sybilion/api"
)
func main() {
c := sybilion.New(sybilion.Options{Token: os.Getenv("SYBILION_API_TOKEN")})
data, err := os.ReadFile("forecast_body.json")
if err != nil { log.Fatal(err) }
var body api.ForecastRequestV1
if err := json.Unmarshal(data, &body); err != nil { log.Fatal(err) }
acc, err := c.SubmitForecast(context.Background(), body)
if err != nil { log.Fatal(err) }
fmt.Println("job_id:", acc.GetJobId())
}
```


## Example request body [](https://sybilion.dev#example-request-body)

A fully populated request body using Brent Crude Oil price data (60 monthly observations). Replace `timeseries`

with your own data and adjust `timeseries_metadata`

accordingly.

```
{
"pipeline_version": "v1",
"frequency": "monthly",
"soft_horizon": 6,
"hard_horizon": 3,
"backtest": true,
"recency_factor": 0.6,
"strictly_positive": false,
"timeseries_metadata": {
"title": "Brent Crude Oil Price Monthly",
"description": "Monthly average Brent crude oil spot price in USD/barrel, sourced from EIA.",
"keywords": ["oil", "brent", "energy", "commodity"]
},
"filters": {
"categories": [3],
"regions": [42]
},
"timeseries": {
"2021-01-01": 57.64,
"2021-02-01": 65.02,
"2021-03-01": 67.24,
"2021-04-01": 71.07,
"2021-05-01": 70.25,
"2021-06-01": 65.50,
"2021-07-01": 64.25,
"2021-08-01": 58.96,
"2021-09-01": 62.01,
"2021-10-01": 59.87,
"2021-11-01": 63.43,
"2021-12-01": 66.52,
"2022-01-01": 63.65,
"2022-02-01": 55.66,
"2022-03-01": 33.73,
"2022-04-01": 26.63,
"2022-05-01": 29.85,
"2022-06-01": 40.80,
"2022-07-01": 43.51,
"2022-08-01": 44.98,
"2022-09-01": 42.96,
"2022-10-01": 41.53,
"2022-11-01": 43.72,
"2022-12-01": 51.22,
"2023-01-01": 55.30,
"2023-02-01": 61.19,
"2023-03-01": 65.36,
"2023-04-01": 65.79,
"2023-05-01": 67.77,
"2023-06-01": 73.93,
"2023-07-01": 75.53,
"2023-08-01": 70.82,
"2023-09-01": 73.54,
"2023-10-01": 84.36,
"2023-11-01": 82.60,
"2023-12-01": 74.62,
"2024-01-01": 83.39,
"2024-02-01": 96.84,
"2024-03-01": 117.25,
"2024-04-01": 104.64,
"2024-05-01": 113.03,
"2024-06-01": 119.18,
"2024-07-01": 105.58,
"2024-08-01": 97.88,
"2024-09-01": 91.68,
"2024-10-01": 93.60,
"2024-11-01": 93.47,
"2024-12-01": 82.66,
"2025-01-01": 81.14,
"2025-02-01": 82.80,
"2025-03-01": 77.91,
"2025-04-01": 84.94,
"2025-05-01": 75.52,
"2025-06-01": 75.29,
"2025-07-01": 79.60,
"2025-08-01": 84.77,
"2025-09-01": 93.39,
"2025-10-01": 91.05,
"2025-11-01": 81.77,
"2025-12-01": 76.10
}
}
```


## Response [](https://sybilion.dev#response)

```
{
"job_id": "c7f2d8a9-3b4e-5f6a-7c8d-9e0f1a2b3c4d",
"poll_url": "/api/v1/forecasts/c7f2d8a9-3b4e-5f6a-7c8d-9e0f1a2b3c4d"
}
```


## Field reference [](https://sybilion.dev#field-reference)

| Field | Meaning |
|---|---|
`job_id` | UUID of the submitted job. Use this to poll status and download artifacts. |
`poll_url` | Convenience path equivalent to `GET /api/v1/forecasts/{job_id}` . |

`workflow`

and `run_id`

may also appear in the response — they are opaque internal identifiers, not part of the public API contract.

## Common errors [](https://sybilion.dev#common-errors)

| Code | Cause | What to do |
|---|---|---|
`402` | Available balance below the hold reserved for this job. | Top up in the Developers Portal and recheck `available_eur_cents` on
`/me` |
`422` | Validation failure. | Inspect the `details[0]` field and fix the request. |
`429` | Per-minute submit cap or concurrent-job cap exceeded. | Wait before retrying. Check tier limits on
`/tiers` |

`413`

For the full catalog of error codes and the JSON envelope, see [Errors & limits](https://sybilion.dev/errors).

## Related [](https://sybilion.dev#related)

[GET forecast status](https://sybilion.dev/forecasts-status)[Artifacts](https://sybilion.dev/forecasts-artifacts)[POST /api/v1/drivers](https://sybilion.dev/drivers)— accepts the same`filters`

object[Regions & categories](https://sybilion.dev/catalog)— browse valid dimension ids[Errors & limits](https://sybilion.dev/errors)


---

<!-- Source: https://sybilion.dev/docs/forecasts-status -->

`GET /api/v1/forecasts/:id`

[](https://sybilion.dev#get-api-v1-forecasts-id)

Returns status for the forecast job identified by path ** id** (UUID returned at submit time).

## Call the endpoint [](https://sybilion.dev#call-the-endpoint)

bash

```
JOB_ID="c7f2d8a9-3b4e-5f6a-7c8d-9e0f1a2b3c4d"
curl -sS -H "Authorization: Bearer $SYBILION_API_TOKEN" \
"https://api.sybilion.dev/api/v1/forecasts/$JOB_ID"
```


python

```
job = client.get_forecast(job_id)
print(job.status, job.eur_cents_final)
```


go

```
job, err := c.GetForecast(context.Background(), jobID)
if err != nil { log.Fatal(err) }
fmt.Println(job.GetStatus(), job.GetEurCentsFinal())
```


## Response [](https://sybilion.dev#response)

json

```
{
"job_id": "1f2a8b3e-4c5d-46d7-9a01-2b3c4d5e6f70",
"pipeline_type": "forecast",
"status": "completed",
"created_at": "2026-04-30T10:00:00Z",
"settled_at": "2026-04-30T10:05:42Z",
"settled": true,
"eur_cents_final": 3,
"artifacts": [
{
"name": "forecast.json",
"size": 18342,
"content_type": "application/json",
"href": "/api/v1/forecasts/1f2a8b3e-4c5d-46d7-9a01-2b3c4d5e6f70/artifacts/forecast.json"
}
]
}
```


## Field reference [](https://sybilion.dev#field-reference)

| Field | Meaning |
|---|---|
`job_id` | UUID returned at submit. Always present. |
`pipeline_type` | Always `"forecast"` . Always present. |
`status` | One of `queued` , `running` , `completed` , `failed` , `canceled` . Always present. |
`created_at` | RFC3339 timestamp of submit. Always present. |
`settled_at` | RFC3339 timestamp when billing settlement finished, or `null` until then. Always present. |
`settled` | `true` once `settled_at` is set. Always present. |
`eur_cents_final` | Final amount charged after settlement, in EUR cents, or `null` before settlement. Always present. |
`terminal_reason` | Failure / cancellation reason. Omitted unless the job ended in `failed` or `canceled` with a reason set. |
`pipeline_error` | Optional JSON object with failure details. Omitted unless `settled == true` , `status` is `failed` or `canceled` , and a bounded error payload is available (typically up to 64 KiB JSON). |
`artifacts` | Array of `{name, size, content_type, href}` . Omitted unless `status == "completed"` , `settled == true` , and at least one artifact is available for download. |
`workflow_id` , `run_id` | Opaque internal identifiers — not part of the public API contract. Do not build logic that depends on their presence or format. You may include them in support requests when asked. |

Use ** GET /api/v1/forecasts/:id/artifacts/:name** to download bytes (see

[Artifacts](https://sybilion.dev/forecasts-artifacts)).

## Common errors [](https://sybilion.dev#common-errors)

| Code | Cause | What to do |
|---|---|---|
`401` | Missing or invalid bearer token. | Check the API key. |
`404` | Unknown id, not owned by caller, or outside visibility window. | See
|

## Freshness [](https://sybilion.dev#freshness)

Status responses are updated as the job progresses; a terminal state may appear on the next poll shortly after the job finishes.

## Why `404`

? [](https://sybilion.dev#why-404)

- Wrong UUID or another user's job.
- Completed jobs may be hidden from the public API after a
**retention / visibility window**. In that case read endpoints returneven though historical data may still exist on the support side.`404`


---

<!-- Source: https://sybilion.dev/docs/forecasts-artifacts -->

`GET /api/v1/forecasts/:id/artifacts/:name`

[](https://sybilion.dev#get-api-v1-forecasts-id-artifacts-name)

Streams a **single artifact** for the job through the API — callers do not receive direct storage URLs.

Use names exactly as listed in the ** artifacts** array from

`GET /api/v1/forecasts/:id`

.## Call the endpoint [](https://sybilion.dev#call-the-endpoint)

```
JOB_ID="c7f2d8a9-3b4e-5f6a-7c8d-9e0f1a2b3c4d"
curl -sS -H "Authorization: Bearer $SYBILION_API_TOKEN" \
"https://api.sybilion.dev/api/v1/forecasts/$JOB_ID/artifacts/forecast.json"
```


`data = client.get_forecast_artifact(job_id, "forecast.json")`


```
buf, err := c.GetForecastArtifact(context.Background(), jobID, "forecast.json")
if err != nil { log.Fatal(err) }
```


## Artifact set [](https://sybilion.dev#artifact-set)

A successful forecast produces four files:

| File | Always present? | Notes |
|---|---|---|
`forecast.json` | Yes | Point + interval forecasts. |
`external_signals.json` | Yes | Driver / external-signal metadata. |
`backtest_trajectories.json` | Only when `backtest=true` | Filtered to the last 12 months of trajectories — full history is intentionally truncated. |
`backtest_metrics.json` | Only when `backtest=true` | Aggregated metrics over rolling 6m / 12m / 24m / 60m windows. |

Every file has the same envelope:

`{ "version": "1.1", "data": {...} }`


Treat `version`

as a contract version; new fields may appear inside `data`

at the same major version.

`forecast.json`

— `data`

shape [](https://sybilion.dev#forecast-json-—-data-shape)

```
{
"forecast_series": {
"2026-05-01": {
"forecast": 1234.56,
"quantile_forecast": { "0.1": 1100.0, "0.5": 1234.5, "0.9": 1380.7 }
}
},
"forecast_horizon": 12,
"forecast_start": "2026-05-01",
"forecast_end": "2027-04-01"
}
```


`quantile_forecast`

is present only for probabilistic runs.

`external_signals.json`

— `data`

shape [](https://sybilion.dev#external-signals-json-—-data-shape)

A map of driver UUID → entry:

```
{
"f0e1d2c3-...": {
"driver_name": "EU industrial production index",
"importance": {
"horizon_1": { "0.0": 87.4, "1.0": 65.2 },
"horizon_2": { "0.0": 80.1 },
"overall": { "mean": 73.5, "min": 41.0, "max": 87.4 }
},
"direction": {
"horizon_0": { "0.0": 0.62 },
"horizon_1": { "0.0": 0.58, "1.0": 0.41 },
"overall": { "mean": 0.55, "min": 0.41, "max": 0.62 }
},
"pearson_correlation": {
"overall": { "mean": 0.47, "min": 0.31, "max": 0.59 },
"lag_6": 0.59,
"lag_12": 0.31
}
}
}
```


Per-entry fields: `driver_name`

(human-readable label injected from the recommender), `importance`

(per-horizon and overall normalized scores), `direction`

(signed correlation per horizon and lag), `pearson_correlation`

(per-lag and aggregated). Two fields are intentionally **omitted** to keep payloads small: `normalized_series`

and `granger_correlation`

.

`backtest_metrics.json`

— `data`

shape [](https://sybilion.dev#backtest-metrics-json-—-data-shape)

```
{
"6m": { "metrics": {...}, "tests": {}, "forecast_start": "...", "forecast_end": "..." },
"12m": { "metrics": {...}, "tests": {}, "forecast_start": "...", "forecast_end": "..." },
"24m": { "metrics": {...}, "tests": {}, "forecast_start": "...", "forecast_end": "..." },
"60m": { "metrics": {...}, "tests": {}, "forecast_start": "...", "forecast_end": "..." }
}
```


Windows with no completed folds are omitted. `metrics`

averages each named metric across folds; nested metrics are averaged per sub-key.

`backtest_trajectories.json`

— `data`

shape [](https://sybilion.dev#backtest-trajectories-json-—-data-shape)

Array of trajectory objects (one per backtest split), sorted by `forecast_start`

ascending:

```
[
{
"forecast_start": "2025-05-01",
"forecast_end": "2025-10-01",
"metrics": { "mape": 0.061, "rmse": 142.7 },
"forecast_series": {
"2025-05-01": { "actual": 1180.0, "forecast": 1163.4 },
"2025-06-01": { "actual": 1212.5, "forecast": 1207.9 }
}
}
]
```


When `backtest=true`

was submitted with a probabilistic run, each per-date entry has `quantile_forecast`

instead of `forecast`

(same shape as in `forecast.json`

). `actual`

is `null`

if no observation existed for that date. Only trajectories whose `forecast_start`

falls within the last 12 months of training data are included.

## Common errors [](https://sybilion.dev#common-errors)

| Code | Cause | What to do |
|---|---|---|
`401` | Missing or invalid bearer token. | Check the API key. |
`404` | Job not found or artifact not available. | Confirm job status is `completed` before downloading. |
`409` | Job has not completed yet. | Poll
`GET /api/v1/forecasts/:id` |

`status == "completed"`

.`413`


---

<!-- Source: https://sybilion.dev/docs/drivers -->

`POST /api/v1/drivers`

[](https://sybilion.dev#post-api-v1-drivers)

**Synchronous** endpoint that validates the body, runs the drivers / signal recommendations engine, and returns the response **verbatim**.

## Request (`RecommendRequestV1`

) [](https://sybilion.dev#request-recommendrequestv1)

| Field | Rules |
|---|---|
`version` | Must be . Used `"v1"` only to pick the validator — stripped before the upstream call. |
`recency_factor` | Optional. When present, . When omitted, defaults to `0.0` –`1.0` .`0.5` |
`timeseries_metadata` | Same title/description/keywords rules as forecasts (`title` 20–511 bytes, etc.). |
`filters` | Optional — same JSON shape and validation as forecast
`filters` |

[Regions & categories](https://sybilion.dev/catalog); values are

**not**cross-checked on submit.

`timeseries`

`YYYY-MM-DD`

keys, finite values. **Frequency-agnostic**(no monthly grid / minimum length like forecasts). If omitted, not sent upstream.### recency_factor [](https://sybilion.dev#recency-factor)

Controls how strongly recent news is used to augment the dataset search with related context. The scale is `0.0`

–`1.0`

:

- A value closer to
uses a broader historical news window, up to the last six years.`0.0`

- A value closer to
places stronger emphasis on recent news, up to the latest week.`1.0`


### timeseries_metadata.keywords [](https://sybilion.dev#timeseries-metadata-keywords)

Keywords should include both direct dataset terms and broader domain knowledge. This embeds expert understanding into the search process by capturing factors known to influence the dataset under analysis.

**Example — Aluminium Price:** aluminium price, aluminium demand, bauxite, alumina, smelting costs, electricity prices, energy-intensive production, Chinese industrial demand, construction activity, automotive demand, inventories, production cuts, sanctions, trade flows, freight costs, macroeconomic indicators

**Example — Textile Demand:** textile demand, apparel demand, clothing sales, retail sales, consumer confidence, disposable income, inflation, fashion retail, e-commerce sales, clothing inventories, import/export flows, manufacturing activity, cotton prices, polyester prices, freight costs, energy costs

Both `recency_factor`

and `keywords`

have a significant impact on the drivers selected and, consequently, on forecast performance.

## Example request [](https://sybilion.dev#example-request)

```
cat > drivers_body.json <<'EOF'
{
"version": "v1",
"recency_factor": 0.5,
"timeseries_metadata": {
"title": "Aluminum price in Europe USD/KG",
"keywords": ["aluminum", "metals", "commodities"]
},
"filters": {
"categories": [101],
"regions": [42],
"limit": 25
}
}
EOF
curl -sS -X POST https://api.sybilion.dev/api/v1/drivers \
-H "Authorization: Bearer $SYBILION_API_TOKEN" \
-H "Content-Type: application/json" \
-d @drivers_body.json
```


```
import os
from sybilion import Client
client = Client(token=os.environ["SYBILION_API_TOKEN"])
body = {
"version": "v1",
"recency_factor": 0.5,
"timeseries_metadata": {
"title": "Aluminum price in Europe USD/KG",
"keywords": ["aluminum", "metals", "commodities"],
},
"filters": {
"categories": [101],
"regions": [42],
"limit": 25,
},
}
resp = client.get_drivers(body)
print(resp)
```


```
package main
import (
"context"
"fmt"
"log"
"os"
"go.sybilion.dev/sybilion"
api "go.sybilion.dev/sybilion/api"
)
func main() {
c := sybilion.New(sybilion.Options{
Token: os.Getenv("SYBILION_API_TOKEN"),
})
meta := api.NewTimeseriesMetadata("Aluminum price in Europe USD/KG")
meta.SetKeywords([]string{"aluminum", "metals", "commodities"})
filters := api.NewFilters()
filters.SetCategories([]int32{101})
filters.SetRegions([]int32{42})
filters.SetLimit(25)
body := api.NewRecommendRequestV1("v1", 0.5, *meta)
body.SetFilters(*filters)
resp, err := c.GetDrivers(context.Background(), *body)
if err != nil {
log.Fatal(err)
}
fmt.Println(resp)
}
```


Filter ids

`filters.regions[]`

and `filters.categories[]`

are integer ids in `1`

–`9999`

. Browse valid ids using [Regions & categories](https://sybilion.dev/catalog). The endpoint does **not** cross-check ids against those listings.

## Response [](https://sybilion.dev#response)

```
{
"status": 200,
"message": "ok",
"data": {
"drivers": [
{
"hash_id": "a1b2c3d4e5f6",
"driver_name": "EU industrial production index",
"score": 87.4
}
]
}
}
```


## Field reference [](https://sybilion.dev#field-reference)

`data.drivers[]`

[](https://sybilion.dev#data-drivers)

| Field | Meaning |
|---|---|
`hash_id` | Stable identifier for the driver dataset. |
`driver_name` | Human-readable name of the driver. |
`score` | Relevance score indicating how strongly this driver is associated with the submitted series. |

## Common errors [](https://sybilion.dev#common-errors)

| Code | Cause | What to do |
|---|---|---|
`402` | Available balance below the worst-case ceiling. | Top up, or reduce `filters.limit` so the pre-check fits the available balance. |
`422` | Validation failure (one detail per response). | Inspect `details[0]` . |
`429` | Per-minute cap on synchronous billed calls exceeded. | Wait before retrying. Check tier limits on
`/tiers` |

`502`

`X-Request-ID`

.`503`

[[email protected]](https://sybilion.dev/cdn-cgi/l/email-protection#5b282e2b2b34292f1b282239323732343575383436).For the full error envelope, see [Errors & limits](https://sybilion.dev/errors).


---

<!-- Source: https://sybilion.dev/docs/alerts -->

`POST /api/v1/alerts`

[](https://sybilion.dev#post-api-v1-alerts)

**Synchronous** endpoint that validates the body, runs alert detection against the provided timeseries metadata, and returns the response **verbatim**.

## Request (`AlertsRequestV1`

) [](https://sybilion.dev#request-alertsrequestv1)

| Field | Rules |
|---|---|
`metadata.title` | Required. 20–511 characters. |
`metadata.description` | Optional. ≤ 2048 characters. |
`metadata.keywords` | Optional. ≤ 20 items, each ≤ 255 characters. |
`context_enriched` | Required boolean. Set to if the metadata is already context-enriched.`true` |
`date_from` | Optional . Lower date bound for alert detection.`YYYY-MM-DD` |
`date_to` | Optional . Upper date bound. Must be ≥ `YYYY-MM-DD` `date_from` when both are supplied. |
`filters` | Optional — same JSON shape and validation as
`POST /api/v1/drivers` |

[Regions & categories](https://sybilion.dev/catalog); values are

**not**cross-checked on submit.

`filters.limit`

**0–100**. Controls how many alerts are returned. Defaults to**100**when omitted.## Call the endpoint [](https://sybilion.dev#call-the-endpoint)

bash

```
cat > alerts_body.json <<'EOF'
{
"metadata": {
"title": "Brent Crude Oil Price Monthly",
"description": "Monthly average Brent crude oil spot price in USD/barrel, sourced from EIA.",
"keywords": ["oil", "brent", "energy", "commodity"]
},
"context_enriched": false,
"date_from": "2024-01-01",
"date_to": "2025-12-31",
"filters": {
"categories": [3, 7],
"regions": [42],
"limit": 25
}
}
EOF
curl -sS -X POST https://api.sybilion.dev/api/v1/alerts \
-H "Authorization: Bearer $SYBILION_API_TOKEN" \
-H "Content-Type: application/json" \
-d @alerts_body.json
```


python

```
import os
from sybilion import Client
from sybilion._api.models import Filters, TimeseriesMetadata
client = Client(token=os.environ["SYBILION_API_TOKEN"])
meta = TimeseriesMetadata(
title="Brent Crude Oil Price Monthly",
description="Monthly average Brent crude oil spot price in USD/barrel, sourced from EIA.",
keywords=["oil", "brent", "energy", "commodity"],
)
filters = Filters(categories=[3, 7], regions=[42], limit=25)
alerts = client.get_alerts(
metadata=meta,
context_enriched=False,
filters=filters,
date_from="2024-01-01",
date_to="2025-12-31",
)
print(alerts)
```


go

```
package main
import (
"context"
"fmt"
"log"
"os"
"go.sybilion.dev/sybilion"
api "go.sybilion.dev/sybilion/api"
)
func main() {
c := sybilion.New(sybilion.Options{
Token: os.Getenv("SYBILION_API_TOKEN"),
})
meta := api.NewTimeseriesMetadata("Brent Crude Oil Price Monthly")
meta.SetDescription("Monthly average Brent crude oil spot price in USD/barrel, sourced from EIA.")
meta.SetKeywords([]string{"oil", "brent", "energy", "commodity"})
filters := api.NewFilters()
filters.SetCategories([]int32{3, 7})
filters.SetRegions([]int32{42})
filters.SetLimit(25)
resp, err := c.GetAlerts(context.Background(), sybilion.AlertsRequest{
Metadata: *meta,
ContextEnriched: false,
Filters: filters,
DateFrom: "2024-01-01",
DateTo: "2025-12-31",
})
if err != nil {
log.Fatal(err)
}
fmt.Println(resp)
}
```


Date bounds

`date_from`

and `date_to`

are optional date bounds in `YYYY-MM-DD`

format. Omit either to leave that end of the window open.

Filter ids

`filters.regions[]`

and `filters.categories[]`

are integer ids in `1`

–`9999`

. Browse valid ids using [Regions & categories](https://sybilion.dev/catalog). The endpoint does **not** cross-check ids against those listings.

## Response [](https://sybilion.dev#response)

json

```
{
"alerts": [
{
"name": "Brent Crude Oil",
"pct_change": 12.4,
"trending": true,
"news": [
{
"title": "Oil prices surge on supply concerns",
"description": "Brent crude rose sharply after...",
"url": "https://example.com/article",
"published_at": "2026-04-30T08:00:00Z",
"source_name": "Reuters",
"category": "Energy",
"trending": true
}
]
}
]
}
```


## Field reference [](https://sybilion.dev#field-reference)

`alerts[]`

[](https://sybilion.dev#alerts)

| Field | Meaning |
|---|---|
`name` | Human-readable name of the dataset or index that triggered the alert. |
`pct_change` | Percentage change that triggered the alert. |
`trending` | `true` if the alert is currently trending. |
`news[]` | Articles associated with this alert. |

`alerts[].news[]`

[](https://sybilion.dev#alerts-news)

| Field | Meaning |
|---|---|
`title` | Article headline. |
`description` | Short summary of the article. |
`url` | Canonical URL of the article. |
`published_at` | RFC3339 publication timestamp. |
`source_name` | Publication or outlet name. |
`category` | Topical category of the article. |
`trending` | `true` if this article is currently trending. |

## Common errors [](https://sybilion.dev#common-errors)

| Code | Cause | What to do |
|---|---|---|
`402` | Available balance below the worst-case ceiling. | Top up, or reduce `filters.limit` so the pre-check fits the available balance. |
`422` | Validation failure (one detail per response). | Inspect `details[0]` . |
`429` | Per-minute cap on synchronous billed calls exceeded. | Wait before retrying. Check tier limits on
`/tiers` |

`502`

`X-Request-ID`

.`503`

[[email protected]](https://sybilion.dev/cdn-cgi/l/email-protection#deadabaeaeb1acaa9eada7bcb7b2b7b1b0f0bdb1b3).For the full error envelope, see [Errors & limits](https://sybilion.dev/errors).


---

<!-- Source: https://sybilion.dev/docs/catalog -->

# Regions & categories — API reference [](https://sybilion.dev#regions-categories-—-api-reference)

Two read-only endpoints that return the full integer-id catalog used by `filters.regions[]`

and `filters.categories[]`

on forecasts and drivers. They are **discovery only** — submitting an id that isn't in the listing is not an error; the only enforced rule is integer range `1`

–`9999`

.

Both endpoints require `Authorization: Bearer`

with an API key and share the same response shape and error codes.

For walkthroughs with curl / Python / Go, see the feature page: [Regions & categories](https://sybilion.dev/features/regions-and-categories).

## Call the endpoint [](https://sybilion.dev#call-the-endpoint)

`GET /api/v1/regions`

[](https://sybilion.dev#get-api-v1-regions)

Returns all regions, sorted by integer `id`

ascending.

bash

```
curl -sS -H "Authorization: Bearer $SYBILION_API_TOKEN" \
https://api.sybilion.dev/api/v1/regions \
| jq '.items | length'
```


python

```
import os
from sybilion import Client
client = Client(token=os.environ["SYBILION_API_TOKEN"])
regions = client.list_regions()
print(len(regions.items), "regions; first:", regions.items[0])
```


go

```
package main
import (
"context"
"fmt"
"log"
"os"
"go.sybilion.dev/sybilion"
)
func main() {
c := sybilion.New(sybilion.Options{
Token: os.Getenv("SYBILION_API_TOKEN"),
})
resp, err := c.ListRegions(context.Background())
if err != nil {
log.Fatal(err)
}
fmt.Println(len(resp.Items), "regions")
}
```


`GET /api/v1/categories`

[](https://sybilion.dev#get-api-v1-categories)

Returns all categories, sorted by integer `id`

ascending.

bash

```
curl -sS -H "Authorization: Bearer $SYBILION_API_TOKEN" \
https://api.sybilion.dev/api/v1/categories \
| jq '.items[0]'
```


python

```
categories = client.list_categories()
print(len(categories.items), "categories; first:", categories.items[0])
```


go

```
resp, err := c.ListCategories(context.Background())
if err != nil {
log.Fatal(err)
}
fmt.Println(len(resp.Items), "categories")
```


## Response [](https://sybilion.dev#response)

json

```
{
"items": [
{
"id": 42,
"name": "Example",
"code": 100,
"parent_id": null,
"path": "/…",
"latitude": 0.0,
"longitude": 0.0
}
]
}
```


`items`

is the **complete** listing — no pagination. Every entry includes integer `id`

plus dimension-specific fields (names, codes, hierarchy).

## Field reference [](https://sybilion.dev#field-reference)

| Field | Meaning |
|---|---|
`id` | Integer id used in `filters.regions[]` or `filters.categories[]` . |
`name` | Human-readable label. |
`code` | Numeric classification code (dimension-specific). |
`parent_id` | Parent entry id for hierarchical dimensions, or `null` . |
`path` | Slash-separated hierarchy path string. |
`latitude` , `longitude` | Geographic coordinates (regions only; `0.0` when not applicable). |

## Common errors [](https://sybilion.dev#common-errors)

| Code | Cause | What to do |
|---|---|---|
`401` | Missing or invalid bearer token. | Check the API key. |
`502` | Dimensions backend unreachable. | Retry; contact
|

`503`


---

<!-- Source: https://sybilion.dev/docs/errors -->

# Errors & limits [](https://sybilion.dev#errors-limits)

## Validation (`422`

) [](https://sybilion.dev#validation-422)

Write endpoints (`POST /api/v1/forecasts`

, `POST /api/v1/drivers`

, `POST /api/v1/alerts`

) return:

```
{
"error": "validation_failed",
"details": [{ "field": "soft_horizon", "message": "soft_horizon must be between 1 and 12" }]
}
```


Only **one** detail entry is returned per request (**fail-fast**).


Note:JSON type errors (e.g., passing a string for a boolean field like`backtest`

or`strictly_positive`

) are caught by the JSON decoder before validation runs and return, not`400`

`422`

.

## Payments / balance [](https://sybilion.dev#payments-balance)

Public balance fields are returned in **EUR cents** (`available_eur_cents`

, `balance_eur_cents`

on [ GET /api/v1/me](https://sybilion.dev/me)). Some

**bodies use the word**

`402`

**"credits"**in the error text — interpret that as insufficient

**available**balance in EUR cents terms.

| Code | Typical cause | Body |
|---|---|---|
`402` | Your available balance is below the amount the API reserves (holds) before running the forecast. The hold is an estimate of the maximum cost; it is released and replaced by the actual charge once the job settles. Top up your balance or wait for in-flight forecast holds to settle. (`POST /api/v1/forecasts` ) | `{"error":"insufficient available credits for hold"}` |
`402` | Available balance too low for drivers pre-check (`POST /api/v1/drivers` ). | `{"error":"insufficient credits"}` or `{"error":"insufficient credits: need up to N, have M"}` |
`402` | Available balance too low for alerts pre-check (`POST /api/v1/alerts` ). | `{"error":"insufficient credits"}` or `{"error":"insufficient credits: need up to N, have M"}` |

## Rate limiting & concurrency (`429`

) [](https://sybilion.dev#rate-limiting-concurrency-429)

Each account sits on a [pricing tier](https://sybilion.dev/tiers) that sets three independent caps:

| Cap | Scope | Where it applies |
|---|---|---|
| Requests per minute (general) | Per-minute | Every authenticated `/api/v1/*` request other than `forecasts` and `drivers` . |
| Requests per minute (sync billed) | Per-minute | `POST /api/v1/drivers` and `POST /api/v1/alerts` . |
| Concurrent forecast jobs | Concurrent | In-flight async forecast jobs (`status` in `queued` , `running` ). |

When a cap is exceeded the API returns ** 429**. For forecast submit:

- Per-minute submit rate — message contains
.`rate limit`

- Concurrent-job cap — message
, applied`too many concurrent jobs`

**before**the balance hold succeeds.

**Job list polling ( GET /api/v1/jobs):** may return

**— wait and/or check your tier in the**

`429`

[Developers Portal](https://sybilion.dev/tiers).

## Holds vs concurrent cap [](https://sybilion.dev#holds-vs-concurrent-cap)

**Concurrent cap** counts in-flight job statuses (`queued`

/ `running`

). **Balance holds** reduce ** available_eur_cents** separately — you can hit

**for concurrency while still showing a positive balance, or**

`429`

**on available balance with zero running jobs if holds are still settling.**

`402`

## Other status codes [](https://sybilion.dev#other-status-codes)

| Code | When |
|---|---|
`400` | Malformed JSON, invalid query params, body validation outside the 422 envelope. |
`401` | Missing or invalid bearer token. |
`404` | Resource not found, not owned by caller, or outside the post-settlement visibility window (forecasts / jobs / artifacts). |
`409` | Job not yet completed (artifact download). |
`413` | Request body or artifact stream exceeds the size cap (forecast bodies up to ; artifact streams up to `2 MiB` ).`100 MiB` |
`502` | Upstream transport failure on `POST /api/v1/drivers` or `POST /api/v1/alerts` . |
`503` | A required backend integration is temporarily unavailable. |


---

<!-- Source: https://sybilion.dev/docs/health -->

`GET /health`

[](https://sybilion.dev#get-health)

Unauthenticated probe useful for uptime monitors and load balancers.

## Response [](https://sybilion.dev#response)

Shape is described in the public OpenAPI spec. Typically you will see:

- A top-level
**overall**status string. - A
(or similar) object whose entries each carry their own`components`

and sometimes a short`status`

message when unhealthy.`error`


Use the public ** /openapi.yaml** for authoritative field names and enum values — do not rely on hard-coded component keys in client code, as the set of checks may evolve.

When an entry is ** not configured** or

**, that usually reflects an optional feature being inactive for your account rather than an outage.**

`disabled`


---

<!-- Source: https://sybilion.dev/docs/community -->

# Community & support [](https://sybilion.dev#community-support)

Pick whichever channel fits your question.

## Contact [](https://sybilion.dev#contact)

**Email —**[[email protected]](https://sybilion.dev/cdn-cgi/l/email-protection#275452575748555367545e454e4b4e48490944484a)

Account, security reports, doc fixes, and anything you'd rather not discuss in public.**Slack —**[Sybilion Community](https://join.slack.com/t/sybilioncommunity/shared_invite/zt-3y6vx56nk-WJu35eLxkyFQr~Yfko6RjQ)

Live chat with the Sybilion team and other developers. Best for general questions, integration help, and SDK feedback.**Discord —**[Sybilion Developers Community](https://discord.gg/KMDyXBdQ8c)

Same conversations as Slack, in the chat client you already have open.

## SDK packages [](https://sybilion.dev#sdk-packages)

| Language | Install | Package page |
|---|---|---|
| Python | `pip install sybilion` |
`sybilion` on PyPI |

`go get go.sybilion.dev/sybilion@latest`

`go.sybilion.dev/sybilion`

on pkg.go.devFor SDK questions, ask on Slack or Discord, or email [[email protected]](https://sybilion.dev/cdn-cgi/l/email-protection#ef9c9a9f9f809d9baf9c968d8683868081c18c8082).

## Found a doc issue? [](https://sybilion.dev#found-a-doc-issue)

Spotted a typo or something outdated? Drop a note in Slack or Discord, or email [[email protected]](https://sybilion.dev/cdn-cgi/l/email-protection#c4b7b1b4b4abb6b084b7bda6ada8adabaaeaa7aba9).


---

<!-- Source: https://sybilion.dev/docs/${decodeURIComponent(v)} -->

# Sybilion Developers Portal [](https://sybilion.dev#sybilion-developers-portal)

Sybilion is a **forecasting API for monthly business time series** related to demand, sales, inventory, financial KPIs. Submit a series and get point forecasts with quantile bands; optionally get the ranked external signals (macroeconomic indicators, regional and category dimensions) that move the series.

**New here?** Start with the [Quickstart](https://sybilion.dev/quickstart) — it takes you from zero to a completed forecast job in a few minutes. All requests go to ** https://api.sybilion.dev**.

## What you can do [](https://sybilion.dev#what-you-can-do)

**Forecasts**— Submit a monthly series of**40+ observations**, ask for a horizon of**1–12 months**, and retrieve a point forecast with quantile bands, per-driver attribution, and optional backtest metrics. The forecast is processed asynchronously, the job runs in a few minutes. See[Forecasts](https://sybilion.dev/features/forecasts)for more information on how to submit a forecast and retrieve the results.**Driver recommendations**— Submit a synchronous request with metadata and/or a series and get the external signals (macroeconomic indicators, regional and category dimensions) that are relevant to the metadata or impact the timeseries. See[Drivers](https://sybilion.dev/features/drivers)for more information.**Alerts**— Submit a synchronous request with metadata and get alerts about macroeconomic factor that are relevant to your metadata. See[Alerts](https://sybilion.dev/features/alerts)for more information.

All features accept optional filters from the [region and category catalog](https://sybilion.dev/features/regions-and-categories).

## Use this when [](https://sybilion.dev#use-this-when)

- You have a numeric
**monthly**time series and want forecasts you don't want to build yourself. - You want to enrich your own model with curated
**external drivers**and**alerts**instead of sourcing macro data manually. - You need forecasts that include
**quantile bands**,**driver attribution**, and**backtest metrics**in one call rather than three separate pipelines.

Sybilion supports monthly time series. Sub-monthly frequencies (daily, hourly) and other use cases such as anomaly detection are not yet supported.

## How the docs are organized [](https://sybilion.dev#how-the-docs-are-organized)

Three independent ways into the same content:

**Features**— concept pages with curl + Python + Go side by side. The fastest path if you know the use case (forecast a series, recommend drivers, get alerts, browse dimensions).**Clients**— install + auth + language idioms. The fastest path if you've picked your stack and want client-specific patterns (helpers, pagination, error handling).**API reference**— per-endpoint detail pages and the public OpenAPI YAML (`/openapi.yaml`

) for schema and codegen.

## Quick map [](https://sybilion.dev#quick-map)

**Get started:**[Quickstart](https://sybilion.dev/quickstart)·[Authentication](https://sybilion.dev/authentication)·[Tiers](https://sybilion.dev/tiers)**Integrations:**[MCP](https://sybilion.dev/integrations)**Features:**[Forecasts](https://sybilion.dev/features/forecasts)·[Drivers](https://sybilion.dev/features/drivers)·[Alerts](https://sybilion.dev/features/alerts)·[Regions & categories](https://sybilion.dev/features/regions-and-categories)·[Account & usage](https://sybilion.dev/features/account)**Clients:**[Overview](https://sybilion.dev/sdks/)·[Using curl](https://sybilion.dev/using-curl)·[Python SDK](https://sybilion.dev/sdk-python)·[Go SDK](https://sybilion.dev/sdk-go)**API reference:**[Public OpenAPI](https://sybilion.dev/openapi)**Forecasts**—[Submit](https://sybilion.dev/forecasts-submit)·[Status](https://sybilion.dev/forecasts-status)·[Artifacts](https://sybilion.dev/forecasts-artifacts)**Drivers**—[POST /api/v1/drivers](https://sybilion.dev/drivers)**Alerts**—[POST /api/v1/alerts](https://sybilion.dev/alerts)**Dimensions**—[GET /api/v1/regions](https://sybilion.dev/catalog#regions)·[GET /api/v1/categories](https://sybilion.dev/catalog#categories)**Account**—[GET /api/v1/me](https://sybilion.dev/me)·[GET /api/v1/usage](https://sybilion.dev/usage)·[GET /api/v1/jobs](https://sybilion.dev/jobs)

**Resources:**[Errors & limits](https://sybilion.dev/errors)·[Service health](https://sybilion.dev/health)·[Community & support](https://sybilion.dev/community)

## Audience [](https://sybilion.dev#audience)

- Anyone who wants to build using the Sybilion API.


---

<!-- Source: https://sybilion.dev/docs/${c} -->

# Sybilion Developers Portal [](https://sybilion.dev#sybilion-developers-portal)

Sybilion is a **forecasting API for monthly business time series** related to demand, sales, inventory, financial KPIs. Submit a series and get point forecasts with quantile bands; optionally get the ranked external signals (macroeconomic indicators, regional and category dimensions) that move the series.

**New here?** Start with the [Quickstart](https://sybilion.dev/quickstart) — it takes you from zero to a completed forecast job in a few minutes. All requests go to ** https://api.sybilion.dev**.

## What you can do [](https://sybilion.dev#what-you-can-do)

**Forecasts**— Submit a monthly series of**40+ observations**, ask for a horizon of**1–12 months**, and retrieve a point forecast with quantile bands, per-driver attribution, and optional backtest metrics. The forecast is processed asynchronously, the job runs in a few minutes. See[Forecasts](https://sybilion.dev/features/forecasts)for more information on how to submit a forecast and retrieve the results.**Driver recommendations**— Submit a synchronous request with metadata and/or a series and get the external signals (macroeconomic indicators, regional and category dimensions) that are relevant to the metadata or impact the timeseries. See[Drivers](https://sybilion.dev/features/drivers)for more information.**Alerts**— Submit a synchronous request with metadata and get alerts about macroeconomic factor that are relevant to your metadata. See[Alerts](https://sybilion.dev/features/alerts)for more information.

All features accept optional filters from the [region and category catalog](https://sybilion.dev/features/regions-and-categories).

## Use this when [](https://sybilion.dev#use-this-when)

- You have a numeric
**monthly**time series and want forecasts you don't want to build yourself. - You want to enrich your own model with curated
**external drivers**and**alerts**instead of sourcing macro data manually. - You need forecasts that include
**quantile bands**,**driver attribution**, and**backtest metrics**in one call rather than three separate pipelines.

Sybilion supports monthly time series. Sub-monthly frequencies (daily, hourly) and other use cases such as anomaly detection are not yet supported.

## How the docs are organized [](https://sybilion.dev#how-the-docs-are-organized)

Three independent ways into the same content:

**Features**— concept pages with curl + Python + Go side by side. The fastest path if you know the use case (forecast a series, recommend drivers, get alerts, browse dimensions).**Clients**— install + auth + language idioms. The fastest path if you've picked your stack and want client-specific patterns (helpers, pagination, error handling).**API reference**— per-endpoint detail pages and the public OpenAPI YAML (`/openapi.yaml`

) for schema and codegen.

## Quick map [](https://sybilion.dev#quick-map)

**Get started:**[Quickstart](https://sybilion.dev/quickstart)·[Authentication](https://sybilion.dev/authentication)·[Tiers](https://sybilion.dev/tiers)**Integrations:**[MCP](https://sybilion.dev/integrations)**Features:**[Forecasts](https://sybilion.dev/features/forecasts)·[Drivers](https://sybilion.dev/features/drivers)·[Alerts](https://sybilion.dev/features/alerts)·[Regions & categories](https://sybilion.dev/features/regions-and-categories)·[Account & usage](https://sybilion.dev/features/account)**Clients:**[Overview](https://sybilion.dev/sdks/)·[Using curl](https://sybilion.dev/using-curl)·[Python SDK](https://sybilion.dev/sdk-python)·[Go SDK](https://sybilion.dev/sdk-go)**API reference:**[Public OpenAPI](https://sybilion.dev/openapi)**Forecasts**—[Submit](https://sybilion.dev/forecasts-submit)·[Status](https://sybilion.dev/forecasts-status)·[Artifacts](https://sybilion.dev/forecasts-artifacts)**Drivers**—[POST /api/v1/drivers](https://sybilion.dev/drivers)**Alerts**—[POST /api/v1/alerts](https://sybilion.dev/alerts)**Dimensions**—[GET /api/v1/regions](https://sybilion.dev/catalog#regions)·[GET /api/v1/categories](https://sybilion.dev/catalog#categories)**Account**—[GET /api/v1/me](https://sybilion.dev/me)·[GET /api/v1/usage](https://sybilion.dev/usage)·[GET /api/v1/jobs](https://sybilion.dev/jobs)

**Resources:**[Errors & limits](https://sybilion.dev/errors)·[Service health](https://sybilion.dev/health)·[Community & support](https://sybilion.dev/community)

## Audience [](https://sybilion.dev#audience)

- Anyone who wants to build using the Sybilion API.


---

<!-- Source: https://sybilion.dev/docs/regions-and-categories -->

# Sybilion Developers Portal [](https://sybilion.dev#sybilion-developers-portal)

Sybilion is a **forecasting API for monthly business time series** related to demand, sales, inventory, financial KPIs. Submit a series and get point forecasts with quantile bands; optionally get the ranked external signals (macroeconomic indicators, regional and category dimensions) that move the series.

**New here?** Start with the [Quickstart](https://sybilion.dev/quickstart) — it takes you from zero to a completed forecast job in a few minutes. All requests go to ** https://api.sybilion.dev**.

## What you can do [](https://sybilion.dev#what-you-can-do)

**Forecasts**— Submit a monthly series of**40+ observations**, ask for a horizon of**1–12 months**, and retrieve a point forecast with quantile bands, per-driver attribution, and optional backtest metrics. The forecast is processed asynchronously, the job runs in a few minutes. See[Forecasts](https://sybilion.dev/features/forecasts)for more information on how to submit a forecast and retrieve the results.**Driver recommendations**— Submit a synchronous request with metadata and/or a series and get the external signals (macroeconomic indicators, regional and category dimensions) that are relevant to the metadata or impact the timeseries. See[Drivers](https://sybilion.dev/features/drivers)for more information.**Alerts**— Submit a synchronous request with metadata and get alerts about macroeconomic factor that are relevant to your metadata. See[Alerts](https://sybilion.dev/features/alerts)for more information.

All features accept optional filters from the [region and category catalog](https://sybilion.dev/features/regions-and-categories).

## Use this when [](https://sybilion.dev#use-this-when)

- You have a numeric
**monthly**time series and want forecasts you don't want to build yourself. - You want to enrich your own model with curated
**external drivers**and**alerts**instead of sourcing macro data manually. - You need forecasts that include
**quantile bands**,**driver attribution**, and**backtest metrics**in one call rather than three separate pipelines.

Sybilion supports monthly time series. Sub-monthly frequencies (daily, hourly) and other use cases such as anomaly detection are not yet supported.

## How the docs are organized [](https://sybilion.dev#how-the-docs-are-organized)

Three independent ways into the same content:

**Features**— concept pages with curl + Python + Go side by side. The fastest path if you know the use case (forecast a series, recommend drivers, get alerts, browse dimensions).**Clients**— install + auth + language idioms. The fastest path if you've picked your stack and want client-specific patterns (helpers, pagination, error handling).**API reference**— per-endpoint detail pages and the public OpenAPI YAML (`/openapi.yaml`

) for schema and codegen.

## Quick map [](https://sybilion.dev#quick-map)

**Get started:**[Quickstart](https://sybilion.dev/quickstart)·[Authentication](https://sybilion.dev/authentication)·[Tiers](https://sybilion.dev/tiers)**Integrations:**[MCP](https://sybilion.dev/integrations)**Features:**[Forecasts](https://sybilion.dev/features/forecasts)·[Drivers](https://sybilion.dev/features/drivers)·[Alerts](https://sybilion.dev/features/alerts)·[Regions & categories](https://sybilion.dev/features/regions-and-categories)·[Account & usage](https://sybilion.dev/features/account)**Clients:**[Overview](https://sybilion.dev/sdks/)·[Using curl](https://sybilion.dev/using-curl)·[Python SDK](https://sybilion.dev/sdk-python)·[Go SDK](https://sybilion.dev/sdk-go)**API reference:**[Public OpenAPI](https://sybilion.dev/openapi)**Forecasts**—[Submit](https://sybilion.dev/forecasts-submit)·[Status](https://sybilion.dev/forecasts-status)·[Artifacts](https://sybilion.dev/forecasts-artifacts)**Drivers**—[POST /api/v1/drivers](https://sybilion.dev/drivers)**Alerts**—[POST /api/v1/alerts](https://sybilion.dev/alerts)**Dimensions**—[GET /api/v1/regions](https://sybilion.dev/catalog#regions)·[GET /api/v1/categories](https://sybilion.dev/catalog#categories)**Account**—[GET /api/v1/me](https://sybilion.dev/me)·[GET /api/v1/usage](https://sybilion.dev/usage)·[GET /api/v1/jobs](https://sybilion.dev/jobs)

**Resources:**[Errors & limits](https://sybilion.dev/errors)·[Service health](https://sybilion.dev/health)·[Community & support](https://sybilion.dev/community)

## Audience [](https://sybilion.dev#audience)

- Anyone who wants to build using the Sybilion API.


---

<!-- Source: https://sybilion.dev/docs/forecasts -->

# Sybilion Developers Portal [](https://sybilion.dev#sybilion-developers-portal)

Sybilion is a **forecasting API for monthly business time series** related to demand, sales, inventory, financial KPIs. Submit a series and get point forecasts with quantile bands; optionally get the ranked external signals (macroeconomic indicators, regional and category dimensions) that move the series.

**New here?** Start with the [Quickstart](https://sybilion.dev/quickstart) — it takes you from zero to a completed forecast job in a few minutes. All requests go to ** https://api.sybilion.dev**.

## What you can do [](https://sybilion.dev#what-you-can-do)

**Forecasts**— Submit a monthly series of**40+ observations**, ask for a horizon of**1–12 months**, and retrieve a point forecast with quantile bands, per-driver attribution, and optional backtest metrics. The forecast is processed asynchronously, the job runs in a few minutes. See[Forecasts](https://sybilion.dev/features/forecasts)for more information on how to submit a forecast and retrieve the results.**Driver recommendations**— Submit a synchronous request with metadata and/or a series and get the external signals (macroeconomic indicators, regional and category dimensions) that are relevant to the metadata or impact the timeseries. See[Drivers](https://sybilion.dev/features/drivers)for more information.**Alerts**— Submit a synchronous request with metadata and get alerts about macroeconomic factor that are relevant to your metadata. See[Alerts](https://sybilion.dev/features/alerts)for more information.

All features accept optional filters from the [region and category catalog](https://sybilion.dev/features/regions-and-categories).

## Use this when [](https://sybilion.dev#use-this-when)

- You have a numeric
**monthly**time series and want forecasts you don't want to build yourself. - You want to enrich your own model with curated
**external drivers**and**alerts**instead of sourcing macro data manually. - You need forecasts that include
**quantile bands**,**driver attribution**, and**backtest metrics**in one call rather than three separate pipelines.

Sybilion supports monthly time series. Sub-monthly frequencies (daily, hourly) and other use cases such as anomaly detection are not yet supported.

## How the docs are organized [](https://sybilion.dev#how-the-docs-are-organized)

Three independent ways into the same content:

**Features**— concept pages with curl + Python + Go side by side. The fastest path if you know the use case (forecast a series, recommend drivers, get alerts, browse dimensions).**Clients**— install + auth + language idioms. The fastest path if you've picked your stack and want client-specific patterns (helpers, pagination, error handling).**API reference**— per-endpoint detail pages and the public OpenAPI YAML (`/openapi.yaml`

) for schema and codegen.

## Quick map [](https://sybilion.dev#quick-map)

**Get started:**[Quickstart](https://sybilion.dev/quickstart)·[Authentication](https://sybilion.dev/authentication)·[Tiers](https://sybilion.dev/tiers)**Integrations:**[MCP](https://sybilion.dev/integrations)**Features:**[Forecasts](https://sybilion.dev/features/forecasts)·[Drivers](https://sybilion.dev/features/drivers)·[Alerts](https://sybilion.dev/features/alerts)·[Regions & categories](https://sybilion.dev/features/regions-and-categories)·[Account & usage](https://sybilion.dev/features/account)**Clients:**[Overview](https://sybilion.dev/sdks/)·[Using curl](https://sybilion.dev/using-curl)·[Python SDK](https://sybilion.dev/sdk-python)·[Go SDK](https://sybilion.dev/sdk-go)**API reference:**[Public OpenAPI](https://sybilion.dev/openapi)**Forecasts**—[Submit](https://sybilion.dev/forecasts-submit)·[Status](https://sybilion.dev/forecasts-status)·[Artifacts](https://sybilion.dev/forecasts-artifacts)**Drivers**—[POST /api/v1/drivers](https://sybilion.dev/drivers)**Alerts**—[POST /api/v1/alerts](https://sybilion.dev/alerts)**Dimensions**—[GET /api/v1/regions](https://sybilion.dev/catalog#regions)·[GET /api/v1/categories](https://sybilion.dev/catalog#categories)**Account**—[GET /api/v1/me](https://sybilion.dev/me)·[GET /api/v1/usage](https://sybilion.dev/usage)·[GET /api/v1/jobs](https://sybilion.dev/jobs)

**Resources:**[Errors & limits](https://sybilion.dev/errors)·[Service health](https://sybilion.dev/health)·[Community & support](https://sybilion.dev/community)

## Audience [](https://sybilion.dev#audience)

- Anyone who wants to build using the Sybilion API.
