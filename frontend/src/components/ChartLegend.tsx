import { OVERLAY_LEGEND } from '../lib/chartColors';

export default function ChartLegend() {
  return (
    <div className="chart-legend">
      {OVERLAY_LEGEND.map((item) => (
        <span key={item.label} className="legend-item">
          <span
            className="legend-swatch"
            style={
              item.dashed
                ? {
                    backgroundImage: `repeating-linear-gradient(to right, ${item.color} 0, ${item.color} 4px, transparent 4px, transparent 7px)`,
                  }
                : { background: item.color }
            }
          />
          {item.label}
        </span>
      ))}
    </div>
  );
}
