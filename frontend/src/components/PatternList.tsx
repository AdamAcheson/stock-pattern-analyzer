import type { PatternMatch } from '../lib/api';

function biasClass(bias: PatternMatch['directional_bias']): string {
  if (bias === 'Bullish') return 'bias-bullish';
  if (bias === 'Bearish') return 'bias-bearish';
  return 'bias-neutral';
}

export default function PatternList({ patterns }: { patterns: PatternMatch[] }) {
  if (patterns.length === 0) {
    return <p className="pattern-empty">No patterns detected in this window.</p>;
  }

  return (
    <ul className="pattern-list">
      {patterns.map((p, i) => (
        <li key={i} className="pattern-item">
          <div className="pattern-header">
            <span className={`bias-badge ${biasClass(p.directional_bias)}`}>{p.directional_bias}</span>
            <strong>{p.name}</strong>
            <span className={`status-badge ${p.status === 'Confirmed' ? 'status-confirmed' : 'status-forming'}`}>
              {p.status}
            </span>
            <span className="confidence">conf {Math.round(p.confidence * 100)}%</span>
          </div>
          <div className="pattern-range">
            {p.start.slice(0, 10)} → {p.end.slice(0, 10)}
            {p.confirmation_date && ` · confirmed ${p.confirmation_date.slice(0, 10)}`}
          </div>
          <div className="pattern-detail">{p.detail}</div>
          <div className="pattern-volume">{p.volume_note}</div>
        </li>
      ))}
    </ul>
  );
}
