from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class MarketRow:
    symbol: str
    display: str
    source: str
    price: float
    change_24h: float
    volume_24h: float
    market_cap: float
    signal: str
    confidence: float
    pair: str


@dataclass
class StrategyDraft:
    module: str
    symbol: str
    side: str
    mode: str
    thesis: str
    confidence: float
    notional: float
    payload: dict[str, Any]


@dataclass
class ProbeResult:
    provider: str
    target: str
    ok: bool
    latency_ms: float
    preview: str
    error: str = ""

