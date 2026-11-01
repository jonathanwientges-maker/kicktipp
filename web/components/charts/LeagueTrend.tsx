"use client";
// A per-game metric (PPDA, deep completions) drawn against the league: the
// shaded band is the middle 50 % of all team-games, the dashed line the league
// average. Without that reference a single team's line says nothing.
import { useState } from "react";
import type { LeagueStat, TeamGame } from "@/lib/teamAnalysis";
import { fmtNum } from "@/lib/format";
import { teamCode } from "@/lib/teamCodes";
import { teamName } from "@/lib/teamColors";
import { useChartWidth } from "@/hooks/useChartWidth";
import { labelEvery, niceScale } from "./chartUtil";

const H = 230;
const PAD = { l: 38, r: 62, t: 14, b: 40 };

export function LeagueTrend({
  games,
  values,
  league,
  color,
  dp = 1,
  unit,
}: {
  games: TeamGame[];
  values: (number | null)[];
  league: LeagueStat;
  color: string;
  dp?: number;
  /** y-axis caption, e.g. "PPDA" */
  unit: string;
}) {
  const [ref, W] = useChartWidth<HTMLDivElement>();
  const [sel, setSel] = useState<number | null>(null);
  const n = games.length;
  const present = values.filter((v): v is number => v !== null);
  if (n === 0 || !present.length) return <p className="muted fx-small">Noch keine Werte.</p>;

  const { lo, hi, ticks } = niceScale(Math.min(...present, league.p25), Math.max(...present, league.p75), 4);
  const iw = W - PAD.l - PAD.r;
  const band = iw / n;
  const cx = (i: number) => PAD.l + band * (i + 0.5);
  const ys = (v: number) => H - PAD.b - ((v - lo) / (hi - lo)) * (H - PAD.t - PAD.b);
  const every = labelEvery(n, iw);

  let d = "";
  let pen = false;
  values.forEach((v, i) => {
    if (v === null) {
      pen = false;
      return;
    }
    d += `${pen ? "L" : "M"} ${cx(i)} ${ys(v)} `;
    pen = true;
  });

  const lastIdx = values.map((v) => v !== null).lastIndexOf(true);
  const curIdx = sel ?? lastIdx;
  const g = games[curIdx];
  const cv = values[curIdx];

  return (
    <div ref={ref}>
      <div className="chart-readout" aria-live="polite">
        <strong>
          Spieltag {g.round} · {g.venue === "away" ? "@ " : ""}
          {teamName(g.opponent)}
        </strong>
        <span className="num">
          {cv === null ? "–" : fmtNum(cv, dp)} <span className="muted">(Liga Ø {fmtNum(league.mean, dp)})</span>
        </span>
      </div>
      <svg width={W} height={H} role="img" aria-label={`${unit} pro Spiel im Vergleich zur Liga`} style={{ display: "block" }}>
        <rect
          x={PAD.l}
          width={iw}
          y={ys(league.p75)}
          height={Math.max(2, ys(league.p25) - ys(league.p75))}
          fill="var(--text-dim)"
          fillOpacity={0.14}
        />
        {ticks.map((v) => (
          <g key={v}>
            <line className="chart-grid" x1={PAD.l} x2={W - PAD.r} y1={ys(v)} y2={ys(v)} />
            <text x={PAD.l - 7} y={ys(v) + 4} className="chart-tick" textAnchor="end">
              {fmtNum(v, v % 1 ? 1 : 0)}
            </text>
          </g>
        ))}
        <line x1={PAD.l} x2={W - PAD.r} y1={ys(league.mean)} y2={ys(league.mean)} stroke="var(--text-muted)" strokeDasharray="5 4" />
        <text x={W - PAD.r + 6} y={ys(league.mean) + 4} className="chart-end" fill="var(--text-muted)">
          Liga Ø
        </text>
        <text x={PAD.l + 4} y={ys(league.p75) + 12} className="chart-tick chart-tick-dim">
          mittlere 50 % der Liga
        </text>
        <path d={d} fill="none" stroke={color} strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round" />
        {values.map((v, i) =>
          v === null ? null : (
            <circle key={i} cx={cx(i)} cy={ys(v)} r={i === curIdx ? 5.5 : 3.5} fill={color} stroke="var(--surface)" strokeWidth={1.5} />
          ),
        )}
        <line x1={PAD.l} x2={W - PAD.r} y1={H - PAD.b} y2={H - PAD.b} stroke="var(--border-strong)" />
        {games.map((gm, i) =>
          i % every === 0 || i === n - 1 ? (
            <g key={i}>
              <text x={cx(i)} y={H - PAD.b + 15} className="chart-tick" textAnchor="middle">
                {gm.venue === "away" ? "@" : ""}
                {teamCode(gm.opponent)}
              </text>
              <text x={cx(i)} y={H - PAD.b + 29} className="chart-tick chart-tick-dim" textAnchor="middle">
                {gm.round}
              </text>
            </g>
          ) : null,
        )}
        {games.map((_, i) => (
          <rect
            key={i}
            x={PAD.l + band * i}
            y={PAD.t}
            width={band}
            height={H - PAD.t - PAD.b}
            fill="transparent"
            tabIndex={0}
            role="button"
            aria-label={`Spieltag ${games[i].round}`}
            onPointerEnter={() => setSel(i)}
            onClick={() => setSel(i)}
            onFocus={() => setSel(i)}
            onPointerLeave={(e) => e.pointerType === "mouse" && setSel(null)}
            style={{ outline: "none" }}
          />
        ))}
      </svg>
    </div>
  );
}
