from __future__ import annotations
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import Dict, Optional

def build_step_aligned_df(series_map: Dict[str, pd.Series]) -> pd.DataFrame:
    """
    series_map: name -> Series indexed by datetime (UTC), values float
    Returns aligned DF with forward-filled step behavior.
    """
    if not series_map:
        return pd.DataFrame()

    # Union index
    all_index = None
    for s in series_map.values():
        all_index = s.index if all_index is None else all_index.union(s.index)

    df = pd.DataFrame(index=all_index).sort_index()
    for name, s in series_map.items():
        df[name] = s.reindex(df.index).ffill()

    return df

def make_chart(
    prob_df: pd.DataFrame,
    crypto_series: Optional[pd.Series] = None,
    show_sum: bool = True,
) -> go.Figure:
    """
    prob_df: columns = selected outcomes, values in [0,1]
    crypto_series: indexed by datetime, USD
    """
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Prob lines
    for col in prob_df.columns:
        fig.add_trace(
            go.Scatter(
                x=prob_df.index,
                y=(prob_df[col] * 100.0),
                mode="lines",
                name=col,
                hovertemplate=f"{col}: %{{y:.2f}}%<extra></extra>",
            ),
            secondary_y=False,
        )

    # SUM
    if show_sum and len(prob_df.columns) >= 2:
        s = prob_df.sum(axis=1) * 100.0
        fig.add_trace(
            go.Scatter(
                x=prob_df.index,
                y=s,
                mode="lines",
                name="SUM",
                hovertemplate="SUM: %{y:.2f}%<extra></extra>",
            ),
            secondary_y=False,
        )

    # Crypto line
    if crypto_series is not None and not crypto_series.empty:
        fig.add_trace(
            go.Scatter(
                x=crypto_series.index,
                y=crypto_series.values,
                mode="lines",
                name="Crypto Price (USD)",
                hovertemplate="Crypto: $%{y:,.2f}<extra></extra>",
            ),
            secondary_y=True,
        )

    fig.update_layout(
        template="plotly_dark",
        hovermode="x unified",
        uirevision="keep",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(l=20, r=20, t=30, b=20),
    )

    fig.update_yaxes(title_text="Share Price / Probability (%)", secondary_y=False)
    fig.update_yaxes(title_text="Crypto Price (USD)", secondary_y=True)

    return fig