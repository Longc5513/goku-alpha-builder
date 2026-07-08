from __future__ import annotations

from datetime import datetime
import json
import uuid
from typing import Any, Callable
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import requests
import streamlit as st

try:
    import plotly.express as px
    import plotly.graph_objects as go
    HAS_PLOTLY = True
except ModuleNotFoundError:
    px = None
    go = None
    HAS_PLOTLY = False

from alpha_builder.analytics import (
    as_dict,
    build_market_rows,
    build_price_frame,
    build_strategy_draft,
    depth_stats,
    execution_plan_notional,
    build_leaderboard_consensus,
    normalize_perps_positions,
    replay_strategy,
    score_repos_summary,
    simple_peer_score,
    smart_money_consensus,
    summarize_news,
    trade_check_verdict,
)
from alpha_builder.clients import ApiError, GroqClient, SoDexClient, SoSoValueClient
from alpha_builder.config import ensure_parent_dir, load_config
from alpha_builder.storage import Storage


st.set_page_config(page_title="GOKU Alpha Builder", page_icon="🧠", layout="wide", initial_sidebar_state="expanded")

st.markdown(
    """
    <style>
    .stApp { background: linear-gradient(180deg, #07111f 0%, #0d1728 100%); color: #eef4ff; }
    .block-container { padding-top: 1.2rem; }
    .hero {
      padding: 24px 28px;
      border-radius: 24px;
      background: radial-gradient(circle at top right, rgba(255,125,88,0.22), transparent 24%), linear-gradient(135deg, #0d1220 0%, #141f39 100%);
      border: 1px solid rgba(119, 140, 255, 0.16);
      box-shadow: 0 18px 50px rgba(0, 0, 0, 0.28);
    }
    .hero h1 { margin: 0; font-size: 2.2rem; color: #f7fbff; }
    .hero p { margin-top: 0.5rem; color: #b8c7e0; }
    .pill { display: inline-block; padding: 0.3rem 0.65rem; border: 1px solid rgba(151,167,255,0.22); border-radius: 999px; margin-right: 0.4rem; color: #d8e3ff; font-size: 0.82rem; }
    .section-card {
      background: rgba(13, 21, 37, 0.9);
      border: 1px solid rgba(151,167,255,0.12);
      border-radius: 20px;
      padding: 18px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


config = load_config()
ensure_parent_dir(config.db_path)
storage = Storage(config.db_path)
soso = SoSoValueClient(config.sosovalue_base_url, config.sosovalue_api_key)
sodex = SoDexClient(
    spot_base_url=config.sodex_spot_base_url,
    perps_base_url=config.sodex_perps_base_url,
    api_key_name=config.sodex_api_key_name,
    private_key=config.sodex_private_key,
    account_id=config.sodex_account_id,
    wallet_address=config.sodex_wallet_address,
)
groq = GroqClient(config.groq_api_key, config.groq_model)


def ensure_ui_state() -> None:
    st.session_state.setdefault("api_tray", [])
    st.session_state.setdefault("last_ai_draft", None)


def remember_api_call(provider: str, endpoint: str, status: str, latency_ms: float, detail: str) -> None:
    try:
        tray = st.session_state.get("api_tray", [])
    except Exception:
        return
    tray.insert(
        0,
        {
            "time": datetime.now().strftime("%H:%M:%S"),
            "provider": provider,
            "endpoint": endpoint,
            "status": status,
            "latency_ms": round(latency_ms, 1),
            "detail": detail[:140],
        },
    )
    try:
        st.session_state["api_tray"] = tray[:18]
    except Exception:
        return


def api_call(provider: str, endpoint: str, fn: Callable[[], Any]) -> Any:
    started = datetime.utcnow()
    try:
        payload = fn()
        latency = (datetime.utcnow() - started).total_seconds() * 1000
        remember_api_call(provider, endpoint, "ok", latency, str(payload))
        return payload
    except Exception as exc:
        latency = (datetime.utcnow() - started).total_seconds() * 1000
        remember_api_call(provider, endpoint, "error", latency, str(exc))
        raise


@st.cache_data(ttl=45, show_spinner=False)
def load_market_bundle() -> dict[str, object]:
    try:
        tickers = api_call("SoDEX", "spot_tickers", lambda: sodex.spot_tickers())
        book_tickers = api_call("SoDEX", "spot_book_tickers", lambda: sodex.spot_book_tickers())
        rows = build_market_rows(tickers, book_tickers)
        if rows:
            return {"rows": rows, "tickers": tickers, "book_tickers": book_tickers, "provider": "sodex"}
    except Exception:
        return {"rows": [], "tickers": [], "book_tickers": [], "provider": "sodex-error"}
    return {"rows": [], "tickers": [], "book_tickers": [], "provider": "sodex-empty"}


@st.cache_data(ttl=90, show_spinner=False)
def load_orderbook(symbol: str) -> dict[str, object]:
    payload = api_call("SoDEX", f"orderbook:{symbol}", lambda: sodex.spot_orderbook(symbol, limit=20))
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        return payload["data"]
    return payload


@st.cache_data(ttl=90, show_spinner=False)
def load_klines(symbol: str, interval: str) -> pd.DataFrame:
    try:
        frame = build_price_frame(api_call("SoDEX", f"klines:{symbol}:{interval}", lambda: sodex.spot_klines(symbol, interval=interval, limit=180)))
        if not frame.empty:
            return frame
    except Exception:
        return pd.DataFrame()
    return pd.DataFrame()


@st.cache_data(ttl=180, show_spinner=False)
def load_news_bundle() -> dict[str, object]:
    news_hot: object = {}
    featured: object = {}
    macro: object = {}
    try:
        news_hot = api_call("SoSoValue", "news_hot", lambda: soso.news_hot(page=1, page_size=10))
    except Exception:
        news_hot = {}
    try:
        featured = api_call("SoSoValue", "news_featured", lambda: soso.news_featured(page_num=1, page_size=10))
    except Exception:
        featured = {}
    try:
        macro = api_call("SoSoValue", "macro_events", lambda: soso.macro_events(datetime.utcnow().strftime("%Y-%m-%d")))
    except Exception:
        macro = {}
    return {"news": summarize_news(news_hot, featured), "macro": macro}


@st.cache_data(ttl=120, show_spinner=False)
def load_symbol_news(symbol: str) -> pd.DataFrame:
    currency = symbol.replace("USDC", "").replace("v", "", 1).replace("_", "").replace("ssi", "").replace("WSOSO", "SOSO")
    currency = "BTC" if currency.startswith("BTC") else "ETH" if currency.startswith("ETH") else "SOL" if currency.startswith("SOL") else "LINK" if currency.startswith("LINK") else "SOSO" if "SOSO" in currency else "ARB" if currency.startswith("ARB") else "AVAX" if currency.startswith("AVAX") else "SHIB" if currency.startswith("SHIB") else "PEPE" if currency.startswith("PEPE") else "HYPE" if currency.startswith("HYPE") else currency
    try:
        payload = api_call("SoSoValue", f"news_featured_currency:{currency}", lambda: soso.news_featured_currency(currency, page_num=1, page_size=6))
        return summarize_news(payload, {})
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=240, show_spinner=False)
def load_leaderboard_consensus() -> pd.DataFrame:
    leaderboard = api_call("SoDEX", "leaderboard:30d", lambda: sodex.leaderboard(window_type="30d", sort_by="volume", sort_order="desc", page=1, page_size=50))
    items = leaderboard.get("items") if isinstance(leaderboard, dict) else []
    items = [item for item in items or [] if float(item.get("pnl_usd", 0) or 0) > 0][:20]
    wallets = [str(item.get("wallet_address") or "").strip() for item in items if item.get("wallet_address")]
    positions_by_wallet: dict[str, Any] = {}
    if wallets:
        with ThreadPoolExecutor(max_workers=min(8, len(wallets))) as pool:
            futures = {pool.submit(lambda w=wallet: api_call("SoDEX", f"perps_positions:{w[:8]}", lambda: sodex.perps_positions(w))): wallet for wallet in wallets}
            for future, wallet in futures.items():
                try:
                    positions_by_wallet[wallet] = future.result()
                except Exception:
                    positions_by_wallet[wallet] = {}
    return build_leaderboard_consensus(leaderboard, positions_by_wallet, n_top=20)


def log_and_store(module: str, symbol: str, summary: str, payload: dict[str, object]) -> None:
    storage.add_decision(module, symbol, summary, payload)


def save_draft(draft) -> None:
    storage.add_draft(draft.module, draft.symbol, draft.side, draft.mode, draft.thesis, as_dict(draft))


def hero() -> None:
    st.markdown(
        """
        <div class="hero">
          <div>
            <span class="pill">SoSoValue research</span>
            <span class="pill">SoDEX execution</span>
            <span class="pill">Real market, real depth, real payload prep</span>
          </div>
          <h1>GOKU SoDEX Operator</h1>
          <p>Live operator desk for SoDEX spot execution with SoSoValue research context, smart-money consensus, depth inspection, and signed order preparation.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_api_visibility_tray() -> None:
    with st.expander("API Visibility Tray", expanded=False):
        tray = pd.DataFrame(st.session_state.get("api_tray", []))
        if tray.empty:
            st.caption("No API calls recorded yet in this session.")
        else:
            st.dataframe(tray, use_container_width=True, hide_index=True)


def render_operator_queue() -> None:
    st.subheader("Operator Queue")
    drafts = pd.DataFrame(storage.list_drafts(40))
    if drafts.empty:
        st.info("No drafts staged yet. Use Strategy Rack, News Agent, or Execution Copilot to create operator-ready items.")
        return
    ai_drafts = drafts[drafts["module"].isin(["groq-execution", "news-agent", "strategy-rack", "execution-copilot"])]
    if ai_drafts.empty:
        st.info("No AI or staged execution drafts found yet.")
        return
    st.metric("Queued drafts", len(ai_drafts))
    st.dataframe(ai_drafts[["id", "module", "symbol", "side", "mode", "thesis", "status", "created_at"]], use_container_width=True, hide_index=True)
    latest = ai_drafts.iloc[0].to_dict()
    st.caption("Latest queued draft payload")
    st.json(latest["payload"])


def render_overview(rows: list) -> None:
    st.subheader("Launch Rail")
    data = pd.DataFrame([row.__dict__ for row in rows])
    if data.empty:
        st.warning("No live SoDEX market rows returned.")
        return
    top = data.head(8).copy()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tracked symbols", len(data))
    c2.metric("24H volume", f"${top['volume_24h'].sum():,.0f}")
    c3.metric("Best mover", top.sort_values("change_24h", ascending=False).iloc[0]["symbol"])
    c4.metric("Worst mover", top.sort_values("change_24h").iloc[0]["symbol"])
    news_bundle = load_news_bundle()
    news_frame = news_bundle["news"] if isinstance(news_bundle["news"], pd.DataFrame) else pd.DataFrame()
    macro = news_bundle.get("macro")
    thesis_col, regime_col = st.columns(2)
    with thesis_col:
        st.markdown("**Regime Verdict**")
        positive = int((data["change_24h"] > 0).sum())
        breadth = round((positive / max(len(data), 1)) * 100, 1)
        leader = top.sort_values("change_24h", ascending=False).iloc[0]
        regime = "risk-on" if breadth >= 55 else "mixed" if breadth >= 40 else "risk-off"
        st.info(f"{regime.upper()} | breadth {breadth}% | leader {leader['symbol']} {leader['change_24h']:+.2f}%")
    with regime_col:
        st.markdown("**Research Trigger**")
        if not news_frame.empty:
            top_story = news_frame.iloc[0]
            st.success(top_story["title"])
            st.caption(top_story["summary"][:180] or "Live SoSoValue story available.")
        else:
            st.caption("Live research feed not available right now.")
        if macro:
            st.caption("Macro event payload detected from SoSoValue.")
    st.dataframe(
        top[["symbol", "price", "change_24h", "volume_24h", "signal", "confidence", "source"]],
        use_container_width=True,
        hide_index=True,
    )
    if HAS_PLOTLY:
        fig = px.bar(top, x="symbol", y="change_24h", color="signal", title="Live SoDEX momentum tape")
        fig.update_layout(height=330, margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.bar_chart(top.set_index("symbol")["change_24h"], use_container_width=True)


def render_strategy_rack(rows: list) -> None:
    st.subheader("Strategy Rack")
    st.caption("Live SoDEX rows are ranked into operator-ready drafts. No mock markets are used here.")
    repo_notes = score_repos_summary()
    data = pd.DataFrame([row.__dict__ for row in rows])
    if data.empty:
        st.info("Waiting for market rows.")
        return
    leader = data.sort_values(["confidence", "change_24h"], ascending=[False, False]).iloc[0]
    laggard = data.sort_values("change_24h").iloc[0]
    vol_breakout = data.assign(breakout_score=data["volume_24h"] * data["change_24h"].abs()).sort_values("breakout_score", ascending=False).iloc[0]
    c1, c2, c3 = st.columns(3)
    cards = [
        ("Trend Capture", leader, "BUY" if leader["change_24h"] >= 0 else "SELL", "MARKET", "Harrier-style execution core for tape leaders."),
        ("Mean Reversion", laggard, "BUY" if laggard["change_24h"] < 0 else "SELL", "LIMIT", "prediction-market-backtesting style reversal candidate."),
        ("Vol Breakout", vol_breakout, "BUY" if vol_breakout["change_24h"] >= 0 else "SELL", "MARKET", "CloddsBot/Harrier breakout promotion when participation expands."),
    ]
    for column, (title, row, side, mode, thesis) in zip((c1, c2, c3), cards):
        with column:
            st.markdown(f"**{title}**")
            st.write(f"{row['symbol']} | {row['signal']} | {row['confidence']} confidence")
            st.caption(thesis)
            if st.button(f"Stage {title}", key=f"strategy-{title}"):
                draft = build_strategy_draft(
                    row=type("RowObj", (), row.to_dict())(),
                    module="strategy-rack",
                    side=side,
                    mode=mode,
                    notional=execution_plan_notional(10000, float(row["confidence"]), 1800),
                    thesis=thesis,
                    extra={"repo_refs": [note["repo"] for note in repo_notes[:3]]},
                )
                save_draft(draft)
                log_and_store("strategy-rack", draft.symbol, f"Staged {title}", draft.payload)
                st.success(f"Draft staged for {draft.symbol}")
    st.dataframe(pd.DataFrame(repo_notes), use_container_width=True, hide_index=True)


def render_replay_lab(rows: list) -> None:
    st.subheader("Replay Lab")
    symbols = [row.source for row in rows]
    selected = st.selectbox("Replay symbol", symbols, index=0)
    interval = st.selectbox("Interval", ["15m", "1h", "4h"], index=1)
    frame = load_klines(selected, interval)
    if frame.empty:
        st.warning("No live SoDEX kline data returned for replay.")
        return
    strategy = st.selectbox("Replay mode", ["Trend", "Mean Reversion", "Vol Breakout"])
    metrics = replay_strategy(frame, strategy)
    a, b, c, d = st.columns(4)
    a.metric("Return", f"{metrics['return_pct']}%")
    b.metric("Sharpe", f"{metrics['sharpe']}")
    c.metric("Max DD", f"{metrics['max_drawdown_pct']}%")
    d.metric("Win rate", f"{metrics['win_rate_pct']}%")
    if HAS_PLOTLY:
        chart = go.Figure()
        chart.add_trace(go.Scatter(x=list(range(len(frame))), y=frame["close"], mode="lines", name="Close"))
        chart.add_trace(go.Scatter(x=list(range(len(frame))), y=frame["rolling_mean"], mode="lines", name="Mean"))
        chart.update_layout(height=360, margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(chart, use_container_width=True)
    else:
        st.line_chart(frame[["close", "rolling_mean"]], use_container_width=True)


def render_smart_money(rows: list) -> None:
    st.subheader("Smart Money Mirror")
    leaderboard_consensus = load_leaderboard_consensus()
    if not leaderboard_consensus.empty:
        st.markdown("**Qualified top-trader consensus**")
        st.dataframe(
            leaderboard_consensus[["symbol", "bias", "dominance_ratio", "long_traders", "short_traders", "long_notional", "short_notional"]].head(12),
            use_container_width=True,
            hide_index=True,
        )
    current = storage.list_peer_wallets()
    peer_input = st.text_area("Peer wallets", value="\n".join(current), placeholder="One 0x wallet per line")
    if st.button("Save peer set"):
        wallets = [value.strip() for value in peer_input.splitlines() if value.strip().startswith("0x")]
        storage.set_peer_wallets(wallets)
        st.success(f"Saved {len(wallets)} peer wallets")
        current = wallets
    if not current:
        st.info("Add peer wallets to unlock replication scoring. Global smart-money consensus is already loaded from the SoDEX leaderboard above.")
        return
    trades_by_wallet: dict[str, list[dict[str, object]]] = {}
    for wallet in current[:8]:
        try:
            trades = sodex.spot_user_trades(wallet)
            items = trades if isinstance(trades, list) else trades.get("data") or trades.get("result") or []
            trades_by_wallet[wallet] = [item for item in items if isinstance(item, dict)]
        except Exception:
            trades_by_wallet[wallet] = []
    consensus = smart_money_consensus(trades_by_wallet)
    if consensus.empty:
        st.warning("No peer trade history returned from SoDEX.")
    else:
        st.dataframe(consensus.head(10), use_container_width=True, hide_index=True)
        top = consensus.iloc[0]
        st.success(f"Top consensus: {top['symbol']} | {top['bias']} | conviction {top['conviction']:.1f}%")
    score_rows = []
    for wallet, trades in trades_by_wallet.items():
        score = simple_peer_score(trades)
        score_rows.append({"wallet": wallet, **score, "trades": len(trades)})
    score_frame = pd.DataFrame(score_rows)
    st.dataframe(score_frame, use_container_width=True, hide_index=True)
    if not score_frame.empty:
        a, b, c = st.columns(3)
        a.metric("Best timing", score_frame.sort_values("timing", ascending=False).iloc[0]["wallet"][:10] + "...")
        b.metric("Best sizing", score_frame.sort_values("sizing", ascending=False).iloc[0]["wallet"][:10] + "...")
        c.metric("Best discipline", score_frame.sort_values("discipline", ascending=False).iloc[0]["wallet"][:10] + "...")


def render_lp_guard(rows: list) -> None:
    st.subheader("LP Guard")
    selected = st.selectbox("LP symbol", [row.source for row in rows], index=0, key="lp-symbol")
    book = load_orderbook(selected)
    stats = depth_stats(book)
    a, b, c, d = st.columns(4)
    a.metric("Spread", f"{stats['spread_bps']} bps")
    b.metric("Bid depth", f"${stats['bid_depth']:,.0f}")
    c.metric("Ask depth", f"${stats['ask_depth']:,.0f}")
    d.metric("Imbalance", f"{stats['imbalance_pct']}%")
    bids = pd.DataFrame(book.get("bids") or [], columns=["price", "size"]).head(10)
    asks = pd.DataFrame(book.get("asks") or [], columns=["price", "size"]).head(10)
    col1, col2 = st.columns(2)
    col1.dataframe(bids, use_container_width=True, hide_index=True)
    col2.dataframe(asks, use_container_width=True, hide_index=True)
    if not bids.empty and not asks.empty:
        maker_side = "BUY" if stats["imbalance_pct"] >= 0 else "SELL"
        recommended = float(bids.iloc[0]["price"]) if maker_side == "BUY" else float(asks.iloc[0]["price"])
        st.info(f"Recommended maker action: {maker_side} near {recommended}")


def render_execution_copilot(rows: list) -> None:
    st.subheader("Execution Copilot")
    data = pd.DataFrame([row.__dict__ for row in rows])
    symbol = st.selectbox("Execution symbol", data["source"].tolist(), index=0)
    row = data[data["source"] == symbol].iloc[0]
    notional = st.number_input("Target notional (USDC)", min_value=50.0, value=float(execution_plan_notional(10000, float(row["confidence"]), 2500)))
    mode = st.selectbox("Route mode", ["LIMIT", "MARKET"])
    side = st.selectbox("Side", ["BUY", "SELL"], index=0 if row["change_24h"] >= 0 else 1)
    symbol_meta = api_call("SoDEX", f"symbols:{symbol}", lambda: sodex.spot_symbols(symbol))
    meta_items = symbol_meta if isinstance(symbol_meta, list) else symbol_meta.get("data") or symbol_meta.get("result") or []
    chosen = next(
        (
            item
            for item in meta_items
            if symbol in {
                str(item.get("symbol") or "").strip(),
                str(item.get("name") or "").strip(),
                str(item.get("displayName") or "").strip(),
            }
        ),
        {},
    )
    symbol_id = chosen.get("symbolID") or chosen.get("symbolId") or chosen.get("id")
    account_id = config.sodex_account_id or st.text_input("SoDEX account ID", value=config.sodex_account_id)
    quantity = round(notional / max(float(row["price"]), 1.0), 6)
    st.write({"venue_symbol": symbol, "symbol_id": symbol_id, "quantity": quantity, "price": row["price"]})
    leaderboard_consensus = load_leaderboard_consensus()
    consensus_row = None
    if not leaderboard_consensus.empty:
        target = {
            "BTC": "vBTC_vUSDC",
            "ETH": "vETH_vUSDC",
            "SOL": "vSOL_vUSDC",
            "LINK": "vLINK_vUSDC",
            "SOSO": "WSOSO_vUSDC",
            "MAGI7": "vMAG7ssi_vUSDC",
            "USSI": "vUSSI_vUSDC",
            "ARB": "vARB_vUSDC",
            "PEPE": "vPEPE_vUSDC",
            "AVAX": "vAVAX_vUSDC",
            "SHIB": "vSHIB_vUSDC",
            "HYPE": "vHYPE_vUSDC",
        }.get(row["symbol"])
        if target:
            matched = leaderboard_consensus[leaderboard_consensus["symbol"] == target]
            if not matched.empty:
                consensus_row = matched.iloc[0].to_dict()
    verdict = trade_check_verdict(type("RowObj", (), row.to_dict())(), side, consensus_row)
    verdict_col1, verdict_col2, verdict_col3 = st.columns(3)
    verdict_col1.metric("Trade Check", verdict["verdict"])
    verdict_col2.metric("Momentum bias", verdict["momentum_bias"])
    verdict_col3.metric("Smart money", verdict["consensus_label"])
    symbol_news = load_symbol_news(symbol)
    if not symbol_news.empty:
        st.markdown("**Live SoSoValue research for this symbol**")
        st.dataframe(symbol_news[["title", "summary", "link"]].head(4), use_container_width=True, hide_index=True)
    fee_rate = None
    if config.sodex_wallet_address and account_id:
        try:
            fee_rate = api_call("SoDEX", f"fee_rate:{symbol}", lambda: sodex.spot_fee_rate(config.sodex_wallet_address, symbol=symbol, account_id=account_id))
        except Exception:
            fee_rate = None
    fee_preview = json.dumps(fee_rate)[:120] if fee_rate else "Unavailable"
    risk_gate = {
        "aid_blocked": str(account_id).strip() in ("", "0"),
        "min_notional_ok": notional >= 50,
        "max_notional_ok": notional <= 5000,
        "fee_visible": fee_rate is not None,
    }
    gate_col1, gate_col2, gate_col3, gate_col4 = st.columns(4)
    gate_col1.metric("Min notional", "PASS" if risk_gate["min_notional_ok"] else "BLOCK")
    gate_col2.metric("Max notional", "PASS" if risk_gate["max_notional_ok"] else "BLOCK")
    gate_col3.metric("Account ID", "BLOCK" if risk_gate["aid_blocked"] else "PASS")
    gate_col4.metric("Fee aware", "PASS" if risk_gate["fee_visible"] else "WARN")
    st.caption(f"Fee probe: {fee_preview}")
    if groq.enabled and st.button("Generate Groq execution draft"):
        try:
            bundle = load_news_bundle()
            payload = api_call(
                "Groq",
                f"draft_execution:{symbol}",
                lambda: groq.draft_execution(
                    {
                        "symbol": row["symbol"],
                        "venue_symbol": symbol,
                        "price": row["price"],
                        "change_24h": row["change_24h"],
                        "volume_24h": row["volume_24h"],
                        "signal": row["signal"],
                        "confidence": row["confidence"],
                        "news": bundle["news"].head(3).to_dict(orient="records") if isinstance(bundle["news"], pd.DataFrame) else [],
                        "target_notional": notional,
                    }
                ),
            )
            st.session_state["last_ai_draft"] = payload
            storage.add_draft("groq-execution", row["symbol"], side, mode, payload.get("thesis", "Groq execution draft"), payload)
            storage.add_decision("groq", row["symbol"], "Generated Groq execution draft", payload)
            st.json(payload)
        except Exception as exc:
            st.error(f"Groq draft failed: {exc}")
    if st.button("Prepare SoDEX order", type="primary"):
        if not account_id or not symbol_id:
            st.error("Missing SoDEX account ID or symbol ID.")
        elif risk_gate["aid_blocked"]:
            st.error("Risk gate blocked this action because accountID is 0 or empty.")
        elif not risk_gate["min_notional_ok"]:
            st.error("Risk gate blocked this action because notional is below 50 USDC.")
        elif not risk_gate["max_notional_ok"]:
            st.error("Risk gate blocked this action because notional is above 5,000 USDC.")
        else:
            cl_ord_id = f"goku-{uuid.uuid4().hex[:12]}"
            params = (
                sodex.build_spot_limit_order(
                    account_id=account_id,
                    symbol_id=symbol_id,
                    cl_ord_id=cl_ord_id,
                    side=1 if side == "BUY" else 2,
                    price=str(row["price"]),
                    quantity=str(quantity),
                )
                if mode == "LIMIT"
                else sodex.build_spot_market_order(
                    account_id=account_id,
                    symbol_id=symbol_id,
                    cl_ord_id=cl_ord_id,
                    side=1 if side == "BUY" else 2,
                    quantity=str(quantity),
                )
            )
            prepared = sodex.prepare_spot_batch(params)
            draft_payload = {
                "prepared": {
                    "payload_hash": prepared.payload_hash,
                    "nonce": prepared.nonce,
                    "signature_present": bool(prepared.signature),
                    "path": prepared.path,
                    "params": prepared.params,
                }
            }
            storage.add_draft("execution-copilot", row["symbol"], side, mode, "Manual execution copilot draft", draft_payload)
            storage.add_decision("execution-copilot", row["symbol"], "Prepared SoDEX payload", draft_payload)
            st.json(draft_payload)
            if st.checkbox("Submit live order now", value=False) and prepared.signature:
                try:
                    response = sodex.submit_prepared(prepared)
                    st.success("Live submit attempted")
                    st.json(response)
                except Exception as exc:
                    st.error(f"Live submit failed: {exc}")


def render_news_agent(rows: list) -> None:
    st.subheader("News Intelligence")
    bundle = load_news_bundle()
    news = bundle["news"]
    if isinstance(news, pd.DataFrame) and not news.empty:
        st.dataframe(news[["source", "title", "summary", "link", "published_at"]].head(8), use_container_width=True, hide_index=True)
    else:
        st.info("Live SoSoValue news feed unavailable right now.")
    if groq.enabled and isinstance(news, pd.DataFrame) and not news.empty:
        if st.button("Summarize news into action plan"):
            try:
                summary = api_call("Groq", "draft_execution:news", lambda: groq.draft_execution({"module": "news-agent", "stories": news.head(5).to_dict(orient="records")}))
                storage.add_draft("news-agent", "MULTI", "BUY", "AI", summary.get("thesis", "News-to-execution AI draft"), summary)
                storage.add_decision("news-agent", "MULTI", "Groq summarized live news", summary)
                st.json(summary)
            except Exception as exc:
                st.error(f"Groq news summary failed: {exc}")


def render_portfolio() -> None:
    st.subheader("Portfolio Live")
    if not config.sodex_wallet_address:
        st.info("Set `SODEX_WALLET_ADDRESS` to read SoDEX account state.")
        return
    try:
        balances = sodex.spot_balances(config.sodex_wallet_address, config.sodex_account_id)
        state = sodex.spot_state(config.sodex_wallet_address, config.sodex_account_id)
        orders = sodex.spot_orders(config.sodex_wallet_address, account_id=config.sodex_account_id)
        st.write("Account state")
        st.json({"state": state, "balances": balances, "orders": orders})
    except Exception as exc:
        st.error(f"Portfolio read failed: {exc}")


def render_audit() -> None:
    st.subheader("Audit Trail")
    st.caption("Every draft and decision below was produced from live market, research, or execution workflows in this session.")
    st.write("Recent drafts")
    st.dataframe(pd.DataFrame(storage.list_drafts(20)), use_container_width=True, hide_index=True)
    st.write("Recent decisions")
    st.dataframe(pd.DataFrame(storage.list_decisions(30)), use_container_width=True, hide_index=True)


def render_diagnostics(rows: list) -> None:
    st.subheader("Diagnostics")
    probes = []
    for label, action in (
        ("SoDEX tickers", lambda: sodex.spot_tickers()),
        ("SoDEX symbols", lambda: sodex.spot_symbols()),
        ("SoSoValue news", lambda: soso.news_hot(page=1, page_size=3)),
    ):
        started = datetime.utcnow()
        try:
            payload = action()
            latency = (datetime.utcnow() - started).total_seconds() * 1000
            probes.append({"probe": label, "ok": True, "latency_ms": round(latency, 1), "preview": str(payload)[:120]})
        except Exception as exc:
            latency = (datetime.utcnow() - started).total_seconds() * 1000
            probes.append({"probe": label, "ok": False, "latency_ms": round(latency, 1), "preview": str(exc)[:120]})
    st.dataframe(pd.DataFrame(probes), use_container_width=True, hide_index=True)
    st.write("Config readiness")
    st.json(
        {
            "has_sosovalue_key": config.has_sosovalue,
            "has_sodex_signing": config.has_sodex_signing,
            "has_groq_key": config.has_groq,
            "groq_model": config.groq_model,
            "wallet_address": config.sodex_wallet_address,
            "account_id": config.sodex_account_id,
            "rows_loaded": len(rows),
        }
    )


def main() -> None:
    ensure_ui_state()
    hero()
    try:
        bundle = load_market_bundle()
        rows = bundle["rows"]
    except (ApiError, requests.RequestException) as exc:
        st.error(f"Market bootstrap failed: {exc}")
        rows = []
    menu = st.sidebar.radio(
        "Workspace",
        [
            "Launch",
            "Strategy Rack",
            "Replay Lab",
            "Smart Money Mirror",
            "LP Guard",
            "Execution Copilot",
            "News Agent",
            "Operator Queue",
            "Portfolio Live",
            "Audit Trail",
            "Diagnostics",
        ],
    )
    st.sidebar.caption("Wave 3 builder desk: live SoDEX execution, live SoSoValue research, and auditable operator workflows.")
    render_api_visibility_tray()
    if menu == "Launch":
        render_overview(rows)
    elif menu == "Strategy Rack":
        render_strategy_rack(rows)
    elif menu == "Replay Lab":
        render_replay_lab(rows)
    elif menu == "Smart Money Mirror":
        render_smart_money(rows)
    elif menu == "LP Guard":
        render_lp_guard(rows)
    elif menu == "Execution Copilot":
        render_execution_copilot(rows)
    elif menu == "News Agent":
        render_news_agent(rows)
    elif menu == "Operator Queue":
        render_operator_queue()
    elif menu == "Portfolio Live":
        render_portfolio()
    elif menu == "Audit Trail":
        render_audit()
    else:
        render_diagnostics(rows)


if __name__ == "__main__":
    main()
