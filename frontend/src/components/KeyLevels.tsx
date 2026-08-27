import type { SRLevel } from '../lib/api';

function sortedByPrice(levels: SRLevel[]): SRLevel[] {
  return [...levels].sort((a, b) => b.price - a.price);
}

export default function KeyLevels({ support, resistance }: { support: SRLevel[]; resistance: SRLevel[] }) {
  if (support.length === 0 && resistance.length === 0) {
    return null;
  }

  return (
    <div className="key-levels">
      <div className="key-levels-col">
        <h3 className="key-levels-title resistance">Resistance</h3>
        {sortedByPrice(resistance).map((lv) => (
          <div key={lv.price} className="key-level-row resistance">
            {lv.price.toFixed(2)} <span className="touches">({lv.touches}× touched)</span>
          </div>
        ))}
      </div>
      <div className="key-levels-col">
        <h3 className="key-levels-title support">Support</h3>
        {sortedByPrice(support).map((lv) => (
          <div key={lv.price} className="key-level-row support">
            {lv.price.toFixed(2)} <span className="touches">({lv.touches}× touched)</span>
          </div>
        ))}
      </div>
    </div>
  );
}
