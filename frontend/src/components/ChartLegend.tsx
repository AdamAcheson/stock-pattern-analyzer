import { OVERLAY_LEGEND } from '../lib/chartColors';

export default function ChartLegend() {
  return (
    <div className="chart-legend">
      {OVERLAY_LEGEND.map((item) => (
        <span key={item.label} className="legend-item">
          <span className="legend-swatch" style={{ background: item.color }} />
          {item.label}
        </span>
      ))}
    </div>
  );
}
