"""Chart pattern detection.

Every detector here is a heuristic approximation, not a precise
mathematical test -- chart patterns are informal, visually-defined
shapes, and reasonable technical analysts can disagree on whether a
given price series "really" shows one. Each function documents the
specific thresholds it uses (how close two peaks have to be to count as
a "double top", how flat a trendline has to be to count as the
resistance line of a triangle, etc.) so those judgment calls are visible
and can be revisited, rather than hidden inside magic numbers.

Every match reports a `confidence` float in [0, 1]. This is NOT a
statistical probability -- there's no labeled dataset behind it. It's a
relative measure of how comfortably the match cleared this detector's
thresholds (a peak pair 0.1% apart scores higher than one 2.9% apart
against a 3% tolerance). Treat it as "how textbook does this look",
not "how likely is this to play out".

Directional bias, breakout-confirmation logic, and volume corroboration
follow the definitions in the user-provided "Stock Chart Pattern
Directional Reference Guide" (see BUILD_SPEC.md Stage 3 notes): a
pattern's *shape* forming is not the same as it being *confirmed* --
confirmation requires a close beyond the pattern's neckline/trendline/
channel boundary, ideally on higher volume. None of this changes the
fact that classical chart-pattern TA has weak, contested predictive
power in the literature; it only makes the tool's language match how a
technical analyst would actually describe a chart, per that document's
own repeated caveat that patterns "describe a statistically probable
direction, not certainty."

All detectors take the OHLCV DataFrame from `app.data_fetch.fetch_ohlcv`
and the swing-point table from `app.indicators.swing_highs_lows`.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.indicators import ma_crossovers, swing_highs_lows

# Confidence scores are deliberately compressed into [0.3, 0.9]: even a
# perfect textbook match isn't reported as 100% certain (pattern
# detection is inherently fuzzy, per the project brief), and anything
# that cleared the thresholds at all is reported as at least "some"
# confidence rather than near-zero.
_CONF_FLOOR = 0.3
_CONF_CEIL = 0.9


def _confidence(*margins: float) -> float:
    """Combine one or more 0..1 "how comfortably did this clear its
    threshold" margins (1.0 = exactly at the edge of passing, 0.0 =
    perfect/exact match) into a single confidence score."""
    margins = [max(0.0, min(1.0, m)) for m in margins]
    avg_margin = sum(margins) / len(margins)
    return round(_CONF_CEIL - avg_margin * (_CONF_CEIL - _CONF_FLOOR), 3)


def _clamp_confidence(value: float) -> float:
    return round(max(_CONF_FLOOR, min(_CONF_CEIL, value)), 3)


def get_swing_points(df: pd.DataFrame, window: int = 5) -> list[dict]:
    """Flatten the swing_highs_lows boolean table into a time-ordered
    list of {pos, time, price, type} points, type in {"high", "low"}."""
    swings = swing_highs_lows(df, window=window)
    points = []
    for pos, (idx, is_high, is_low) in enumerate(
        zip(df.index, swings["swing_high"], swings["swing_low"])
    ):
        if is_high:
            points.append({"pos": pos, "time": idx, "price": float(df["high"].iloc[pos]), "type": "high"})
        if is_low:
            points.append({"pos": pos, "time": idx, "price": float(df["low"].iloc[pos]), "type": "low"})
    points.sort(key=lambda p: p["pos"])
    return points


def _find_breakout(df: pd.DataFrame, start_pos: int, level_at, direction: str) -> int | None:
    """Scan forward from `start_pos` (inclusive) for the first bar whose
    close breaks a level. `level_at(pos)` returns the level's price at a
    given bar position (constant for a flat neckline/channel, or a
    line-fit value for a sloped neckline/trendline). `direction` is
    "above" or "below". Returns the breakout bar's position, or None if
    no bar in the available data broke it yet (the pattern is still
    "forming"/unconfirmed as of the most recent bar)."""
    n = len(df)
    closes = df["close"]
    for pos in range(max(start_pos, 0), n):
        level = level_at(pos)
        close = closes.iloc[pos]
        if direction == "above" and close > level:
            return pos
        if direction == "below" and close < level:
            return pos
    return None


def _volume_note(df: pd.DataFrame, formation_start_pos: int, formation_end_pos: int, breakout_pos: int | None) -> tuple[str, float]:
    """Compare breakout-bar volume to the pattern's average volume during
    formation. The reference guide repeatedly cites "close beyond the
    level, ideally on a volume increase" as part of confirmation -- this
    makes that check explicit and reports it as a small, transparent
    confidence nudge (+/-0.05) rather than folding it silently into the
    shape-based confidence score."""
    formation_start_pos = max(formation_start_pos, 0)
    avg_vol = df["volume"].iloc[formation_start_pos : formation_end_pos + 1].mean()
    if breakout_pos is None:
        return "Not yet confirmed by a breakout close, so there's no breakout volume to check.", 0.0
    if not avg_vol or avg_vol <= 0:
        return "Volume data unavailable for this period.", 0.0
    breakout_vol = df["volume"].iloc[breakout_pos]
    ratio = breakout_vol / avg_vol
    if ratio >= 1.2:
        return f"Breakout volume was {ratio:.1f}x the pattern's average -- corroborates the move.", 0.05
    if ratio <= 0.8:
        return f"Breakout volume was only {ratio:.1f}x the pattern's average -- weak confirmation.", -0.05
    return f"Breakout volume was {ratio:.1f}x the pattern's average -- unremarkable, no strong signal either way.", 0.0


def _prior_trend_bias(df: pd.DataFrame, pos: int, lookback: int = 20, threshold_pct: float = 0.02) -> str:
    """Was price trending up, down, or sideways in the `lookback` bars
    immediately before `pos`? Used for patterns whose directional bias
    depends on context rather than shape alone (symmetrical triangles,
    per the reference guide: "breakout direction isn't guaranteed by the
    shape alone -- context (prior trend) sets the bias"). Returns
    "Bullish", "Bearish", or "Neutral"."""
    start = max(0, pos - lookback)
    if start >= pos:
        return "Neutral"
    change_pct = (df["close"].iloc[pos] - df["close"].iloc[start]) / df["close"].iloc[start]
    if change_pct > threshold_pct:
        return "Bullish"
    if change_pct < -threshold_pct:
        return "Bearish"
    return "Neutral"


def detect_double_top_bottom(
    df: pd.DataFrame,
    window: int = 5,
    peak_tolerance_pct: float = 0.03,
    min_trough_depth_pct: float = 0.03,
    min_separation_bars: int | None = None,
) -> list[dict]:
    """Double top: two swing highs of similar price with a meaningfully
    lower swing low between them ("M" shape). Double bottom is the mirror
    ("W" shape).

    ASSUMPTIONS: "similar price" = within `peak_tolerance_pct` (default
    3%) of each other. "Meaningfully lower" trough = at least
    `min_trough_depth_pct` (default 3%) below the average of the two
    peaks. Peaks must be at least `min_separation_bars` apart (defaults
    to 2x the swing window) so the two peaks aren't just noise around the
    same local high. For each first peak, only the nearest qualifying
    second peak is matched (to avoid reporting many overlapping matches
    for the same visual shape). Critically, the two matched peaks
    (troughs) must also be the two most extreme points across the *entire*
    span between them, checked against the raw high/low series rather
    than only the sampled swing points -- without this, two swing highs
    of similar price with an even bigger rally in between would still
    "match" on paper while looking nothing like an M-shaped double top
    (this was caught by rendering and eyeballing real matches during
    Stage 3 verification, see BUILD_SPEC.md).

    Per the reference guide, confirmation is a close beyond the neckline
    (the intermediate trough for a double top, peak for a double bottom)
    -- checked here against every bar after the second peak/trough using
    the actual data, not assumed. Directional bias is fixed by
    definition (double top = Bearish, double bottom = Bullish).
    """
    if min_separation_bars is None:
        min_separation_bars = window * 2

    points = get_swing_points(df, window=window)
    highs = [p for p in points if p["type"] == "high"]
    lows = [p for p in points if p["type"] == "low"]
    matches = []

    for i, h1 in enumerate(highs):
        for h2 in highs[i + 1 :]:
            if h2["pos"] - h1["pos"] < min_separation_bars:
                continue
            avg_peak = (h1["price"] + h2["price"]) / 2
            price_diff_pct = abs(h1["price"] - h2["price"]) / avg_peak
            if price_diff_pct > peak_tolerance_pct:
                continue
            span_high = df["high"].iloc[h1["pos"] : h2["pos"] + 1].max()
            if span_high > max(h1["price"], h2["price"]) * 1.001:
                continue  # something in between spiked higher than both peaks -- not an M shape
            between = [l for l in lows if h1["pos"] < l["pos"] < h2["pos"]]
            if not between:
                continue
            trough = min(between, key=lambda l: l["price"])
            depth_pct = (avg_peak - trough["price"]) / avg_peak
            if depth_pct < min_trough_depth_pct:
                continue
            confidence = _confidence(
                price_diff_pct / peak_tolerance_pct,
                max(0.0, 1 - (depth_pct - min_trough_depth_pct) / min_trough_depth_pct),
            )
            neckline_price = trough["price"]
            breakout_pos = _find_breakout(df, h2["pos"] + 1, lambda p: neckline_price, "below")
            volume_note, vol_adjust = _volume_note(df, h1["pos"], h2["pos"], breakout_pos)
            matches.append(
                {
                    "name": "Double Top",
                    "start": h1["time"],
                    "end": h2["time"],
                    "confidence": _clamp_confidence(confidence + vol_adjust),
                    "detail": (
                        f"Peaks {h1['price']:.2f} ({h1['time'].date()}) and "
                        f"{h2['price']:.2f} ({h2['time'].date()}), {price_diff_pct:.1%} apart, "
                        f"trough {trough['price']:.2f} ({depth_pct:.1%} below peak average)"
                    ),
                    "directional_bias": "Bearish",
                    "status": "Confirmed" if breakout_pos is not None else "Forming",
                    "confirmation_date": df.index[breakout_pos] if breakout_pos is not None else None,
                    "volume_note": volume_note,
                }
            )
            break  # nearest qualifying second peak only

    for i, l1 in enumerate(lows):
        for l2 in lows[i + 1 :]:
            if l2["pos"] - l1["pos"] < min_separation_bars:
                continue
            avg_trough = (l1["price"] + l2["price"]) / 2
            price_diff_pct = abs(l1["price"] - l2["price"]) / avg_trough
            if price_diff_pct > peak_tolerance_pct:
                continue
            span_low = df["low"].iloc[l1["pos"] : l2["pos"] + 1].min()
            if span_low < min(l1["price"], l2["price"]) * 0.999:
                continue  # something in between dropped lower than both troughs -- not a W shape
            between = [h for h in highs if l1["pos"] < h["pos"] < l2["pos"]]
            if not between:
                continue
            peak = max(between, key=lambda h: h["price"])
            height_pct = (peak["price"] - avg_trough) / avg_trough
            if height_pct < min_trough_depth_pct:
                continue
            confidence = _confidence(
                price_diff_pct / peak_tolerance_pct,
                max(0.0, 1 - (height_pct - min_trough_depth_pct) / min_trough_depth_pct),
            )
            neckline_price = peak["price"]
            breakout_pos = _find_breakout(df, l2["pos"] + 1, lambda p: neckline_price, "above")
            volume_note, vol_adjust = _volume_note(df, l1["pos"], l2["pos"], breakout_pos)
            matches.append(
                {
                    "name": "Double Bottom",
                    "start": l1["time"],
                    "end": l2["time"],
                    "confidence": _clamp_confidence(confidence + vol_adjust),
                    "detail": (
                        f"Troughs {l1['price']:.2f} ({l1['time'].date()}) and "
                        f"{l2['price']:.2f} ({l2['time'].date()}), {price_diff_pct:.1%} apart, "
                        f"peak {peak['price']:.2f} ({height_pct:.1%} above trough average)"
                    ),
                    "directional_bias": "Bullish",
                    "status": "Confirmed" if breakout_pos is not None else "Forming",
                    "confirmation_date": df.index[breakout_pos] if breakout_pos is not None else None,
                    "volume_note": volume_note,
                }
            )
            break

    return matches


def detect_head_and_shoulders(
    df: pd.DataFrame,
    window: int = 5,
    shoulder_tolerance_pct: float = 0.06,
    min_head_prominence_pct: float = 0.03,
) -> list[dict]:
    """Head and shoulders: three consecutive swing highs where the middle
    one (head) is higher than both outer ones (shoulders), and the two
    shoulders are roughly level. Inverse head and shoulders is the mirror
    using swing lows (head is the lowest of the three).

    ASSUMPTIONS: "roughly level" shoulders = within `shoulder_tolerance_pct`
    (default 6% -- shoulders are visually allowed more slack than a double
    top's twin peaks) of each other. "Higher/lower" head = at least
    `min_head_prominence_pct` (default 3%) more extreme than both
    shoulders. Only consecutive swing highs (with nothing in between) are
    considered for the three peaks/troughs, matching how the pattern is
    drawn visually.

    Confirmation, per the reference guide, is a close beyond the neckline
    connecting the two troughs (H&S) or two peaks (inverse H&S) between
    the shoulders and head. The neckline is not assumed flat -- it's the
    actual line through those two points, evaluated at each bar position.
    """
    points = get_swing_points(df, window=window)
    highs = [p for p in points if p["type"] == "high"]
    lows = [p for p in points if p["type"] == "low"]
    matches = []

    def neckline_fn(p1: dict, p2: dict):
        if p2["pos"] == p1["pos"]:
            return lambda pos: p1["price"]
        slope = (p2["price"] - p1["price"]) / (p2["pos"] - p1["pos"])
        return lambda pos: p1["price"] + slope * (pos - p1["pos"])

    for i in range(len(highs) - 2):
        s1, head, s2 = highs[i], highs[i + 1], highs[i + 2]
        if not (head["price"] > s1["price"] and head["price"] > s2["price"]):
            continue
        shoulder_avg = (s1["price"] + s2["price"]) / 2
        shoulder_diff_pct = abs(s1["price"] - s2["price"]) / shoulder_avg
        if shoulder_diff_pct > shoulder_tolerance_pct:
            continue
        prominence_pct = min(
            (head["price"] - s1["price"]) / s1["price"],
            (head["price"] - s2["price"]) / s2["price"],
        )
        if prominence_pct < min_head_prominence_pct:
            continue
        span_high = df["high"].iloc[s1["pos"] : s2["pos"] + 1].max()
        if span_high > head["price"] * 1.001:
            continue  # head must be the single highest point of the whole span
        neckline = [l for l in lows if s1["pos"] < l["pos"] < s2["pos"]]
        if len(neckline) < 2:
            continue
        confidence = _confidence(
            shoulder_diff_pct / shoulder_tolerance_pct,
            max(0.0, 1 - (prominence_pct - min_head_prominence_pct) / min_head_prominence_pct),
        )
        level_at = neckline_fn(neckline[0], neckline[-1])
        breakout_pos = _find_breakout(df, s2["pos"] + 1, level_at, "below")
        volume_note, vol_adjust = _volume_note(df, s1["pos"], s2["pos"], breakout_pos)
        matches.append(
            {
                "name": "Head and Shoulders",
                "start": s1["time"],
                "end": s2["time"],
                "confidence": _clamp_confidence(confidence + vol_adjust),
                "detail": (
                    f"Shoulders {s1['price']:.2f} ({s1['time'].date()}) / "
                    f"{s2['price']:.2f} ({s2['time'].date()}), "
                    f"head {head['price']:.2f} ({head['time'].date()}), "
                    f"{shoulder_diff_pct:.1%} shoulder difference"
                ),
                "directional_bias": "Bearish",
                "status": "Confirmed" if breakout_pos is not None else "Forming",
                "confirmation_date": df.index[breakout_pos] if breakout_pos is not None else None,
                "volume_note": volume_note,
            }
        )

    for i in range(len(lows) - 2):
        s1, head, s2 = lows[i], lows[i + 1], lows[i + 2]
        if not (head["price"] < s1["price"] and head["price"] < s2["price"]):
            continue
        shoulder_avg = (s1["price"] + s2["price"]) / 2
        shoulder_diff_pct = abs(s1["price"] - s2["price"]) / shoulder_avg
        if shoulder_diff_pct > shoulder_tolerance_pct:
            continue
        prominence_pct = min(
            (s1["price"] - head["price"]) / head["price"],
            (s2["price"] - head["price"]) / head["price"],
        )
        if prominence_pct < min_head_prominence_pct:
            continue
        span_low = df["low"].iloc[s1["pos"] : s2["pos"] + 1].min()
        if span_low < head["price"] * 0.999:
            continue  # head must be the single lowest point of the whole span
        neckline = [h for h in highs if s1["pos"] < h["pos"] < s2["pos"]]
        if len(neckline) < 2:
            continue
        confidence = _confidence(
            shoulder_diff_pct / shoulder_tolerance_pct,
            max(0.0, 1 - (prominence_pct - min_head_prominence_pct) / min_head_prominence_pct),
        )
        level_at = neckline_fn(neckline[0], neckline[-1])
        breakout_pos = _find_breakout(df, s2["pos"] + 1, level_at, "above")
        volume_note, vol_adjust = _volume_note(df, s1["pos"], s2["pos"], breakout_pos)
        matches.append(
            {
                "name": "Inverse Head and Shoulders",
                "start": s1["time"],
                "end": s2["time"],
                "confidence": _clamp_confidence(confidence + vol_adjust),
                "detail": (
                    f"Shoulders {s1['price']:.2f} ({s1['time'].date()}) / "
                    f"{s2['price']:.2f} ({s2['time'].date()}), "
                    f"head {head['price']:.2f} ({head['time'].date()}), "
                    f"{shoulder_diff_pct:.1%} shoulder difference"
                ),
                "directional_bias": "Bullish",
                "status": "Confirmed" if breakout_pos is not None else "Forming",
                "confirmation_date": df.index[breakout_pos] if breakout_pos is not None else None,
                "volume_note": volume_note,
            }
        )

    return matches


def detect_triangles(
    df: pd.DataFrame,
    window: int = 5,
    lookback_bars: int = 60,
    flat_slope_threshold: float = 0.0006,
) -> list[dict]:
    """Ascending/descending/symmetrical triangle over the most recent
    `lookback_bars` (default 60, roughly a quarter of daily bars). Fits a
    straight line (least squares) through the recent swing highs and,
    separately, the recent swing lows, then classifies by slope:
    - Ascending: highs ~flat (resistance), lows rising (support) -- buyers
      stepping in at higher prices under a fixed ceiling.
    - Descending: highs falling (resistance), lows ~flat (support) -- the
      mirror image.
    - Symmetrical: highs falling AND lows rising -- converging trendlines.

    ASSUMPTIONS: needs at least 2 swing highs and 2 swing lows within the
    lookback window to fit a line at all. Slopes are normalized by the
    window's average close price (giving a %-per-bar slope) so the "flat"
    threshold (default 0.06%/bar) is comparable across tickers at very
    different price levels. This only ever reports the single
    highest-confidence pattern found in the current lookback window, not
    triangles that formed and completed earlier in the series --
    exhaustively scanning every possible window for historical triangles
    was judged out of scope for an MVP pattern scanner.

    Directional bias: ascending = Bullish, descending = Bearish (the
    reference guide's "typical" reading for these -- it notes both can
    occasionally act as reversals in the opposite context, which this
    detector doesn't attempt to distinguish). Symmetrical triangles have
    no inherent bias by shape alone per the guide -- "context (prior
    trend) sets the bias" -- so bias is derived from the 20-bar trend
    immediately before the triangle started (`_prior_trend_bias`); if
    that's ambiguous, bias stays "Neutral" and confirmation is checked
    against whichever trendline breaks first, with the bias assigned
    retroactively from the breakout direction (mirroring how the guide
    treats its neutral/bilateral patterns).

    Confirmation is a close beyond the *actual fitted trendline's*
    extrapolated value at that bar (not a flat snapshot of the swing
    prices), matching how a real ascending/descending resistance or
    support line moves over time.
    """
    if len(df) < lookback_bars:
        return []

    recent_start_pos = len(df) - lookback_bars
    points = get_swing_points(df, window=window)
    recent = [p for p in points if p["pos"] >= recent_start_pos]
    highs = [p for p in recent if p["type"] == "high"]
    lows = [p for p in recent if p["type"] == "low"]
    if len(highs) < 2 or len(lows) < 2:
        return []

    avg_price = float(df["close"].iloc[recent_start_pos:].mean())
    high_fit = np.polyfit([p["pos"] for p in highs], [p["price"] for p in highs], 1)
    low_fit = np.polyfit([p["pos"] for p in lows], [p["price"] for p in lows], 1)
    high_slope = high_fit[0] / avg_price
    low_slope = low_fit[0] / avg_price
    resistance_at = lambda pos: high_fit[0] * pos + high_fit[1]
    support_at = lambda pos: low_fit[0] * pos + low_fit[1]

    high_flat = abs(high_slope) < flat_slope_threshold
    low_flat = abs(low_slope) < flat_slope_threshold

    if high_flat and low_slope > flat_slope_threshold:
        name = "Ascending Triangle"
    elif high_slope < -flat_slope_threshold and low_flat:
        name = "Descending Triangle"
    elif high_slope < -flat_slope_threshold and low_slope > flat_slope_threshold:
        name = "Symmetrical Triangle"
    else:
        return []

    start = min(highs[0]["time"], lows[0]["time"])
    end_pos = max(highs[-1]["pos"], lows[-1]["pos"])
    end = df.index[end_pos]

    def slope_margin(slope, want_flat):
        if want_flat:
            return abs(slope) / flat_slope_threshold
        return max(0.0, 1 - (abs(slope) - flat_slope_threshold) / (2 * flat_slope_threshold))

    if name == "Ascending Triangle":
        confidence = _confidence(slope_margin(high_slope, True), slope_margin(low_slope, False))
        bias = "Bullish"
        breakout_pos = _find_breakout(df, end_pos + 1, resistance_at, "above")
    elif name == "Descending Triangle":
        confidence = _confidence(slope_margin(high_slope, False), slope_margin(low_slope, True))
        bias = "Bearish"
        breakout_pos = _find_breakout(df, end_pos + 1, support_at, "below")
    else:
        confidence = _confidence(slope_margin(high_slope, False), slope_margin(low_slope, False))
        bias = _prior_trend_bias(df, recent_start_pos)
        up_break = _find_breakout(df, end_pos + 1, resistance_at, "above")
        down_break = _find_breakout(df, end_pos + 1, support_at, "below")
        if up_break is not None and (down_break is None or up_break <= down_break):
            breakout_pos, bias = up_break, "Bullish"
            name = "Bullish Symmetrical Triangle"
        elif down_break is not None:
            breakout_pos, bias = down_break, "Bearish"
            name = "Bearish Symmetrical Triangle"
        else:
            breakout_pos = None
            name = f"{bias} Symmetrical Triangle" if bias != "Neutral" else "Symmetrical Triangle"

    volume_note, vol_adjust = _volume_note(df, recent_start_pos, end_pos, breakout_pos)

    return [
        {
            "name": name,
            "start": start,
            "end": end,
            "confidence": _clamp_confidence(confidence + vol_adjust),
            "detail": (
                f"Resistance slope {high_slope * 100:.3f}%/bar, "
                f"support slope {low_slope * 100:.3f}%/bar over last {lookback_bars} bars"
            ),
            "directional_bias": bias,
            "status": "Confirmed" if breakout_pos is not None else "Forming",
            "confirmation_date": df.index[breakout_pos] if breakout_pos is not None else None,
            "volume_note": volume_note,
        }
    ]


def detect_flags_pennants(
    df: pd.DataFrame,
    pole_window: int = 10,
    min_pole_move_pct: float = 0.08,
    consolidation_window: int = 10,
    max_consolidation_range_pct: float = 0.06,
) -> list[dict]:
    """Flag/pennant: a sharp directional move (the "pole") over
    `pole_window` bars, immediately followed by `consolidation_window`
    bars of tight sideways/counter-trend drift (the "flag"/"pennant").
    Classified as a pennant if the consolidation's high/low trendlines
    converge (like a small triangle), a flag if they run roughly parallel.

    ASSUMPTIONS: a "sharp move" is a >= `min_pole_move_pct` (default 8%)
    change in close price over `pole_window` bars (default 10). "Tight"
    consolidation = the following `consolidation_window` bars (default
    10) stay within `max_consolidation_range_pct` (default 6%) of their
    own mean price. Overlapping candidate poles are common (a strong move
    looks like a valid pole from many nearby starting points); only the
    single strongest (largest |move|) pole ending in any given
    `pole_window`-bar span is kept, to avoid reporting near-duplicates of
    the same visual move.

    Directional bias matches the pole direction (Bull* = Bullish, Bear* =
    Bearish). Confirmation, per the reference guide, is a close beyond
    the consolidation's own high/low channel in the pole's direction.
    """
    n = len(df)
    closes = df["close"].to_numpy()
    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    candidates = []

    for pole_end in range(pole_window, n - consolidation_window):
        pole_start = pole_end - pole_window
        pole_change_pct = (closes[pole_end] - closes[pole_start]) / closes[pole_start]
        if abs(pole_change_pct) < min_pole_move_pct:
            continue

        cons_highs = highs[pole_end : pole_end + consolidation_window]
        cons_lows = lows[pole_end : pole_end + consolidation_window]
        cons_mean = closes[pole_end : pole_end + consolidation_window].mean()
        cons_range_pct = (cons_highs.max() - cons_lows.min()) / cons_mean
        if cons_range_pct > max_consolidation_range_pct:
            continue

        x = np.arange(consolidation_window)
        high_slope = np.polyfit(x, cons_highs, 1)[0] / cons_mean
        low_slope = np.polyfit(x, cons_lows, 1)[0] / cons_mean
        # Converging = the gap between the two trendlines is shrinking,
        # i.e. slopes move toward each other regardless of direction.
        converging = (cons_highs[0] - cons_lows[0]) > (cons_highs[-1] - cons_lows[-1])
        direction = "Bull" if pole_change_pct > 0 else "Bear"
        shape = "Pennant" if converging else "Flag"

        candidates.append(
            {
                "pole_start": pole_start,
                "pole_end": pole_end,
                "cons_end": pole_end + consolidation_window - 1,
                "pole_change_pct": pole_change_pct,
                "cons_range_pct": cons_range_pct,
                "cons_high": float(cons_highs.max()),
                "cons_low": float(cons_lows.min()),
                "name": f"{direction} {shape}",
                "bias": "Bullish" if direction == "Bull" else "Bearish",
            }
        )

    # Non-maximum suppression: within any window of `pole_window` bars,
    # keep only the candidate with the strongest pole move.
    candidates.sort(key=lambda c: -abs(c["pole_change_pct"]))
    kept = []
    for c in candidates:
        if all(abs(c["pole_end"] - k["pole_end"]) >= pole_window for k in kept):
            kept.append(c)

    matches = []
    for c in sorted(kept, key=lambda c: c["pole_start"]):
        confidence = _confidence(
            max(0.0, 1 - (abs(c["pole_change_pct"]) - min_pole_move_pct) / min_pole_move_pct),
            c["cons_range_pct"] / max_consolidation_range_pct,
        )
        if c["bias"] == "Bullish":
            breakout_pos = _find_breakout(df, c["cons_end"] + 1, lambda p: c["cons_high"], "above")
        else:
            breakout_pos = _find_breakout(df, c["cons_end"] + 1, lambda p: c["cons_low"], "below")
        volume_note, vol_adjust = _volume_note(df, c["pole_end"], c["cons_end"], breakout_pos)
        matches.append(
            {
                "name": c["name"],
                "start": df.index[c["pole_start"]],
                "end": df.index[c["cons_end"]],
                "confidence": _clamp_confidence(confidence + vol_adjust),
                "detail": (
                    f"Pole move {c['pole_change_pct']:.1%} over {pole_window} bars, "
                    f"consolidation range {c['cons_range_pct']:.1%}"
                ),
                "directional_bias": c["bias"],
                "status": "Confirmed" if breakout_pos is not None else "Forming",
                "confirmation_date": df.index[breakout_pos] if breakout_pos is not None else None,
                "volume_note": volume_note,
            }
        )
    return matches


def detect_cup_and_handle(
    df: pd.DataFrame,
    window: int = 5,
    rim_tolerance_pct: float = 0.05,
    min_cup_depth_pct: float = 0.10,
    max_cup_depth_pct: float = 0.50,
    min_cup_bars: int = 20,
    max_handle_bars: int = 20,
    max_handle_depth_pct: float = 0.20,
) -> list[dict]:
    """Cup and handle: price falls from a swing high (left rim) to a
    swing low (the cup bottom), recovers to a swing high near the left
    rim's price (right rim -- the "U" shape), then pulls back shallowly
    for a short "handle" before a breakout above the rim.

    ASSUMPTIONS: this is one of the fuzziest classical patterns to define
    algorithmically -- real chartists judge how "rounded" the cup looks
    visually, which this doesn't attempt to measure directly.
    - Left/right rim = swing highs within `rim_tolerance_pct` (default
      5%, looser than double-top's 3% since the cup's recovery doesn't
      need to retest as precisely) of each other, separated by at least
      `min_cup_bars` (default 20) bars, with a swing low (the cup bottom)
      between them that isn't right at either edge (at least a quarter of
      `min_cup_bars` in from both sides, so the shape has a genuine base
      rather than a sharp V pinned to one rim).
    - Cup depth (rim average to bottom) must fall between
      `min_cup_depth_pct` and `max_cup_depth_pct` (10%-50%) -- shallower
      isn't really a cup, deeper starts to look like a different (likely
      bearish) structure entirely.
    - The handle is the price action in the `max_handle_bars` (default
      20) bars after the right rim: it must stay within
      `max_handle_depth_pct` (default 20%) of the rim without falling
      back to or past the cup bottom -- a pullback that deep isn't a
      "handle", it's the cup failing.
    - Confirmation is a close above the higher of the two rims, scanned
      for after the handle window closes, consistent with every other
      detector here treating "confirmed" as a close beyond the pattern's
      defining level.

    Directional bias is always Bullish -- unlike triangles or flags, this
    pattern doesn't have a bearish mirror image in standard usage.
    """
    points = get_swing_points(df, window=window)
    highs = [p for p in points if p["type"] == "high"]
    lows = [p for p in points if p["type"] == "low"]
    matches = []

    for i, left in enumerate(highs):
        for right in highs[i + 1 :]:
            if right["pos"] - left["pos"] < min_cup_bars:
                continue
            rim_avg = (left["price"] + right["price"]) / 2
            rim_diff_pct = abs(left["price"] - right["price"]) / rim_avg
            if rim_diff_pct > rim_tolerance_pct:
                continue

            between_lows = [l for l in lows if left["pos"] < l["pos"] < right["pos"]]
            if not between_lows:
                continue
            bottom = min(between_lows, key=lambda l: l["price"])
            edge_margin = max(1, min_cup_bars // 4)
            if bottom["pos"] - left["pos"] < edge_margin or right["pos"] - bottom["pos"] < edge_margin:
                continue  # bottom sits right at one rim -- a V, not a rounded cup
            depth_pct = (rim_avg - bottom["price"]) / rim_avg
            if not (min_cup_depth_pct <= depth_pct <= max_cup_depth_pct):
                continue

            handle_end_pos = min(right["pos"] + max_handle_bars, len(df) - 1)
            handle_low = float(df["low"].iloc[right["pos"] : handle_end_pos + 1].min())
            if handle_low <= bottom["price"]:
                continue  # pullback erased the whole cup -- not a handle
            rim_level = max(left["price"], right["price"])
            handle_depth_pct = (rim_level - handle_low) / rim_level
            if handle_depth_pct > max_handle_depth_pct:
                continue

            confidence = _confidence(
                rim_diff_pct / rim_tolerance_pct,
                handle_depth_pct / max_handle_depth_pct,
            )
            breakout_pos = _find_breakout(df, handle_end_pos + 1, lambda p: rim_level, "above")
            volume_note, vol_adjust = _volume_note(df, left["pos"], handle_end_pos, breakout_pos)
            matches.append(
                {
                    "name": "Cup and Handle",
                    "start": left["time"],
                    "end": df.index[handle_end_pos],
                    "confidence": _clamp_confidence(confidence + vol_adjust),
                    "detail": (
                        f"Rims {left['price']:.2f} ({left['time'].date()}) / "
                        f"{right['price']:.2f} ({right['time'].date()}), cup bottom "
                        f"{bottom['price']:.2f} ({depth_pct:.1%} deep), handle pulled back "
                        f"{handle_depth_pct:.1%} from the rim"
                    ),
                    "directional_bias": "Bullish",
                    "status": "Confirmed" if breakout_pos is not None else "Forming",
                    "confirmation_date": df.index[breakout_pos] if breakout_pos is not None else None,
                    "volume_note": volume_note,
                }
            )
            break  # nearest qualifying right rim only, like double-top/bottom

    return matches


def detect_ma_crossovers(df: pd.DataFrame, fast: int = 50, slow: int = 200) -> list[dict]:
    """Wraps the golden/death cross detection already computed in
    app.indicators.ma_crossovers (Stage 2) into the same pattern-match
    shape as the other detectors, so the API and frontend can treat all
    detected patterns uniformly. These are exact crossings of computed
    SMAs, not a fuzzy shape match, so confidence is fixed at the ceiling.
    The crossover itself IS the event (there's no separate "shape" to
    later confirm), so status is always "Confirmed". This pattern isn't
    in the reference guide at all -- it's a moving-average signal, not a
    price-shape pattern -- so there's no volume-corroboration convention
    to apply here.
    """
    crosses = ma_crossovers(df, fast=fast, slow=slow)
    matches = []
    for idx in crosses.index[crosses["golden_cross"]]:
        matches.append(
            {
                "name": "Golden Cross",
                "start": idx,
                "end": idx,
                "confidence": _CONF_CEIL,
                "detail": f"SMA{fast} crossed above SMA{slow} on {idx.date()}",
                "directional_bias": "Bullish",
                "status": "Confirmed",
                "confirmation_date": idx,
                "volume_note": "Not applicable -- a moving-average crossover, not a price-shape pattern.",
            }
        )
    for idx in crosses.index[crosses["death_cross"]]:
        matches.append(
            {
                "name": "Death Cross",
                "start": idx,
                "end": idx,
                "confidence": _CONF_CEIL,
                "detail": f"SMA{fast} crossed below SMA{slow} on {idx.date()}",
                "directional_bias": "Bearish",
                "status": "Confirmed",
                "confirmation_date": idx,
                "volume_note": "Not applicable -- a moving-average crossover, not a price-shape pattern.",
            }
        )
    return matches


def _suppress_overlaps(matches: list[dict]) -> list[dict]:
    """Within each pattern name, keep only the highest-confidence match
    for any given date range, dropping others that substantially overlap
    it. Choppy/sideways price action can satisfy the double-top/bottom
    and head-and-shoulders thresholds many times over on overlapping
    swing pairs (each individually a valid reading of *some* two peaks or
    troughs) -- reporting all of them would bury the strongest read of
    the same visual region under near-duplicates.
    """
    by_name: dict[str, list[dict]] = {}
    for m in matches:
        by_name.setdefault(m["name"], []).append(m)

    kept = []
    for name, group in by_name.items():
        group.sort(key=lambda m: -m["confidence"])
        accepted: list[dict] = []
        for m in group:
            overlaps = any(m["start"] <= a["end"] and a["start"] <= m["end"] for a in accepted)
            if not overlaps:
                accepted.append(m)
        kept.extend(accepted)
    return kept


def detect_all(df: pd.DataFrame, window: int = 5) -> list[dict]:
    """Run every detector and return all matches, most recent first, with
    overlapping same-name matches suppressed down to the strongest one
    (see `_suppress_overlaps`)."""
    matches = [
        *detect_double_top_bottom(df, window=window),
        *detect_head_and_shoulders(df, window=window),
        *detect_cup_and_handle(df, window=window),
        *detect_triangles(df, window=window),
        *detect_flags_pennants(df),
        *detect_ma_crossovers(df),
    ]
    matches = _suppress_overlaps(matches)
    matches.sort(key=lambda m: m["end"], reverse=True)
    return matches
