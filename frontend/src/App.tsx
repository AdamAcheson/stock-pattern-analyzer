import { useEffect, useState } from 'react';
import {
  fetchOhlcv,
  fetchIndicators,
  fetchPatterns,
  fetchSummary,
  TIMEFRAMES,
  ApiError,
  type Timeframe,
  type OHLCVResponse,
  type IndicatorsResponse,
  type PatternsResponse,
  type SummaryResponse,
} from './lib/api';
import StockChart from './components/StockChart';
import PatternList from './components/PatternList';
import ChartLegend from './components/ChartLegend';
import KeyLevels from './components/KeyLevels';
import SummaryPanel from './components/SummaryPanel';
import './App.css';

interface LoadedData {
  ohlcv: OHLCVResponse;
  indicators: IndicatorsResponse;
  patterns: PatternsResponse;
  summary: SummaryResponse;
}

function lastValue(points: { value: number | null }[]): number | null {
  for (let i = points.length - 1; i >= 0; i--) {
    if (points[i].value !== null) return points[i].value;
  }
  return null;
}

function App() {
  const [tickerInput, setTickerInput] = useState('AAPL');
  const [ticker, setTicker] = useState('AAPL');
  const [timeframe, setTimeframe] = useState<Timeframe>('1Y');
  const [data, setData] = useState<LoadedData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    Promise.all([
      fetchOhlcv(ticker, timeframe),
      fetchIndicators(ticker, timeframe),
      fetchPatterns(ticker, timeframe),
      fetchSummary(ticker, timeframe),
    ])
      .then(([ohlcv, indicators, patterns, summary]) => {
        if (cancelled) return;
        setData({ ohlcv, indicators, patterns, summary });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setData(null);
        setError(err instanceof ApiError ? err.message : 'Failed to load data. Is the backend running?');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [ticker, timeframe]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = tickerInput.trim().toUpperCase();
    if (trimmed) setTicker(trimmed);
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>Stock Pattern &amp; Technical Analysis</h1>
        <p className="disclaimer">
          Research/learning tool only. Nothing here is investment advice or a recommendation to buy or sell.
        </p>
      </header>

      <form className="controls" onSubmit={handleSubmit}>
        <input
          type="text"
          value={tickerInput}
          onChange={(e) => setTickerInput(e.target.value)}
          placeholder="Ticker, e.g. AAPL"
          maxLength={10}
        />
        <button type="submit">Analyze</button>
        <div className="timeframe-buttons">
          {TIMEFRAMES.map((tf) => (
            <button
              key={tf}
              type="button"
              className={tf === timeframe ? 'active' : ''}
              onClick={() => setTimeframe(tf)}
            >
              {tf}
            </button>
          ))}
        </div>
      </form>

      {loading && <p className="status-message">Loading {ticker}…</p>}
      {error && <p className="status-message error">{error}</p>}

      {data && !loading && !error && (
        <>
          <section className="indicator-summary">
            <SummaryStat label="Last Close" value={data.ohlcv.bars.at(-1)?.close.toFixed(2)} />
            <SummaryStat label="Day High" value={data.indicators.price_range.day_high?.toFixed(2)} />
            <SummaryStat label="Day Low" value={data.indicators.price_range.day_low?.toFixed(2)} />
            <SummaryStat label="52W High" value={data.indicators.price_range.year_high?.toFixed(2)} />
            <SummaryStat label="52W Low" value={data.indicators.price_range.year_low?.toFixed(2)} />
            <SummaryStat label="SMA 20" value={lastValue(data.indicators.sma_20)?.toFixed(2)} />
            <SummaryStat label="SMA 50" value={lastValue(data.indicators.sma_50)?.toFixed(2)} />
            <SummaryStat label="SMA 200" value={lastValue(data.indicators.sma_200)?.toFixed(2)} />
            <SummaryStat label="RSI 14" value={lastValue(data.indicators.rsi_14)?.toFixed(1)} />
          </section>

          <section className="chart-section">
            <ChartLegend />
            <StockChart
              ohlcv={data.ohlcv}
              indicators={data.indicators}
              patterns={data.patterns}
              timeframe={timeframe}
            />
          </section>

          <section className="levels-section">
            <KeyLevels support={data.indicators.support} resistance={data.indicators.resistance} />
          </section>

          <section className="pattern-section">
            <h2>Detected Patterns</h2>
            <PatternList patterns={data.patterns.patterns} />
          </section>

          <section className="summary-section-wrapper">
            <SummaryPanel summary={data.summary} />
          </section>
        </>
      )}
    </div>
  );
}

function SummaryStat({ label, value }: { label: string; value: string | undefined }) {
  return (
    <div className="summary-stat">
      <span className="summary-label">{label}</span>
      <span className="summary-value">{value ?? '—'}</span>
    </div>
  );
}

export default App;
