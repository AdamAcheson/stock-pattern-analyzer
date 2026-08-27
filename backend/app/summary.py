"""Plain-English synthesis of the indicator values and detected patterns.

This is NOT a prediction engine and does not call any external model --
it's a deterministic, rule-based generator that turns the numbers
already computed in Stages 2-3 into readable sentences that cite those
exact numbers. The project brief requires the summary to "reference the
specific indicator values and any detected patterns, not generic
boilerplate" -- every sentence below is built from a real value pulled
off the DataFrame/indicator dict for the ticker being analyzed, not a
static template with blanks filled in.

The synthesis step (`_synthesize`) is the one place where this module
makes a judgment call rather than just restating a number: it tallies a
handful of simple bullish/bearish signals (trend, momentum, confirmed
pattern bias) and says whether they agree or conflict. This is honest
bookkeeping ("2 of 3 signals lean bullish"), not a forecast -- and where
signals conflict, the summary says so explicitly rather than picking a
side, per the project brief's requirement to be honest about fuzziness
rather than falsely precise.
"""

from __future__ import annotations

import pandas as pd

DISCLAIMER = (
    "This is an automated technical read of historical price data, not a recommendation "
    "to buy, sell, or hold any security, and it is not financial advice. Technical "
    "indicators and chart patterns are inherently imprecise and backward-looking -- "
    "past price action does not predict future results."
)


def _last_valid(series: pd.Series) -> float | None:
    valid = series.dropna()
    return float(valid.iloc[-1]) if not valid.empty else None


def _confidence_word(confidence: float) -> str:
    if confidence >= 0.65:
        return "high"
    if confidence >= 0.45:
        return "moderate"
    return "low"


def _describe_trend(df: pd.DataFrame, ind: dict, timeframe: str) -> tuple[str, str]:
    """Returns (sentence, signal) where signal is 'bullish'/'bearish'/'mixed'."""
    close = float(df["close"].iloc[-1])
    period_start = float(df["close"].iloc[0])
    period_change_pct = (close / period_start - 1) * 100

    sma20 = _last_valid(ind["sma_20"])
    sma50 = _last_valid(ind["sma_50"])
    sma200 = _last_valid(ind["sma_200"])

    parts = [
        f"Price closed at ${close:.2f}, {period_change_pct:+.1f}% over this {timeframe} window."
    ]

    available_smas = [(label, v) for label, v in [("20-day", sma20), ("50-day", sma50), ("200-day", sma200)] if v is not None]
    if available_smas:
        above = [label for label, v in available_smas if close > v]
        below = [label for label, v in available_smas if close <= v]
        if above:
            parts.append(f"Price is above its {', '.join(above)} SMA{'s' if len(above) > 1 else ''} " + "(" + ", ".join(f"${v:.2f}" for label, v in available_smas if label in above) + ").")
        if below:
            parts.append(f"Price is below its {', '.join(below)} SMA{'s' if len(below) > 1 else ''} " + "(" + ", ".join(f"${v:.2f}" for label, v in available_smas if label in below) + ").")

    signal = "mixed"
    if sma50 is not None and sma200 is not None:
        if sma50 > sma200:
            parts.append(
                f"The 50-day SMA (${sma50:.2f}) sits above the 200-day SMA (${sma200:.2f}) -- "
                "the configuration a golden cross produces, generally read as a longer-term uptrend."
            )
            signal = "bullish" if close > sma50 else "mixed"
        else:
            parts.append(
                f"The 50-day SMA (${sma50:.2f}) sits below the 200-day SMA (${sma200:.2f}) -- "
                "the configuration a death cross produces, generally read as a longer-term downtrend."
            )
            signal = "bearish" if close < sma50 else "mixed"
    elif sma20 is not None:
        signal = "bullish" if close > sma20 else "bearish"

    return " ".join(parts), signal


def _describe_momentum(ind: dict) -> tuple[str, str]:
    """Returns (sentence, signal) where signal is 'bullish'/'bearish'/'neutral'."""
    rsi = _last_valid(ind["rsi_14"])
    macd_df = ind["macd"].dropna()

    parts = []
    signal_votes = []

    if rsi is not None:
        if rsi >= 70:
            zone = "overbought territory (RSI >= 70)"
            signal_votes.append("bearish")  # potential pullback risk, not a certainty
        elif rsi <= 30:
            zone = "oversold territory (RSI <= 30)"
            signal_votes.append("bullish")
        else:
            zone = "neutral territory"
        parts.append(f"RSI(14) is {rsi:.1f}, in {zone}.")

    if not macd_df.empty:
        last = macd_df.iloc[-1]
        if last["macd"] > last["signal"]:
            parts.append(
                f"MACD ({last['macd']:.2f}) is above its signal line ({last['signal']:.2f}), "
                "a bullish momentum reading."
            )
            signal_votes.append("bullish")
        else:
            parts.append(
                f"MACD ({last['macd']:.2f}) is below its signal line ({last['signal']:.2f}), "
                "a bearish momentum reading."
            )
            signal_votes.append("bearish")

    if not signal_votes:
        signal = "neutral"
    elif signal_votes.count("bullish") > signal_votes.count("bearish"):
        signal = "bullish"
    elif signal_votes.count("bearish") > signal_votes.count("bullish"):
        signal = "bearish"
    else:
        signal = "neutral"

    if not parts:
        parts.append("Not enough history in this window to compute momentum indicators.")

    return " ".join(parts), signal


def _describe_bands(df: pd.DataFrame, ind: dict) -> str:
    bb = ind["bollinger"].dropna()
    if bb.empty:
        return "Not enough history in this window to compute Bollinger Bands."
    last = bb.iloc[-1]
    close = float(df["close"].iloc[-1])
    band_width_pct = (last["upper"] - last["lower"]) / last["middle"] * 100
    if close >= last["upper"]:
        position = "at or above the upper band"
    elif close <= last["lower"]:
        position = "at or below the lower band"
    else:
        pct_through = (close - last["lower"]) / (last["upper"] - last["lower"]) * 100
        position = f"{pct_through:.0f}% of the way between the lower and upper bands"
    return (
        f"Price is {position} (lower ${last['lower']:.2f}, middle ${last['middle']:.2f}, "
        f"upper ${last['upper']:.2f}), a band width of {band_width_pct:.1f}% of the middle band."
    )


def _describe_patterns(patterns: list[dict], max_patterns: int = 5) -> tuple[str, list[dict]]:
    """Returns (sentence, confirmed_patterns) -- confirmed_patterns feeds the synthesis step."""
    if not patterns:
        return "No chart patterns were detected in this window.", []

    shown = patterns[:max_patterns]
    sentences = []
    for p in shown:
        conf_word = _confidence_word(p["confidence"])
        status_phrase = (
            f"confirmed by a breakout on {p['confirmation_date'].date()}"
            if p["status"] == "Confirmed" and p["confirmation_date"] is not None
            else "still forming and not yet confirmed by a breakout"
        )
        sentences.append(
            f"A {conf_word}-confidence {p['name']} ({p['directional_bias'].lower()} bias) "
            f"spanning {p['start'].date()} to {p['end'].date()} is {status_phrase}. {p['volume_note']}"
        )
    if len(patterns) > max_patterns:
        sentences.append(f"({len(patterns) - max_patterns} additional pattern(s) detected but not detailed here.)")

    confirmed = [p for p in patterns if p["status"] == "Confirmed"]
    return " ".join(sentences), confirmed


def _synthesize(trend_signal: str, momentum_signal: str, confirmed_patterns: list[dict]) -> str:
    pattern_bias_counts = {"Bullish": 0, "Bearish": 0}
    for p in confirmed_patterns:
        if p["directional_bias"] in pattern_bias_counts:
            pattern_bias_counts[p["directional_bias"]] += 1
    pattern_signal = (
        "bullish"
        if pattern_bias_counts["Bullish"] > pattern_bias_counts["Bearish"]
        else "bearish"
        if pattern_bias_counts["Bearish"] > pattern_bias_counts["Bullish"]
        else None
    )

    factors = [("trend", trend_signal), ("momentum", momentum_signal)]
    if pattern_signal is not None:
        factors.append(("confirmed patterns", pattern_signal))
    bullish_factors = [name for name, sig in factors if sig == "bullish"]
    bearish_factors = [name for name, sig in factors if sig == "bearish"]

    contributor_text = (
        f"trend reads {trend_signal}, momentum reads {momentum_signal}, "
        f"and confirmed patterns lean {pattern_signal or 'neither way'} "
        f"({pattern_bias_counts['Bullish']} bullish, {pattern_bias_counts['Bearish']} bearish confirmed)"
    )

    if not bullish_factors and not bearish_factors:
        return f"No clearly directional signal here: {contributor_text}."
    if len(bullish_factors) == len(bearish_factors):
        return (
            f"These signals are mixed, not a clean read in either direction: {contributor_text}. "
            "That disagreement is itself informative -- it suggests caution rather than conviction."
        )

    majority = "bullish" if len(bullish_factors) > len(bearish_factors) else "bearish"
    disagreeing = bearish_factors if majority == "bullish" else bullish_factors
    opposite = "bearish" if majority == "bullish" else "bullish"
    caveat = (
        f" Note that {' and '.join(disagreeing)} specifically read{'s' if len(disagreeing) == 1 else ''} "
        f"{opposite}, cutting against that overall lean."
        if disagreeing
        else ""
    )
    return (
        f"The available signals lean {majority} overall: {contributor_text}.{caveat} "
        "This is a description of what the data currently shows, not a forecast of what happens next."
    )


def generate_summary(ticker: str, timeframe: str, df: pd.DataFrame, ind: dict, patterns: list[dict]) -> dict:
    trend_text, trend_signal = _describe_trend(df, ind, timeframe)
    momentum_text, momentum_signal = _describe_momentum(ind)
    bands_text = _describe_bands(df, ind)
    patterns_text, confirmed_patterns = _describe_patterns(patterns)
    synthesis_text = _synthesize(trend_signal, momentum_signal, confirmed_patterns)

    return {
        "headline": f"{ticker} technical read over {timeframe}",
        "trend": trend_text,
        "momentum": momentum_text,
        "volatility": bands_text,
        "patterns": patterns_text,
        "synthesis": synthesis_text,
        "disclaimer": DISCLAIMER,
    }
