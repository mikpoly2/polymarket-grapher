from __future__ import annotations
import time
import requests
from typing import List, Tuple

class CryptoError(Exception):
    pass

COINGECKO_BASE = "https://api.coingecko.com/api/v3"

SYMBOL_TO_COINGECKO_ID = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
}

def fetch_crypto_price_range(symbol: str, start_ts: int, end_ts: int) -> List[Tuple[int, float]]:
    symbol = symbol.upper()
    if symbol not in SYMBOL_TO_COINGECKO_ID:
        raise CryptoError("Unsupported crypto symbol")

    if end_ts <= start_ts:
        raise CryptoError(f"Bad time range: start={start_ts}, end={end_ts}")

    coin_id = SYMBOL_TO_COINGECKO_ID[symbol]
    url = f"{COINGECKO_BASE}/coins/{coin_id}/market_chart/range"
    params = {"vs_currency": "usd", "from": int(start_ts), "to": int(end_ts)}

    headers = {
        "User-Agent": "polymarket-grapher/1.0 (local streamlit app)"
    }

    # простая retry логика для 429/временных сбоев
    last_err = None
    for attempt in range(4):
        r = requests.get(url, params=params, headers=headers, timeout=30)
        if r.status_code == 200:
            data = r.json()
            prices = data.get("prices") or []  # [[ms, price], ...]
            out = [(int(ms // 1000), float(px)) for ms, px in prices if ms is not None and px is not None]
            if not out:
                raise CryptoError("CoinGecko returned empty prices[] for this range.")
            return out

        if r.status_code in (429, 500, 502, 503, 504):
            last_err = f"CoinGecko HTTP {r.status_code}: {r.text[:200]}"
            time.sleep(0.8 * (attempt + 1))
            continue

        raise CryptoError(f"CoinGecko HTTP {r.status_code}: {r.text[:200]}")

    raise CryptoError(last_err or "CoinGecko request failed")