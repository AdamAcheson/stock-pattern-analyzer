// Types mirror backend/app/schemas.py exactly -- keep them in sync by
// hand since there's no shared schema generation step in this project.

export const TIMEFRAMES = ['1D', '1W', '1M', '3M', '6M', '1Y', '5Y'] as const;
export type Timeframe = (typeof TIMEFRAMES)[number];

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

export interface OHLCVBar {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface OHLCVResponse {
  ticker: string;
  timeframe: string;
  interval: string;
  bars: OHLCVBar[];
}

export interface IndicatorPoint {
  time: string;
  value: number | null;
}

export interface MACDPoint {
  time: string;
  macd: number | null;
  signal: number | null;
  histogram: number | null;
}

export interface BollingerPoint {
  time: string;
  upper: number | null;
  middle: number | null;
  lower: number | null;
}

export interface CrossEvent {
  time: string;
  type: 'golden' | 'death';
}

export interface SRLevel {
  price: number;
  touches: number;
}

export interface PriceRange {
  day_high: number | null;
  day_low: number | null;
  year_high: number | null;
  year_low: number | null;
}

export interface FibonacciLevel {
  ratio: number;
  price: number;
}

export interface FibonacciRetracement {
  swing_high: number;
  swing_high_time: string;
  swing_low: number;
  swing_low_time: string;
  direction: string;
  levels: FibonacciLevel[];
}

export interface VolumeTrend {
  available: boolean;
  recent_avg_volume: number | null;
  baseline_avg_volume: number | null;
  change_pct: number | null;
  up_day_avg_volume: number | null;
  down_day_avg_volume: number | null;
  pressure_ratio: number | null;
  dominant_side: string | null;
}

export interface IndicatorsResponse {
  ticker: string;
  timeframe: string;
  sma_20: IndicatorPoint[];
  sma_50: IndicatorPoint[];
  sma_100: IndicatorPoint[];
  sma_200: IndicatorPoint[];
  ema_12: IndicatorPoint[];
  ema_26: IndicatorPoint[];
  rsi_14: IndicatorPoint[];
  vwma_20: IndicatorPoint[];
  macd: MACDPoint[];
  bollinger: BollingerPoint[];
  crossovers: CrossEvent[];
  support: SRLevel[];
  resistance: SRLevel[];
  price_range: PriceRange;
  fibonacci: FibonacciRetracement;
  volume_trend: VolumeTrend;
}

export interface TimeframeTrend {
  label: string;
  trend: string;
  close: number | null;
  short_ma: number | null;
  short_window: number;
  long_ma: number | null;
  long_window: number;
  error: string | null;
}

export interface TrendOverviewResponse {
  ticker: string;
  timeframes: TimeframeTrend[];
}

export interface PatternMatch {
  name: string;
  start: string;
  end: string;
  confidence: number;
  detail: string;
  directional_bias: 'Bullish' | 'Bearish' | 'Neutral';
  status: 'Confirmed' | 'Forming';
  confirmation_date: string | null;
  volume_note: string;
}

export interface PatternsResponse {
  ticker: string;
  timeframe: string;
  patterns: PatternMatch[];
}

export interface SummaryResponse {
  ticker: string;
  timeframe: string;
  headline: string;
  trend: string;
  moving_averages: string;
  momentum: string;
  volatility: string;
  volume: string;
  fibonacci: string;
  patterns: string;
  synthesis: string;
  disclaimer: string;
}

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(body?.detail ?? `Request failed (${res.status})`, res.status);
  }
  return res.json();
}

export function fetchOhlcv(ticker: string, timeframe: Timeframe): Promise<OHLCVResponse> {
  return getJson(`/api/ohlcv?ticker=${encodeURIComponent(ticker)}&timeframe=${timeframe}`);
}

export function fetchIndicators(ticker: string, timeframe: Timeframe): Promise<IndicatorsResponse> {
  return getJson(`/api/indicators?ticker=${encodeURIComponent(ticker)}&timeframe=${timeframe}`);
}

export function fetchPatterns(ticker: string, timeframe: Timeframe): Promise<PatternsResponse> {
  return getJson(`/api/patterns?ticker=${encodeURIComponent(ticker)}&timeframe=${timeframe}`);
}

export function fetchSummary(ticker: string, timeframe: Timeframe): Promise<SummaryResponse> {
  return getJson(`/api/summary?ticker=${encodeURIComponent(ticker)}&timeframe=${timeframe}`);
}

export function fetchTrendOverview(ticker: string): Promise<TrendOverviewResponse> {
  return getJson(`/api/trend-overview?ticker=${encodeURIComponent(ticker)}`);
}
