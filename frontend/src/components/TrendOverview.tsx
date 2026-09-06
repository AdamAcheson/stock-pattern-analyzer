import type { TimeframeTrend } from '../lib/api';

function trendClass(trend: string): string {
  if (trend === 'Uptrend') return 'trend-up';
  if (trend === 'Downtrend') return 'trend-down';
  return 'trend-mixed';
}

export default function TrendOverview({ timeframes }: { timeframes: TimeframeTrend[] }) {
  return (
    <div className="trend-overview">
      <h3>Trend Overview</h3>
      <div className="trend-overview-row">
        {timeframes.map((tf) => (
          <div key={tf.label} className="trend-overview-cell">
            <span className="trend-overview-label">{tf.label}</span>
            <span className={`trend-overview-value ${trendClass(tf.trend)}`}>{tf.trend}</span>
            {tf.short_ma !== null && tf.long_ma !== null && (
              <span className="trend-overview-detail">
                {tf.short_window}-period {tf.short_ma.toFixed(2)} vs {tf.long_window}-period {tf.long_ma.toFixed(2)}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
