from __future__ import annotations
import requests
from typing import List, Tuple

class CryptoError(Exception):
    pass

BINANCE_BASE = "https://api.binance.com/api/v3"

SYMBOL_MAP = {
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
    "SOL": "SOLUSDT",
}

def fetch_crypto_price_range(symbol: str, start_ts: int, end_ts: int) -> List[Tuple[int, float]]:
    symbol = symbol.upper()
    if symbol not in SYMBOL_MAP:
        raise CryptoError(f"Unsupported symbol: {symbol}")

    pair = SYMBOL_MAP[symbol]

    # Binance ограничивает количество свечей за запрос
    limit = 1000
    interval = "1h"  # 1 час — оптимально

    out: List[Tuple[int, float]] = []
    start_ms = start_ts * 1000
    end_ms = end_ts * 1000

    while start_ms < end_ms:
        params = {
            "symbol": pair,
            "interval": interval,
            "startTime": start_ms,
            "endTime": end_ms,
            "limit": limit,
        }

        r = requests.get(BINANCE_BASE + "/klines", params=params, timeout=20)
        if r.status_code != 200:
            raise CryptoError(f"Binance HTTP {r.status_code}: {r.text[:200]}")

        data = r.json()
        if not data:
            break

        for k in data:
            # k[0] = open time (ms), k[4] = close price
            out.append((int(k[0] // 1000), float(k[4])))

        # двигаемся дальше
        start_ms = data[-1][0] + 1

    if not out:
        raise CryptoError("Binance returned empty data")

    return out
