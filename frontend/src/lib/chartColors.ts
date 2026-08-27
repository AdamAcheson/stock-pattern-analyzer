// Single source of truth for overlay colors, shared between the chart
// (which needs them for series options) and the HTML legend (since
// lightweight-charts renders everything to <canvas> -- a series `title`
// draws its own always-on price-scale label with no way to suppress it
// short of leaving the field empty, so overlay identification has to
// live in real DOM/CSS instead).
export const OVERLAY_COLORS = {
  sma20: '#2563eb',
  sma50: '#7c3aed',
  sma200: '#ea580c',
  ema12: '#0891b2',
  ema26: '#be185d',
  bollinger: '#94a3b8',
  vwma20: '#f59e0b',
  rsi14: '#7c3aed',
  macd: '#2563eb',
  signal: '#ea580c',
} as const;

export const OVERLAY_LEGEND: { label: string; color: string }[] = [
  { label: 'SMA 20', color: OVERLAY_COLORS.sma20 },
  { label: 'SMA 50', color: OVERLAY_COLORS.sma50 },
  { label: 'SMA 200', color: OVERLAY_COLORS.sma200 },
  { label: 'EMA 12', color: OVERLAY_COLORS.ema12 },
  { label: 'EMA 26', color: OVERLAY_COLORS.ema26 },
  { label: 'Bollinger Bands', color: OVERLAY_COLORS.bollinger },
  { label: 'VWMA 20 (volume pane)', color: OVERLAY_COLORS.vwma20 },
];
