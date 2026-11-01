// Small helpers shared by the team-page charts.

/** A "nice" axis: round bounds and evenly spaced ticks covering [min, max]. */
export function niceScale(min: number, max: number, count = 4): { lo: number; hi: number; ticks: number[] } {
  if (max - min < 1e-9) {
    max = min + 1;
  }
  const raw = (max - min) / count;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? 10 * mag;
  const lo = Math.floor(min / step) * step;
  const hi = Math.ceil(max / step) * step;
  const ticks: number[] = [];
  for (let v = lo; v <= hi + step / 2; v += step) ticks.push(Math.round(v / step) * step);
  return { lo, hi, ticks };
}

/** Show every k-th x label so they never collide. */
export function labelEvery(count: number, innerWidth: number, minPx = 34): number {
  const band = innerWidth / Math.max(count, 1);
  return Math.max(1, Math.ceil(minPx / band));
}
