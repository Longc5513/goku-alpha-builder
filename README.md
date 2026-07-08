# GOKU SoDEX Operator

GOKU SoDEX Operator is a live trading workstation built for `SoDEX + SoSoValue`.

This repo is no longer positioned as a demo shell. It is a real operator surface that:

- reads live SoDEX spot markets
- inspects live SoDEX orderbook depth
- builds smart-money context from the SoDEX leaderboard and perps positions
- pulls live SoSoValue research
- prepares signed SoDEX order payloads for execution review

## Live Product Scope

The current app keeps only modules that map to real exchange or research work:

- `Launch`
  - live SoDEX market rows
  - regime verdict from current breadth
  - live research trigger from SoSoValue
- `Strategy Rack`
  - promotes live SoDEX rows into staged operator drafts
- `Replay Lab`
  - replays live SoDEX spot klines only
- `Smart Money Mirror`
  - combines manual peer-wallet tracking with qualified SoDEX leaderboard consensus
- `LP Guard`
  - reads real spread, depth, and imbalance from the SoDEX orderbook
- `Execution Copilot`
  - checks symbol metadata
  - probes fee-rate
  - runs a trade verdict
  - prepares a signed SoDEX payload
- `News Intelligence`
  - reads live SoSoValue hot and featured news
  - reads live currency-filtered SoSoValue research by symbol
- `Portfolio Live`
  - reads SoDEX balances, state, and open orders
- `Operator Queue`
  - stores staged drafts generated during the session
- `Audit Trail`
  - records decisions and payloads in SQLite
- `Diagnostics`
  - verifies live API readiness and configuration health

## What Is Real

### SoDEX

- spot tickers
- spot book tickers
- spot klines
- spot orderbook
- spot symbol metadata
- spot balances
- spot state
- spot open orders
- spot fee-rate
- SoDEX leaderboard
- SoDEX perps open positions for smart-money consensus
- signed spot payload preparation

### SoSoValue

- hot news
- featured news
- featured news by currency
- macro events

### Groq

- execution-draft generation
- research summarization

## What The Tool Actually Helps With

This product is built around one practical workflow:

1. monitor live SoDEX spot structure
2. inspect spread and depth before acting
3. compare the trade to qualified smart-money bias
4. read symbol-specific SoSoValue research
5. run a risk gate
6. prepare the exact SoDEX payload before submit

That is the core operator loop.

## Important Constraint

Live account surfaces depend on the configured SoDEX wallet actually having an active account.

If the wallet returns:

- `aid = 0`
- empty balances
- empty orders

then market, depth, and leaderboard functions still work, but personal portfolio and live execution history will remain sparse until the SoDEX account is active.

## Environment Variables

```env
SOSOVALUE_API_KEY=
SOSOVALUE_BASE_URL=https://openapi.sosovalue.com/openapi/v1

SODEX_API_KEY_NAME=
SODEX_API_PRIVATE_KEY=
SODEX_PUBLIC_KEY=
SODEX_ACCOUNT_ID=
SODEX_WALLET_ADDRESS=
SODEX_SPOT_BASE_URL=https://mainnet-gw.sodex.dev/api/v1/spot
SODEX_PERPS_BASE_URL=https://mainnet-gw.sodex.dev/api/v1/perps

GROQ_API_KEY=
GROQ_MODEL=llama-3.3-70b-versatile

GOKU_DB_PATH=./data/goku_alpha_builder.db
```

## Local Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deployment

This repo is configured for container deployment:

- `Dockerfile`
- `Dockerfile.vercel`
- `Procfile`
- `render.yaml`

Example:

```bash
docker build -t goku-sodex-operator .
docker run -p 8501:8501 --env-file .env goku-sodex-operator
```

## Repo Layout

```text
alpha_builder/
  analytics.py
  clients.py
  config.py
  models.py
  storage.py
app.py
requirements.txt
.env.example
Dockerfile
Dockerfile.vercel
```

## Build Standard

The standard for this repo is simple:

`If a feature is shown in the UI, it should be backed by a real provider call, real exchange logic, or a real operator workflow.`
