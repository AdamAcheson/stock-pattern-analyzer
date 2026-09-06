// Single source of truth for overlay colors, shared between the chart
// (which needs them for series options) and the HTML legend (since
// lightweight-charts renders everything to <canvas> -- a series `title`
// draws its own always-on price-scale label with no way to suppress it
// short of leaving the field empty, so overlay identification has to
// live in real DOM/CSS instead).
export const OVERLAY_COLORS = {
  sma20: '#2563eb',
  sma50: '#7c3aed',
  sma100: '#059669',
  sma200: '#ea580c',
  ema12: '#0891b2',
  ema26: '#be185d',
  bollinger: '#94a3b8',
  vwma20: '#f59e0b',
  fibonacci: '#a855f7',
  rsi14: '#7c3aed',
  macd: '#2563eb',
  signal: '#ea580c',
} as const;

// `key` matches the corresponding OVERLAY_COLORS key and the id StockChart
// registers its series/price-lines under, so hovering a legend entry can
// tell the chart which one to highlight.
export type OverlayKey = keyof typeof OVERLAY_COLORS;

// `dashed` mirrors each series' actual `lineStyle` in StockChart.tsx (2 =
// dashed) -- Bollinger Bands and Fibonacci Levels are drawn dashed on the
// chart, so the legend swatch needs to render dashed too, or it misleads
// readers into expecting a solid line (caught by a user comparing the
// legend swatch against the actual dashed line on the chart).
export const OVERLAY_LEGEND: { label: string; color: string; key: OverlayKey; dashed?: boolean }[] = [
  { label: 'SMA 20', color: OVERLAY_COLORS.sma20, key: 'sma20' },
  { label: 'SMA 50', color: OVERLAY_COLORS.sma50, key: 'sma50' },
  { label: 'SMA 100', color: OVERLAY_COLORS.sma100, key: 'sma100' },
  { label: 'SMA 200', color: OVERLAY_COLORS.sma200, key: 'sma200' },
  { label: 'EMA 12', color: OVERLAY_COLORS.ema12, key: 'ema12' },
  { label: 'EMA 26', color: OVERLAY_COLORS.ema26, key: 'ema26' },
  { label: 'Bollinger Bands', color: OVERLAY_COLORS.bollinger, key: 'bollinger', dashed: true },
  { label: 'VWMA 20 (volume pane)', color: OVERLAY_COLORS.vwma20, key: 'vwma20' },
  { label: 'Fibonacci Levels', color: OVERLAY_COLORS.fibonacci, key: 'fibonacci', dashed: true },
];

// Converts a '#rrggbb' overlay color to a low-alpha rgba() for dimming
// everything except whichever legend entry is currently hovered.
export function dimColor(hex: string, alpha = 0.15): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}
