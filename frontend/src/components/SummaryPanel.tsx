import type { SummaryResponse } from '../lib/api';

export default function SummaryPanel({ summary }: { summary: SummaryResponse }) {
  return (
    <div className="summary-panel">
      <h2>{summary.headline}</h2>
      <SummarySection title="Trend" text={summary.trend} />
      <SummarySection title="Momentum" text={summary.momentum} />
      <SummarySection title="Volatility" text={summary.volatility} />
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
