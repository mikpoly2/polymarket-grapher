from __future__ import annotations
import re
import requests
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse

GAMMA_BASE = "https://gamma-api.polymarket.com"
CLOB_BASE = "https://clob.polymarket.com"

class PolymarketError(Exception):
    pass

def extract_slug(url: str) -> str:
    """
    Supports:
      https://polymarket.com/event/<slug>?tid=...
      https://polymarket.com/market/<slug>?...
    """
    try:
        p = urlparse(url.strip())
    except Exception:
        raise PolymarketError("Некорректный URL")

    if not p.netloc.endswith("polymarket.com"):
        raise PolymarketError("URL должен быть с polymarket.com")

    m = re.match(r"^/(event|market)/([^/?#]+)", p.path)
    if not m:
        raise PolymarketError("Не удалось извлечь slug из URL. Ожидаю /event/<slug> или /market/<slug>")

    return m.group(2)

def _get_json(url: str, params: Dict[str, Any] | None = None) -> Any:
    r = requests.get(url, params=params, timeout=30)
    if r.status_code >= 400:
        raise PolymarketError(f"HTTP {r.status_code} при запросе {url}: {r.text[:200]}")
    return r.json()

def fetch_event_by_slug(slug: str) -> Dict[str, Any]:
    # Recommended in docs: /events/slug/<slug>
    url = f"{GAMMA_BASE}/events/slug/{slug}"
    return _get_json(url)

def normalize_event_markets(event_obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Gamma event response usually includes `markets` array.
    Each market has outcomes + clobTokenIds (often encoded as JSON string in some clients).
    We'll try to handle both 'already parsed list' and 'json string'.
    """
    markets = event_obj.get("markets") or []
    if not isinstance(markets, list) or len(markets) == 0:
        raise PolymarketError("У события нет markets (или они недоступны).")

    def ensure_list(v):
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            # Some gamma fields can be JSON-encoded strings
            import json
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except Exception:
                pass
        return None

    out = []
    for m in markets:
        outcomes = ensure_list(m.get("outcomes"))
        token_ids = ensure_list(m.get("clobTokenIds")) or ensure_list(m.get("clobTokenIDs"))
        if not outcomes or not token_ids or len(outcomes) != len(token_ids):
            # Skip malformed
            continue

        out.append({
            "id": m.get("id"),
            "title": (m.get("title") or m.get("question") or "Untitled market").strip(),
            "outcomes": outcomes,
            "token_ids": token_ids,
        })

    if not out:
        raise PolymarketError("Не нашёл валидных markets с outcomes + clobTokenIds.")
    return out

def fetch_token_price_history(token_id: str, interval: str = "max", fidelity_min: int = 10) -> List[Tuple[int, float]]:
    """
    Returns list[(unix_ts_seconds, price_float_0_1)]
    """
    url = f"{CLOB_BASE}/prices-history"
    data = _get_json(url, params={
        "market": token_id,
        "interval": interval,
        "fidelity": fidelity_min,
    })
    hist = data.get("history") or []
    out = []
    for pt in hist:
        t = pt.get("t")
        p = pt.get("p")
        if t is None or p is None:
            continue
        # p is in [0,1] for Polymarket shares; keep as float
        out.append((int(t), float(p)))
    if not out:
        raise PolymarketError(f"Пустая история цен для token_id={token_id}")
    return out