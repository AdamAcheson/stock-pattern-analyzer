"""Stage 3 verification helper #2: render a chart with a specific
detected pattern's date range shaded and its constituent swing points
marked, so the match can be checked by eye against the actual price
shape -- per the project's feedback-loop protocol ("does the detected
pattern actually correspond to a visible shape in the price series?").
"""

import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from app.data_fetch import fetch_ohlcv
from app.pattern_detection import detect_all, get_swing_points


def render(ticker: str, timeframe: str, pattern_name: str, out_path: str, match_index: int = 0):
    df = fetch_ohlcv(ticker, timeframe)
    matches = [m for m in detect_all(df) if m["name"] == pattern_name]
    if not matches:
        print(f"No '{pattern_name}' match found for {ticker} {timeframe}")
        return
    match = matches[match_index]

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(df.index, df["close"], color="#2563eb", linewidth=1.2, label="Close")

    swings = get_swing_points(df)
    swing_highs = [p for p in swings if p["type"] == "high"]
    swing_lows = [p for p in swings if p["type"] == "low"]
    ax.scatter([p["time"] for p in swing_highs], [p["price"] for p in swing_highs],
               color="#dc2626", marker="v", s=40, zorder=5, label="Swing high")
    ax.scatter([p["time"] for p in swing_lows], [p["price"] for p in swing_lows],
               color="#16a34a", marker="^", s=40, zorder=5, label="Swing low")

    ax.axvspan(match["start"], match["end"], color="#facc15", alpha=0.25, label="Detected pattern range")

    ax.set_title(
        f"{ticker} {timeframe} — {pattern_name} (confidence {match['confidence']:.2f})\n{match['detail']}",
        fontsize=10,
    )
    ax.legend(loc="best", fontsize=8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out_path, dpi=110)
    plt.close(fig)
    print(f"Saved {out_path}")


if __name__ == "__main__":
    ticker, timeframe, pattern_name, out_path = sys.argv[1:5]
    match_index = int(sys.argv[5]) if len(sys.argv) > 5 else 0
    render(ticker, timeframe, pattern_name, out_path, match_index)
