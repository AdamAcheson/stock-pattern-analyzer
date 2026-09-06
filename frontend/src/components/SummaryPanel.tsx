import type { SummaryResponse, TrendOverviewResponse } from '../lib/api';
import TrendOverview from './TrendOverview';

export default function SummaryPanel({
  summary,
  trendOverview,
}: {
  summary: SummaryResponse;
  trendOverview: TrendOverviewResponse | null;
}) {
  return (
    <div className="summary-panel">
      <h2>{summary.headline}</h2>
      {trendOverview && <TrendOverview timeframes={trendOverview.timeframes} />}
      <SummarySection title="Trend" text={summary.trend} />
      <SummarySection title="Moving Averages" text={summary.moving_averages} />
      <SummarySection title="Momentum (RSI / MACD)" text={summary.momentum} />
      <SummarySection title="Volatility (Bollinger Bands)" text={summary.volatility} />
      <SummarySection title="Volume" text={summary.volume} />
      <SummarySection title="Fibonacci Retracement" text={summary.fibonacci} />
      <SummarySection title="Patterns" text={summary.patterns} />
      <SummarySection title="Synthesis" text={summary.synthesis} emphasize />
      <p className="summary-disclaimer">{summary.disclaimer}</p>
    </div>
  );
}

function SummarySection({ title, text, emphasize }: { title: string; text: string; emphasize?: boolean }) {
  return (
    <div className={`summary-section${emphasize ? ' summary-section-emphasized' : ''}`}>
      <h3>{title}</h3>
      <p>{text}</p>
    </div>
  );
}
