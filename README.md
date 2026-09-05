# Memecoin Scanner

An explainable, alert-only research bot for finding newly promoted memecoins and filtering
obvious hazards. It combines market activity, public X posts, contract-security signals, and
public on-chain wallet behavior. It does **not** promise a 1000x return or prove that any wallet
belongs to an insider.

## What it detects

- Fresh and recently promoted pairs from DexScreener
- Liquidity, market cap, short-term volume, buy/sell activity, and pair age
- Honeypots, sell restrictions, mutable balances, minting, taxes, holder concentration, LP locks
- Earliest token recipients and unusually fresh wallets
- Multiple early wallets funded by the same address
- Early wallets funded by the deployer/creator
- Recent X mention volume, unique authors, engagement, and repeated-author spam
- Separate `opportunity_score`, `insider_risk_score`, reasons, and verdict

Wallet clustering is a warning signal—not proof of insider trading. Only public blockchain data
is used. The scanner never buys or sells tokens.

## Supported chains

The default configuration includes Ethereum, Base, BNB Chain, Arbitrum, and Robinhood Chain.
DexScreener discovery depends on the chain being indexed there. Etherscan V2 wallet analysis
depends on that chain and endpoint being available for your API plan. GoPlus security analysis
uses the numeric chain ID and currently includes Robinhood Chain ID `4663`.

## Quick start

```bash
git clone https://github.com/tuanphan2448-hash/memecoin-scanner.git
cd memecoin-scanner
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
memecoin-scanner scan
```

Run continuously:

```bash
memecoin-scanner scan --no-once
```

## API keys

The bot runs in a limited discovery/security mode without keys. Add these to `.env` for the
full signal set:

- `ETHERSCAN_API_KEY`: enables early-wallet transfer history, first-funder links, and fresh-wallet
  checks through Etherscan API V2.
- `X_BEARER_TOKEN`: enables recent-post search through X API v2. Access and rate limits depend on
  your X developer plan.
- `ALERT_WEBHOOK_URL`: optional Discord-compatible webhook. Without it, alerts print to the console.

Never commit `.env` or API keys. `.gitignore` excludes them.

## Scoring

The score is deterministic and explainable:

- Opportunity points: liquidity, five-minute volume, buy breadth, early market-cap range, diverse
  X authors, engagement, and project links.
- Risk points: honeypot/sell restrictions, dangerous owner controls, minting, high sell tax,
  concentration, weak LP locking, fresh-wallet bursts, shared funders, deployer funding, and spam.
- `total_score = opportunity_score - 0.65 × insider_risk_score`, clamped to 0–100.
- A honeypot or sell restriction forces `AVOID` and a score of zero.

The initial weights are hypotheses, not a validated trading edge. Paper-test them and track false
positives before risking money.

## Configuration

| Variable | Default | Meaning |
|---|---:|---|
| `CHAINS` | `ethereum,base,bsc,arbitrum,robinhood` | DexScreener chain slugs |
| `MIN_LIQUIDITY_USD` | `25000` | Reject thinner pools |
| `MAX_MARKET_CAP_USD` | `5000000` | Focus on earlier tokens |
| `MAX_PAIR_AGE_MINUTES` | `1440` | Maximum pair age |
| `MIN_TOTAL_SCORE` | `55` | Minimum score for an alert |
| `POLL_SECONDS` | `60` | Continuous-mode delay |
| `DATABASE_PATH` | `scanner.db` | SQLite history and alert deduplication |

## Known limitations

- A shared funding source can be an exchange or bridge and may create a false positive.
- Earliest ERC-20 recipients are an approximation of early participants, not guaranteed buyers.
- Token symbols are ambiguous on X; contract-address mentions are stronger evidence.
- DexScreener boosts can be paid promotion. Promotion is a discovery seed, never an endorsement.
- Solana requires a separate transaction/indexer implementation and is not analyzed by the current
  EVM wallet module.
- Rate limits can reduce coverage; production use should add caching and a paid indexer/webhook.

## Development

```bash
ruff check src tests
pytest -q
```

## Safety

Memecoins can go to zero and many are manipulated. Treat every alert as a lead for manual research,
not financial advice. Verify the contract, liquidity, taxes, ownership, and your ability to sell with
a tiny test transaction before considering any position.
