"""OHLCV data fetching layer.

Wraps yfinance and normalizes its output into a clean, ascending-by-date
pandas DataFrame with a fixed column set. Isolated in one module so the
data source can be swapped (e.g. for Alpha Vantage / Polygon) without
touching indicator or pattern-detection code.
"""

from __future__ import annotations

import logging

import pandas as pd
import yfinance as yf

from app.timeframes import TIMEFRAMES

logger = logging.getLogger(__name__)

OHLCV_COLUMNS = ["open", "high", "low", "close", "volume"]


class InvalidTickerError(Exception):
    """Raised when a ticker doesn't resolve to any data."""


class NoDataError(Exception):
    """Raised when a ticker is valid but no data exists for the requested timeframe."""


def fetch_ohlcv(ticker: str, timeframe: str) -> pd.DataFrame:
    """Fetch and normalize OHLCV data for a ticker over a given timeframe.

    Returns a DataFrame indexed by UTC-naive timestamp (ascending), with
    columns: open, high, low, close, volume. Raises InvalidTickerError if
    the ticker doesn't exist, or NoDataError if it exists but has no bars
    for the requested timeframe.
    """
    ticker = ticker.strip().upper()
    if not ticker:
        raise InvalidTickerError("Ticker symbol is empty")

    spec = TIMEFRAMES.get(timeframe)
    if spec is None:
        raise ValueError(
            f"Unknown timeframe '{timeframe}'. Valid options: {sorted(TIMEFRAMES)}"
        )

    t = yf.Ticker(ticker)

    # yfinance doesn't raise on an unknown ticker for history(); it just
    # returns an empty frame. We distinguish "unknown ticker" from
    # "known ticker, no bars in this window" by checking `info`/`fast_info`
    # is unable to resolve anything meaningful either.
    try:
        raw = t.history(period=spec.period, interval=spec.interval, auto_adjust=True)
    except Exception as exc:  # yfinance raises assorted exceptions on network/parse errors
        logger.warning("yfinance history() raised for %s: %s", ticker, exc)
        raise NoDataError(f"Could not fetch data for '{ticker}': {exc}") from exc

    if raw.empty:
        # Disambiguate: does the ticker exist at all?
        if not _ticker_exists(t):
            raise InvalidTickerError(f"'{ticker}' is not a recognized ticker symbol")
        raise NoDataError(
            f"'{ticker}' is a valid ticker but has no data for timeframe '{timeframe}'"
        )

    df = _normalize(raw)

    if df.empty:
        raise NoDataError(
            f"'{ticker}' returned only invalid/incomplete bars for timeframe '{timeframe}'"
        )

    return df


def _ticker_exists(t: yf.Ticker) -> bool:
    try:
        fast_info = t.fast_info
        # fast_info behaves like a dict; a resolvable ticker has a last price.
        return fast_info.get("lastPrice") is not None
    except Exception:
        return False


def _normalize(raw: pd.DataFrame) -> pd.DataFrame:
    """Lowercase columns, drop tz info, sort ascending, drop bad rows."""
    df = raw.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]].copy()

    # yfinance returns a tz-aware DatetimeIndex; strip tz for consistent
    # JSON serialization (frontend treats timestamps as exchange-local).
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)

    df = df.sort_index()

    # Drop rows with NaN OHLC (can happen for halted/partial sessions) or
    # non-positive prices (bad data from the source).
    price_cols = ["open", "high", "low", "close"]
    df = df.dropna(subset=price_cols)
    df = df[(df[price_cols] > 0).all(axis=1)]

    # Volume can legitimately be 0 (e.g. some intraday bars); NaN volume
    # is not legitimate and gets treated as 0.
    df["volume"] = df["volume"].fillna(0).astype("int64")

    df = df[~df.index.duplicated(keep="last")]

    return df
