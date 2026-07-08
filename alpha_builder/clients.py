from __future__ import annotations

import json
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

import requests
from eth_account import Account
from eth_utils import keccak


class ApiError(RuntimeError):
    pass


def _compact_json(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def _normalize_private_key(key: str) -> str:
    key = key.strip()
    if key.startswith("0x"):
        key = key[2:]
    if len(key) != 64:
        raise ValueError("Expected a 32-byte hex private key")
    return key


def _encode_uint(value: int) -> bytes:
    return int(value).to_bytes(32, "big")


def _to_address_bytes(value: str) -> bytes:
    value = value.strip().lower()
    if not value.startswith("0x"):
        raise ValueError("Address must be hex")
    raw = bytes.fromhex(value[2:])
    if len(raw) != 20:
        raise ValueError("Address must be 20 bytes")
    return raw.rjust(32, b"\x00")


def _eip712_digest(domain: dict[str, Any], payload_hash_hex: str, nonce: int) -> bytes:
    domain_typehash = keccak(text="EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)")
    exchange_typehash = keccak(text="ExchangeAction(bytes32 payloadHash,uint64 nonce)")
    payload_hash = bytes.fromhex(payload_hash_hex[2:] if payload_hash_hex.startswith("0x") else payload_hash_hex)
    domain_hash = keccak(
        b"".join(
            [
                domain_typehash,
                keccak(text=str(domain["name"])),
                keccak(text=str(domain["version"])),
                _encode_uint(int(domain["chainId"])),
                _to_address_bytes(str(domain["verifyingContract"])),
            ]
        )
    )
    action_hash = keccak(b"".join([exchange_typehash, payload_hash, _encode_uint(int(nonce))]))
    return keccak(b"\x19\x01" + domain_hash + action_hash)


def sign_exchange_action(private_key_hex: str, domain: dict[str, Any], payload_hash_hex: str, nonce: int) -> str:
    digest = _eip712_digest(domain, payload_hash_hex, nonce)
    account = Account.from_key("0x" + _normalize_private_key(private_key_hex))
    signed = account.unsafe_sign_hash(digest)
    v = signed.v + 27 if signed.v in (0, 1) else signed.v
    return "0x01" + signed.r.to_bytes(32, "big").hex() + signed.s.to_bytes(32, "big").hex() + f"{v:02x}"


def payload_hash(action_type: str, params: dict[str, Any]) -> str:
    return "0x" + keccak(text=_compact_json({"type": action_type, "params": params})).hex()


@dataclass
class PreparedOrder:
    venue: str
    path: str
    action_type: str
    params: dict[str, Any]
    payload_hash: str
    nonce: int
    signature: str | None
    domain_name: str
    chain_id: int


class SoSoValueClient:
    def __init__(self, base_url: str, api_key: str, timeout: int = 20) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key.strip()
        self.timeout = timeout
        self.session = requests.Session()

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["x-soso-api-key"] = self.api_key
        return headers

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        if not path.startswith("/"):
            path = "/" + path
        response = self.session.get(
            f"{self.base_url}{path}",
            params=params,
            headers=self._headers(),
            timeout=self.timeout,
        )
        if not response.ok:
            raise ApiError(f"SoSoValue {response.status_code}: {response.text[:300]}")
        return response.json()

    def currencies(self) -> Any:
        return self.get("/currencies")

    def currency_snapshot(self, currency_id: str) -> Any:
        return self.get(f"/currencies/{currency_id}/market-snapshot")

    def currency_klines(self, currency_id: str, interval: str = "1d", limit: int = 90) -> Any:
        return self.get(f"/currencies/{currency_id}/klines", {"interval": interval, "limit": limit})

    def news_hot(self, page: int = 1, page_size: int = 20) -> Any:
        return self.get("/news/hot", {"page": page, "page_size": page_size})

    def news_featured(self, page_num: int = 1, page_size: int = 10) -> Any:
        return self.get("/news/featured", {"pageNum": page_num, "pageSize": page_size})

    def news_featured_currency(self, currency: str, page_num: int = 1, page_size: int = 10) -> Any:
        return self.get("/news/featured/currency", {"currency": currency, "pageNum": page_num, "pageSize": page_size})

    def macro_events(self, date: str | None = None) -> Any:
        return self.get("/macro/events", {"date": date} if date else None)


class BinanceClient:
    def __init__(self, base_url: str = "https://api.binance.com/api/v3", timeout: int = 20) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        response = self.session.get(f"{self.base_url}{path}", params=params, timeout=self.timeout)
        if not response.ok:
            raise ApiError(f"Binance {response.status_code}: {response.text[:300]}")
        return response.json()

    def tickers(self, symbol: str | None = None) -> Any:
        return self._get("/ticker/24hr", {"symbol": symbol} if symbol else None)

    def klines(self, symbol: str, interval: str = "1h", limit: int = 180) -> Any:
        return self._get("/klines", {"symbol": symbol, "interval": interval, "limit": limit})


class CoinGeckoClient:
    def __init__(self, base_url: str = "https://api.coingecko.com/api/v3", timeout: int = 20) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        response = self.session.get(f"{self.base_url}{path}", params=params, timeout=self.timeout)
        if not response.ok:
            raise ApiError(f"CoinGecko {response.status_code}: {response.text[:300]}")
        return response.json()

    def coins_markets(self, ids: str, currency: str = "usd") -> Any:
        return self._get(
            "/coins/markets",
            {
                "vs_currency": currency,
                "ids": ids,
                "price_change_percentage": "24h",
                "per_page": 50,
                "page": 1,
            },
        )


class GroqClient:
    def __init__(self, api_key: str = "", model: str = "llama-3.3-70b-versatile", timeout: int = 30) -> None:
        self.api_key = api_key.strip()
        self.model = model
        self.timeout = timeout
        self.session = requests.Session()

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def draft_execution(self, context: dict[str, Any]) -> dict[str, Any]:
        if not self.enabled:
            raise ApiError("Groq API key is missing")
        payload = {
            "model": self.model,
            "temperature": 0.2,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a trading execution copilot. "
                        "Return concise JSON with keys summary, side, mode, thesis, risk, and steps. "
                        "Do not wrap JSON in markdown."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(context, ensure_ascii=False),
                },
            ],
            "response_format": {"type": "json_object"},
        }
        response = self.session.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=self.timeout,
        )
        if not response.ok:
            raise ApiError(f"Groq {response.status_code}: {response.text[:300]}")
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        return json.loads(content)


class SoDexClient:
    def __init__(
        self,
        spot_base_url: str,
        perps_base_url: str,
        api_key_name: str = "",
        private_key: str = "",
        account_id: str = "",
        wallet_address: str = "",
        chain_id: int = 286623,
        timeout: int = 20,
    ) -> None:
        self.spot_base_url = spot_base_url.rstrip("/")
        self.perps_base_url = perps_base_url.rstrip("/")
        self.api_key_name = api_key_name.strip()
        self.private_key = private_key.strip()
        self.account_id = str(account_id).strip()
        self.wallet_address = wallet_address.strip()
        self.chain_id = chain_id
        self.timeout = timeout
        self.session = requests.Session()

    def _headers(self, signed: bool = False, signature: str | None = None, nonce: int | None = None) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if signed:
            headers["Content-Type"] = "application/json"
            if self.api_key_name:
                headers["X-API-Key"] = self.api_key_name
            if signature:
                headers["X-API-Sign"] = signature
            if nonce is not None:
                headers["X-API-Nonce"] = str(nonce)
        return headers

    def _get(self, base_url: str, path: str, params: dict[str, Any] | None = None) -> Any:
        response = self.session.get(f"{base_url}{path}", params=params, headers=self._headers(), timeout=self.timeout)
        if not response.ok:
            raise ApiError(f"SoDEX {response.status_code}: {response.text[:300]}")
        return response.json()

    def spot_tickers(self, symbol: str | None = None) -> Any:
        return self._get(self.spot_base_url, "/markets/tickers", {"symbol": symbol} if symbol else None)

    def spot_symbols(self, symbol: str | None = None) -> Any:
        return self._get(self.spot_base_url, "/markets/symbols", {"symbol": symbol} if symbol else None)

    def spot_book_tickers(self, symbol: str | None = None) -> Any:
        return self._get(self.spot_base_url, "/markets/bookTickers", {"symbol": symbol} if symbol else None)

    def spot_orderbook(self, symbol: str, limit: int = 20) -> Any:
        return self._get(self.spot_base_url, f"/markets/{symbol}/orderbook", {"limit": limit})

    def spot_klines(self, symbol: str, interval: str = "1h", limit: int = 120) -> Any:
        return self._get(self.spot_base_url, f"/markets/{symbol}/klines", {"interval": interval, "limit": limit})

    def spot_trades(self, symbol: str, limit: int = 50) -> Any:
        return self._get(self.spot_base_url, f"/markets/{symbol}/trades", {"limit": limit})

    def spot_state(self, user_address: str, account_id: str | None = None) -> Any:
        params = {"accountID": account_id or self.account_id} if (account_id or self.account_id) else None
        return self._get(self.spot_base_url, f"/accounts/{user_address}/state", params)

    def spot_balances(self, user_address: str, account_id: str | None = None) -> Any:
        params = {"accountID": account_id or self.account_id} if (account_id or self.account_id) else None
        return self._get(self.spot_base_url, f"/accounts/{user_address}/balances", params)

    def spot_orders(self, user_address: str, symbol: str | None = None, account_id: str | None = None) -> Any:
        params: dict[str, Any] = {}
        if symbol:
            params["symbol"] = symbol
        if account_id or self.account_id:
            params["accountID"] = account_id or self.account_id
        return self._get(self.spot_base_url, f"/accounts/{user_address}/orders", params or None)

    def spot_order_history(self, user_address: str, symbol: str | None = None, account_id: str | None = None) -> Any:
        params: dict[str, Any] = {}
        if symbol:
            params["symbol"] = symbol
        if account_id or self.account_id:
            params["accountID"] = account_id or self.account_id
        return self._get(self.spot_base_url, f"/accounts/{user_address}/orders/history", params or None)

    def spot_user_trades(self, user_address: str, symbol: str | None = None, account_id: str | None = None) -> Any:
        params: dict[str, Any] = {}
        if symbol:
            params["symbol"] = symbol
        if account_id or self.account_id:
            params["accountID"] = account_id or self.account_id
        return self._get(self.spot_base_url, f"/accounts/{user_address}/trades", params or None)

    def spot_fee_rate(self, user_address: str, symbol: str | None = None, account_id: str | None = None) -> Any:
        params: dict[str, Any] = {}
        if symbol:
            params["symbol"] = symbol
        if account_id or self.account_id:
            params["accountID"] = account_id or self.account_id
        return self._get(self.spot_base_url, f"/accounts/{user_address}/fee-rate", params or None)

    def spot_api_keys(self, user_address: str, account_id: str | None = None) -> Any:
        params = {"accountID": account_id or self.account_id} if (account_id or self.account_id) else None
        return self._get(self.spot_base_url, f"/accounts/{user_address}/api-keys", params)

    def perps_positions(self, user_address: str, account_id: str | None = None) -> Any:
        params = {"accountID": account_id or self.account_id} if (account_id or self.account_id) else None
        return self._get(self.perps_base_url, f"/accounts/{user_address}/positions", params)

    def perps_orderbook(self, symbol: str, limit: int = 20) -> Any:
        return self._get(self.perps_base_url, f"/markets/{symbol}/orderbook", {"limit": limit})

    def leaderboard(
        self,
        window_type: str = "30d",
        sort_by: str = "volume",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 50,
    ) -> Any:
        response = self.session.get(
            "https://mainnet-data.sodex.dev/api/v1/leaderboard",
            params={
                "window_type": window_type,
                "sort_by": sort_by,
                "sort_order": sort_order,
                "page": page,
                "page_size": page_size,
            },
            headers={"Accept": "application/json"},
            timeout=self.timeout,
        )
        if not response.ok:
            raise ApiError(f"SoDEX leaderboard {response.status_code}: {response.text[:300]}")
        payload = response.json()
        if isinstance(payload, dict) and payload.get("code") not in (None, 0):
            raise ApiError(f"SoDEX leaderboard {payload.get('code')}: {payload.get('error', 'unknown')}")
        return payload.get("data") if isinstance(payload, dict) and "data" in payload else payload

    def build_spot_limit_order(
        self,
        *,
        account_id: int | str,
        symbol_id: int | str,
        cl_ord_id: str,
        side: int,
        price: str,
        quantity: str,
        reduce_only: bool = False,
        position_side: int = 1,
        modifier: int = 1,
        time_in_force: int = 3,
    ) -> dict[str, Any]:
        order = OrderedDict(
            [
                ("clOrdID", cl_ord_id),
                ("modifier", modifier),
                ("side", side),
                ("type", 2),
                ("timeInForce", time_in_force),
                ("price", str(price)),
                ("quantity", str(quantity)),
                ("reduceOnly", reduce_only),
                ("positionSide", position_side),
            ]
        )
        return OrderedDict([("accountID", int(account_id)), ("symbolID", int(symbol_id)), ("orders", [order])])

    def build_spot_market_order(
        self,
        *,
        account_id: int | str,
        symbol_id: int | str,
        cl_ord_id: str,
        side: int,
        quantity: str | None = None,
        funds: str | None = None,
        reduce_only: bool = False,
        position_side: int = 1,
        modifier: int = 1,
    ) -> dict[str, Any]:
        order = OrderedDict(
            [
                ("clOrdID", cl_ord_id),
                ("modifier", modifier),
                ("side", side),
                ("type", 1),
                ("reduceOnly", reduce_only),
                ("positionSide", position_side),
            ]
        )
        if quantity:
            order["quantity"] = str(quantity)
        if funds:
            order["funds"] = str(funds)
        return OrderedDict([("accountID", int(account_id)), ("symbolID", int(symbol_id)), ("orders", [order])])

    def prepare_spot_batch(self, params: dict[str, Any], nonce: int | None = None) -> PreparedOrder:
        nonce = nonce or int(time.time() * 1000)
        digest = payload_hash("newOrder", params)
        signature = None
        if self.private_key:
            signature = sign_exchange_action(
                self.private_key,
                {
                    "name": "spot",
                    "version": "1",
                    "chainId": self.chain_id,
                    "verifyingContract": "0x0000000000000000000000000000000000000000",
                },
                digest,
                nonce,
            )
        return PreparedOrder(
            venue="spot",
            path="/trade/orders/batch",
            action_type="newOrder",
            params=params,
            payload_hash=digest,
            nonce=nonce,
            signature=signature,
            domain_name="spot",
            chain_id=self.chain_id,
        )

    def submit_prepared(self, prepared: PreparedOrder) -> Any:
        body = _compact_json(prepared.params)
        response = self.session.post(
            f"{self.spot_base_url}{prepared.path}",
            data=body,
            headers=self._headers(signed=True, signature=prepared.signature, nonce=prepared.nonce),
            timeout=self.timeout,
        )
        if not response.ok:
            raise ApiError(f"SoDEX {response.status_code}: {response.text[:500]}")
        return response.json()
