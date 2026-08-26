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

**Why it's unverified:** the Claude Code cloud environment this was
built in had its network access level set to "Trusted" (allowlist-only:
npm/PyPI/GitHub/etc.), which blocks Yahoo Finance's domains entirely
(`query1/query2.finance.yahoo.com`, `fc.yahoo.com`, `guce.yahoo.com`),
as well as every alternative tried (Alpha Vantage, Polygon.io, Stooq,
even Finviz — all 403'd at the proxy level). This was confirmed to be a
blanket default-deny policy, not something specific to financial data
sites (a control request to `example.com` also 403'd). The user has
since been walked through changing the environment's Network access
level to "Full" (or "Custom" with the Yahoo hosts allowlisted) via the
environment edit dialog in claude.ai/code.

**Next step for whoever picks this up:** confirm network access now
works (try `curl -sS -o /dev/null -w '%{http_code}\n' https://query2.finance.yahoo.com/`
or just run the verification below), then complete Stage 1 verification:

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 -c "
from app.data_fetch import fetch_ohlcv
for ticker in ['AAPL', 'TSLA', 'NVDA']:
    for tf in ['1Y', '1M', '1D']:
        df = fetch_ohlcv(ticker, tf)
        print(ticker, tf, df.shape, df.index.is_monotonic_increasing, df.index.min(), df.index.max())
        print(df.tail(3))
"
```
Check: ascending index, no gaps/NaNs, sane OHLC ranges (e.g. AAPL not
priced at $3 or $30,000), volume non-negative. Also test an invalid
ticker (e.g. `ZZZZZZ`) to confirm `InvalidTickerError` fires cleanly.
Once that's confirmed, report a short verification summary and move to
Stage 2 (indicator calculations) per the Feedback Loop Protocol above.
Remaining stages (indicators, pattern detection, frontend, summary
generation, end-to-end test) have not been started yet.
