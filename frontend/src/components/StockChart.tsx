import { useEffect, useRef } from 'react';
import {
  createChart,
  CandlestickSeries,
  LineSeries,
  HistogramSeries,
  createSeriesMarkers,
  type IChartApi,
  type SeriesMarker,
  type Time,
  type UTCTimestamp,
} from 'lightweight-charts';
import type {
  OHLCVResponse,
  IndicatorsResponse,
  PatternsResponse,
  PatternMatch,
} from '../lib/api';
import { isoToUtcSeconds, isIntradayTimeframe } from '../lib/time';
import { OVERLAY_COLORS } from '../lib/chartColors';

interface Props {
  ohlcv: OHLCVResponse;
  indicators: IndicatorsResponse;
  patterns: PatternsResponse;
  timeframe: string;
}

const BULLISH_COLOR = '#16a34a';
const BEARISH_COLOR = '#dc2626';
const NEUTRAL_COLOR = '#6b7280';

function biasColor(bias: PatternMatch['directional_bias']): string {
  if (bias === 'Bullish') return BULLISH_COLOR;
  if (bias === 'Bearish') return BEARISH_COLOR;
  return NEUTRAL_COLOR;
}

// Drop null-value points -- lightweight-charts line series don't accept
// null, and early bars in any windowed indicator (e.g. day 1-19 of a
// 20-day SMA) are genuinely undefined, not zero.
function toLinePoints(points: { time: string; value: number | null }[]) {
  return points
    .filter((p): p is { time: string; value: number } => p.value !== null)
    .map((p) => ({ time: isoToUtcSeconds(p.time) as UTCTimestamp, value: p.value }));
}

export default function StockChart({ ohlcv, indicators, patterns, timeframe }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: 720,
      layout: {
        background: { color: '#ffffff' },
        textColor: '#1f2937',
      },
      grid: {
        vertLines: { color: '#f0f0f0' },
        horzLines: { color: '#f0f0f0' },
      },
      timeScale: {
        timeVisible: isIntradayTimeframe(timeframe),
        secondsVisible: false,
      },
      rightPriceScale: {
        borderVisible: false,
      },
      // Explicit rather than the library's default of deriving this from
      // the browser's language settings -- a viewer with no configured
      // locale (observed in a headless test container with no LANG set
      // at all) would otherwise hand lightweight-charts an invalid BCP-47
      // tag and spam console errors on every date/number format call.
      localization: {
        locale: 'en-US',
      },
    });
    chartRef.current = chart;

    // ---- Pane 0: price candles + MA/EMA/Bollinger overlays ----
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#16a34a',
      downColor: '#dc2626',
      borderVisible: false,
      wickUpColor: '#16a34a',
      wickDownColor: '#dc2626',
    });
    candleSeries.setData(
      ohlcv.bars.map((bar) => ({
        time: isoToUtcSeconds(bar.time) as UTCTimestamp,
        open: bar.open,
        high: bar.high,
        low: bar.low,
        close: bar.close,
      })),
    );
    candleSeries.priceScale().applyOptions({ scaleMargins: { top: 0.05, bottom: 0.25 } });

    // NOTE on `title`: lightweight-charts draws a series' `title` as its
    // own always-visible label on the price scale -- in this version
    // that happens regardless of `lastValueVisible`, which only governs
    // the separate numeric last-value box. With 7 overlays sharing one
    // price scale in a ~$100 range, titled labels collide into an
    // unreadable stack (caught by actually rendering this in a browser
    // and looking at it, not just by reading the type signature). So
    // every overlay series here is titled '' and identified instead by
    // the HTML/CSS legend in ChartLegend.tsx, which shares the same
    // color constants from lib/chartColors.ts.
    const overlaySpecs: { data: IndicatorsResponse['sma_20']; color: string; lineWidth: 1 | 2 }[] = [
      { data: indicators.sma_20, color: OVERLAY_COLORS.sma20, lineWidth: 1 },
      { data: indicators.sma_50, color: OVERLAY_COLORS.sma50, lineWidth: 1 },
      { data: indicators.sma_200, color: OVERLAY_COLORS.sma200, lineWidth: 2 },
      { data: indicators.ema_12, color: OVERLAY_COLORS.ema12, lineWidth: 1 },
      { data: indicators.ema_26, color: OVERLAY_COLORS.ema26, lineWidth: 1 },
    ];
    for (const spec of overlaySpecs) {
      const series = chart.addSeries(LineSeries, {
        color: spec.color,
        lineWidth: spec.lineWidth,
        title: '',
        priceLineVisible: false,
        lastValueVisible: false,
      });
      series.setData(toLinePoints(spec.data));
    }

    // Bollinger Bands: upper/lower as thin dashed lines, middle omitted
    // (it's identical to SMA 20, already drawn above).
    for (const key of ['upper', 'lower'] as const) {
      const series = chart.addSeries(LineSeries, {
        color: OVERLAY_COLORS.bollinger,
        lineWidth: 1,
        lineStyle: 2, // dashed
        title: '',
        priceLineVisible: false,
        lastValueVisible: false,
      });
      series.setData(
        indicators.bollinger
          .filter((p) => p[key] !== null)
          .map((p) => ({ time: isoToUtcSeconds(p.time) as UTCTimestamp, value: p[key] as number })),
      );
    }

    // Support/resistance as horizontal price lines on the candle series.
    // No axis label here either, for the same collision reason as above
    // (up to 5 support + 5 resistance levels sharing the price scale) --
    // the exact prices and touch counts are listed as text in the
    // "Key Levels" panel instead, where they're actually legible.
    for (const level of indicators.support) {
      candleSeries.createPriceLine({
        price: level.price,
        color: '#16a34a',
        lineWidth: 1,
        lineStyle: 3, // dotted
        axisLabelVisible: false,
      });
    }
    for (const level of indicators.resistance) {
      candleSeries.createPriceLine({
        price: level.price,
        color: '#dc2626',
        lineWidth: 1,
        lineStyle: 3,
        axisLabelVisible: false,
      });
    }

    // Pattern markers: one at the pattern's start, one at its end (or,
    // if confirmed, at the actual breakout date instead of the shape's
    // end -- the two can be well apart, e.g. a triangle that finished
    // forming in June but didn't break out until August).
    const markers: SeriesMarker<Time>[] = [];
    for (const p of patterns.patterns) {
      const color = biasColor(p.directional_bias);
      markers.push({
        time: isoToUtcSeconds(p.start) as UTCTimestamp,
        position: 'aboveBar',
        color,
        shape: 'circle',
        text: p.name,
      });
      const endTime = p.confirmation_date ?? p.end;
      const confirmedShape = p.directional_bias === 'Bearish' ? 'arrowDown' : 'arrowUp';
      markers.push({
        time: isoToUtcSeconds(endTime) as UTCTimestamp,
        position: p.directional_bias === 'Bearish' ? 'aboveBar' : 'belowBar',
        color,
        shape: p.status === 'Confirmed' ? confirmedShape : 'square',
        text: p.status === 'Confirmed' ? `${p.name} ✓` : `${p.name} (forming)`,
      });
    }
    markers.sort((a, b) => (a.time as number) - (b.time as number));
    createSeriesMarkers(candleSeries, markers);

    // ---- Pane 1: volume + VWMA ----
    const volumeSeries = chart.addSeries(
      HistogramSeries,
      {
        priceFormat: { type: 'volume' },
        color: '#94a3b8',
        priceLineVisible: false,
        lastValueVisible: false,
      },
      1,
    );
    volumeSeries.setData(
      ohlcv.bars.map((bar) => ({
        time: isoToUtcSeconds(bar.time) as UTCTimestamp,
        value: bar.volume,
        color: bar.close >= bar.open ? 'rgba(22,163,74,0.5)' : 'rgba(220,38,38,0.5)',
      })),
    );
    const vwmaSeries = chart.addSeries(
      LineSeries,
      { color: OVERLAY_COLORS.vwma20, lineWidth: 1, title: '', priceLineVisible: false, lastValueVisible: false },
      1,
    );
    vwmaSeries.setData(toLinePoints(indicators.vwma_20));

    // ---- Pane 2: RSI ----
    // Only 2 reference lines share this pane's own price scale (no other
    // series here), so axis labels for them don't collide the way the
    // price pane's overlays did -- fine to keep visible. RSI is 0-100 by
    // definition (verified in Stage 2), but lightweight-charts
    // auto-scales each pane's price axis to the *visible data's*
    // min/max, not a fixed range -- if RSI spent the whole window
    // between 35 and 70, that's what the axis would stretch to fit,
    // making the 70/30 lines land in visually misleading positions
    // (caught by rendering this and looking at it: the RSI line and its
    // reference lines were compressed into an unrepresentative band).
    // `autoscaleInfoProvider` is the documented way to pin a series'
    // price scale to a fixed range regardless of its actual data.
    const rsiSeries = chart.addSeries(
      LineSeries,
      {
        color: OVERLAY_COLORS.rsi14,
        lineWidth: 1,
        title: '',
        priceLineVisible: false,
        lastValueVisible: false,
        autoscaleInfoProvider: () => ({ priceRange: { minValue: 0, maxValue: 100 } }),
      },
      2,
    );
    rsiSeries.setData(toLinePoints(indicators.rsi_14));
    rsiSeries.createPriceLine({ price: 70, color: '#dc2626', lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: '70' });
    rsiSeries.createPriceLine({ price: 30, color: '#16a34a', lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: '30' });

    // ---- Pane 3: MACD ----
    const macdSeries = chart.addSeries(
      LineSeries,
      { color: OVERLAY_COLORS.macd, lineWidth: 1, title: '', priceLineVisible: false, lastValueVisible: false },
      3,
    );
    macdSeries.setData(
      indicators.macd
        .filter((p) => p.macd !== null)
        .map((p) => ({ time: isoToUtcSeconds(p.time) as UTCTimestamp, value: p.macd as number })),
    );
    const signalSeries = chart.addSeries(
      LineSeries,
      { color: OVERLAY_COLORS.signal, lineWidth: 1, title: '', priceLineVisible: false, lastValueVisible: false },
      3,
    );
    signalSeries.setData(
      indicators.macd
        .filter((p) => p.signal !== null)
        .map((p) => ({ time: isoToUtcSeconds(p.time) as UTCTimestamp, value: p.signal as number })),
    );
    const histSeries = chart.addSeries(
      HistogramSeries,
      { priceLineVisible: false, lastValueVisible: false, title: '' },
      3,
    );
    histSeries.setData(
      indicators.macd
        .filter((p) => p.histogram !== null)
        .map((p) => ({
          time: isoToUtcSeconds(p.time) as UTCTimestamp,
          value: p.histogram as number,
          color: (p.histogram as number) >= 0 ? 'rgba(22,163,74,0.6)' : 'rgba(220,38,38,0.6)',
        })),
    );

    // Give each indicator pane a fixed, readable height instead of the
    // default even split across 4 panes (which makes RSI/MACD unreadably
    // short next to the candlestick pane).
    // `setHeight` sets a one-off pixel height that gets overridden by the
    // chart's own layout pass (observed directly: panes ended up
    // [552, 27, 27, 83] instead of the requested [420, 120, 90, 90], and
    // that 27px RSI pane was the real reason its 0-100-scaled line and
    // 70/30 reference lines looked visually compressed into a sliver --
    // the scale itself was correct, the pane just had almost no room).
    // `setStretchFactor` is the persistent, ratio-based sizing API and
    // is respected across layout passes.
    const panes = chart.panes();
    panes[0]?.setStretchFactor(420);
    panes[1]?.setStretchFactor(120);
    panes[2]?.setStretchFactor(90);
    panes[3]?.setStretchFactor(90);

    chart.timeScale().fitContent();

    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
      chartRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ohlcv, indicators, patterns, timeframe]);

  return <div ref={containerRef} style={{ width: '100%' }} />;
}
