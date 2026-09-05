from __future__ import annotations

import asyncio
from collections import Counter, defaultdict
from datetime import UTC, datetime
from typing import Any

import httpx

from .models import SecuritySignals, SocialSignals, TokenCandidate, WalletSignals

CHAIN_IDS = {
    "ethereum": "1",
    "bsc": "56",
    "polygon": "137",
    "arbitrum": "42161",
    "base": "8453",
    "avalanche": "43114",
    "robinhood": "4663",
}


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0


def _flag(value: Any) -> bool:
    return str(value).lower() in {"1", "true", "yes"}


class DexScreenerClient:
    BASE = "https://api.dexscreener.com"

    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def discover(self) -> list[TokenCandidate]:
        endpoints = ["/token-boosts/latest/v1", "/token-profiles/latest/v1"]
        responses = await asyncio.gather(
            *(self.client.get(self.BASE + path) for path in endpoints), return_exceptions=True
        )
        seeds: dict[tuple[str, str], dict[str, Any]] = {}
        for response in responses:
            if isinstance(response, Exception) or response.status_code >= 400:
                continue
            for item in response.json() if isinstance(response.json(), list) else []:
                chain, address = item.get("chainId"), item.get("tokenAddress")
                if chain and address:
                    seeds[(chain, address)] = item

        details = await asyncio.gather(
            *(self.client.get(f"{self.BASE}/latest/dex/tokens/{address}") for _, address in seeds),
            return_exceptions=True,
        )
        candidates: dict[tuple[str, str], TokenCandidate] = {}
        for response in details:
            if isinstance(response, Exception) or response.status_code >= 400:
                continue
            for pair in response.json().get("pairs") or []:
                base = pair.get("baseToken") or {}
                address = base.get("address")
                chain = pair.get("chainId")
                if not address or not chain:
                    continue
                key = (chain, address.lower())
                existing = candidates.get(key)
                liquidity = _number((pair.get("liquidity") or {}).get("usd"))
                if existing and existing.liquidity_usd >= liquidity:
                    continue
                info = pair.get("info") or {}
                websites = [w.get("url") for w in info.get("websites") or [] if w.get("url")]
                socials = [s.get("url") for s in info.get("socials") or [] if s.get("url")]
                created_ms = pair.get("pairCreatedAt")
                candidates[key] = TokenCandidate(
                    chain=chain,
                    chain_id=CHAIN_IDS.get(chain),
                    token_address=address,
                    pair_address=pair.get("pairAddress"),
                    symbol=base.get("symbol") or "?",
                    name=base.get("name") or "Unknown",
                    dex_url=pair.get("url"),
                    created_at=(
                        datetime.fromtimestamp(created_ms / 1000, tz=UTC)
                        if created_ms else None
                    ),
                    price_usd=_number(pair.get("priceUsd")),
                    liquidity_usd=liquidity,
                    market_cap_usd=_number(pair.get("marketCap") or pair.get("fdv")),
                    volume_5m=_number((pair.get("volume") or {}).get("m5")),
                    volume_1h=_number((pair.get("volume") or {}).get("h1")),
                    buys_5m=int(_number(((pair.get("txns") or {}).get("m5") or {}).get("buys"))),
                    sells_5m=int(_number(((pair.get("txns") or {}).get("m5") or {}).get("sells"))),
                    price_change_5m=_number((pair.get("priceChange") or {}).get("m5")),
                    socials=websites + socials,
                )
        return list(candidates.values())


class GoPlusClient:
    BASE = "https://api.gopluslabs.io/api/v1/token_security"

    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def token_security(self, token: TokenCandidate) -> SecuritySignals:
        if not token.chain_id:
            return SecuritySignals(warnings=["Security API does not support this chain mapping"])
        response = await self.client.get(
            f"{self.BASE}/{token.chain_id}", params={"contract_addresses": token.token_address}
        )
        if response.status_code >= 400:
            return SecuritySignals(warnings=[f"GoPlus returned HTTP {response.status_code}"])
        raw = (response.json().get("result") or {}).get(token.token_address.lower()) or {}
        holders = raw.get("holders") or []
        top10 = sum(_number(item.get("percent")) for item in holders[:10]) * 100
        lp_holders = raw.get("lp_holders") or []
        locked = sum(
            _number(item.get("percent")) for item in lp_holders if _flag(item.get("is_locked"))
        ) * 100
        warnings: list[str] = []
        for field, label in {
            "is_honeypot": "Honeypot signal",
            "cannot_sell_all": "Cannot sell all tokens",
            "hidden_owner": "Hidden owner",
            "is_mintable": "Supply can be minted",
            "owner_change_balance": "Owner can change balances",
        }.items():
            if _flag(raw.get(field)):
                warnings.append(label)
        return SecuritySignals(
            honeypot=_flag(raw.get("is_honeypot")),
            cannot_sell_all=_flag(raw.get("cannot_sell_all")),
            hidden_owner=_flag(raw.get("hidden_owner")),
            mintable=_flag(raw.get("is_mintable")),
            proxy=_flag(raw.get("is_proxy")),
            owner_can_change_balance=_flag(raw.get("owner_change_balance")),
            buy_tax=_number(raw.get("buy_tax")) * 100,
            sell_tax=_number(raw.get("sell_tax")) * 100,
            holder_count=int(_number(raw.get("holder_count"))),
            top10_percent=top10,
            lp_locked_percent=locked,
            deployer=raw.get("creator_address") or raw.get("owner_address"),
            warnings=warnings,
        )


class XClient:
    BASE = "https://api.x.com/2/tweets/search/recent"

    def __init__(self, client: httpx.AsyncClient, bearer_token: str | None):
        self.client = client
        self.bearer_token = bearer_token

    async def search(self, token: TokenCandidate) -> SocialSignals:
        if not self.bearer_token:
            return SocialSignals(query="X_BEARER_TOKEN not configured")
        query = f'("${token.symbol}" OR "{token.token_address}") -is:retweet lang:en'
        response = await self.client.get(
            self.BASE,
            headers={"Authorization": f"Bearer {self.bearer_token}"},
            params={
                "query": query,
                "max_results": 100,
                "tweet.fields": "author_id,public_metrics,created_at",
            },
        )
        if response.status_code >= 400:
            return SocialSignals(query=f"X API HTTP {response.status_code}")
        posts = response.json().get("data") or []
        authors = Counter(post.get("author_id") for post in posts if post.get("author_id"))
        metrics = [post.get("public_metrics") or {} for post in posts]
        repeated = sum(count - 1 for count in authors.values() if count > 1)
        return SocialSignals(
            post_count=len(posts),
            unique_authors=len(authors),
            total_likes=sum(int(m.get("like_count", 0)) for m in metrics),
            total_reposts=sum(int(m.get("retweet_count", 0)) for m in metrics),
            spam_ratio=(repeated / len(posts) if posts else 0),
            query=query,
        )


class EtherscanWalletClient:
    BASE = "https://api.etherscan.io/v2/api"

    def __init__(self, client: httpx.AsyncClient, api_key: str | None, early_limit: int = 20):
        self.client = client
        self.api_key = api_key
        self.early_limit = early_limit

    async def _call(self, chain_id: str, **params: Any) -> list[dict[str, Any]] | dict[str, Any]:
        if not self.api_key:
            return []
        response = await self.client.get(
            self.BASE, params={"chainid": chain_id, "apikey": self.api_key, **params}
        )
        if response.status_code >= 400:
            return []
        data = response.json()
        return data.get("result") if data.get("status") == "1" else []

    async def analyze(self, token: TokenCandidate, deployer: str | None) -> WalletSignals:
        if not self.api_key or not token.chain_id:
            return WalletSignals(notes=["Set ETHERSCAN_API_KEY to enable early-wallet analysis"])
        transfers = await self._call(
            token.chain_id,
            module="account",
            action="tokentx",
            contractaddress=token.token_address,
            startblock=0,
            endblock=99_999_999,
            page=1,
            offset=200,
            sort="asc",
        )
        if not isinstance(transfers, list):
            return WalletSignals(notes=["No transfer history returned"])
        ignored = {
            "0x0000000000000000000000000000000000000000",
            (deployer or "").lower(),
            (token.pair_address or "").lower(),
        }
        recipients: list[str] = []
        amounts: dict[str, float] = defaultdict(float)
        total_supply_hint = 0.0
        for transfer in transfers:
            wallet = str(transfer.get("to", "")).lower()
            if not wallet or wallet in ignored:
                continue
            decimals = int(transfer.get("tokenDecimal") or 0)
            amount = _number(transfer.get("value")) / (10**decimals if decimals else 1)
            amounts[wallet] += amount
            total_supply_hint = max(total_supply_hint, amounts[wallet])
            if wallet not in recipients:
                recipients.append(wallet)
            if len(recipients) >= self.early_limit:
                break
        funders = await asyncio.gather(
            *(
                self._call(
                    token.chain_id, module="account", action="fundedby", address=wallet
                )
                for wallet in recipients
            )
        )
        by_funder: dict[str, list[str]] = defaultdict(list)
        fresh = 0
        for wallet, result in zip(recipients, funders, strict=False):
            if isinstance(result, dict):
                funder = str(result.get("funded_by") or result.get("from") or "").lower()
                if funder:
                    by_funder[funder].append(wallet)
            txs = await self._call(
                token.chain_id, module="account", action="txlist", address=wallet,
                startblock=0, endblock=99_999_999, page=1, offset=6, sort="asc"
            )
            if isinstance(txs, list) and len(txs) <= 5:
                fresh += 1
        clusters = [wallets for wallets in by_funder.values() if len(wallets) >= 2]
        deployer_lower = (deployer or "").lower()
        deployer_linked = len(by_funder.get(deployer_lower, [])) if deployer_lower else 0
        suspicious = sorted({wallet for cluster in clusters for wallet in cluster})
        return WalletSignals(
            early_wallets=recipients,
            fresh_wallet_count=fresh,
            shared_funder_clusters=len(clusters),
            largest_cluster_size=max((len(cluster) for cluster in clusters), default=0),
            deployer_linked_wallets=deployer_linked,
            suspicious_wallets=suspicious,
            notes=["Wallet links are behavioral risk signals, not proof of insider trading."],
        )
