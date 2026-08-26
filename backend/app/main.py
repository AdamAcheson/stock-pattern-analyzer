import logging

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.data_fetch import InvalidTickerError, NoDataError, fetch_ohlcv
from app.schemas import OHLCVBar, OHLCVResponse
from app.timeframes import TIMEFRAMES

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Stock Pattern & Technical Analysis API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
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
