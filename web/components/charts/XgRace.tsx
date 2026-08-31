"use client";
// Stepped cumulative xG, one line per side, goals as filled dots, minute
// axis 0-90 with a half-time divider.
import type { MatchDetail } from "@/lib/data";
import { fmtNum } from "@/lib/format";
import { teamColor, teamName } from "@/lib/teamColors";
import { useInView } from "@/hooks/useInView";
import { DrawPath } from "@/components/motion/DrawPath";

const W = 640;
const H = 260;
const PAD = { l: 34, r: 12, t: 12, b: 26 };

function stepPath(pts: { minute: number; xg: number }[], xs: (m: number) => number, ys: (v: number) => number) {
  if (!pts.length) return "";
  let d = `M ${xs(pts[0].minute)} ${ys(pts[0].xg)}`;
  for (let i = 1; i < pts.length; i++) {
    d += ` L ${xs(pts[i].minute)} ${ys(pts[i - 1].xg)} L ${xs(pts[i].minute)} ${ys(pts[i].xg)}`;
  }
  d += ` L ${xs(90)} ${ys(pts[pts.length - 1].xg)}`;
  return d;
}

export function XgRace({ match }: { match: MatchDetail }) {
  const [ref, inView] = useInView<HTMLDivElement>();
  const maxMinute = 90;
  const maxXg =
    Math.max(
      0.5,
      ...match.xg_race.home.map((p) => p.xg),
      ...match.xg_race.away.map((p) => p.xg),
    ) * 1.1;

  const xs = (m: number) => PAD.l + (Math.min(m, maxMinute) / maxMinute) * (W - PAD.l - PAD.r);
  const ys = (v: number) => H - PAD.b - (v / maxXg) * (H - PAD.t - PAD.b);

  const homeColor = teamColor(match.home).color;
  const awayColor = teamColor(match.away).color;
  const goals = match.shots.filter((s) => s.result === "Goal" || s.result === "OwnGoal");

  return (
    <div ref={ref}>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet" style={{ width: "100%", height: "auto" }} role="img">
        <title>
          xG-Verlauf: {teamName(match.home)} {fmtNum(match.home_xg)} – {fmtNum(match.away_xg)}{" "}
          {teamName(match.away)}
        </title>
        {/* horizontal grid only */}
        {[0, maxXg / 2, maxXg].map((v, i) => (
          <line key={i} className="chart-grid" x1={PAD.l} y1={ys(v)} x2={W - PAD.r} y2={ys(v)} />
        ))}
        {/* half-time divider */}
        <line
          x1={xs(45)}
          y1={PAD.t}
          x2={xs(45)}
          y2={H - PAD.b}
          stroke="var(--border-strong)"
          strokeDasharray="3 4"
        />
        <text x={xs(45)} y={H - 8} className="chart-axis-label" textAnchor="middle">
          HZ
        </text>
        {[0, 90].map((m) => (
          <text key={m} x={xs(m)} y={H - 8} className="chart-axis-label" textAnchor="middle">
            {m}&#39;
          </text>
        ))}
        {[0, maxXg / 2, maxXg].map((v, i) => (
          <text key={i} x={PAD.l - 6} y={ys(v) + 3} className="chart-axis-label" textAnchor="end">
            {fmtNum(v, 1)}
          </text>
        ))}
        <DrawPath
          d={stepPath(match.xg_race.home, xs, ys)}
          inView={inView}
          fill="none"
          stroke={homeColor}
          strokeWidth={2.5}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <DrawPath
          d={stepPath(match.xg_race.away, xs, ys)}
          inView={inView}
          fill="none"
          stroke={awayColor}
          strokeWidth={2.5}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        {goals.map((g, i) => {
          const race = g.team_side === "h" ? match.xg_race.home : match.xg_race.away;
          const near = race.reduce(
            (a, b) => (Math.abs(b.minute - g.minute) < Math.abs(a.minute - g.minute) ? b : a),
            race[0] ?? { minute: 0, xg: 0 },
          );
          return (
            <circle
              key={i}
              cx={xs(g.minute)}
              cy={ys(near.xg)}
              r={6}
              fill={g.team_side === "h" ? homeColor : awayColor}
              stroke="var(--bg)"
              strokeWidth={2}
            >
              <title>
                {g.minute}&#39; {g.player ?? ""} (
                {g.team_side === "h" ? teamName(match.home) : teamName(match.away)})
              </title>
            </circle>
          );
        })}
        <text x={W - PAD.r} y={PAD.t + 10} fontSize={11} textAnchor="end" fill={homeColor}>
          {teamName(match.home)}
        </text>
        <text x={W - PAD.r} y={PAD.t + 24} fontSize={11} textAnchor="end" fill={awayColor}>
          {teamName(match.away)}
        </text>
      </svg>
    </div>
  );
}
