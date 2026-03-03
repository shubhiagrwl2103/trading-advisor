# AI Investment Advisor

Event-driven trade suggestions powered by **TradingView + LuxAlgo → Claude claude-opus-4-6 → Telegram**.

Monitors your live portfolio (Kraken crypto + Robinhood stocks), receives real-time technical signals via TradingView webhooks, and uses Claude to generate trade recommendations whenever a meaningful setup occurs.

> **The agent never executes trades.** All suggestions are for manual review only.

---

## How It Works

```
[TradingView fires a LuxAlgo alert — any time, any asset]
        │
        ▼
FastAPI /webhook/signal
  • Validates token
  • Parses signal + all TA values (RSI, MACD, EMA, BBands, LuxAlgo confidence)
  • Returns 200 immediately
        │
        ▼ (background task)
Live portfolio fetch
  • Kraken API → current crypto balances + prices (always live)
  • SQLite → latest Robinhood CSV snapshot
  • Compute total portfolio value dynamically
        │
        ▼
Claude claude-opus-4-6
  • Receives: signal + all indicator values + live portfolio context
  • Produces: JSON recommendation (action, conviction, entry/target/stop, holding period)
        │
        ▼
Telegram push + SQLite storage + Streamlit dashboard
```

TradingView Premium computes all indicators on their servers. No local TA computation — no `yfinance`, no `pandas-ta`, no OHLCV fetching.

---

## Features

- **Event-driven** — analysis fires when TradingView sends a webhook, not on a schedule
- **Live portfolio** — Kraken balance fetched in real-time; Robinhood via CSV upload
- **No timeframe bias** — Claude freely recommends days, weeks, or months based on signal quality
- **Per-ticker cooldown** — avoids re-analyzing the same ticker within 2 hours (configurable); STRONG signals bypass it
- **Streamlit dashboard** — 5 tabs: Portfolio, Live Signals, Recommendations, History, Config
- **Telegram bot** — immediate push on signal + `/analyze`, `/portfolio`, `/signals` commands
- **Daily digest** — 9 AM ET summary of last 24h signals

---

## Stack

| Layer | Technology |
|-------|-----------|
| AI model | `claude-opus-4-6` (Anthropic) |
| Webhook server | FastAPI + uvicorn |
| Portfolio (crypto) | ccxt → Kraken read-only API |
| Portfolio (stocks) | Robinhood CSV export |
| Storage | SQLite + aiosqlite |
| Dashboard | Streamlit + Plotly |
| Notifications | python-telegram-bot |
| Scheduler | APScheduler |

---

## Project Structure

```
ai-advisor/
├── config/
│   ├── settings.py          # Loads .env, typed constants
│   └── assets.py            # Ticker → crypto/stock/etf mapping
├── portfolio/
│   ├── kraken_portfolio.py  # Live Kraken balances (ccxt)
│   ├── robinhood_portfolio.py # CSV parser
│   └── aggregator.py        # get_live_portfolio() → PortfolioSnapshot
├── webhooks/
│   ├── server.py            # FastAPI endpoint
│   ├── models.py            # TradingViewSignal (all TA fields optional)
│   └── signal_store.py      # Persist + trigger analysis
├── ai/
│   ├── claude_client.py     # Full pipeline: portfolio → prompt → Claude → store → notify
│   ├── prompt_builder.py    # System + user prompt
│   └── recommendation_parser.py # Validate JSON output
├── alerts/
│   └── advisor_alerts.py    # Extends AlertSystem with Telegram handler
├── storage/
│   ├── database.py          # SQLite schema init
│   └── queries.py           # Async (FastAPI) + sync (Streamlit) helpers
├── output/
│   ├── streamlit_app.py     # Dashboard
│   └── telegram_bot.py      # Push + command handlers
├── scheduler/
│   └── jobs.py              # Daily Kraken refresh + morning digest
├── scripts/
│   ├── run_analysis.py      # Manual trigger
│   └── start_webhook_server.py
└── docs/
    └── tradingview_setup.md # Step-by-step TradingView + LuxAlgo alert setup
```

---

## Setup

### 1. Clone and install

```bash
git clone https://github.com/shubhiagrwl2103/trading-advisor.git
cd trading-advisor
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```bash
KRAKEN_API_KEY=<read-only key>
KRAKEN_API_SECRET=<read-only secret>

ANTHROPIC_API_KEY=sk-ant-...

TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...

WEBHOOK_SECRET_TOKEN=<any random string>

DATABASE_PATH=./advisor.db
ANALYSIS_TIMEZONE=America/New_York
```

> Use a **read-only** Kraken API key — the agent never trades.

### 3. Configure TradingView alerts

Follow [`docs/tradingview_setup.md`](docs/tradingview_setup.md) for the complete step-by-step guide:
- Adding LuxAlgo indicators to charts
- Creating alerts with JSON webhook payloads
- Setting the secret token header
- Testing with curl before going live

### 4. Start the webhook server

```bash
python -m scripts.start_webhook_server
```

The server starts on `http://0.0.0.0:8000`. For TradingView to reach it you need a public URL — see the setup guide for ngrok and VPS options.

### 5. (Optional) Start the Streamlit dashboard

```bash
streamlit run output/streamlit_app.py
# → http://localhost:8501
```

### 6. (Optional) Start the Telegram bot command listener

```bash
python -m output.telegram_bot
```

---

## Usage

### Webhook test (curl)

```bash
curl -X POST http://localhost:8000/webhook/signal \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Token: your_secret_token" \
  -d '{
    "ticker": "MSTR",
    "timeframe": "1W",
    "close": 241.50,
    "signal_type": "BUY",
    "indicator": "LuxAlgo_AIStrategy",
    "rsi_14": 44.2,
    "ema_50": 238.0,
    "ema_200": 231.5,
    "macd_histogram": 1.7,
    "luxalgo_confidence": 0.91,
    "timestamp": "2026-03-01T20:00:00Z"
  }'
```

Expected: `{"status": "accepted", "ticker": "MSTR"}` — Telegram message within ~10 seconds.

### Manual analysis

```bash
python -m scripts.run_analysis --ticker MSTR
python -m scripts.run_analysis --ticker BTC --timeframe 1W --signal BUY --close 85000 --rsi 44.2
```

### Telegram commands

| Command | Action |
|---------|--------|
| `/analyze MSTR` | Trigger manual analysis for any ticker |
| `/portfolio` | Show live portfolio value and top holdings |
| `/signals` | Show last 10 received signals |

---

## Recommendation Output

Claude returns structured JSON for every signal:

```json
{
  "trigger_signal": { "ticker": "MSTR", "signal_type": "BUY", "timeframe": "1W" },
  "portfolio_at_analysis": { "total_value_usd": 154320.00, "ticker_weight_pct": 4.2 },
  "recommendation": {
    "current_action": "ADD",
    "conviction": "HIGH",
    "risk_rating": "HIGH",
    "suggested_position_size_pct": 7.0,
    "estimated_holding_period": "1-3 weeks",
    "entry_zone": "$235 - $248",
    "target_zone": "$290 - $320",
    "stop_loss_zone": "$200",
    "reasoning": "...",
    "supporting_signals": ["Weekly RSI at 44.2 — room to move higher", "..."],
    "conflicting_signals": ["MACD histogram small — momentum building"]
  },
  "urgency": "standard"
}
```

---

## Robinhood Note

Robinhood has no safe official API. Upload your CSV export weekly via the Portfolio tab in the Streamlit dashboard. The agent notes the snapshot age in every recommendation and flags it explicitly when > 7 days old. Kraken is always live.

---

## Cost

Claude claude-opus-4-6 costs ~$0.15–0.30 per analysis call. At ~100 signals/month that's roughly $20–30/month.
