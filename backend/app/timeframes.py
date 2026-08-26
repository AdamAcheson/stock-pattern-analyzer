"""Timeframe -> yfinance (period, interval) mapping.

ASSUMPTION: yfinance limits intraday granularity by how far back you can
query (e.g. 1m bars only within the last ~7 days, and requests over ~60
days of 5m/15m data get truncated/rejected by Yahoo's backend). The
period/interval pairs below were chosen to stay inside those limits while
giving a reasonable amount of history for each timeframe. If Yahoo changes
these limits, only this file needs to change.
"""

from typing import NamedTuple


class TimeframeSpec(NamedTuple):
    period: str
    interval: str


TIMEFRAMES: dict[str, TimeframeSpec] = {
    "1D": TimeframeSpec(period="1d", interval="5m"),
    "1W": TimeframeSpec(period="5d", interval="15m"),
    "1M": TimeframeSpec(period="1mo", interval="1d"),
    "3M": TimeframeSpec(period="3mo", interval="1d"),
    "6M": TimeframeSpec(period="6mo", interval="1d"),
    "1Y": TimeframeSpec(period="1y", interval="1d"),
    "5Y": TimeframeSpec(period="5y", interval="1wk"),
}

DEFAULT_TIMEFRAME = "1Y"
