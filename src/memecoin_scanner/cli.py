from __future__ import annotations

import asyncio
import logging

import typer

from .config import Settings
from .scanner import Scanner

app = typer.Typer(help="Scan emerging memecoins and explain wallet/security risk.")


@app.callback()
def main() -> None:
    """Memecoin discovery and public wallet-risk scanner."""


@app.command()
def scan(once: bool = typer.Option(True, help="Run once; use --no-once for continuous mode.")) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    scanner = Scanner(Settings())
    if once:
        asyncio.run(_once(scanner))
    else:
        asyncio.run(scanner.run_forever())


async def _once(scanner: Scanner) -> None:
    scanner.display(await scanner.scan_once())


if __name__ == "__main__":
    app()
