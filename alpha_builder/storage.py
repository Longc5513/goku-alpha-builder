from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class Storage:
    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS drafts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    module TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    thesis TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'draft',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS decision_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    module TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS peer_wallets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    wallet TEXT NOT NULL UNIQUE,
                    note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

    def add_draft(self, module: str, symbol: str, side: str, mode: str, thesis: str, payload: dict[str, Any], status: str = "draft") -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO drafts(module, symbol, side, mode, thesis, payload_json, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (module, symbol, side, mode, thesis, json.dumps(payload, ensure_ascii=False), status),
            )

    def list_drafts(self, limit: int = 30) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, module, symbol, side, mode, thesis, payload_json, status, created_at FROM drafts ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "module": row["module"],
                "symbol": row["symbol"],
                "side": row["side"],
                "mode": row["mode"],
                "thesis": row["thesis"],
                "payload": json.loads(row["payload_json"]),
                "status": row["status"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def add_decision(self, module: str, symbol: str, summary: str, payload: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO decision_log(module, symbol, summary, payload_json) VALUES (?, ?, ?, ?)",
                (module, symbol, summary, json.dumps(payload, ensure_ascii=False)),
            )

    def list_decisions(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, module, symbol, summary, payload_json, created_at FROM decision_log ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "module": row["module"],
                "symbol": row["symbol"],
                "summary": row["summary"],
                "payload": json.loads(row["payload_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def set_peer_wallets(self, wallets: list[str]) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM peer_wallets")
            for wallet in wallets:
                conn.execute("INSERT OR IGNORE INTO peer_wallets(wallet) VALUES (?)", (wallet,))

    def list_peer_wallets(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute("SELECT wallet FROM peer_wallets ORDER BY id ASC").fetchall()
        return [str(row["wallet"]) for row in rows]

