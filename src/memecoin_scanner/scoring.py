from __future__ import annotations

from .models import ScanResult, SecuritySignals, SocialSignals, TokenCandidate, WalletSignals


def clamp(value: float, low: float = 0, high: float = 100) -> float:
    return round(max(low, min(high, value)), 1)


def score_candidate(
    candidate: TokenCandidate,
    security: SecuritySignals,
    wallets: WalletSignals,
    social: SocialSignals,
) -> ScanResult:
    reasons: list[str] = []
    opportunity = 0.0
    if candidate.liquidity_usd >= 100_000:
        opportunity += 22
        reasons.append("Liquidity is at least $100k")
    elif candidate.liquidity_usd >= 25_000:
        opportunity += 14
    if candidate.volume_5m >= 25_000:
        opportunity += 18
        reasons.append("Strong five-minute volume")
    elif candidate.volume_5m >= 5_000:
        opportunity += 10
    trade_count = candidate.buys_5m + candidate.sells_5m
    buy_ratio = candidate.buys_5m / trade_count if trade_count else 0
    if trade_count >= 20 and buy_ratio >= 0.6:
        opportunity += 15
        reasons.append("Buy activity is broad and dominant")
    if 0 < candidate.market_cap_usd <= 1_000_000:
        opportunity += 12
        reasons.append("Early market-cap range")
    elif candidate.market_cap_usd <= 5_000_000:
        opportunity += 7
    if social.unique_authors >= 20 and social.spam_ratio < 0.35:
        opportunity += 18
        reasons.append("Social mentions come from diverse authors")
    elif social.unique_authors >= 5:
        opportunity += 8
    if social.total_likes + social.total_reposts >= 250:
        opportunity += 10
    if len(candidate.socials) >= 2:
        opportunity += 5

    risk = 0.0
    hard_block = security.honeypot or security.cannot_sell_all
    if hard_block:
        risk += 100
        reasons.append("Critical sell restriction or honeypot signal")
    if security.hidden_owner or security.owner_can_change_balance:
        risk += 25
    if security.mintable:
        risk += 15
    if security.sell_tax >= 10:
        risk += 20
    if security.top10_percent >= 50:
        risk += 20
        reasons.append("Top holders control at least 50%")
    if security.lp_locked_percent < 50:
        risk += 12
    if wallets.fresh_wallet_count >= 5:
        risk += 15
        reasons.append("Many earliest recipients are fresh wallets")
    if wallets.shared_funder_clusters:
        risk += min(30, wallets.shared_funder_clusters * 10)
        reasons.append("Early wallets share funding sources")
    if wallets.deployer_linked_wallets:
        risk += min(35, wallets.deployer_linked_wallets * 12)
        reasons.append("Early wallets are funded by the deployer")
    if wallets.largest_cluster_size >= 5:
        risk += 15
    if social.spam_ratio >= 0.5:
        risk += 12

    opportunity = clamp(opportunity)
    risk = clamp(risk)
    total = 0.0 if hard_block else clamp(opportunity - risk * 0.65)
    verdict = "AVOID" if hard_block or risk >= 65 else "HIGH RISK" if risk >= 40 else "WATCH"
    if total >= 70 and risk < 25:
        verdict = "STRONG WATCH"
    return ScanResult(
        candidate=candidate,
        security=security,
        wallets=wallets,
        social=social,
        opportunity_score=opportunity,
        insider_risk_score=risk,
        total_score=total,
        verdict=verdict,
        reasons=reasons,
    )
