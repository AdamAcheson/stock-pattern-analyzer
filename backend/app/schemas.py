from pydantic import BaseModel


class OHLCVBar(BaseModel):
    time: str  # ISO 8601 timestamp
    open: float
    high: float
    low: float
    close: float
    volume: int


class OHLCVResponse(BaseModel):
    ticker: str
    timeframe: str
    interval: str
    bars: list[OHLCVBar]


class ErrorResponse(BaseModel):
    detail: str
