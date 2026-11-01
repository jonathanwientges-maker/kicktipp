"use client";
// One column per match: xG scored goes up, xG conceded goes down, dots mark
// the goals that actually fell. A dot above its bar = clinical, below = wasteful.
import { useState } from "react";
import type { TeamGame } from "@/lib/teamAnalysis";
import { fmtNum } from "@/lib/format";
import { teamCode } from "@/lib/teamCodes";
import { teamName } from "@/lib/teamColors";
import { useChartWidth } from "@/hooks/useChartWidth";
import { labelEvery, niceScale } from "./chartUtil";

const H = 280;
const PAD = { l: 34, r: 10, t: 12, b: 46 };

const resOf = (g: TeamGame) => (g.pts === 3 ? "S" : g.pts === 1 ? "U" : "N");
const resColor = (g: TeamGame) => (g.pts === 3 ? "var(--positive)" : g.pts === 1 ? "var(--text-muted)" : "var(--negative)");

export function MatchBars({ games, color }: { games: TeamGame[]; color: string }) {
  const [ref, W] = useChartWidth<HTMLDivElement>();
  const [sel, setSel] = useState<number | null>(null);
  const n = games.length;
  if (n === 0) return <p className="muted fx-small">Noch keine Spiele.</p>;

  const peak = Math.max(...games.flatMap((g) => [g.xgf, g.xga, g.gf, g.ga]), 1);
  const { hi, ticks: pos } = niceScale(0, peak, 3);
  const iw = W - PAD.l - PAD.r;
  const band = iw / n;
  const bw = Math.min(30, band * 0.58);
  const y0 = PAD.t + (H - PAD.t - PAD.b) / 2;
  const half = (H - PAD.t - PAD.b) / 2;
  const ys = (v: number) => y0 - (v / hi) * half; // v may be negative
  const cx = (i: number) => PAD.l + band * (i + 0.5);
  const every = labelEvery(n, iw, 30);
  const cur = sel ?? n - 1;
  const g = games[cur];

  return (
    <div ref={ref}>
      <div className="chart-readout" aria-live="polite">
        <strong>
          Spieltag {g.round} · {g.venue === "away" ? "@ " : ""}
          {teamName(g.opponent)} {g.gf}:{g.ga}
        </strong>
        <span className="num">
          xG {fmtNum(g.xgf, 2)} : {fmtNum(g.xga, 2)}
        </span>
      </div>
      <svg width={W} height={H} role="img" aria-label="xG und Tore pro Spiel" style={{ display: "block" }}>
        {[...pos.slice(1).map((v) => v), ...pos.slice(1).map((v) => -v)].map((v) => (
          <g key={v}>
            <line className="chart-grid" x1={PAD.l} x2={W - PAD.r} y1={ys(v)} y2={ys(v)} />
            <text x={PAD.l - 6} y={ys(v) + 4} className="chart-tick" textAnchor="end">
              {Math.abs(v)}
            </text>
          </g>
        ))}
        <line x1={PAD.l} x2={W - PAD.r} y1={y0} y2={y0} stroke="var(--border-strong)" />
        <text x={PAD.l + 2} y={PAD.t + 9} className="chart-tick chart-tick-dim">↑ xG erzielt</text>
        <text x={PAD.l + 2} y={H - PAD.b - 3} className="chart-tick chart-tick-dim">↓ xG zugelassen</text>
        {games.map((gm, i) => (
          <g key={i} opacity={sel === null || sel === i ? 1 : 0.55}>
            <rect x={cx(i) - bw / 2} y={ys(gm.xgf)} width={bw} height={Math.max(0, y0 - ys(gm.xgf))} rx={2} fill={color} />
            <rect x={cx(i) - bw / 2} y={y0} width={bw} height={Math.max(0, ys(-gm.xga) - y0)} rx={2} fill="var(--text-dim)" fillOpacity={0.75} />
            <circle cx={cx(i)} cy={ys(gm.gf)} r={4.5} fill="var(--text)" stroke="var(--surface)" strokeWidth={1.5} />
            <circle cx={cx(i)} cy={ys(-gm.ga)} r={4} fill="var(--surface)" stroke="var(--text)" strokeWidth={1.75} />
            {i % every === 0 || i === n - 1 ? (
              <>
                <text x={cx(i)} y={H - PAD.b + 15} className="chart-tick" textAnchor="middle">
                  {gm.venue === "away" ? "@" : ""}
                  {teamCode(gm.opponent)}
                </text>
                <text x={cx(i)} y={H - PAD.b + 30} className="chart-tick" textAnchor="middle" fill={resColor(gm)} style={{ fontWeight: 700 }}>
                  {gm.gf}:{gm.ga}
                </text>
              </>
            ) : null}
            <title>{`${gm.venue === "away" ? "@ " : ""}${teamName(gm.opponent)} ${gm.gf}:${gm.ga} (${resOf(gm)}) · xG ${fmtNum(gm.xgf, 2)}:${fmtNum(gm.xga, 2)}`}</title>
          </g>
        ))}
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
      <div className="chart-legend">
        <span><i className="lg-box" style={{ background: color }} /> xG erzielt</span>
        <span><i className="lg-box" style={{ background: "var(--text-dim)" }} /> xG zugelassen</span>
        <span><i className="lg-dot" /> eigene Tore</span>
        <span><i className="lg-dot lg-hollow" /> Gegentore</span>
      </div>
    </div>
  );
}
