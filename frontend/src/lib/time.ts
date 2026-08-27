// The backend sends naive ISO-8601 timestamps (no timezone suffix) that
// already represent exchange-local wall-clock time (see
// backend/app/data_fetch.py's _normalize: tz is stripped, not converted).
// lightweight-charts' UTCTimestamp is always interpreted and *displayed*
// in UTC regardless of the viewer's browser timezone, so encoding the
// exchange-local wall-clock components as if they were UTC is the
// correct trick here: it makes the chart show exactly the wall-clock
// time the backend sent, for every viewer, with no local-timezone drift.
// (Do NOT use `new Date(iso).getTime()` -- a string with no "Z"/offset is
// parsed as browser-local time by the JS Date constructor, which would
// shift bars by the viewer's UTC offset.)
export function isoToUtcSeconds(iso: string): number {
  const [datePart, timePart] = iso.split('T');
  const [year, month, day] = datePart.split('-').map(Number);
  const [hh = 0, mm = 0, ss = 0] = (timePart ?? '00:00:00').split(':').map(Number);
  return Math.floor(Date.UTC(year, month - 1, day, hh, mm, ss) / 1000);
}

export function isIntradayTimeframe(timeframe: string): boolean {
  return timeframe === '1D' || timeframe === '1W';
}
