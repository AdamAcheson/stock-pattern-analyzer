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


def fibonacci_retracement(df: pd.DataFrame, lookback: int | None = None) -> dict:
    """Fibonacci retracement levels between the highest high and lowest
    low over the given window (the whole DataFrame, or just the trailing
    `lookback` bars if given).

    ASSUMPTION: uses the window's highest high / lowest low as "the"
    swing rather than trying to algorithmically pick a single "most
    significant" swing-point pair -- this matches how every real charting
    platform's fib tool actually works (you drag it between any two
    points yourself), so it's the standard, not a simplification of one.
    Direction is inferred from which extreme came later in time: if the
    low predates the high, price is being read as retracing down from a
    rally (levels are potential support on a pullback); if the high
    predates the low, price is retracing up from a decline (levels are
    potential resistance on a bounce). These are read as descriptive
    "zones technical analysts watch", not predictions that price will
    reach or reverse at any of them. 50% is included alongside the true
    Fibonacci ratios (23.6%, 38.2%, 61.8%, 78.6%) because it's standard
    practice on virtually every charting platform despite not being a
    Fibonacci number itself.
    """
    window = df if lookback is None else df.iloc[-lookback:]
    high_idx = window["high"].idxmax()
    low_idx = window["low"].idxmin()
    high_price = float(window.loc[high_idx, "high"])
    low_price = float(window.loc[low_idx, "low"])
    span = high_price - low_price
    uptrend = low_idx < high_idx

    ratios = [0.236, 0.382, 0.5, 0.618, 0.786]
    if uptrend:
        levels = [{"ratio": r, "price": round(high_price - span * r, 4)} for r in ratios]
    else:
        levels = [{"ratio": r, "price": round(low_price + span * r, 4)} for r in ratios]

    return {
        "swing_high": high_price,
        "swing_high_time": high_idx,
        "swing_low": low_price,
        "swing_low_time": low_idx,
        "direction": "pullback zones within an uptrend" if uptrend else "bounce zones within a decline",
        "levels": levels,
    }


def volume_trend(df: pd.DataFrame, recent_window: int = 10, baseline_window: int = 50) -> dict:
    """Compares recent volume to its own longer-run baseline, and volume
    on up days vs down days, as a plain-English read of buying vs selling
    pressure.

    ASSUMPTIONS: "recent" = trailing `recent_window` bars (default 10);
    "baseline" = trailing `baseline_window` bars (default 50), which
    *includes* the recent window rather than a disjoint prior period --
    this deliberately answers "is volume elevated right now relative to
    the last couple months" rather than comparing two separate eras.
    Buy/sell pressure is a simple average-volume-on-up-days vs
    average-volume-on-down-days ratio over the baseline window: a
    heuristic proxy for accumulation/distribution, not a true
    volume-weighted calculation like OBV. A ratio within +/-15% of 1.0 is
    read as "balanced" rather than forcing every reading into a side.
    """
    n = len(df)
    if n == 0:
        return {"available": False}

    baseline_start = max(0, n - baseline_window)
    baseline_vol = df["volume"].iloc[baseline_start:]
    recent_vol = df["volume"].iloc[max(0, n - recent_window):]
    if baseline_vol.empty or recent_vol.empty:
        return {"available": False}

    baseline_avg = float(baseline_vol.mean())
    recent_avg = float(recent_vol.mean())
    change_pct = ((recent_avg / baseline_avg) - 1) * 100 if baseline_avg > 0 else None

    changes = df["close"].diff().iloc[baseline_start:]
    vols_in_window = df["volume"].iloc[baseline_start:]
    up_day_vol = vols_in_window[changes > 0]
    down_day_vol = vols_in_window[changes < 0]
    up_avg = float(up_day_vol.mean()) if not up_day_vol.empty else None
    down_avg = float(down_day_vol.mean()) if not down_day_vol.empty else None

    pressure_ratio = None
    dominant_side = "balanced"
    if up_avg is not None and down_avg is not None and down_avg > 0:
        pressure_ratio = up_avg / down_avg
        if pressure_ratio >= 1.15:
            dominant_side = "buyers"
        elif pressure_ratio <= 0.87:
            dominant_side = "sellers"

    return {
        "available": True,
        "recent_avg_volume": recent_avg,
        "baseline_avg_volume": baseline_avg,
        "change_pct": change_pct,
        "up_day_avg_volume": up_avg,
        "down_day_avg_volume": down_avg,
        "pressure_ratio": pressure_ratio,
        "dominant_side": dominant_side,
    }


def compute_all(df: pd.DataFrame) -> dict[str, pd.DataFrame | pd.Series]:
    """Compute the full indicator bundle used by the API layer."""
    close = df["close"]
    return {
        "sma_20": sma(close, 20),
        "sma_50": sma(close, 50),
        "sma_100": sma(close, 100),
        "sma_200": sma(close, 200),
        "ema_12": ema(close, 12),
        "ema_26": ema(close, 26),
        "rsi_14": rsi(close, 14),
        "vwma_20": volume_weighted_ma(df, 20),
        "macd": macd(close),
        "bollinger": bollinger_bands(close),
        "ma_crossovers": ma_crossovers(df),
        "support_resistance": support_resistance_levels(df),
        "fibonacci": fibonacci_retracement(df),
        "volume_trend": volume_trend(df),
    }
