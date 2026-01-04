from __future__ import annotations
import time
import requests
from typing import List, Tuple, Dict

class CryptoError(Exception):
    pass

KRAKEN_BASE = "https://api.kraken.com/0/public"

# Kraken uses XBT instead of BTC
PAIR_MAP: Dict[str, str] = {
    "BTC": "XBTUSD",
    "ETH": "ETHUSD",
    "SOL": "SOLUSD",
}

def fetch_crypto_price_range(symbol: str, start_ts: int, end_ts: int) -> List[Tuple[int, float]]:
    """
    Returns (timestamp_seconds, close_price_usd) using Kraken OHLC.
    interval = 60 minutes (1h) for performance + stability.
    """
    symbol = symbol.upper()
    if symbol not in PAIR_MAP:
        raise CryptoError(f"Unsupported symbol: {symbol}")

    if end_ts <= start_ts:
        raise CryptoError(f"Bad time range: start={start_ts}, end={end_ts}")

    pair = PAIR_MAP[symbol]
    interval = 60  # minutes
    out: List[Tuple[int, float]] = []

    since = int(start_ts)
    max_iters = 40  # safety (40 * 720h ~ plenty for most ranges)

    for _ in range(max_iters):
        params = {"pair": pair, "interval": interval, "since": since}
        r = requests.get(f"{KRAKEN_BASE}/OHLC", params=params, timeout=25)

        if r.status_code == 429:
            # simple backoff
            time.sleep(1.0)
            continue

        if r.status_code != 200:
            raise CryptoError(f"Kraken HTTP {r.status_code}: {r.text[:200]}")

        data = r.json()
        if data.get("error"):
            raise CryptoError(f"Kraken error: {data['error']}")

        result = data.get("result") or {}
        last = result.get("last")

        # Pair key is not always exactly the same string; find the first list value
        ohlc = None
        for k, v in result.items():
            if k == "last":
                continue
            if isinstance(v, list):
                ohlc = v
                break

        if not ohlc:
            break

        # Each entry: [time, open, high, low, close, vwap, volume, count]
        for row in ohlc:
            t = int(row[0])
            if t < start_ts:
                continue
            if t > end_ts:
                break
            close_px = float(row[4])
            out.append((t, close_px))

        if not last:
            break

        # Stop if we've moved past end_ts or no progress
        if int(last) <= since:
            break
        since = int(last)
        if since > end_ts:
            break

        # Be gentle
        time.sleep(0.05)

    # Deduplicate + sort (sometimes overlaps)
    if not out:
        raise CryptoError("Kraken returned empty data for this range")
    out = sorted(set(out), key=lambda x: x[0])
    return out
