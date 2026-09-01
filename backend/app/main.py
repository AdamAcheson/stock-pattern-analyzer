import logging
import math
import os

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.data_fetch import InvalidTickerError, NoDataError, fetch_ohlcv
from app.indicators import compute_all
from app.pattern_detection import detect_all
from app.schemas import (
    BollingerPoint,
    CrossEvent,
    IndicatorPoint,
    IndicatorsResponse,
    MACDPoint,
    OHLCVBar,
    OHLCVResponse,
    PatternMatch,
    PatternsResponse,
    SRLevel,
    SummaryResponse,
)
from app.summary import generate_summary
from app.timeframes import TIMEFRAMES

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Stock Pattern & Technical Analysis API")

# The frontend is deployed as a separate Vercel project (see
# backend/vercel.json and DEPLOYMENT.md), so this API has to allow
# cross-origin requests explicitly rather than relying on same-origin.
# allow_origin_regex covers both the production domain and every
# preview-deployment URL Vercel generates per-branch/per-PR (they're all
# random subdomains of vercel.app); FRONTEND_ORIGIN is an escape hatch
# for a custom domain, which wouldn't match that pattern.
_extra_origins = [o for o in [os.environ.get("FRONTEND_ORIGIN")] if o]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", *_extra_origins],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get(
    "/api/ohlcv",
    response_model=OHLCVResponse,
    responses={404: {"description": "Invalid ticker or no data"}},
)
def get_ohlcv(
    ticker: str = Query(..., min_length=1, max_length=10),
    timeframe: str = Query("1Y"),
) -> OHLCVResponse:
    if timeframe not in TIMEFRAMES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown timeframe '{timeframe}'. Valid options: {sorted(TIMEFRAMES)}",
        )

    try:
        df = fetch_ohlcv(ticker, timeframe)
    except InvalidTickerError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except NoDataError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    bars = [
        OHLCVBar(
            time=idx.isoformat(),
            open=round(float(row.open), 4),
            high=round(float(row.high), 4),
            low=round(float(row.low), 4),
            close=round(float(row.close), 4),
            volume=int(row.volume),
        )
        for idx, row in df.iterrows()
    ]

    return OHLCVResponse(
        ticker=ticker.strip().upper(),
        timeframe=timeframe,
        interval=TIMEFRAMES[timeframe].interval,
        bars=bars,
    )


def _num_or_none(value: float) -> float | None:
    return None if pd.isna(value) or math.isinf(value) else round(float(value), 6)


def _series_to_points(series: pd.Series) -> list[IndicatorPoint]:
    return [
        IndicatorPoint(time=idx.isoformat(), value=_num_or_none(v))
        for idx, v in series.items()
    ]


@app.get(
    "/api/indicators",
    response_model=IndicatorsResponse,
    responses={404: {"description": "Invalid ticker or no data"}},
)
def get_indicators(
    ticker: str = Query(..., min_length=1, max_length=10),
    timeframe: str = Query("1Y"),
) -> IndicatorsResponse:
    if timeframe not in TIMEFRAMES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown timeframe '{timeframe}'. Valid options: {sorted(TIMEFRAMES)}",
        )

    try:
        df = fetch_ohlcv(ticker, timeframe)
    except InvalidTickerError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except NoDataError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    ind = compute_all(df)

    macd_df = ind["macd"]
    macd_points = [
        MACDPoint(
            time=row.Index.isoformat(),
            macd=_num_or_none(row.macd),
            signal=_num_or_none(row.signal),
            histogram=_num_or_none(row.histogram),
        )
        for row in macd_df.itertuples()
    ]

    bb_df = ind["bollinger"]
    bollinger_points = [
        BollingerPoint(
            time=row.Index.isoformat(),
            upper=_num_or_none(row.upper),
            middle=_num_or_none(row.middle),
            lower=_num_or_none(row.lower),
        )
        for row in bb_df.itertuples()
    ]

    crosses_df = ind["ma_crossovers"]
    crossovers = [
        CrossEvent(time=idx.isoformat(), type="golden")
        for idx in crosses_df.index[crosses_df["golden_cross"]]
    ] + [
        CrossEvent(time=idx.isoformat(), type="death")
        for idx in crosses_df.index[crosses_df["death_cross"]]
    ]
    crossovers.sort(key=lambda c: c.time)

    sr = ind["support_resistance"]

    return IndicatorsResponse(
        ticker=ticker.strip().upper(),
        timeframe=timeframe,
        sma_20=_series_to_points(ind["sma_20"]),
        sma_50=_series_to_points(ind["sma_50"]),
        sma_200=_series_to_points(ind["sma_200"]),
        ema_12=_series_to_points(ind["ema_12"]),
        ema_26=_series_to_points(ind["ema_26"]),
        rsi_14=_series_to_points(ind["rsi_14"]),
        vwma_20=_series_to_points(ind["vwma_20"]),
        macd=macd_points,
        bollinger=bollinger_points,
        crossovers=crossovers,
        support=[SRLevel(**lv) for lv in sr["support"]],
        resistance=[SRLevel(**lv) for lv in sr["resistance"]],
    )


@app.get(
    "/api/patterns",
    response_model=PatternsResponse,
    responses={404: {"description": "Invalid ticker or no data"}},
)
def get_patterns(
    ticker: str = Query(..., min_length=1, max_length=10),
    timeframe: str = Query("1Y"),
) -> PatternsResponse:
    if timeframe not in TIMEFRAMES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown timeframe '{timeframe}'. Valid options: {sorted(TIMEFRAMES)}",
        )

    try:
        df = fetch_ohlcv(ticker, timeframe)
    except InvalidTickerError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except NoDataError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    matches = detect_all(df)

    return PatternsResponse(
        ticker=ticker.strip().upper(),
        timeframe=timeframe,
        patterns=[
            PatternMatch(
                name=m["name"],
                start=m["start"].isoformat(),
                end=m["end"].isoformat(),
                confidence=m["confidence"],
                detail=m["detail"],
                directional_bias=m["directional_bias"],
                status=m["status"],
                confirmation_date=m["confirmation_date"].isoformat() if m["confirmation_date"] is not None else None,
                volume_note=m["volume_note"],
            )
            for m in matches
        ],
    )


@app.get(
    "/api/summary",
    response_model=SummaryResponse,
    responses={404: {"description": "Invalid ticker or no data"}},
)
def get_summary(
    ticker: str = Query(..., min_length=1, max_length=10),
    timeframe: str = Query("1Y"),
) -> SummaryResponse:
    if timeframe not in TIMEFRAMES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown timeframe '{timeframe}'. Valid options: {sorted(TIMEFRAMES)}",
        )

    try:
        df = fetch_ohlcv(ticker, timeframe)
    except InvalidTickerError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except NoDataError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    ind = compute_all(df)
    matches = detect_all(df)
    ticker_upper = ticker.strip().upper()

    summary = generate_summary(ticker_upper, timeframe, df, ind, matches)

    return SummaryResponse(
        ticker=ticker_upper,
        timeframe=timeframe,
        **summary,
    )
