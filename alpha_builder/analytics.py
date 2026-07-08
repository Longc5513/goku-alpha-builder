from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any
import math
import statistics

import pandas as pd

from .models import MarketRow, StrategyDraft


TRACKED = {
    "vBTC_vUSDC": ("BTC", "Bitcoin"),
    "vETH_vUSDC": ("ETH", "Ethereum"),
    "vSOL_vUSDC": ("SOL", "Solana"),
    "vLINK_vUSDC": ("LINK", "Chainlink"),
    "WSOSO_vUSDC": ("SOSO", "SoSoValue"),
    "vMAG7ssi_vUSDC": ("MAGI7", "MAG7.ssi"),
    "vUSSI_vUSDC": ("USSI", "USSI Treasury Index"),
    "vARB_vUSDC": ("ARB", "Arbitrum"),
    "vPEPE_vUSDC": ("PEPE", "Pepe"),
    "vAVAX_vUSDC": ("AVAX", "Avalanche"),
    "vSHIB_vUSDC": ("SHIB", "Shiba Inu"),
    "vHYPE_vUSDC": ("HYPE", "Hype"),
}


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def build_market_rows(spot_tickers: Any, book_tickers: Any) -> list[MarketRow]:
    book_map: dict[str, dict[str, Any]] = {}
    for item in _extract_items(book_tickers):
        symbol = str(item.get("symbol") or item.get("s") or "").strip()
        if symbol:
            book_map[symbol] = item
    rows: list[MarketRow] = []
    for item in _extract_items(spot_tickers):
        venue_symbol = str(item.get("symbol") or item.get("s") or "").strip()
        symbol, name = TRACKED.get(venue_symbol, _fallback_symbol_name(venue_symbol, item))
        price = safe_float(item.get("price") or item.get("lastPrice") or item.get("lastPx") or item.get("close"))
        change_24h = safe_float(item.get("priceChangePercent") or item.get("change24h") or item.get("changePct") or item.get("change"))
        volume_24h = safe_float(item.get("quoteVolume") or item.get("volume"))
        bid = safe_float(book_map.get(venue_symbol, {}).get("bidPrice") or book_map.get(venue_symbol, {}).get("bidPx"))
        ask = safe_float(book_map.get(venue_symbol, {}).get("askPrice") or book_map.get(venue_symbol, {}).get("askPx"))
        spread_bps = 0.0
        if bid and ask and price:
            spread_bps = ((ask - bid) / price) * 10000
        confidence = max(35.0, min(95.0, 55.0 + min(abs(change_24h), 12.0) * 1.7 - min(spread_bps, 40.0) * 0.4))
        signal = signal_for_row(change_24h, spread_bps, volume_24h)
        rows.append(
            MarketRow(
                symbol=symbol,
                display=name,
                source=venue_symbol,
                price=price,
                change_24h=change_24h,
                volume_24h=volume_24h,
                market_cap=0.0,
                signal=signal,
                confidence=round(confidence, 1),
                pair=f"{symbol}/USDC",
            )
        )
    rows.sort(key=lambda row: row.volume_24h, reverse=True)
    return rows


def _fallback_symbol_name(venue_symbol: str, item: dict[str, Any]) -> tuple[str, str]:
    display_name = str(item.get("displayName") or "").strip()
    if display_name and "/" in display_name:
        base = display_name.split("/", 1)[0]
        return base.replace("ssi", "").upper(), display_name
    compact = venue_symbol.replace("_vUSDC", "").replace("_USDC", "").replace("v", "", 1)
    return compact.upper(), venue_symbol


def signal_for_row(change_24h: float, spread_bps: float, volume_24h: float) -> str:
    if volume_24h <= 0:
        return "WATCH"
    if abs(change_24h) >= 2.8 and spread_bps <= 18:
        return "BUY" if change_24h > 0 else "SELL"
    if abs(change_24h) >= 1.2:
        return "WATCH"
    return "HOLD"


def _extract_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("data", "result", "rows", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def build_price_frame(klines: Any) -> pd.DataFrame:
    rows = []
    for item in _extract_items(klines):
        rows.append(
            {
                "time": item.get("openTime") or item.get("t") or item.get("time"),
                "open": safe_float(item.get("open") or item.get("o")),
                "high": safe_float(item.get("high") or item.get("h")),
                "low": safe_float(item.get("low") or item.get("l")),
                "close": safe_float(item.get("close") or item.get("c")),
                "volume": safe_float(item.get("quoteVolume") or item.get("volume") or item.get("v")),
            }
        )
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame["close"] = frame["close"].replace(0, pd.NA).ffill()
    frame["ret"] = frame["close"].pct_change().fillna(0.0)
    frame["rolling_mean"] = frame["close"].rolling(20).mean()
    frame["rolling_std"] = frame["close"].rolling(20).std().fillna(0.0)
    frame["volume_mean"] = frame["volume"].rolling(20).mean().fillna(0.0)
    return frame


def build_price_frame_from_binance(klines: Any) -> pd.DataFrame:
    rows = []
    if isinstance(klines, list):
        for item in klines:
            if not isinstance(item, (list, tuple)) or len(item) < 6:
                continue
            rows.append(
                {
                    "time": item[0],
                    "open": safe_float(item[1]),
                    "high": safe_float(item[2]),
                    "low": safe_float(item[3]),
                    "close": safe_float(item[4]),
                    "volume": safe_float(item[5]),
                }
            )
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame["ret"] = frame["close"].pct_change().fillna(0.0)
    frame["rolling_mean"] = frame["close"].rolling(20).mean()
    frame["rolling_std"] = frame["close"].rolling(20).std().fillna(0.0)
    frame["volume_mean"] = frame["volume"].rolling(20).mean().fillna(0.0)
    return frame


def replay_strategy(frame: pd.DataFrame, mode: str) -> dict[str, float]:
    if frame.empty or len(frame) < 30:
        return {"return_pct": 0.0, "sharpe": 0.0, "max_drawdown_pct": 0.0, "win_rate_pct": 0.0}
    if mode == "Mean Reversion":
        zscore = (frame["close"] - frame["rolling_mean"]) / frame["rolling_std"].replace(0, pd.NA)
        signal = (-zscore).clip(-1, 1).fillna(0.0)
    elif mode == "Vol Breakout":
        volume_spike = (frame["volume"] / frame["volume_mean"].replace(0, pd.NA)).fillna(0.0)
        breakout = ((frame["close"] > frame["rolling_mean"]) & (volume_spike > 1.4)).astype(float)
        signal = breakout.replace(0, -1.0)
    else:
        momentum = frame["close"].pct_change(5).fillna(0.0)
        signal = momentum.apply(lambda value: 1.0 if value > 0 else -1.0)
    strategy_ret = signal.shift(1).fillna(0.0) * frame["ret"]
    equity = (1 + strategy_ret).cumprod()
    running_max = equity.cummax()
    drawdown = (equity / running_max) - 1
    sharpe = 0.0
    if strategy_ret.std() and not math.isnan(strategy_ret.std()):
        sharpe = (strategy_ret.mean() / strategy_ret.std()) * math.sqrt(365)
    wins = strategy_ret[strategy_ret != 0]
    win_rate = (wins > 0).mean() * 100 if len(wins) else 0.0
    return {
        "return_pct": round((equity.iloc[-1] - 1) * 100, 2),
        "sharpe": round(sharpe, 2),
        "max_drawdown_pct": round(drawdown.min() * 100, 2),
        "win_rate_pct": round(float(win_rate), 2),
    }


def depth_stats(orderbook: Any) -> dict[str, float]:
    if not isinstance(orderbook, dict):
        return {"bid_depth": 0.0, "ask_depth": 0.0, "spread_bps": 0.0, "imbalance_pct": 0.0}
    if isinstance(orderbook.get("data"), dict):
        orderbook = orderbook["data"]
    bids = orderbook.get("bids") or []
    asks = orderbook.get("asks") or []
    bid_depth = sum(safe_float(level[0]) * safe_float(level[1]) for level in bids[:8] if isinstance(level, (list, tuple)) and len(level) >= 2)
    ask_depth = sum(safe_float(level[0]) * safe_float(level[1]) for level in asks[:8] if isinstance(level, (list, tuple)) and len(level) >= 2)
    top_bid = safe_float(bids[0][0]) if bids else 0.0
    top_ask = safe_float(asks[0][0]) if asks else 0.0
    mid = (top_bid + top_ask) / 2 if top_bid and top_ask else 0.0
    spread_bps = ((top_ask - top_bid) / mid) * 10000 if mid else 0.0
    imbalance = ((bid_depth - ask_depth) / max(bid_depth + ask_depth, 1.0)) * 100
    return {
        "bid_depth": round(bid_depth, 2),
        "ask_depth": round(ask_depth, 2),
        "spread_bps": round(spread_bps, 2),
        "imbalance_pct": round(imbalance, 2),
    }


def build_strategy_draft(row: MarketRow, module: str, side: str, mode: str, notional: float, thesis: str, extra: dict[str, Any]) -> StrategyDraft:
    confidence = row.confidence
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "module": module,
        "symbol": row.symbol,
        "venue_symbol": row.source,
        "side": side,
        "mode": mode,
        "notional": round(notional, 2),
        "entry": row.price,
        "thesis": thesis,
        "confidence": confidence,
        "extra": extra,
    }
    return StrategyDraft(module=module, symbol=row.symbol, side=side, mode=mode, thesis=thesis, confidence=confidence, notional=round(notional, 2), payload=payload)


def smart_money_consensus(trades_by_wallet: dict[str, list[dict[str, Any]]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for wallet, trades in trades_by_wallet.items():
        for trade in trades:
            symbol = str(trade.get("symbol") or trade.get("s") or "").strip()
            if not symbol:
                continue
            qty = abs(safe_float(trade.get("size") or trade.get("quantity") or trade.get("q"), 0.0))
            price = safe_float(trade.get("price") or trade.get("p"), 0.0)
            side = str(trade.get("side") or trade.get("S") or "BUY").upper()
            rows.append({"wallet": wallet, "symbol": symbol, "side": side, "notional": qty * price})
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    grouped = frame.groupby(["symbol", "side"], as_index=False)["notional"].sum()
    pivot = grouped.pivot(index="symbol", columns="side", values="notional").fillna(0.0).reset_index()
    pivot["total"] = pivot.get("BUY", 0.0) + pivot.get("SELL", 0.0)
    pivot["bias"] = pivot.apply(lambda row: "BUY" if row.get("BUY", 0.0) >= row.get("SELL", 0.0) else "SELL", axis=1)
    pivot["conviction"] = (pivot[[col for col in ("BUY", "SELL") if col in pivot.columns]].max(axis=1) / pivot["total"].replace(0, pd.NA)).fillna(0.0) * 100
    return pivot.sort_values(["conviction", "total"], ascending=[False, False])


def score_repos_summary() -> list[dict[str, str]]:
    return [
        {"repo": "Polymarket_data", "use": "Dataset discipline -> replay-ready market lab"},
        {"repo": "prediction-market-backtesting", "use": "Simulation discipline -> promote only replay-tested ideas"},
        {"repo": "polybot", "use": "Trader behavior -> peer consensus and replication scoring"},
        {"repo": "polymarket_lp_tool", "use": "Maker discipline -> quote and repricing monitor"},
        {"repo": "CloddsBot + Harrier", "use": "Multi-strategy execution core instead of isolated widgets"},
        {"repo": "TradingAgents + pydantic-ai", "use": "Typed AI drafts and operator-ready theses"},
        {"repo": "pmxt + awesome list", "use": "Unified market tooling mindset and product breadth"},
    ]


def summarize_news(news_hot: Any, featured: Any) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for source, payload in (("hot", news_hot), ("featured", featured)):
        items = _extract_items(payload)
        for item in items[:12]:
            rows.append(
                {
                    "source": source,
                    "title": item.get("title") or item.get("name") or "Untitled",
                    "summary": item.get("summary") or item.get("description") or "",
                    "link": item.get("link") or item.get("url") or "",
                }
            )
    return pd.DataFrame(rows)


def execution_plan_notional(balance_total: float, confidence: float, max_notional: float) -> float:
    budget = max(150.0, min(max_notional, balance_total * (0.08 + confidence / 400)))
    return round(budget, 2)


def simple_peer_score(trades: list[dict[str, Any]]) -> dict[str, float]:
    notionals = []
    prices = []
    for trade in trades:
        qty = abs(safe_float(trade.get("size") or trade.get("quantity") or trade.get("q"), 0.0))
        price = safe_float(trade.get("price") or trade.get("p"), 0.0)
        if qty and price:
            notionals.append(qty * price)
            prices.append(price)
    if not notionals:
        return {"timing": 0.0, "sizing": 0.0, "discipline": 0.0}
    avg = statistics.mean(notionals)
    timing = min(100.0, 40.0 + len(notionals) * 3.0)
    sizing = min(100.0, 35.0 + math.log10(max(avg, 1.0)) * 12.0)
    discipline = max(0.0, min(100.0, 75.0 - statistics.pstdev(prices) / max(statistics.mean(prices), 1.0) * 300))
    return {"timing": round(timing, 1), "sizing": round(sizing, 1), "discipline": round(discipline, 1)}


def as_dict(draft: StrategyDraft) -> dict[str, Any]:
    return asdict(draft)
