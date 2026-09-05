from __future__ import annotations

import sqlite3
from pathlib import Path

from .models import ScanResult


class Store:
    def __init__(self, path: str):
        self.path = Path(path)
        with self._connect() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS scans (
                    chain TEXT NOT NULL, token_address TEXT NOT NULL, scanned_at TEXT NOT NULL,
                    symbol TEXT, price_usd REAL, market_cap_usd REAL, total_score REAL,
                    insider_risk_score REAL, verdict TEXT, payload_json TEXT NOT NULL,
                    PRIMARY KEY (chain, token_address, scanned_at)
                )"""
            )
            db.execute(
                """CREATE TABLE IF NOT EXISTS alerts (
                    chain TEXT NOT NULL, token_address TEXT NOT NULL, last_score REAL,
                    alerted_at TEXT NOT NULL, PRIMARY KEY (chain, token_address)
                )"""
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def save(self, result: ScanResult) -> None:
        c = result.candidate
        with self._connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO scans VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    c.chain, c.token_address.lower(), result.scanned_at.isoformat(), c.symbol,
                    c.price_usd, c.market_cap_usd, result.total_score,
                    result.insider_risk_score, result.verdict, result.model_dump_json(),
                ),
            )

    def should_alert(self, result: ScanResult, threshold: float) -> bool:
        if result.total_score < threshold or result.verdict in {"AVOID", "HIGH RISK"}:
            return False
        c = result.candidate
        with self._connect() as db:
            row = db.execute(
                "SELECT last_score FROM alerts WHERE chain=? AND token_address=?",
                (c.chain, c.token_address.lower()),
            ).fetchone()
        return row is None or result.total_score >= float(row[0]) + 10

    def mark_alerted(self, result: ScanResult) -> None:
        c = result.candidate
        with self._connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO alerts VALUES (?, ?, ?, ?)",
                (c.chain, c.token_address.lower(), result.total_score, result.scanned_at.isoformat()),
            )
