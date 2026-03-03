# TradingView + LuxAlgo Alert Setup Guide

> **Phase 0 deliverable** — complete this before starting the server.
> You can configure all TradingView alerts while the code is being built in parallel.

---

## Overview

TradingView Premium computes all indicators on their servers. LuxAlgo adds proprietary AI signals on top.
When a condition is met, TradingView fires an HTTP POST (webhook) to your server with the indicator values baked into the JSON body.

Your server receives live RSI, MACD, EMA, Bollinger Bands, and LuxAlgo confidence — no local computation required.

---

## What You Need

| Item | Status |
|------|--------|
| TradingView Premium subscription | Required for webhook alerts |
| LuxAlgo subscription (AI Signals & Overlays, or Oscillator Matrix) | Required |
| Your server URL (ngrok or VPS) | Needs to be reachable from TradingView |
| Your `WEBHOOK_SECRET_TOKEN` from `.env` | Any random string you chose |

---

## Step 1: Prepare Your Server URL

Before creating alerts, your webhook server must be reachable. TradingView needs a public HTTPS URL.

### Option A: ngrok (development/testing)
```bash
# Install ngrok: https://ngrok.com/download
ngrok http 8000

# You get a URL like: https://abc123.ngrok.io
# Your webhook endpoint: https://abc123.ngrok.io/webhook/signal
```

> ⚠️ ngrok free tier URLs change on restart. Use a paid plan for stable URLs, or use a VPS.

### Option B: VPS (production)
Deploy the server to a VPS (e.g. DigitalOcean $6/mo, Hetzner, Linode).
```bash
# On the VPS:
pip install -r requirements.txt
python -m scripts.start_webhook_server --host 0.0.0.0 --port 8000

# Point a domain or use the raw IP:
# https://your-vps-ip:8000/webhook/signal
```

---

## Step 2: Understand Your LuxAlgo Indicators

You have three LuxAlgo products. Use them as follows:

| Indicator | Best Use | When to Trigger Alert |
|-----------|----------|----------------------|
| **LuxAlgo AI Strategy Alerts** | Full BUY/SELL automation | Alert fires automatically when LuxAlgo's AI gives a signal |
| **LuxAlgo Signals & Overlays** | Visual confirmation | Alert when new label appears on chart |
| **LuxAlgo Oscillator Matrix** | Momentum confirmation | Alert on RSI/momentum crossovers |

**Recommended starting point:** Use **LuxAlgo AI Strategy Alerts** — it generates the cleanest signals and includes a confidence score.

---

## Step 3: Add LuxAlgo to a Chart

1. Open TradingView and navigate to your chart (e.g. **MSTR, Daily**)
2. Click the **Indicators** button (top toolbar)
3. Search for `LuxAlgo AI Strategy Alerts`
4. Click it to add to the chart
5. The indicator will appear as a panel below or overlaid on the chart
6. **Note the plot numbers** — hover over the indicator values in the panel to see which plot index (0, 1, 2...) corresponds to RSI, MACD, EMA, etc. (varies by indicator version)

---

## Step 4: Create an Alert

For each asset + timeframe combination:

1. **Set the correct timeframe** on the chart (e.g. click "D" for Daily, "W" for Weekly)

2. **Click the clock icon** in the top toolbar (Alerts), or press **Alt+A**

3. Click **Create Alert**

4. Set the condition:
   - **Condition**: `LuxAlgo AI Strategy Alerts`
   - **Trigger**: `New Signal` (or equivalent — the exact label depends on indicator version)

5. Set **Alert Name**: e.g. `MSTR_1D_LuxAlgo`

6. **Set expiry**: Choose the longest available (1 year, or "Open-Ended" if available)

7. **Notifications section**: Enable **Webhook URL**
   - Enter your server URL: `https://your-server/webhook/signal`

8. **Add the secret header** (CRITICAL for security):
   - Look for "Additional headers" or similar field
   - Add: `X-Webhook-Token` = `your_secret_token_from_env`

   > ⚠️ If TradingView doesn't support custom headers in the UI, include the token in the URL as a query param instead: `https://your-server/webhook/signal?token=YOUR_SECRET` and update `server.py` to check `request.query_params.get("token")`.

9. **Alert message** — paste the JSON template from Step 5 below

10. Click **Create**

---

## Step 5: JSON Alert Message Templates

Copy and paste the appropriate template into the TradingView alert message field.

### Template A: LuxAlgo AI Strategy Alerts (recommended)

```json
{
  "ticker": "{{ticker}}",
  "exchange": "{{exchange}}",
  "timeframe": "{{interval}}",
  "close": {{close}},
  "signal_type": "{{strategy.order.action}}",
  "indicator": "LuxAlgo_AIStrategy",
  "rsi_14": {{plot_0}},
  "macd_histogram": {{plot_1}},
  "ema_50": {{plot_2}},
  "ema_200": {{plot_3}},
  "luxalgo_confidence": {{plot_4}},
  "volume": {{volume}},
  "timestamp": "{{timenow}}"
}
```

> **Finding the right plot numbers:** Open the LuxAlgo indicator settings and look at the "Style" tab — plots are listed in order. `plot_0` is typically the first output value. Hover over indicator values in the data panel to confirm which is which. Adjust the numbers if needed.

### Template B: LuxAlgo Signals & Overlays

```json
{
  "ticker": "{{ticker}}",
  "exchange": "{{exchange}}",
  "timeframe": "{{interval}}",
  "close": {{close}},
  "signal_type": "BUY",
  "indicator": "LuxAlgo_Signals",
  "rsi_14": {{plot_0}},
  "ema_50": {{plot_2}},
  "ema_200": {{plot_3}},
  "luxalgo_signal": "BUY",
  "luxalgo_confidence": {{plot_1}},
  "volume": {{volume}},
  "timestamp": "{{timenow}}"
}
```

### Template C: EMA Crossover (built-in Pine Script)

Use this to monitor EMA 50 crossing above EMA 200 (golden cross):

```json
{
  "ticker": "{{ticker}}",
  "exchange": "{{exchange}}",
  "timeframe": "{{interval}}",
  "close": {{close}},
  "signal_type": "BUY",
  "indicator": "EMA_Crossover_50_200",
  "ema_50": {{plot_0}},
  "ema_200": {{plot_1}},
  "volume": {{volume}},
  "timestamp": "{{timenow}}"
}
```

### Template D: RSI Alert (oversold/overbought)

```json
{
  "ticker": "{{ticker}}",
  "exchange": "{{exchange}}",
  "timeframe": "{{interval}}",
  "close": {{close}},
  "signal_type": "BUY",
  "indicator": "RSI_Oversold",
  "rsi_14": {{plot_0}},
  "volume": {{volume}},
  "timestamp": "{{timenow}}"
}
```

---

## Step 6: Recommended Alert Setup

Configure these first. You can expand to more assets over time.

| Asset | Exchange | Timeframe | Indicator | Trigger |
|-------|----------|-----------|-----------|---------|
| MSTR | NASDAQ | Daily (1D) | LuxAlgo AI Strategy | New Signal |
| MSTR | NASDAQ | Weekly (1W) | LuxAlgo AI Strategy | New Signal |
| BTC/USD | Kraken/Coinbase | Daily (1D) | LuxAlgo AI Strategy | New Signal |
| BTC/USD | Kraken/Coinbase | Weekly (1W) | LuxAlgo AI Strategy | New Signal |
| ETH/USD | Kraken/Coinbase | Daily (1D) | LuxAlgo AI Strategy | New Signal |
| ETH/USD | Kraken/Coinbase | Weekly (1W) | LuxAlgo AI Strategy | New Signal |
| COIN | NASDAQ | Daily (1D) | LuxAlgo AI Strategy | New Signal |
| HOOD | NASDAQ | Daily (1D) | LuxAlgo AI Strategy | New Signal |
| IBIT | NASDAQ | Weekly (1W) | LuxAlgo AI Strategy | New Signal |
| TSLA | NASDAQ | Weekly (1W) | LuxAlgo AI Strategy | New Signal |

**Total: ~10 alerts.** Each alert = one row above. You can expand to more assets/timeframes anytime.

---

## Step 7: Test Each Alert

### 7a. Simulate with curl (before TradingView is configured)

Start the server first:
```bash
cd ~/ai-advisor
python -m scripts.start_webhook_server
```

Then in another terminal:
```bash
curl -X POST http://localhost:8000/webhook/signal \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Token: YOUR_SECRET_TOKEN" \
  -d '{
    "ticker": "MSTR",
    "exchange": "NASDAQ",
    "timeframe": "1W",
    "close": 241.50,
    "signal_type": "BUY",
    "indicator": "LuxAlgo_AIStrategy",
    "rsi_14": 44.2,
    "macd_histogram": 1.7,
    "ema_50": 238.0,
    "ema_200": 231.5,
    "luxalgo_confidence": 0.91,
    "volume": 4820000,
    "timestamp": "2026-03-01T20:00:00Z"
  }'
```

**Expected response:**
```json
{"status": "accepted", "ticker": "MSTR"}
```

Within ~10 seconds you should receive a Telegram message.

### 7b. TradingView test alert

After creating an alert:
1. Go to the **Alerts** panel (clock icon)
2. Find your alert and click the **three dots** menu
3. Select **Send test notification**
4. Check your server logs and Telegram

### 7c. Verify storage

```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('advisor.db')
rows = conn.execute('SELECT ticker, signal_type, rsi_14, luxalgo_confidence FROM tv_signals ORDER BY id DESC LIMIT 5').fetchall()
for r in rows: print(r)
"
```

---

## Step 8: Troubleshooting

### Signal received but no Telegram message
- Check `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `.env`
- Run `python -c "from config.settings import TELEGRAM_BOT_TOKEN; print(TELEGRAM_BOT_TOKEN)"` to verify env loads

### 401 Unauthorized from webhook
- Verify `X-Webhook-Token` header matches `WEBHOOK_SECRET_TOKEN` in `.env`
- Check for trailing spaces in the header value

### `{{plot_0}}` appears literally in stored JSON
- TradingView didn't resolve the placeholder because the indicator isn't loaded on the chart
- Confirm the LuxAlgo indicator is visible on the chart before creating the alert

### Signal stored but no Claude analysis
- Check server logs: `signal_is_meaningful()` may have returned False (no TA data)
- Ensure at least one of: `rsi_14`, `ema_50`, `close`, `luxalgo_confidence` is in the payload

### Cooldown blocking re-analysis
- Default cooldown is 120 minutes per ticker
- Override: set `COOLDOWN_MINUTES=0` in `.env` for testing
- STRONG signals (confidence ≥ 0.90 or signal_type contains "STRONG") always bypass cooldown

---

## Step 9: LuxAlgo Plot Index Reference

> These indices are for the most common LuxAlgo versions as of early 2026.
> Always verify by checking the indicator's Style tab in TradingView settings.

### LuxAlgo AI Strategy Alerts (typical)
| plot_N | Value |
|--------|-------|
| plot_0 | RSI (14) |
| plot_1 | MACD Histogram |
| plot_2 | EMA Fast (50) |
| plot_3 | EMA Slow (200) |
| plot_4 | LuxAlgo AI Confidence (0.0–1.0) |

### LuxAlgo Signals & Overlays (typical)
| plot_N | Value |
|--------|-------|
| plot_0 | RSI (14) |
| plot_1 | Signal Strength / Confidence |
| plot_2 | EMA 50 |
| plot_3 | EMA 200 |

### LuxAlgo Oscillator Matrix (typical)
| plot_N | Value |
|--------|-------|
| plot_0 | Oscillator value |
| plot_1 | Signal line |
| plot_2 | Histogram |
| plot_3 | RSI |

---

## Verification Checklist

Before going live, confirm:

- [ ] Server is accessible from the internet (ngrok or VPS)
- [ ] `curl` test above returns `{"status": "accepted", ...}`
- [ ] Telegram receives the test recommendation within 10 seconds
- [ ] Signal is stored in SQLite (`advisor.db`)
- [ ] At least one TradingView alert is created and pointed at your server
- [ ] TradingView test alert triggers a Telegram message
- [ ] Alert message JSON uses correct `plot_N` indices for your LuxAlgo version

---

*This guide covers the initial setup. After real signals start flowing, update this file with any corrections to plot indices or payload formats.*
