"use client";
// Cumulative points vs. cumulative xPunkte. The shaded area between the two
// lines IS the luck: amber where the team has more points than its chances
// earned, blue where it has fewer.
import { useState } from "react";
import type { TeamGame } from "@/lib/teamAnalysis";
import { fmtNum, fmtSigned } from "@/lib/format";
import { teamCode } from "@/lib/teamCodes";
import { teamName } from "@/lib/teamColors";
import { useChartWidth } from "@/hooks/useChartWidth";
import { labelEvery, niceScale } from "./chartUtil";

const H = 250;
const PAD = { l: 38, r: 74, t: 14, b: 40 };

export function PointsVsXpts({ games, color }: { games: TeamGame[]; color: string }) {
  const [ref, W] = useChartWidth<HTMLDivElement>();
  const [sel, setSel] = useState<number | null>(null);
  const n = games.length;
  if (n === 0) return <p className="muted fx-small">Noch keine Spiele.</p>;

  const pts = [0, ...games.map((g) => g.cumPts)];
  const xpts = [0, ...games.map((g) => g.cumXpts)];
  const { hi, ticks } = niceScale(0, Math.max(...pts, ...xpts), 4);
  const iw = W - PAD.l - PAD.r;
  const xs = (i: number) => PAD.l + (i / n) * iw;
  const ys = (v: number) => H - PAD.b - (v / hi) * (H - PAD.t - PAD.b);
  const every = labelEvery(n, iw);

  // shaded gap, split where the two lines cross
  const gap: { d: string; hot: boolean }[] = [];
  for (let i = 0; i < n; i++) {
    const d0 = pts[i] - xpts[i];
    const d1 = pts[i + 1] - xpts[i + 1];
    const poly = (ps: [number, number][], hot: boolean) =>
      gap.push({ d: `M ${ps.map((p) => p.join(" ")).join(" L ")} Z`, hot });
    if (d0 * d1 >= 0) {
      poly(
        [
          [xs(i), ys(pts[i])],
          [xs(i + 1), ys(pts[i + 1])],
          [xs(i + 1), ys(xpts[i + 1])],
          [xs(i), ys(xpts[i])],
        ],
        d0 + d1 >= 0,
      );
    } else {
      const t = d0 / (d0 - d1);
      const cx = xs(i + t);
      const cy = ys(pts[i] + (pts[i + 1] - pts[i]) * t);
      poly([[xs(i), ys(pts[i])], [cx, cy], [xs(i), ys(xpts[i])]], d0 > 0);
      poly([[cx, cy], [xs(i + 1), ys(pts[i + 1])], [xs(i + 1), ys(xpts[i + 1])]], d1 > 0);
    }
  }

  const line = (v: number[]) => v.map((y, i) => `${i ? "L" : "M"} ${xs(i)} ${ys(y)}`).join(" ");
  const cur = sel ?? n;
  const g = games[cur - 1];
  const luck = pts[cur] - xpts[cur];
  // end labels must not overlap
  const yP = ys(pts[n]);
  const yX = ys(xpts[n]);
  const sep = Math.abs(yP - yX) < 13 ? 7 : 0;
  const pDy = yP <= yX ? -sep : sep;

  return (
    <div ref={ref}>
      <div className="chart-readout" aria-live="polite">
        <strong>
          Nach Spiel {cur} · {g.venue === "away" ? "@ " : ""}
          {teamName(g.opponent)} {g.gf}:{g.ga}
        </strong>
        <span className="num">
          {pts[cur]} Pkt · {fmtNum(xpts[cur], 1)} xPkt ·{" "}
          <span style={{ color: luck >= 0 ? "var(--luck-hot)" : "var(--luck-cold)" }}>{fmtSigned(luck, 1)}</span>
        </span>
      </div>
      <svg width={W} height={H} role="img" aria-label="Kumulierte Punkte und xPunkte pro Spiel" style={{ display: "block" }}>
        {ticks.map((v) => (
          <g key={v}>
            <line className="chart-grid" x1={PAD.l} x2={W - PAD.r} y1={ys(v)} y2={ys(v)} />
            <text x={PAD.l - 7} y={ys(v) + 4} className="chart-tick" textAnchor="end">
              {v}
            </text>
          </g>
        ))}
        {gap.map((s, i) => (
          <path key={i} d={s.d} fill={s.hot ? "var(--luck-hot)" : "var(--luck-cold)"} fillOpacity={0.28} />
        ))}
        <path d={line(xpts)} fill="none" stroke="var(--text-muted)" strokeWidth={2} strokeDasharray="5 4" />
        <path d={line(pts)} fill="none" stroke={color} strokeWidth={2.75} strokeLinecap="round" strokeLinejoin="round" />
        {pts.map((v, i) => (
          <circle key={i} cx={xs(i)} cy={ys(v)} r={i === cur ? 5 : 3} fill={color} stroke="var(--surface)" strokeWidth={1.5} />
        ))}
        {sel !== null && <line x1={xs(cur)} x2={xs(cur)} y1={PAD.t} y2={H - PAD.b} stroke="var(--border-strong)" />}
        <text x={xs(n) + 9} y={yP + 4 + pDy} className="chart-end" fill={color}>
          Punkte
        </text>
        <text x={xs(n) + 9} y={yX + 4 - pDy} className="chart-end" fill="var(--text-muted)">
          xPunkte
        </text>
        {/* x axis: one tick per game, opponent underneath */}
        <line x1={PAD.l} x2={W - PAD.r} y1={H - PAD.b} y2={H - PAD.b} stroke="var(--border-strong)" />
        {games.map((gm, i) =>
          i % every === 0 || i === n - 1 ? (
            <g key={i}>
              <text x={xs(i + 1)} y={H - PAD.b + 15} className="chart-tick" textAnchor="middle">
                {gm.venue === "away" ? "@" : ""}
                {teamCode(gm.opponent)}
              </text>
              <text x={xs(i + 1)} y={H - PAD.b + 29} className="chart-tick chart-tick-dim" textAnchor="middle">
                {i + 1}
              </text>
            </g>
          ) : null,
        )}
        {games.map((_, i) => (
          <rect
            key={i}
            x={xs(i + 1) - iw / n / 2}
            y={PAD.t}
            width={iw / n}
            height={H - PAD.t - PAD.b}
            fill="transparent"
            tabIndex={0}
            role="button"
            aria-label={`Spiel ${i + 1}`}
            onPointerEnter={() => setSel(i + 1)}
            onClick={() => setSel(i + 1)}
            onFocus={() => setSel(i + 1)}
            onPointerLeave={(e) => e.pointerType === "mouse" && setSel(null)}
            style={{ outline: "none" }}
          />
        ))}
      </svg>
      <div className="chart-legend">
        <span><i className="lg-line" style={{ background: color }} /> Punkte</span>
        <span><i className="lg-line lg-dash" /> xPunkte</span>
        <span><i className="lg-box" style={{ background: "var(--luck-hot)" }} /> mehr Punkte als xPunkte (Glück)</span>
        <span><i className="lg-box" style={{ background: "var(--luck-cold)" }} /> weniger (Pech)</span>
      </div>
    </div>
  );
}
