from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv


@dataclass(frozen=True)
class AppConfig:
    sosovalue_api_key: str
    sosovalue_base_url: str
    sodex_api_key_name: str
    sodex_private_key: str
    sodex_public_key: str
    sodex_account_id: str
    sodex_wallet_address: str
    sodex_spot_base_url: str
    sodex_perps_base_url: str
    groq_api_key: str
    groq_model: str
    db_path: str

    @property
    def has_sosovalue(self) -> bool:
        return bool(self.sosovalue_api_key.strip())

    @property
    def has_sodex_signing(self) -> bool:
        return bool(self.sodex_private_key.strip() and self.sodex_api_key_name.strip())

    @property
    def has_groq(self) -> bool:
        return bool(self.groq_api_key.strip())


def load_config() -> AppConfig:
    load_dotenv()
    return AppConfig(
        sosovalue_api_key=os.getenv("SOSOVALUE_API_KEY", "").strip(),
        sosovalue_base_url=os.getenv("SOSOVALUE_BASE_URL", "https://openapi.sosovalue.com/openapi/v1").rstrip("/"),
        sodex_api_key_name=os.getenv("SODEX_API_KEY_NAME", "").strip(),
        sodex_private_key=os.getenv("SODEX_PRIVATE_KEY", os.getenv("SODEX_API_PRIVATE_KEY", "")).strip(),
        sodex_public_key=os.getenv("SODEX_PUBLIC_KEY", "").strip(),
        sodex_account_id=os.getenv("SODEX_ACCOUNT_ID", "").strip(),
        sodex_wallet_address=os.getenv("SODEX_WALLET_ADDRESS", os.getenv("SODEX_PUBLIC_KEY", "")).strip(),
        sodex_spot_base_url=os.getenv("SODEX_SPOT_BASE_URL", "https://mainnet-gw.sodex.dev/api/v1/spot").rstrip("/"),
        sodex_perps_base_url=os.getenv("SODEX_PERPS_BASE_URL", "https://mainnet-gw.sodex.dev/api/v1/perps").rstrip("/"),
        groq_api_key=os.getenv("GROQ_API_KEY", "").strip(),
        groq_model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip(),
        db_path=os.getenv("GOKU_DB_PATH", "./data/goku_alpha_builder.db").strip(),
    )


def ensure_parent_dir(path: str) -> None:
    Path(path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)

