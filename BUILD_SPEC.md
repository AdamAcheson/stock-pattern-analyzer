# Build Spec: Stock Pattern & Technical Analysis Website

This is the original project prompt, preserved verbatim, plus a status
note on where the build currently stands. If you are a fresh Claude
Code session picking this up: read this whole file before doing
anything else, then check "Current Status" at the bottom for what's
done and what's next.

---

## Project Goal

Build a web app that analyzes a given stock ticker and shows:
1. **Technical indicators** (current values + historical chart overlays)
2. **Chart pattern detection** (identifies known patterns forming or recently completed in the price data)
3. **A synthesized read** combining both into a plain-English summary of what the data suggests (NOT financial advice — always label it as analysis, not a recommendation)

## Tech Stack

- **Backend**: Python (FastAPI) — handles data fetching, indicator math, and pattern detection
- **Frontend**: React + a charting library (lightweight-charts or recharts)
- **Data source**: yfinance (free, no API key) for OHLCV data. If rate limits or gaps become a problem during testing, fall back to Alpha Vantage or Polygon.io free tier and ask for an API key.
- **No database needed initially** — fetch on demand, cache in memory per session.

## Core Features

### 1. Ticker input + timeframe selector
User enters a ticker (e.g., AAPL) and picks a timeframe (1D/1W intraday granularity, up to 1Y/5Y daily).

### 2. Technical indicators to compute and display
- Moving averages: SMA 20/50/200, EMA 12/26
- RSI (14)
- MACD (12, 26, 9)
- Bollinger Bands (20, 2)
- Volume with a volume-weighted moving average
- Support/resistance levels (derived from recent swing highs/lows, not hardcoded)

### 3. Pattern detection
Detect and flag on the chart when these are present in the recent price action:
- Head and shoulders / inverse head and shoulders
- Double top / double bottom
- Ascending/descending/symmetrical triangles
- Flags and pennants
- Golden cross / death cross (MA crossovers)

Each detected pattern should show: name, approximate date range, and a confidence indicator (this is inherently fuzzy — be honest about that in the UI, not falsely precise).

### 4. Summary panel
A plain-language summary that references the specific indicator values and any detected patterns — not generic boilerplate. Explicitly state this is not investment advice.

## Feedback Loop Protocol (important — follow this workflow)

Don't build the entire app in one pass. Work in the following loop, and repeat it for each stage below:

1. **Build** a small, testable slice of functionality.
2. **Run it against real data** — pick 2-3 real tickers (e.g., AAPL, TSLA, and one you choose) and actually execute the code against live/recent data, not mocked data.
3. **Verify the output makes sense**: e.g., do the SMA values roughly match what's visible on a real chart from a source like Yahoo Finance? Does RSI stay within 0-100? Do detected patterns actually correspond to visible shapes in the price series?
4. **If something looks wrong, diagnose and fix it before moving to the next stage** — don't push forward with a known bug.
5. **Show me the verification results** (a short before/after or a summary of what you checked) before moving to the next stage, so I can catch anything you might miss.

Apply this loop to these stages in order:
1. Data fetching layer (confirm you're getting clean, correctly-ordered OHLCV data for multiple tickers and timeframes)
2. Indicator calculations (spot-check each indicator's math against a known reference value)
3. Pattern detection logic (test against tickers/date ranges with a known, visually obvious pattern before trusting it on arbitrary data)
4. Frontend chart rendering (confirm indicators and pattern flags actually align with the correct dates/prices on the chart — off-by-one errors here are common)
5. Summary generation (confirm the language matches what the data actually shows, not a templated response that ignores the numbers)

At the end, do one full end-to-end test with a ticker not yet mentioned during development, and walk through what it output and why, so it can be confirmed working before calling it done.

## Constraints & Notes

- Handle invalid tickers and missing data gracefully (clear error message, not a crash).
- Be explicit in code comments about which pattern-detection rules are heuristic approximations vs. precise math, since pattern detection is inherently judgment-based.
- Keep the UI clean and readable — this isn't a trading terminal, it's a research/learning tool.
- Flag any point where an assumption had to be made (e.g., how many bars define a "swing high") for review.

---

## Current Status (updated as the build progresses)

**Repo:** `AdamAcheson/stock-pattern-analyzer`, branch `main`.

**Stage 1 — Data fetching layer: code written, NOT YET LIVE-VERIFIED.**

What exists:
- `backend/app/data_fetch.py` — `fetch_ohlcv(ticker, timeframe)`: wraps
  `yfinance`, normalizes to a clean ascending-by-date DataFrame with
  columns `open, high, low, close, volume`, drops NaN/non-positive rows,
  strips timezone, distinguishes an invalid ticker (`InvalidTickerError`)
  from a valid ticker with no data in the requested window
  (`NoDataError`).
- `backend/app/timeframes.py` — maps timeframe strings (`1D, 1W, 1M, 3M,
  6M, 1Y, 5Y`) to yfinance `(period, interval)` pairs. Documented
  assumption: intraday granularity is capped by how far back Yahoo
  allows querying it, so short timeframes use finer intervals.
- `backend/app/schemas.py` — Pydantic response models (`OHLCVBar`,
  `OHLCVResponse`).
- `backend/app/main.py` — FastAPI app with `GET /api/health` and
  `GET /api/ohlcv?ticker=...&timeframe=...`.
- `backend/requirements.txt` — pinned deps (fastapi, uvicorn, yfinance,
  pandas, numpy, pydantic).
- A Python venv was created locally at `backend/.venv` (not committed;
  recreate with `python3 -m venv .venv && pip install -r requirements.txt`).

**Stage 1 is now LIVE-VERIFIED (2026-08-26).** Network access to Yahoo
Finance works in this environment, but getting real data required one
code fix — documented here so it isn't rediscovered:

**Bug found and fixed: yfinance's default TLS impersonation gets reset
by this environment's egress proxy.** yfinance uses `curl_cffi` to
impersonate a browser's TLS fingerprint (Yahoo blocks/rate-limits
requests that don't look like a real browser — a plain, non-impersonated
request gets a permanent HTTP 429). yfinance's hardcoded default is
`impersonate="chrome"`. In this environment, Chrome impersonation's TLS
ClientHello gets reset mid-handshake by the proxy (`curl: (35) Recv
failure: Connection reset by peer`) — confirmed to be proxy-specific,
not a Yahoo block, by testing other impersonation targets: `safari` and
`edge` both pass through the proxy cleanly and return real data, only
`chrome*` variants fail. Fix, in `backend/app/data_fetch.py`: build a
single module-level `curl_cffi.requests.Session(impersonate="safari")`
and pass it into every `yf.Ticker(ticker, session=...)` call instead of
using yfinance's default session. If this project is ever run outside
this proxied environment, that override is harmless (Safari
impersonation is just as valid a browser fingerprint as Chrome for
clearing Yahoo's bot check).

**Verification performed:**
- Fetched `AAPL`, `TSLA`, `NVDA` across `1Y` (daily), `1M` (daily), and
  `1D` (5-minute intraday) timeframes. All returned ascending-by-date,
  gap-free, NaN-free DataFrames with strictly positive OHLC and
  non-negative volume.
- Sanity-checked prices against known ranges: AAPL ~$308-339, TSLA
  ~$345-363, NVDA ~$208-215 — all plausible, no $3 or $30,000 garbage
  values, no stale/duplicate bars.
- Confirmed `InvalidTickerError` fires cleanly for a bogus ticker
  (`ZZZZZZ`) instead of crashing or silently returning empty data.
- Ran the actual FastAPI app end-to-end (not just the fetch function):
  `GET /api/health` → `{"status":"ok"}`; `GET /api/ohlcv?ticker=AAPL&timeframe=1M`
  → 200 with well-formed JSON bars; `GET /api/ohlcv?ticker=ZZZZZZ&timeframe=1M`
  → clean 404 with a descriptive error body, no stack trace leaked.

**Stage 1 is done.**

**Stage 2 — Indicator calculations: DONE, LIVE-VERIFIED (2026-08-26).**

What exists:
- `backend/app/indicators.py` — pure functions over a `fetch_ohlcv`
  DataFrame: `sma`, `ema`, `rsi` (Wilder smoothing), `macd`, `bollinger_bands`,
  `volume_weighted_ma`, `ma_crossovers` (golden/death cross via SMA50/SMA200
  sign changes), `swing_highs_lows` and `support_resistance_levels`
  (clustered swing points), plus `compute_all(df)` bundling everything.
  Docstrings mark which calculations are precise textbook formulas (SMA,
  EMA, MACD, Bollinger, VWMA) vs. heuristic judgment calls flagged for
  review: RSI's smoothing convention (Wilder's, the market-standard
  choice), the swing-high/low window (fixed at 5 bars each side — an
  arbitrary trade-off between noise and sensitivity), and the
  support/resistance clustering tolerance (1.5% merge threshold, "most
  touched" used as a proxy for "most significant").
- `backend/app/schemas.py` — added `IndicatorPoint`, `MACDPoint`,
  `BollingerPoint`, `CrossEvent`, `SRLevel`, `IndicatorsResponse`.
- `backend/app/main.py` — added `GET /api/indicators?ticker=...&timeframe=...`,
  same error handling pattern as `/api/ohlcv` (404 for invalid ticker,
  400 for unknown timeframe). NaN values (bars before a window has enough
  history) serialize as JSON `null`, not `NaN` or a dropped key.
- `backend/verify_stage2.py` — a standalone verification script (not a
  pytest suite) that fetches real data and checks each indicator against
  an independent from-scratch reference implementation (plain Python
  loops, not a second call into pandas rolling/ewm) rather than just
  re-running the same code. Kept in the repo so the check is
  reproducible if `indicators.py` changes.

**Verification performed** (`python3 verify_stage2.py`, AAPL/TSLA/MSFT,
1Y daily):
- SMA20/50/200, EMA12/26, RSI14, and VWMA20 all matched independent
  plain-Python reference calculations to within floating-point
  tolerance at the most recent bar.
- RSI stayed within [0, 100] for every valid bar across all three
  tickers (237 bars each).
- MACD identities held exactly: `histogram == macd - signal` and
  `macd == EMA12 - EMA26` for every valid bar.
- Bollinger Bands: `upper >= middle >= lower` held for every valid bar,
  and the middle band matched SMA20 exactly.
- Golden/death cross detection was under-exercised on 1Y data (SMA200
  only has ~51 valid bars in a 251-bar series, and none of AAPL/TSLA/MSFT
  crossed in that window) — separately verified against 5 years of AAPL
  daily data, which produced 4 golden crosses and 3 death crosses
  (2022-09-26, 2023-03-22, 2024-06-13, 2025-09-15 golden; 2022-10-07,
  2024-03-14, 2025-04-07 death). Each was confirmed mechanically: SMA50
  was below (above) SMA200 on the prior bar and above (below) it on the
  flagged bar, exactly matching what "golden"/"death" cross means — not
  cross-checked against any external narrative of what happened in the
  market on those dates.
- Support/resistance levels for all three tickers fell within the
  actual traded price range for the period (sanity bound — clustering
  quality is inherently subjective and flagged as a heuristic above).
- Ran the actual `GET /api/indicators` endpoint end-to-end: 200 with
  well-formed JSON (including correct `null`s for early-bar NaNs) for a
  valid ticker, clean 404 for an invalid one.

**Stage 2 is done.**

**Stage 3 — Pattern detection: DONE, LIVE-VERIFIED (2026-08-27).**

What exists:
- `backend/app/pattern_detection.py` — heuristic detectors for double
  top/bottom, head and shoulders/inverse, ascending/descending/
  symmetrical triangles, and bull/bear flags/pennants, plus a thin
  wrapper around Stage 2's `ma_crossovers` for golden/death cross. Every
  match is a dict with `name`, `start`, `end`, a `confidence` float
  deliberately compressed into [0.3, 0.9] (never claims certainty), and
  a human-readable `detail` string citing the actual prices/dates
  involved. `detect_all(df)` runs every detector and applies
  `_suppress_overlaps` (see below). Every threshold (peak-similarity
  tolerance, trough depth, shoulder tolerance, triangle flatness, pole
  size, consolidation tightness, swing window) is a documented
  assumption in the relevant docstring, per the project brief's
  requirement to flag judgment calls for review.
- `backend/app/schemas.py` / `backend/app/main.py` — added
  `PatternMatch`, `PatternsResponse`, `GET /api/patterns?ticker=...&timeframe=...`.
- `backend/scan_patterns.py` — scans ~14 tickers x 3 timeframes and
  reports the highest-confidence matches per pattern type, so
  verification isn't limited to hoping one hand-picked ticker happens to
  show a given shape right now.
- `backend/render_pattern_chart.py` — renders a real price chart with
  swing points marked and a specific detected match's date range shaded,
  as a PNG, so the match can actually be looked at rather than trusted
  on the numbers alone (added `matplotlib` as a dev-only dependency in
  `requirements.txt` for this).

**Bug found and fixed via visual verification.** The double top/bottom
detector originally checked pairs of swing highs/lows directly against
each other but never checked what happened *between* them against the
raw price series. Rendering the first real matches found by
`scan_patterns.py` and looking at them (AAPL "Double Bottom",
2025-12-2026-04; AMZN "Double Top", 2025-11-2026-07) showed the bug
immediately: in both cases, price moved *more* extremely somewhere
between the two matched points than either matched point itself (AAPL's
"double bottom" had a rally to a new high between the two troughs that
made the shape read as three-plus swings, not a clean W; AMZN's "double
top" had a rally well above both "peaks" in between, meaning the two
matched points weren't even the most prominent peaks in their own
range). Fixed by requiring the two matched points to be the genuine
extrema of the *entire* span between them (checked against `df['high']`/
`df['low']`, not just the sampled swing points) — added the same
safeguard to head-and-shoulders/inverse for consistency. Re-scanning
after the fix dropped double-top matches from 151 to 111 and
double-bottom from 153 to 92 across the scan universe (confirming real,
substantial filtering, not a no-op), and the new top matches (GOOGL
Double Bottom, NVDA Double Top) were re-rendered and now show textbook
W/M shapes with no competing extremum in between.

**Second issue found and fixed:** `detect_all` on a single ticker/
timeframe was returning many overlapping double-top/bottom matches for
the same choppy stretch of price (AAPL 1Y initially returned 10 matches,
several sharing most of their date range) — each individually satisfied
the thresholds against some pair of swings, but reporting all of them
buried the strongest read of a region under near-duplicates. Added
`_suppress_overlaps`: within each pattern name, keep only the
highest-confidence match for any overlapping date range. AAPL 1Y now
returns 5 non-overlapping matches instead of 10.

**Verification performed:**
- Scanned AAPL, TSLA, NVDA, MSFT, AMZN, GOOGL, META, AMD, NFLX, DIS, BA,
  PLTR, COIN, SOFI across 1Y/6M/3M timeframes. Got real matches for
  every pattern type except Symmetrical Triangle (zero occurrences in
  the current data, not a detector bug — confirmed separately by
  feeding `detect_triangles` a synthetic converging price series, which
  it correctly classified as "Symmetrical Triangle").
- Rendered and visually inspected charts (swing points + shaded match
  range) for: Double Bottom (AAPL, then GOOGL post-fix), Double Top
  (AMZN, then NVDA post-fix), Head and Shoulders (META), Inverse Head
  and Shoulders (AMD), Ascending Triangle (PLTR), Descending Triangle
  (COIN), Bull Flag (MSFT), Bull Pennant (META), Bear Flag (AMZN) — all
  post-fix matches show a shape a chartist would actually recognize as
  the claimed pattern; the MSFT Bull Flag and AMZN Bear Flag in
  particular are textbook (sharp pole, tight consolidation right after).
- Golden/death cross wiring re-verified end-to-end through
  `detect_ma_crossovers` (reuses the Stage-2-verified `ma_crossovers`
  math, so this only checked that it's correctly surfaced, not the
  underlying crossover math again).
- Ran the actual `GET /api/patterns` endpoint end-to-end: 200 with
  well-formed JSON for a valid ticker, clean 404 for an invalid one.

**Honest limitation to flag for review:** the Inverse Head and Shoulders
match found on AMD (shoulders ~460/463, head ~424) is mechanically
correct (head is the genuine extreme of the span, shoulders are within
tolerance, a real neckline exists) but reads, by eye, more like noisy
consolidation within a strong uptrend than a textbook inverse H&S — the
neckline highs on either side of the head are ~550 and ~580, i.e. far
above the shoulders, which is structurally valid but not visually
"clean". This reads like the fuzziness the project brief warned about
rather than a bug to fix: tightening the thresholds further to exclude
it risks also excluding genuine, tighter H&S patterns elsewhere. Flagged
here rather than silently tuned away.

**Stage 3 addendum — directional bias, confirmation, and volume,
sourced from a user-provided reference document (2026-08-27).**

The user supplied a "Stock Chart Pattern Directional Reference Guide"
(23 patterns, confirmation criteria, invalidation criteria, and a
directional-bias label per pattern) partway through Stage 3, asked how
it compared to what was already built, and then asked for it to be
folded in. It was NOT used to build the original Stage 3 detectors —
those came from the project brief plus standard TA definitions — so
this was a genuine retrofit, done and re-verified against live data
before moving on. Comparison against the doc found the shape logic
already matched (double top/bottom's neckline structure, head &
shoulders' shoulder/head/neckline structure, triangle slope logic,
flag/pennant flagpole+consolidation structure all lined up), but three
things the doc treats as central were missing entirely: a directional
label, breakout confirmation, and volume corroboration. Added to
`pattern_detection.py`:
- **`directional_bias`** ("Bullish"/"Bearish"/"Neutral") on every match.
  Fixed by pattern identity for most (double top/H&S = Bearish, double
  bottom/inverse H&S = Bullish, ascending triangle/bull flag/pennant =
  Bullish, descending triangle/bear flag/pennant = Bearish), except
  symmetrical triangles, which the doc explicitly says have no bias from
  shape alone — bias there is derived from the 20-bar price trend
  *before* the triangle formed (`_prior_trend_bias`), and the pattern is
  renamed "Bullish/Bearish Symmetrical Triangle" once a bias is known,
  matching the doc's own naming split. If price actually breaks out
  before a prior trend gives a clear read, the breakout direction wins
  over the prior-trend guess (mirroring how the doc treats its
  neutral/bilateral patterns: "the breakout direction is the signal").
- **`status`** ("Confirmed"/"Forming") and **`confirmation_date`**. The
  doc is explicit that "confirmation matters more than the shape" — a
  completed M/W or shoulder-head-shoulder shape is not yet a breakout.
  `_find_breakout` scans every bar after the pattern's defining points
  for the first close beyond the actual neckline/trendline/channel
  level (a real fitted line for sloped necklines and triangle
  trendlines, not a flat snapshot), and reports the exact date it broke,
  or `None` if it hasn't yet.
- **`volume_note`** plus a small transparent confidence nudge (±0.05,
  clamped back into [0.3, 0.9]): compares breakout-bar volume to the
  pattern's average volume during formation, since the doc repeatedly
  cites "close beyond the level, ideally on a volume increase" as part
  of confirmation. This is reported as an auditable ratio in plain
  English, not folded silently into the base confidence score.
- Golden/death cross (not in the reference doc at all — it's a
  moving-average signal, not a price-shape pattern) got bias fields for
  API consistency but `status` is trivially always "Confirmed" (the
  crossover IS the event) and `volume_note` says the concept doesn't
  apply.

**Important scope note, restated from the earlier chat discussion:**
none of this makes the tool's directional read more *accurate* — chart-
pattern TA has weak, contested predictive power in the literature, and
the reference doc itself hedges throughout ("statistically probable
direction, not certainty," "one input, not a standalone signal"). This
change makes the tool's output match how a technical analyst actually
talks about a chart (shape vs. confirmed breakout vs. volume behind it),
not how *likely* that breakout is to hold. Stage 5's summary language
needs to preserve that same hedge — "double bottom, confirmed, bullish
bias" is a factual description of the data, not a prediction.

**Re-verification after the addendum:**
- Re-ran `scan_patterns.py` across all 14 tickers/3 timeframes — same
  match counts and shapes as before (the addendum only adds fields, it
  doesn't change which shapes qualify), confirming no regression.
- Re-rendered three charts with the new confirmation date marked as a
  vertical line: NVDA Double Top (correctly still "Forming" — price
  hasn't closed back below the ~190 neckline as of the last bar, so no
  confirmation line is drawn), GOOGL Double Bottom (confirmed exactly
  where price closes above the ~348 neckline peak), and PLTR Ascending
  Triangle (confirmed exactly at the sharp breakout above resistance,
  with volume 4.4x the pattern's average — a clean, textbook example of
  everything working together correctly).
- Verified the symmetrical-triangle bias/confirmation logic on a
  synthetic converging series with a forced breakout: correctly labeled
  "Bullish Symmetrical Triangle" (prior 20 bars were rising) and
  correctly confirmed at the exact bar the synthetic breakout occurred.

**Next step for whoever picks this up:** Move to Stage 4 (frontend chart
rendering) per the Feedback Loop Protocol above: build the React +
charting-library frontend against the three existing endpoints
(`/api/ohlcv`, `/api/indicators`, `/api/patterns`), then confirm
indicators and pattern flags actually align with the correct dates/
prices on the rendered chart — the brief specifically calls out off-by-
one errors here as common, so check bar alignment carefully (the
backend's `_num_or_none` rounding and ISO-8601 `time` strings should
make this straightforward, but timezone/date-boundary handling in
whatever charting library gets used is worth double-checking). The
frontend should surface `directional_bias`, `status`, and
`confirmation_date` alongside each pattern, not just its name — a
"Forming, unconfirmed" pattern and a "Confirmed" one are meaningfully
different claims and the UI shouldn't flatten that distinction. Remaining
stages (frontend, summary generation, end-to-end test) have not been
started yet.
