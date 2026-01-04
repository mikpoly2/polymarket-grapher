from __future__ import annotations
import streamlit as st
import pandas as pd

from polymarket_api import (
    extract_slug,
    fetch_event_by_slug,
    normalize_event_markets,
    fetch_token_price_history,
    PolymarketError,
)
from crypto_api import fetch_crypto_price_range, CryptoError
from plotter import build_step_aligned_df, make_chart

st.set_page_config(page_title="Polymarket Grapher", page_icon="📈", layout="wide")

# --- minimal, safe styling (не ломает стандартные элементы Streamlit)
st.markdown("""
<style>
.block-container { max-width: 1200px; padding-top: 1.3rem; }
.small-muted { opacity: 0.75; font-size: 0.9rem; }
.card {
  border: 1px solid rgba(255,255,255,0.08);
  background: rgba(255,255,255,0.03);
  border-radius: 18px;
  padding: 18px;
}
.center { display: flex; justify-content: center; }
.h1 { font-size: 44px; font-weight: 750; letter-spacing: -0.02em; margin: 0; }
.h1 span { color: #4cc9f0; }
</style>
""", unsafe_allow_html=True)

# -------------------- session --------------------
if "stage" not in st.session_state:
    st.session_state.stage = 1
if "event" not in st.session_state:
    st.session_state.event = None
if "markets" not in st.session_state:
    st.session_state.markets = None
if "crypto" not in st.session_state:
    st.session_state.crypto = "Don't show crypto price"
if "selected" not in st.session_state:
    # key -> {"label": str, "token_id": str}
    st.session_state.selected = {}
if "history_cache" not in st.session_state:
    st.session_state.history_cache = {}  # token_id -> pd.Series
if "crypto_cache" not in st.session_state:
    # (symbol, start_ts, end_ts) -> pd.Series
    st.session_state.crypto_cache = {}

def nice_label(market_title: str, outcome: str) -> str:
    return f"{market_title} ({outcome})"

def outcome_tag(outcome: str) -> str:
    o = (outcome or "").strip().lower()
    if o == "yes":
        return "🟩 YES"
    if o == "no":
        return "🟥 NO"
    return outcome

def crypto_symbol(choice: str) -> str | None:
    if choice == "Don't show crypto price":
        return None
    # "Bitcoin (BTC)" -> BTC
    return choice.split("(")[-1].split(")")[0].strip().upper()

# ==================== SCREEN 1 ====================
if st.session_state.stage == 1:
    st.markdown('<div class="center">', unsafe_allow_html=True)
    st.markdown('<div class="card" style="width: min(900px, 100%);">', unsafe_allow_html=True)

    st.markdown('<div class="h1">Polymarket <span>Grapher</span></div>', unsafe_allow_html=True)
    st.markdown('<div class="small-muted">Visualize prediction market prices alongside crypto trends</div>', unsafe_allow_html=True)
    st.write("")

    url = st.text_input("Polymarket Event URL", placeholder="https://polymarket.com/event/...")
    crypto = st.selectbox(
        "Compare with Cryptocurrency",
        ["Don't show crypto price", "Bitcoin (BTC)", "Ethereum (ETH)", "Solana (SOL)"],
        index=0,
    )

    c1, c2 = st.columns([1, 1])
    with c1:
        visualize = st.button("Visualize Event", use_container_width=True)
    with c2:
        st.caption("Tip: paste any Polymarket event URL. No hardcode.")

    st.markdown("</div></div>", unsafe_allow_html=True)

    if visualize:
        try:
            if not url.strip():
                raise PolymarketError("Вставь URL события Polymarket.")
            slug = extract_slug(url)
            with st.spinner("Loading event metadata..."):
                event = fetch_event_by_slug(slug)
                markets = normalize_event_markets(event)

            st.session_state.event = event
            st.session_state.markets = markets
            st.session_state.crypto = crypto
            st.session_state.selected = {}
            st.session_state.history_cache = {}
            st.session_state.crypto_cache = {}
            st.session_state.stage = 2
            st.rerun()

        except PolymarketError as e:
            st.error(str(e))

# ==================== SCREEN 2 ====================
else:
    event = st.session_state.event or {}
    markets = st.session_state.markets or []
    title = (event.get("title") or event.get("slug") or "Event").strip()

    topL, topR = st.columns([3, 1])
    with topL:
        st.markdown(f"## {title}")
        st.caption(f"Markets: {len(markets)} • Crypto overlay: {st.session_state.crypto}")
    with topR:
        if st.button("← New event", use_container_width=True):
            st.session_state.stage = 1
            st.rerun()

    left, right = st.columns([1.15, 2], gap="large")

    # ---------- LEFT: controls + selection ----------
    with left:
        st.markdown("### Controls")
        q = st.text_input("Search markets/outcomes", placeholder="e.g. 86000, yes, january...")
        show_sum = st.toggle("Show Sum", value=True)
        fidelity = st.slider("History fidelity (minutes)", 1, 60, 10, 1)

        st.write("---")

        st.markdown("### Selected")
        if st.session_state.selected:
            st.caption(f"{len(st.session_state.selected)} line(s)")
            for item in st.session_state.selected.values():
                st.write("• " + item["label"])
            if st.button("Clear selection", use_container_width=True):
                st.session_state.selected = {}
                st.rerun()
        else:
            st.caption("Nothing selected yet.")

        st.write("---")
        st.markdown("### Markets / Outcomes")

        ql = q.strip().lower()

        for m in markets:
            mtitle = m["title"]
            outs = m["outcomes"]

            if ql:
                if ql not in mtitle.lower() and not any(ql in (o or "").lower() for o in outs):
                    continue

            with st.expander(mtitle, expanded=False):
                cols = st.columns(2)
                for i, (outcome, token_id) in enumerate(zip(outs, m["token_ids"])):
                    key = f"{m['id']}::{outcome}"
                    label = outcome_tag(outcome)

                    with cols[i % 2]:
                        checked = st.checkbox(label, value=(key in st.session_state.selected), key=f"cb_{key}")

                    if checked:
                        st.session_state.selected[key] = {
                            "label": nice_label(mtitle, outcome),
                            "token_id": token_id,
                        }
                    else:
                        st.session_state.selected.pop(key, None)

    # ---------- RIGHT: chart ----------
    with right:
        if not st.session_state.selected:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown("### No bets selected")
            st.caption("Choose outcomes on the left to show price history.")
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            crypto_diag = None

            with st.spinner("Loading price history..."):
                series_map = {}

                # 1) Polymarket series (selected outcomes)
                for item in st.session_state.selected.values():
                    token_id = item["token_id"]
                    label = item["label"]

                    if token_id not in st.session_state.history_cache:
                        hist = fetch_token_price_history(token_id, interval="max", fidelity_min=int(fidelity))
                        idx = pd.to_datetime([t for t, _ in hist], unit="s", utc=True)
                        vals = [p for _, p in hist]
                        st.session_state.history_cache[token_id] = pd.Series(vals, index=idx).sort_index()

                    series_map[label] = st.session_state.history_cache[token_id]

                prob_df = build_step_aligned_df(series_map)

                # 2) Crypto overlay (ВАЖНО: НЕ reindex на prob_df.index)
                crypto_series = None
                sym = crypto_symbol(st.session_state.crypto)
                if sym is not None:
                    start_ts = int(prob_df.index.min().timestamp())
                    end_ts = int(prob_df.index.max().timestamp())

                    cache_key = (sym, start_ts, end_ts)
                    try:
                        if cache_key in st.session_state.crypto_cache:
                            crypto_series = st.session_state.crypto_cache[cache_key]
                        else:
                            crypto_hist = fetch_crypto_price_range(sym, start_ts, end_ts)
                            cidx = pd.to_datetime([t for t, _ in crypto_hist], unit="s", utc=True)
                            cvals = [p for _, p in crypto_hist]
                            crypto_series = pd.Series(cvals, index=cidx).sort_index()
                            st.session_state.crypto_cache[cache_key] = crypto_series

                        crypto_diag = (
                            f"{sym} points: {len(crypto_series)} • "
                            f"{crypto_series.index.min().strftime('%Y-%m-%d')} → "
                            f"{crypto_series.index.max().strftime('%Y-%m-%d')}"
                        )
                    except CryptoError as e:
                        st.warning(f"Crypto overlay error ({sym}): {e}")

                fig = make_chart(prob_df, crypto_series=crypto_series, show_sum=show_sum)
                st.plotly_chart(fig, use_container_width=True)

            if crypto_diag:
                st.caption(crypto_diag)

            st.caption("Tip: click legend items to hide/show lines. Hover is synced across all active lines.")