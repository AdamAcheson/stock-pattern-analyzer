from pydantic import BaseModel


class IndicatorPoint(BaseModel):
    time: str
    value: float | None


class MACDPoint(BaseModel):
    time: str
    macd: float | None
    signal: float | None
    histogram: float | None


class BollingerPoint(BaseModel):
    time: str
    upper: float | None
    middle: float | None
    lower: float | None


class CrossEvent(BaseModel):
    time: str
    type: str  # "golden" or "death"


class SRLevel(BaseModel):
    price: float
    touches: int


class IndicatorsResponse(BaseModel):
    ticker: str
    timeframe: str
    sma_20: list[IndicatorPoint]
    sma_50: list[IndicatorPoint]
    sma_200: list[IndicatorPoint]
    ema_12: list[IndicatorPoint]
    ema_26: list[IndicatorPoint]
    rsi_14: list[IndicatorPoint]
    vwma_20: list[IndicatorPoint]
    macd: list[MACDPoint]
    bollinger: list[BollingerPoint]
    crossovers: list[CrossEvent]
    support: list[SRLevel]
    resistance: list[SRLevel]


class PatternMatch(BaseModel):
    name: str
    start: str
    end: str
    confidence: float
    detail: str
    directional_bias: str  # "Bullish" | "Bearish" | "Neutral"
    status: str  # "Confirmed" | "Forming"
    confirmation_date: str | None
    volume_note: str


class PatternsResponse(BaseModel):
    ticker: str
    timeframe: str
    patterns: list[PatternMatch]


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
