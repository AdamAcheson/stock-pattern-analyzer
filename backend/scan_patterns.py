"""Stage 3 verification helper #1: scan a broad set of tickers/timeframes
for pattern matches so we have real candidates to visually inspect,
rather than hoping a hand-picked ticker happens to show each pattern
type right now.
"""

from app.data_fetch import fetch_ohlcv
from app.pattern_detection import detect_all

TICKERS = ["AAPL", "TSLA", "NVDA", "MSFT", "AMZN", "GOOGL", "META", "AMD", "NFLX", "DIS", "BA", "PLTR", "COIN", "SOFI"]
TIMEFRAMES = ["1Y", "6M", "3M"]

found_by_pattern = {}

for ticker in TICKERS:
    for tf in TIMEFRAMES:
        try:
            df = fetch_ohlcv(ticker, tf)
        except Exception as e:
            print(f"SKIP {ticker} {tf}: {e}")
            continue
        matches = detect_all(df)
        for m in matches:
            name = m["name"]
            found_by_pattern.setdefault(name, []).append(
                {
                    "ticker": ticker,
                    "timeframe": tf,
                    "start": str(m["start"].date()),
                    "end": str(m["end"].date()),
                    "confidence": m["confidence"],
                    "detail": m["detail"],
                }
            )

for name, matches in found_by_pattern.items():
    print(f"\n=== {name}: {len(matches)} match(es) ===")
    for m in sorted(matches, key=lambda m: -m["confidence"])[:5]:
        print(f"  {m['ticker']:6s} {m['timeframe']:4s} conf={m['confidence']:.2f} {m['start']} -> {m['end']}  {m['detail']}")

missing = {"Double Top", "Double Bottom", "Head and Shoulders", "Inverse Head and Shoulders",
           "Ascending Triangle", "Descending Triangle", "Symmetrical Triangle",
           "Bull Flag", "Bear Flag", "Bull Pennant", "Bear Pennant",
           "Golden Cross", "Death Cross"} - set(found_by_pattern.keys())
print(f"\nPattern types with ZERO matches across scan: {sorted(missing)}")
