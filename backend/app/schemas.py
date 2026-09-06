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


class PriceRange(BaseModel):
    day_high: float | None
    day_low: float | None
    year_high: float | None
    year_low: float | None


class FibonacciLevel(BaseModel):
    ratio: float
    price: float


class FibonacciRetracement(BaseModel):
    swing_high: float
    swing_high_time: str
    swing_low: float
    swing_low_time: str
    direction: str
    levels: list[FibonacciLevel]


class VolumeTrend(BaseModel):
    available: bool
    recent_avg_volume: float | None = None
    baseline_avg_volume: float | None = None
    change_pct: float | None = None
    up_day_avg_volume: float | None = None
    down_day_avg_volume: float | None = None
    pressure_ratio: float | None = None
    dominant_side: str | None = None


class IndicatorsResponse(BaseModel):
    ticker: str
    timeframe: str
    sma_20: list[IndicatorPoint]
    sma_50: list[IndicatorPoint]
    sma_100: list[IndicatorPoint]
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
    price_range: PriceRange
    fibonacci: FibonacciRetracement
    volume_trend: VolumeTrend


class TimeframeTrend(BaseModel):
    label: str  # "Daily" | "Weekly" | "Monthly"
    trend: str
    close: float | None
    short_ma: float | None
    short_window: int
    long_ma: float | None
    long_window: int
    error: str | None = None


class TrendOverviewResponse(BaseModel):
    ticker: str
    timeframes: list[TimeframeTrend]


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


class SummaryResponse(BaseModel):
    ticker: str
    timeframe: str
    headline: str
    trend: str
    moving_averages: str
    momentum: str
    volatility: str
    volume: str
    fibonacci: str
    patterns: str
    synthesis: str
    disclaimer: str


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
