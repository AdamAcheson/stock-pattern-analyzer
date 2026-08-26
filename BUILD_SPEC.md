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

**Next step for whoever picks this up:** Move to Stage 3 (pattern
detection — head and shoulders, double top/bottom, triangles, flags/
pennants; golden/death cross detection is already implemented in Stage 2
and just needs surfacing to the frontend, not re-built) per the Feedback
Loop Protocol above: build the detector(s), then test against
tickers/date ranges with a known, visually obvious pattern before
trusting them on arbitrary data — e.g. pull up a chart for the ticker on
a real source and confirm the flagged date range actually looks like the
claimed pattern before moving on. Remaining stages (pattern detection,
frontend, summary generation, end-to-end test) have not been started
yet.
