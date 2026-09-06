"""Multi-timeframe trend overview: independent daily / weekly / monthly
trend reads for a ticker, regardless of whichever chart timeframe the
user currently has selected.

Each granularity fetches its own period/interval directly from yfinance
(via `app.data_fetch.fetch_history`) rather than resampling the
currently-selected timeframe's data, because a meaningful weekly or
monthly moving-average trend read needs years of history that a "1D" or
"1M" chart selection wouldn't have fetched at all.
"""

from __future__ import annotations

from typing import NamedTuple

import pandas as pd

from app.data_fetch import InvalidTickerError, NoDataError, fetch_history
from app.indicators import sma


class TimeframeSpec(NamedTuple):
    period: str
    interval: str
    short_window: int
    long_window: int


# ASSUMPTIONS: window sizes are chosen per granularity to represent
# "short-term vs longer-term trend" at that granularity, not literally
# the same 20/50 pair reused three times -- a 20-week and 50-week moving
# average pair needs ~1 year of weekly bars just to compute the long one,
# which is why period lengthens as interval coarsens. Trend classification
# itself (see `_classify`) is the same simple rule at every granularity:
# price above a rising short MA above a rising-relative long MA = uptrend,
# the mirror = downtrend, anything else = sideways/mixed. This is a
# heuristic, not a precise trend-strength measure (e.g. ADX) -- documented
# here rather than hidden, consistent with every other heuristic in this
# codebase.
_SPECS: dict[str, TimeframeSpec] = {
    "Daily": TimeframeSpec(period="6mo", interval="1d", short_window=20, long_window=50),
    "Weekly": TimeframeSpec(period="3y", interval="1wk", short_window=10, long_window=40),
    "Monthly": TimeframeSpec(period="10y", interval="1mo", short_window=6, long_window=18),
}


def _classify(close: pd.Series, short_window: int, long_window: int) -> tuple[str, float | None, float | None]:
    short_ma = sma(close, short_window).dropna()
    long_ma = sma(close, long_window).dropna()
    if short_ma.empty or long_ma.empty:
        return "Not enough history", None, None

    price = float(close.iloc[-1])
    short_val = float(short_ma.iloc[-1])
    long_val = float(long_ma.iloc[-1])

    if price > short_val > long_val:
        return "Uptrend", short_val, long_val
    if price < short_val < long_val:
        return "Downtrend", short_val, long_val
    return "Sideways / Mixed", short_val, long_val


def fetch_multi_timeframe_trend(ticker: str) -> list[dict]:
    """Returns one trend read per granularity (Daily/Weekly/Monthly).

    Each granularity is fetched and classified independently -- if one
    fails (e.g. a recent IPO with no 10-year monthly history), the others
    still return normally rather than the whole endpoint failing, since
    by the time this is called the ticker itself has already been
    validated by the main analysis endpoint's own fetch.
    """
    results = []
    for label, spec in _SPECS.items():
        try:
            df = fetch_history(
                ticker, spec.period, spec.interval, context=f"{label.lower()} trend overview"
            )
            trend, short_val, long_val = _classify(df["close"], spec.short_window, spec.long_window)
            results.append(
                {
                    "label": label,
                    "trend": trend,
                    "close": float(df["close"].iloc[-1]),
                    "short_ma": short_val,
                    "short_window": spec.short_window,
                    "long_ma": long_val,
                    "long_window": spec.long_window,
                    "error": None,
                }
            )
        except (InvalidTickerError, NoDataError) as exc:
            results.append(
                {
                    "label": label,
                    "trend": "Unavailable",
                    "close": None,
                    "short_ma": None,
                    "short_window": spec.short_window,
                    "long_ma": None,
                    "long_window": spec.long_window,
                    "error": str(exc),
                }
            )
    return results
