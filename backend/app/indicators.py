"""Technical indicator calculations.

Every function takes a clean OHLCV DataFrame (as returned by
``app.data_fetch.fetch_ohlcv``: ascending index, columns
open/high/low/close/volume) or a single price Series, and returns a
pandas Series/DataFrame aligned to the same index. Leading bars that
don't have enough history for a given window are left as NaN rather
than dropped or backfilled — a 20-day SMA genuinely has no value on day
1, and callers (the API layer) decide how to represent that gap.

Where a calculation is a precise, textbook formula (SMA, EMA, Bollinger
Bands, MACD), it's noted as such. Where it involves a judgment call
(RSI's smoothing method, what counts as a "swing" high/low, how close
two price levels have to be to count as the same support/resistance
zone), it's flagged as a heuristic/assumption in the docstring so it can
be revisited.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def sma(series: pd.Series, window: int) -> pd.Series:
    """Simple moving average. Precise: unweighted mean of the trailing `window` bars."""
    return series.rolling(window=window, min_periods=window).mean()


def ema(series: pd.Series, span: int) -> pd.Series:
    """Exponential moving average. Precise: standard EMA with alpha = 2/(span+1)."""
    return series.ewm(span=span, adjust=False, min_periods=span).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index.

    HEURISTIC CHOICE: uses Wilder's original smoothing (an EMA with
    alpha = 1/period applied to gains/losses), which is what TradingView,
    Yahoo Finance, and most charting platforms use as "the" RSI. A
    simple-moving-average variant also exists and will produce slightly
    different values — Wilder's is the de facto standard so that's what's
    implemented here.
    """
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    rsi_values = 100 - (100 / (1 + rs))
    # By definition RSI = 100 when there have been no losses at all in the
    # smoothing window (rs -> infinity, division gives NaN not inf here
    # because avg_loss == 0 exactly).
    rsi_values = rsi_values.where(avg_loss != 0, 100.0)
    rsi_values = rsi_values.where(avg_gain.notna(), np.nan)
    return rsi_values


def macd(
    series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> pd.DataFrame:
    """MACD line, signal line, and histogram. Precise: standard definition
    (EMA(fast) - EMA(slow)), signal is an EMA of the MACD line."""
    macd_line = ema(series, fast) - ema(series, slow)
    signal_line = macd_line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    histogram = macd_line - signal_line
    return pd.DataFrame(
        {"macd": macd_line, "signal": signal_line, "histogram": histogram}
    )


def bollinger_bands(
    series: pd.Series, window: int = 20, num_std: float = 2.0
) -> pd.DataFrame:
    """Bollinger Bands. Precise: middle band is the SMA, bands are
    +/- num_std population standard deviations (ddof=0, matching the
    standard Bollinger Band definition) around it."""
    middle = sma(series, window)
    std = series.rolling(window=window, min_periods=window).std(ddof=0)
    upper = middle + num_std * std
    lower = middle - num_std * std
    return pd.DataFrame({"upper": upper, "middle": middle, "lower": lower})


def volume_weighted_ma(df: pd.DataFrame, window: int = 20) -> pd.Series:
    """Volume-weighted moving average of close price over `window` bars.
    Precise: sum(close * volume) / sum(volume) over the trailing window."""
    pv = df["close"] * df["volume"]
    return (
        pv.rolling(window=window, min_periods=window).sum()
        / df["volume"].rolling(window=window, min_periods=window).sum()
    )


def ma_crossovers(df: pd.DataFrame, fast: int = 50, slow: int = 200) -> pd.DataFrame:
    """Golden cross (fast MA crosses above slow MA) / death cross (fast
    crosses below slow), based on SMA(fast) vs SMA(slow). Precise given
    the SMA inputs; the choice of 50/200 as "the" golden/death cross
    windows is the market convention, not a free parameter here."""
    sma_fast = sma(df["close"], fast)
    sma_slow = sma(df["close"], slow)
    diff_sign = np.sign(sma_fast - sma_slow)
    sign_change = diff_sign.diff()
    return pd.DataFrame(
        {
            "golden_cross": sign_change == 2,
            "death_cross": sign_change == -2,
        }
    )


def swing_highs_lows(df: pd.DataFrame, window: int = 5) -> pd.DataFrame:
    """Flag bars that are local extrema (swing highs/lows).

    ASSUMPTION: a swing high is a bar whose `high` is strictly greater
    than every other `high` within `window` bars on both sides; a swing
    low is the mirror for `low`. This is a common, simple heuristic for
    "meaningful" turning points, but the window size is an arbitrary
    trade-off: smaller finds more (noisier) swings, larger finds fewer
    (more significant) ones. window=5 is chosen as a reasonable default
    for daily bars and should be revisited if pattern detection (Stage 3)
    needs finer or coarser structure.
    """
    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    n = len(df)
    is_high = np.zeros(n, dtype=bool)
    is_low = np.zeros(n, dtype=bool)

    for i in range(window, n - window):
        h_window = highs[i - window : i + window + 1]
        if highs[i] == h_window.max() and (h_window == highs[i]).sum() == 1:
            is_high[i] = True
        l_window = lows[i - window : i + window + 1]
        if lows[i] == l_window.min() and (l_window == lows[i]).sum() == 1:
            is_low[i] = True

    return pd.DataFrame({"swing_high": is_high, "swing_low": is_low}, index=df.index)


def support_resistance_levels(
    df: pd.DataFrame,
    window: int = 5,
    tolerance_pct: float = 0.015,
    max_levels: int = 5,
) -> dict[str, list[dict[str, float]]]:
    """Derive support/resistance price levels from clustered swing points.

    ASSUMPTION (compounding the swing-detection assumption above): swing
    highs within `tolerance_pct` (default 1.5%) of each other are merged
    into a single resistance level (support: swing lows, symmetrically),
    using the mean price of the cluster and a "touches" count of how many
    swings contributed. Clustering is done by sorting prices and merging
    adjacent points within tolerance, which can chain together a wide
    range if prices step gradually — a real trading-desk definition might
    instead weight by how often each level was tested over a strict price
    band. The `max_levels` most-touched levels of each type are returned;
    "most touched" is used as a proxy for "most significant" since we have
    no volume-at-price data to weight by.
    """
    swings = swing_highs_lows(df, window=window)
    resistance_points = df.loc[swings["swing_high"], "high"]
    support_points = df.loc[swings["swing_low"], "low"]

    def cluster(points: pd.Series) -> list[dict[str, float]]:
        if points.empty:
            return []
        sorted_points = points.sort_values()
        clusters: list[list[float]] = [[float(sorted_points.iloc[0])]]
        for val in sorted_points.iloc[1:]:
            val = float(val)
            if abs(val - clusters[-1][-1]) / clusters[-1][-1] <= tolerance_pct:
                clusters[-1].append(val)
            else:
                clusters.append([val])
        return [
            {"price": float(np.mean(c)), "touches": len(c)} for c in clusters
        ]

    resistance_levels = sorted(cluster(resistance_points), key=lambda lv: -lv["touches"])
    support_levels = sorted(cluster(support_points), key=lambda lv: -lv["touches"])

    return {
        "support": support_levels[:max_levels],
        "resistance": resistance_levels[:max_levels],
    }


def compute_all(df: pd.DataFrame) -> dict[str, pd.DataFrame | pd.Series]:
    """Compute the full indicator bundle used by the API layer."""
    close = df["close"]
    return {
        "sma_20": sma(close, 20),
        "sma_50": sma(close, 50),
        "sma_200": sma(close, 200),
        "ema_12": ema(close, 12),
        "ema_26": ema(close, 26),
        "rsi_14": rsi(close, 14),
        "vwma_20": volume_weighted_ma(df, 20),
        "macd": macd(close),
        "bollinger": bollinger_bands(close),
        "ma_crossovers": ma_crossovers(df),
        "support_resistance": support_resistance_levels(df),
    }
