from memecoin_scanner.models import SecuritySignals, SocialSignals, TokenCandidate, WalletSignals
from memecoin_scanner.scoring import score_candidate


def candidate() -> TokenCandidate:
    return TokenCandidate(
        chain="base",
        token_address="0xabc",
        symbol="MOON",
        liquidity_usd=150_000,
        market_cap_usd=800_000,
        volume_5m=30_000,
        buys_5m=80,
        sells_5m=20,
        socials=["https://x.com/moon", "https://moon.example"],
    )


def test_clean_momentum_candidate_scores_high() -> None:
    result = score_candidate(
        candidate(), SecuritySignals(lp_locked_percent=100, top10_percent=20),
        WalletSignals(), SocialSignals(unique_authors=25, total_likes=300, spam_ratio=0.1),
    )
    assert result.total_score >= 70
    assert result.verdict == "STRONG WATCH"


def test_honeypot_is_always_blocked() -> None:
    result = score_candidate(
        candidate(), SecuritySignals(honeypot=True), WalletSignals(), SocialSignals()
    )
    assert result.total_score == 0
    assert result.verdict == "AVOID"


def test_shared_funders_raise_insider_risk() -> None:
    clean = score_candidate(candidate(), SecuritySignals(lp_locked_percent=100), WalletSignals(), SocialSignals())
    clustered = score_candidate(
        candidate(), SecuritySignals(lp_locked_percent=100),
        WalletSignals(shared_funder_clusters=2, largest_cluster_size=6, fresh_wallet_count=8),
        SocialSignals(),
    )
    assert clustered.insider_risk_score > clean.insider_risk_score
    assert clustered.total_score < clean.total_score
