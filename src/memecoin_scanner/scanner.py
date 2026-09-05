from __future__ import annotations

import asyncio
import json
import logging

import httpx

from .config import Settings
from .models import ScanResult, TokenCandidate
from .providers import DexScreenerClient, EtherscanWalletClient, GoPlusClient, XClient
from .scoring import score_candidate
from .storage import Store

log = logging.getLogger(__name__)


class Scanner:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.store = Store(settings.database_path)

    def eligible(self, candidate: TokenCandidate) -> bool:
        age = candidate.age_minutes
        return (
            candidate.chain in self.settings.chains
            and candidate.liquidity_usd >= self.settings.min_liquidity_usd
            and 0 < candidate.market_cap_usd <= self.settings.max_market_cap_usd
            and (age is None or age <= self.settings.max_pair_age_minutes)
        )

    async def analyze_one(
        self,
        candidate: TokenCandidate,
        security_client: GoPlusClient,
        wallet_client: EtherscanWalletClient,
        x_client: XClient,
    ) -> ScanResult:
        security = await security_client.token_security(candidate)
        wallets, social = await asyncio.gather(
            wallet_client.analyze(candidate, security.deployer),
            x_client.search(candidate),
        )
        return score_candidate(candidate, security, wallets, social)

    async def scan_once(self) -> list[ScanResult]:
        async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
            dex = DexScreenerClient(client)
            security = GoPlusClient(client)
            wallets = EtherscanWalletClient(
                client, self.settings.etherscan_api_key, self.settings.early_wallet_limit
            )
            x_client = XClient(client, self.settings.x_bearer_token)
            candidates = [candidate for candidate in await dex.discover() if self.eligible(candidate)]
            results = await asyncio.gather(
                *(self.analyze_one(c, security, wallets, x_client) for c in candidates)
            )
            for result in results:
                self.store.save(result)
                if self.store.should_alert(result, self.settings.min_total_score):
                    await self.send_alert(client, result)
                    self.store.mark_alerted(result)
            return sorted(results, key=lambda item: item.total_score, reverse=True)

    async def send_alert(self, client: httpx.AsyncClient, result: ScanResult) -> None:
        c = result.candidate
        message = (
            f"{result.verdict}: {c.symbol} on {c.chain}\n"
            f"Score {result.total_score}/100 | Insider risk {result.insider_risk_score}/100\n"
            f"MC ${c.market_cap_usd:,.0f} | Liquidity ${c.liquidity_usd:,.0f}\n"
            f"Contract: {c.token_address}\n{c.dex_url or ''}\n"
            + "Reasons: " + "; ".join(result.reasons[:5])
        )
        if not self.settings.alert_webhook_url:
            log.info("ALERT\n%s", message)
            return
        response = await client.post(self.settings.alert_webhook_url, json={"content": message})
        response.raise_for_status()

    @staticmethod
    def display(results: list[ScanResult]) -> None:
        for result in results[:20]:
            c = result.candidate
            print(json.dumps({
                "symbol": c.symbol,
                "chain": c.chain,
                "market_cap": round(c.market_cap_usd),
                "liquidity": round(c.liquidity_usd),
                "score": result.total_score,
                "insider_risk": result.insider_risk_score,
                "verdict": result.verdict,
                "contract": c.token_address,
                "url": c.dex_url,
                "reasons": result.reasons,
            }))

    async def run_forever(self) -> None:
        while True:
            try:
                self.display(await self.scan_once())
            except Exception:
                log.exception("Scan failed")
            await asyncio.sleep(self.settings.poll_seconds)
