# GOKU Alpha Builder

GOKU Alpha Builder is a focused buildathon workstation for `SoSoValue + SoDEX`.

It is designed for a builder demo, not a passive dashboard. The product turns live market data, research context, peer behavior, and microstructure into staged execution drafts that an operator can actually review and route.

## What The Product Does

GOKU keeps only the modules that have a clear operator job:

- `Launch`
  - live market overview
  - regime verdict
  - research trigger from SoSoValue news
- `Strategy Rack`
  - promotes live symbols into staged drafts
  - supports trend capture, mean reversion, and vol breakout
- `Replay Lab`
  - validates recent tape before promotion
  - shows return, Sharpe, max drawdown, and win rate
- `Smart Money Mirror`
  - reads real SoDEX wallet trade history
  - ranks peer wallets by timing, sizing, and discipline
  - derives consensus symbols and conviction
- `LP Guard`
  - inspects spread, bid depth, ask depth, and imbalance
  - recommends maker-side behavior
- `Execution Copilot`
  - prepares real SoDEX order payloads
  - supports live signing flow when keys are configured
  - enforces a risk gate before submit
- `News Agent`
  - pulls SoSoValue news and macro context
  - uses Groq to generate an execution-oriented draft
- `Operator Queue`
  - central queue of AI drafts and staged execution plans
- `Portfolio Live`
  - reads SoDEX balances, state, and orders for the configured wallet
- `Audit Trail`
  - stores decisions and staged drafts in SQLite
- `Diagnostics`
  - verifies API readiness and configuration health

## Why This Build Is Useful

Most hackathon trading tools stop at one of these layers:

- pretty charts
- static signals
- isolated AI summaries
- isolated order form demos

GOKU connects the full loop:

1. read live SoDEX market structure
2. add SoSoValue news and macro context
3. validate candidates through replay logic
4. learn from peer wallet behavior
5. enforce spread, size, and account checks
6. produce an operator-ready execution draft

That makes the demo much more credible in front of judges.

## External Inspiration Distilled Into The Product

The product direction was intentionally shaped by public trading and prediction-market repos:

- [`SII-WANGZJ/Polymarket_data`](https://github.com/SII-WANGZJ/Polymarket_data)
  - dataset-first thinking and replay discipline
- [`evan-kolberg/prediction-market-backtesting`](https://github.com/evan-kolberg/prediction-market-backtesting)
  - validate before deploy
- [`ent0n29/polybot`](https://github.com/ent0n29/polybot)
  - peer behavior analysis and wallet mirroring
- [`lihanyu81/polymarket_lp_tool`](https://github.com/lihanyu81/polymarket_lp_tool)
  - maker protection and repricing awareness
- [`alsk1992/CloddsBot`](https://github.com/alsk1992/CloddsBot)
  - multi-strategy rack structure
- [`HarrierOnChain/Prediction-Markets-Trading-Bot-Toolkits`](https://github.com/HarrierOnChain/Prediction-Markets-Trading-Bot-Toolkits)
  - execution-first product mindset
- [`TauricResearch/TradingAgents`](https://github.com/TauricResearch/TradingAgents)
  - research-to-action workflow design
- [`pydantic/pydantic-ai`](https://github.com/pydantic/pydantic-ai)
  - typed AI output thinking
- [`pmxt-dev/pmxt`](https://github.com/pmxt-dev/pmxt)
  - unified market-tool ergonomics
- [`aarora4/Awesome-Prediction-Market-Tools`](https://github.com/aarora4/Awesome-Prediction-Market-Tools)
  - breadth benchmark for judging what is actually worth including

## Data Providers

Primary:

- `SoDEX`
  - tickers
  - book tickers
  - orderbook
  - klines
  - balances
  - orders
  - trades
  - fee rate
  - signed order submission flow
- `SoSoValue`
  - hot news
  - featured news
  - macro events
- `Groq`
  - execution draft generation
  - research-to-action summarization

Fallback:

- `Binance`
  - market tickers
  - klines
- `CoinGecko`
  - market snapshot fallback when research feed is unavailable

## Operator Features That Matter In Demo

### API Visibility Tray

Every session now records the most recent API calls with:

- provider
- endpoint
- status
- latency
- short payload/error preview

This helps judges see that the product is actually calling live providers instead of hiding everything behind static UI.

### Risk Gate Before Live Submit

Execution Copilot blocks weak order attempts using:

- empty or zero `accountID`
- notional below `50 USDC`
- notional above `5,000 USDC`
- fee-rate awareness status

This is the kind of operator control that makes a builder tool feel serious.

### Operator Queue

AI drafts and staged execution plans do not disappear after generation. They are stored and surfaced in a single queue so the operator can review what the system wants to do next.

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

This repo includes deployment files for container-style hosting:

- `Dockerfile`
- `Dockerfile.vercel`
- `Procfile`
- `render.yaml`

Example local container run:

```bash
docker build -t goku-alpha-builder .
docker run -p 8501:8501 --env-file .env goku-alpha-builder
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

## Product Standard For Judges

This repo is intentionally optimized around a buildathon question:

`Can this product help a single operator move from research to execution with real market context and real exchange integration?`

The current answer is yes:

- real SoDEX reads
- real SoSoValue research hooks
- real Groq draft generation
- real signed payload preparation
- real audit memory
- clean module scope without filler pages
