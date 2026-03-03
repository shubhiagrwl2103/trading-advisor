"""
AI Investment Advisor — Streamlit Dashboard
5 tabs: Portfolio | Live Signals | Recommendations | History | Config

Run: streamlit run output/streamlit_app.py
"""

import json
import os
import sys
from datetime import datetime, timezone

import pandas as pd
import plotly.express as px
import streamlit as st

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage.database import init_db_sync
from storage.queries import (
    sync_get_recent_signals,
    sync_get_recent_recommendations,
    sync_get_latest_robinhood_snapshot,
    sync_mark_acted_on,
    sync_save_robinhood_snapshot,
)

# ──────────────────────────────────────────────────────────────────────────────
# Page config
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Investment Advisor",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Ensure DB exists
init_db_sync()


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def load_live_portfolio():
    """Fetch live portfolio — Kraken API + SQLite Robinhood snapshot."""
    try:
        from portfolio.aggregator import get_live_portfolio
        return get_live_portfolio()
    except Exception as e:
        st.error(f"Portfolio fetch failed: {e}")
        return None


ACTION_COLORS = {
    "BUY": "🟢",
    "ADD": "🟢",
    "HOLD": "🟡",
    "WAIT": "🟡",
    "REDUCE": "🔴",
    "AVOID": "🔴",
}

SIGNAL_COLORS = {
    "BUY": "green",
    "STRONG_BUY": "darkgreen",
    "SELL": "red",
    "STRONG_SELL": "darkred",
    "HOLD": "grey",
    "NEUTRAL": "grey",
}


# ──────────────────────────────────────────────────────────────────────────────
# Main app
# ──────────────────────────────────────────────────────────────────────────────

st.title("AI Investment Advisor")
st.caption("Event-driven trade suggestions via TradingView + LuxAlgo → Claude claude-opus-4-6")

tab_portfolio, tab_signals, tab_recs, tab_history, tab_config = st.tabs(
    ["Portfolio", "Live Signals", "Recommendations", "History", "Config"]
)


# ─────────────────────────────────────────────────────────────────────────────
# TAB 1: Portfolio
# ─────────────────────────────────────────────────────────────────────────────
with tab_portfolio:
    col_left, col_right = st.columns([2, 1])

    with col_left:
        st.subheader("Live Portfolio Value")

        if st.button("Refresh Live Data"):
            st.rerun()

        portfolio = load_live_portfolio()

        if portfolio:
            kpi1, kpi2, kpi3 = st.columns(3)
            kpi1.metric("Total Value", f"${portfolio.total_value_usd:,.0f}")
            kpi2.metric("Kraken (live)", f"${portfolio.kraken_value_usd:,.0f}")
            kpi3.metric(
                f"Robinhood ({portfolio.robinhood_snapshot_age_days or '?'}d old)",
                f"${portfolio.robinhood_value_usd:,.0f}",
                help="From last uploaded CSV",
            )

            if portfolio.robinhood_stale:
                st.warning(
                    f"Robinhood snapshot is {portfolio.robinhood_snapshot_age_days:.0f} days old. "
                    "Upload a fresh CSV below."
                )

            if portfolio.holdings:
                # Pie chart
                df_pie = pd.DataFrame(
                    [
                        {"Symbol": h.symbol, "Value ($)": h.value_usd, "Type": h.asset_type}
                        for h in portfolio.holdings
                        if h.value_usd > 0
                    ]
                )
                fig = px.pie(
                    df_pie,
                    names="Symbol",
                    values="Value ($)",
                    color="Type",
                    title="Portfolio Allocation",
                    hole=0.3,
                )
                st.plotly_chart(fig, use_container_width=True)

                # Holdings table
                df_holdings = pd.DataFrame(
                    [
                        {
                            "Symbol": h.symbol,
                            "Type": h.asset_type,
                            "Quantity": round(h.quantity, 4),
                            "Price ($)": f"${h.price_usd:,.2f}",
                            "Value ($)": f"${h.value_usd:,.0f}",
                            "Weight %": f"{h.weight_pct:.1f}%",
                        }
                        for h in sorted(portfolio.holdings, key=lambda x: x.value_usd, reverse=True)
                    ]
                )
                st.dataframe(df_holdings, use_container_width=True, hide_index=True)

    with col_right:
        st.subheader("Upload Robinhood CSV")
        st.caption(
            "Export from Robinhood: Account → Statements → Export CSV. "
            "Re-upload weekly for fresh stock data."
        )

        uploaded = st.file_uploader("Choose Robinhood CSV", type=["csv"])
        if uploaded is not None:
            try:
                from portfolio.robinhood_portfolio import parse_robinhood_csv, robinhood_holdings_to_snapshot
                raw = uploaded.read()
                holdings = parse_robinhood_csv(raw)
                snapshot = robinhood_holdings_to_snapshot(holdings)
                total_equity = snapshot["total_equity_usd"]
                sync_save_robinhood_snapshot(snapshot, total_equity)
                st.success(
                    f"Uploaded {len(holdings)} holdings, total equity ${total_equity:,.0f}. "
                    "Refresh to see updated portfolio."
                )
            except Exception as e:
                st.error(f"Failed to parse CSV: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# TAB 2: Live Signals
# ─────────────────────────────────────────────────────────────────────────────
with tab_signals:
    st.subheader("Incoming TradingView / LuxAlgo Signals")

    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        ticker_filter = st.text_input("Filter by ticker", "")
    with col_f2:
        tf_filter = st.selectbox("Timeframe", ["All", "1D", "1W", "1M", "4h", "1h"])
    with col_f3:
        limit = st.number_input("Max rows", min_value=10, max_value=500, value=50, step=10)

    signals = sync_get_recent_signals(limit=int(limit))

    if ticker_filter:
        signals = [s for s in signals if ticker_filter.upper() in s.get("ticker", "").upper()]
    if tf_filter != "All":
        signals = [s for s in signals if s.get("timeframe") == tf_filter]

    if not signals:
        st.info("No signals received yet. Configure TradingView webhooks to start.")
    else:
        rows = []
        for s in signals:
            rows.append(
                {
                    "Time": s.get("received_at", "")[:16],
                    "Ticker": s.get("ticker", ""),
                    "TF": s.get("timeframe", ""),
                    "Signal": s.get("signal_type", ""),
                    "Indicator": s.get("indicator", ""),
                    "Close": s.get("close_price"),
                    "RSI": s.get("rsi_14"),
                    "EMA50": s.get("ema_50"),
                    "EMA200": s.get("ema_200"),
                    "MACD Hist": s.get("macd_histogram"),
                    "LuxAlgo Conf": s.get("luxalgo_confidence"),
                }
            )
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)


# ─────────────────────────────────────────────────────────────────────────────
# TAB 3: Recommendations
# ─────────────────────────────────────────────────────────────────────────────
with tab_recs:
    st.subheader("Latest Recommendations")

    recs = sync_get_recent_recommendations(limit=20)

    if not recs:
        st.info("No recommendations yet. Trigger a webhook or run a manual analysis.")
    else:
        for row in recs:
            try:
                rec = json.loads(row["recommendation_json"]) if isinstance(row["recommendation_json"], str) else row["recommendation_json"]
                r = rec.get("recommendation", {})
                sig = rec.get("trigger_signal", {})
                port_info = rec.get("portfolio_at_analysis", {})

                ticker = row.get("ticker", "?")
                action = r.get("current_action", "?")
                conviction = r.get("conviction", "?")
                risk = r.get("risk_rating", "?")
                emoji = ACTION_COLORS.get(action, "⚪")
                tf = sig.get("timeframe", "?")
                indicator = sig.get("indicator", "?")
                holding_period = r.get("estimated_holding_period", "?")

                with st.expander(
                    f"{emoji} [{row['generated_at'][:16]}]  {ticker} ({tf})  →  {action}  |  {conviction} conviction",
                    expanded=False,
                ):
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Action", action)
                    c2.metric("Conviction", conviction)
                    c3.metric("Risk", risk)
                    c4.metric("Holding Period", holding_period)

                    c5, c6, c7 = st.columns(3)
                    c5.metric("Entry", r.get("entry_zone", "?"))
                    c6.metric("Target", r.get("target_zone", "?"))
                    c7.metric("Stop Loss", r.get("stop_loss_zone", "?"))

                    port_val = port_info.get("total_value_usd", row.get("portfolio_value_at_time"))
                    weight = port_info.get("ticker_weight_pct", "?")
                    suggested = r.get("suggested_position_size_pct", "?")

                    st.caption(
                        f"Portfolio at time: ${port_val:,.0f}  |  "
                        f"{ticker} weight: {weight}%  |  "
                        f"Suggested: {suggested}%  |  "
                        f"Trigger: {indicator}"
                    )

                    if r.get("reasoning"):
                        st.write(r["reasoning"])

                    supporting = r.get("supporting_signals", [])
                    conflicting = r.get("conflicting_signals", [])
                    if supporting:
                        st.write("**Supporting signals:**")
                        for s in supporting:
                            st.write(f"  ✅ {s}")
                    if conflicting:
                        st.write("**Conflicting signals:**")
                        for s in conflicting:
                            st.write(f"  ⚠️ {s}")

                    if r.get("portfolio_note"):
                        st.info(r["portfolio_note"])

            except Exception as e:
                st.error(f"Error rendering recommendation: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# TAB 4: History
# ─────────────────────────────────────────────────────────────────────────────
with tab_history:
    st.subheader("Recommendation History")
    st.caption("Mark which recommendations you acted on.")

    recs_all = sync_get_recent_recommendations(limit=200)

    col_h1, col_h2 = st.columns(2)
    with col_h1:
        h_ticker = st.text_input("Filter ticker", "", key="hist_ticker")
    with col_h2:
        h_action = st.selectbox("Filter action", ["All", "BUY", "ADD", "HOLD", "REDUCE", "AVOID", "WAIT"], key="hist_action")

    if h_ticker:
        recs_all = [r for r in recs_all if h_ticker.upper() in r.get("ticker", "").upper()]
    if h_action != "All":
        recs_all = [
            r for r in recs_all
            if json.loads(r["recommendation_json"]).get("recommendation", {}).get("current_action") == h_action
        ]

    if not recs_all:
        st.info("No history to show.")
    else:
        for row in recs_all:
            try:
                rec = json.loads(row["recommendation_json"])
                r = rec.get("recommendation", {})
                action = r.get("current_action", "?")
                emoji = ACTION_COLORS.get(action, "⚪")
                acted = bool(row.get("acted_on", 0))

                cols = st.columns([4, 1, 1])
                cols[0].write(
                    f"{emoji} [{row['generated_at'][:16]}] **{row['ticker']}** — {action} "
                    f"| Entry: {r.get('entry_zone','?')} | Target: {r.get('target_zone','?')}"
                )
                cols[1].write("✅ Acted" if acted else "")
                if cols[2].button("Toggle", key=f"act_{row['id']}"):
                    sync_mark_acted_on(row["id"], not acted)
                    st.rerun()
            except Exception:
                continue


# ─────────────────────────────────────────────────────────────────────────────
# TAB 5: Config
# ─────────────────────────────────────────────────────────────────────────────
with tab_config:
    st.subheader("System Configuration & Health")

    # Environment check
    st.write("**Environment variables:**")
    env_keys = [
        "KRAKEN_API_KEY", "ANTHROPIC_API_KEY", "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID", "WEBHOOK_SECRET_TOKEN", "DATABASE_PATH",
    ]
    env_df = pd.DataFrame(
        [
            {"Variable": k, "Set": "✅" if os.getenv(k) else "❌"}
            for k in env_keys
        ]
    )
    st.dataframe(env_df, use_container_width=True, hide_index=True)

    st.divider()

    # Signal stats per ticker
    st.write("**Signal counts by ticker (all time):**")
    all_signals = sync_get_recent_signals(limit=1000)
    if all_signals:
        from collections import Counter
        counts = Counter(s["ticker"] for s in all_signals)
        st.bar_chart(counts)
    else:
        st.info("No signals yet.")

    st.divider()

    # Last signal per ticker
    st.write("**Last signal per ticker:**")
    if all_signals:
        seen = {}
        for s in all_signals:
            if s["ticker"] not in seen:
                seen[s["ticker"]] = s
        df_last = pd.DataFrame(
            [
                {
                    "Ticker": t,
                    "Last Signal": v.get("received_at", "")[:16],
                    "Type": v.get("signal_type", ""),
                    "TF": v.get("timeframe", ""),
                }
                for t, v in sorted(seen.items())
            ]
        )
        st.dataframe(df_last, use_container_width=True, hide_index=True)

    st.divider()
    st.write("**Cooldown & settings:**")
    try:
        from config.settings import COOLDOWN_MINUTES, ROBINHOOD_STALE_DAYS, CLAUDE_MODEL, ANALYSIS_TIMEZONE
        settings_df = pd.DataFrame(
            [
                {"Setting": "Cooldown (minutes)", "Value": COOLDOWN_MINUTES},
                {"Setting": "Robinhood stale threshold (days)", "Value": ROBINHOOD_STALE_DAYS},
                {"Setting": "Claude model", "Value": CLAUDE_MODEL},
                {"Setting": "Timezone", "Value": ANALYSIS_TIMEZONE},
            ]
        )
        st.dataframe(settings_df, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"Failed to load settings: {e}")

    st.divider()
    st.write("**Manual analysis trigger:**")
    manual_ticker = st.text_input("Ticker to analyze", "")
    if st.button("Run analysis") and manual_ticker:
        with st.spinner(f"Analyzing {manual_ticker.upper()}..."):
            try:
                import asyncio
                from ai.claude_client import run_manual_analysis
                rec = asyncio.run(run_manual_analysis(manual_ticker.upper()))
                if rec:
                    st.success("Analysis complete — check Recommendations tab.")
                    st.json(rec)
                else:
                    st.error("Analysis failed — check server logs.")
            except Exception as e:
                st.error(f"Error: {e}")
