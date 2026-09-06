import { OVERLAY_LEGEND, type OverlayKey } from '../lib/chartColors';

interface Props {
  hovered: OverlayKey | null;
  onHover: (key: OverlayKey | null) => void;
}

export default function ChartLegend({ hovered, onHover }: Props) {
  return (
    <div className="chart-legend">
      {OVERLAY_LEGEND.map((item) => (
        <span
          key={item.label}
          className={`legend-item${hovered === item.key ? ' legend-item-active' : ''}`}
          onMouseEnter={() => onHover(item.key)}
          onMouseLeave={() => onHover(null)}
        >
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
