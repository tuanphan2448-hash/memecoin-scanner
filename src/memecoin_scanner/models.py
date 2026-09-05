from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class TokenCandidate(BaseModel):
    chain: str
    chain_id: str | None = None
    token_address: str
    pair_address: str | None = None
    symbol: str = "?"
    name: str = "Unknown"
    dex_url: str | None = None
    created_at: datetime | None = None
    price_usd: float = 0
    liquidity_usd: float = 0
    market_cap_usd: float = 0
    volume_5m: float = 0
    volume_1h: float = 0
    buys_5m: int = 0
    sells_5m: int = 0
    price_change_5m: float = 0
    socials: list[str] = Field(default_factory=list)

    @property
    def age_minutes(self) -> float | None:
        if not self.created_at:
            return None
        return max(0, (datetime.now(UTC) - self.created_at).total_seconds() / 60)


class SecuritySignals(BaseModel):
    honeypot: bool = False
    cannot_sell_all: bool = False
    hidden_owner: bool = False
    mintable: bool = False
    proxy: bool = False
    owner_can_change_balance: bool = False
    buy_tax: float = 0
    sell_tax: float = 0
    holder_count: int = 0
    top10_percent: float = 0
    lp_locked_percent: float = 0
    deployer: str | None = None
    warnings: list[str] = Field(default_factory=list)


class WalletSignals(BaseModel):
    early_wallets: list[str] = Field(default_factory=list)
    fresh_wallet_count: int = 0
    shared_funder_clusters: int = 0
    largest_cluster_size: int = 0
    deployer_linked_wallets: int = 0
    early_supply_percent: float = 0
    suspicious_wallets: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class SocialSignals(BaseModel):
    post_count: int = 0
    unique_authors: int = 0
    total_likes: int = 0
    total_reposts: int = 0
    spam_ratio: float = 0
    query: str | None = None


class ScanResult(BaseModel):
    candidate: TokenCandidate
    security: SecuritySignals = Field(default_factory=SecuritySignals)
    wallets: WalletSignals = Field(default_factory=WalletSignals)
    social: SocialSignals = Field(default_factory=SocialSignals)
    opportunity_score: float = 0
    insider_risk_score: float = 0
    total_score: float = 0
    verdict: str = "WATCH"
    reasons: list[str] = Field(default_factory=list)
    scanned_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

