# GOKU Alpha Builder

GOKU Alpha Builder is a brand-new SoSoValue x SoDEX buildathon tool rebuilt from scratch around the strongest ideas found in public prediction-market repos.

It is not a generic dashboard. It is a one-person trading workstation that combines:

- dataset discipline
- replay validation
- smart-money replication
- LP quote protection
- staged execution planning

## Product Thesis

Strong builders do not stop at a pretty market page.

They build a loop:

1. collect and normalize live market data
2. validate ideas with replay and structure
3. learn from peer behavior
4. protect execution quality
5. turn everything into a concrete order draft

That is the exact loop this tool implements for SoSoValue + SoDEX.

## What Was Taken From The Referenced Repos

These repos were reviewed and distilled into product features:

- [`SII-WANGZJ/Polymarket_data`](https://github.com/SII-WANGZJ/Polymarket_data)
  - inspired the replay-ready, dataset-first mindset
- [`evan-kolberg/prediction-market-backtesting`](https://github.com/evan-kolberg/prediction-market-backtesting)
  - inspired the Replay Lab and validation-before-promotion workflow
- [`ent0n29/polybot`](https://github.com/ent0n29/polybot)
  - inspired Smart Money Mirror, peer consensus, and replication scoring
- [`lihanyu81/polymarket_lp_tool`](https://github.com/lihanyu81/polymarket_lp_tool)
  - inspired LP Guard and maker-discipline tooling
- [`yangyuan-zhen/PolyWeather`](https://github.com/yangyuan-zhen/PolyWeather)
  - inspired event-driven intelligence and specialized signal framing
- [`alsk1992/CloddsBot`](https://github.com/alsk1992/CloddsBot)
  - inspired the multi-strategy rack design
- [`pydantic/pydantic-ai`](https://github.com/pydantic/pydantic-ai)
  - inspired typed draft payloads and agent-ready outputs
- [`TauricResearch/TradingAgents`](https://github.com/TauricResearch/TradingAgents)
  - inspired research-to-action workflow design
- [`pmxt-dev/pmxt`](https://github.com/pmxt-dev/pmxt)
  - inspired unified market-tooling ergonomics
- [`HarrierOnChain/Prediction-Markets-Trading-Bot-Toolkits`](https://github.com/HarrierOnChain/Prediction-Markets-Trading-Bot-Toolkits)
  - inspired the execution-core mentality
- [`aarora4/Awesome-Prediction-Market-Tools`](https://github.com/aarora4/Awesome-Prediction-Market-Tools)
  - used as a breadth benchmark for feature selection

## Product Modules

### Launch

Live SoDEX market tape for the tracked universe, with signal/confidence scoring and a launch-style overview.

### Strategy Rack

Turns live symbols into staged drafts using:

- trend capture
- mean reversion
- vol breakout

### Replay Lab

Replay recent SoDEX klines with:

- trend
- mean reversion
- vol breakout

Outputs:

- return
- Sharpe
- max drawdown
- win rate

### Smart Money Mirror

Read real SoDEX wallet trade history and derive:

- wallet-level peer scores
- symbol consensus
- conviction ranking

### LP Guard

Microstructure-focused tool for:

- spread
- bid/ask depth
- imbalance
- maker-side recommendation

### Execution Copilot

Builds a real SoDEX prepared order payload with:

- account ID
- symbol ID
- limit or market mode
- payload hash
- EIP-712 signature when signing keys are configured

### News Agent

Pulls SoSoValue hot and featured news for research context.

### Portfolio Live

Reads SoDEX account state when wallet/account environment variables are configured.

### Audit Trail

Stores drafts and decisions locally in SQLite so the demo has memory and proof.

### Diagnostics

Checks readiness of:

- SoDEX public API
- SoSoValue API
- signing configuration
- wallet/account settings

## Repo Structure

```text
alpha_builder/
  analytics.py
  clients.py
  config.py
  models.py
  storage.py
app.py
scripts/
  ship.ps1
  ship.py
requirements.txt
.env.example
```

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

## Why This Build Is Better Focused

The old repo mixed many overlapping demo surfaces.

This rebuild keeps only the tools that are most likely to matter in judging:

- is there real market data?
- can it produce a meaningful draft?
- does it validate signals before routing?
- does it learn from peers?
- does it protect execution quality?

That makes the product much cleaner, more useful, and easier to demo.

