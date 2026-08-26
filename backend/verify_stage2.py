"""Stage 2 verification: spot-check indicator math against independent
from-scratch reference implementations (plain Python loops, not pandas
rolling/ewm), per the project's feedback-loop protocol. Not a pytest
suite -- a throwaway script run once to eyeball correctness against real
data, kept around so the check is reproducible.
"""

from app.data_fetch import fetch_ohlcv
from app.indicators import (
    bollinger_bands,
    compute_all,
    ema,
    macd,
    ma_crossovers,
    rsi,
    sma,
    swing_highs_lows,
    volume_weighted_ma,
)


def ref_sma(values, window, i):
    return sum(values[i - window + 1 : i + 1]) / window


def ref_ema_series(values, span):
    alpha = 2 / (span + 1)
    out = [None] * len(values)
    out[span - 1] = sum(values[:span]) / span
    for i in range(span, len(values)):
        out[i] = values[i] * alpha + out[i - 1] * (1 - alpha)
    return out


def ref_rsi(values, period, i):
    deltas = [values[j] - values[j - 1] for j in range(1, i + 1)]
    gains = [max(d, 0) for d in deltas]
    losses = [max(-d, 0) for d in deltas]
    alpha = 1 / period
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for j in range(period, len(gains)):
        avg_gain = gains[j] * alpha + avg_gain * (1 - alpha)
        avg_loss = losses[j] * alpha + avg_loss * (1 - alpha)
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - 100 / (1 + rs)


def check(label, got, expected, tol=1e-6):
    ok = abs(got - expected) <= tol
    status = "OK" if ok else "MISMATCH"
    print(f"  [{status}] {label}: got={got!r} expected~={expected!r}")
    return ok


all_ok = True

for ticker in ["AAPL", "TSLA", "MSFT"]:
    print(f"\n=== {ticker} (1Y daily) ===")
    df = fetch_ohlcv(ticker, "1Y")
    closes = df["close"].tolist()
    n = len(closes)
    last = n - 1

    ind = compute_all(df)

    # --- SMA: compare against a plain-Python trailing mean at the last bar ---
    for window in (20, 50, 200):
        got = ind[f"sma_{window}"].iloc[last]
        expected = ref_sma(closes, window, last)
        all_ok &= check(f"SMA{window} @ last bar", float(got), expected)

    # --- EMA: compare against a from-scratch EMA recursion over the whole series ---
    for span in (12, 26):
        got = ind[f"ema_{span}"].iloc[last]
        expected = ref_ema_series(closes, span)[last]
        all_ok &= check(f"EMA{span} @ last bar", float(got), expected, tol=1e-4)

    # --- RSI: bounds check + independent Wilder recursion at last bar ---
    rsi_series = ind["rsi_14"]
    valid_rsi = rsi_series.dropna()
    in_bounds = valid_rsi.between(0, 100).all()
    print(f"  [{'OK' if in_bounds else 'MISMATCH'}] RSI14 stays within [0,100] for all {len(valid_rsi)} valid bars")
    all_ok &= bool(in_bounds)
    got_rsi = rsi_series.iloc[last]
    expected_rsi = ref_rsi(closes, 14, last)
    all_ok &= check("RSI14 @ last bar", float(got_rsi), expected_rsi, tol=1e-3)

    # --- MACD: histogram = macd - signal identity, and macd = EMA12 - EMA26 ---
    # (compare only where both sides are defined -- a raw NaN diff() would
    # otherwise compare as `False`, not `NaN`, and look like a mismatch)
    macd_df = ind["macd"]
    hist_diff = (macd_df["macd"] - macd_df["signal"] - macd_df["histogram"]).dropna()
    hist_ok = (hist_diff.abs() < 1e-9).all()
    print(f"  [{'OK' if hist_ok else 'MISMATCH'}] MACD histogram == macd - signal for all {len(hist_diff)} valid bars")
    all_ok &= bool(hist_ok)
    macd_line_diff = (macd_df["macd"] - (ind["ema_12"] - ind["ema_26"])).dropna()
    macd_line_ok = (macd_line_diff.abs() < 1e-9).all()
    print(f"  [{'OK' if macd_line_ok else 'MISMATCH'}] MACD line == EMA12 - EMA26 for all {len(macd_line_diff)} valid bars")
    all_ok &= bool(macd_line_ok)

    # --- Bollinger Bands: upper >= middle >= lower always; middle == SMA20 ---
    bb = ind["bollinger"]
    valid_bb = bb.dropna()
    ordering_ok = (valid_bb["upper"] >= valid_bb["middle"]).all() and (
        valid_bb["middle"] >= valid_bb["lower"]
    ).all()
    print(f"  [{'OK' if ordering_ok else 'MISMATCH'}] Bollinger upper >= middle >= lower for all {len(valid_bb)} valid bars")
    all_ok &= bool(ordering_ok)
    mid_matches_sma = ((bb["middle"] - ind["sma_20"]).dropna().abs() < 1e-9).all()
    print(f"  [{'OK' if mid_matches_sma else 'MISMATCH'}] Bollinger middle band == SMA20")
    all_ok &= bool(mid_matches_sma)

    # --- VWMA: compare against a from-scratch weighted average at the last bar ---
    got_vwma = ind["vwma_20"].iloc[last]
    window_slice = df.iloc[last - 19 : last + 1]
    expected_vwma = (window_slice["close"] * window_slice["volume"]).sum() / window_slice["volume"].sum()
    all_ok &= check("VWMA20 @ last bar", float(got_vwma), float(expected_vwma), tol=1e-6)

    # --- Golden/death cross: sanity print any detected crossovers ---
    crosses = ind["ma_crossovers"]
    golden_dates = crosses.index[crosses["golden_cross"]].tolist()
    death_dates = crosses.index[crosses["death_cross"]].tolist()
    print(f"  [INFO] Golden crosses (SMA50 over SMA200) at: {[str(d.date()) for d in golden_dates]}")
    print(f"  [INFO] Death crosses at: {[str(d.date()) for d in death_dates]}")
    # cross-check: at each flagged golden cross date, sma50 should be above sma200
    # on that bar and below (or equal) on the prior bar.
    for d in golden_dates:
        pos = df.index.get_loc(d)
        prev_diff = ind["sma_50"].iloc[pos - 1] - ind["sma_200"].iloc[pos - 1]
        curr_diff = ind["sma_50"].iloc[pos] - ind["sma_200"].iloc[pos]
        ok = prev_diff <= 0 and curr_diff > 0
        print(f"    [{'OK' if ok else 'MISMATCH'}] golden cross at {d.date()}: prev_diff={prev_diff:.4f} curr_diff={curr_diff:.4f}")
        all_ok &= ok

    # --- Support/resistance: sanity check levels fall within the actual price range ---
    sr = ind["support_resistance"]
    lo, hi = df["low"].min(), df["high"].max()
    levels_in_range = all(lo <= lv["price"] <= hi for lv in sr["support"] + sr["resistance"])
    print(f"  [{'OK' if levels_in_range else 'MISMATCH'}] all support/resistance levels within [{lo:.2f}, {hi:.2f}]")
    all_ok &= levels_in_range
    print(f"  [INFO] support levels: {[(round(l['price'],2), l['touches']) for l in sr['support']]}")
    print(f"  [INFO] resistance levels: {[(round(l['price'],2), l['touches']) for l in sr['resistance']]}")

    print(f"  [INFO] last close={closes[-1]:.2f}  SMA20={ind['sma_20'].iloc[-1]:.2f}  "
          f"SMA50={ind['sma_50'].iloc[-1]:.2f}  SMA200={ind['sma_200'].iloc[-1]:.2f}  "
          f"RSI14={ind['rsi_14'].iloc[-1]:.2f}")

print("\n=== OVERALL:", "ALL CHECKS PASSED" if all_ok else "SOME CHECKS FAILED", "===")
