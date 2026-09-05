from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    etherscan_api_key: str | None = None
    x_bearer_token: str | None = None
    alert_webhook_url: str | None = None
    chains: list[str] = Field(
        default_factory=lambda: ["ethereum", "base", "bsc", "arbitrum", "robinhood"]
    )
    min_liquidity_usd: float = 25_000
    max_market_cap_usd: float = 5_000_000
    max_pair_age_minutes: int = 1_440
    min_total_score: float = 55
    poll_seconds: int = 60
    database_path: str = "scanner.db"
    request_timeout_seconds: float = 20
    early_wallet_limit: int = 20

    @field_validator("chains", mode="before")
    @classmethod
    def split_chains(cls, value: object) -> object:
        if isinstance(value, str):
            return [part.strip().lower() for part in value.split(",") if part.strip()]
        return value

