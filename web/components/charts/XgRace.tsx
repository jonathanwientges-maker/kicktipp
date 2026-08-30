// Stepped cumulative xG, one line per side, goals as filled dots, minute
// axis 0-90 with a half-time divider (BUILD BLUEPRINT §7.1).
import type { MatchDetail } from "@/lib/data";
import { fmtNum } from "@/lib/format";

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
  const maxMinute = 90;
  const maxXg =
    Math.max(
      0.5,
      ...match.xg_race.home.map((p) => p.xg),
      ...match.xg_race.away.map((p) => p.xg),
    ) * 1.1;

  const xs = (m: number) => PAD.l + (Math.min(m, maxMinute) / maxMinute) * (W - PAD.l - PAD.r);
  const ys = (v: number) => H - PAD.b - (v / maxXg) * (H - PAD.t - PAD.b);

  const goals = match.shots.filter((s) => s.result === "Goal" || s.result === "OwnGoal");

  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet" style={{ width: "100%", height: "auto" }} role="img">
      <title>
        xG-Verlauf: {match.home} {fmtNum(match.home_xg)} – {fmtNum(match.away_xg)} {match.away}
      </title>
      {/* axes */}
      <line x1={PAD.l} y1={H - PAD.b} x2={W - PAD.r} y2={H - PAD.b} stroke="var(--border)" />
      <line x1={PAD.l} y1={PAD.t} x2={PAD.l} y2={H - PAD.b} stroke="var(--border)" />
      {/* half-time divider */}
      <line x1={xs(45)} y1={PAD.t} x2={xs(45)} y2={H - PAD.b} stroke="var(--border)" strokeDasharray="3 3" />
      <text x={xs(45)} y={H - 8} fontSize={10} textAnchor="middle" fill="var(--muted)">
        HZ
      </text>
      {[0, 45, 90].map((m) => (
        <text key={m} x={xs(m)} y={H - 8} fontSize={10} textAnchor="middle" fill="var(--muted)">
          {m}&#39;
        </text>
      ))}
      {[0, maxXg / 2, maxXg].map((v, i) => (
        <text key={i} x={PAD.l - 6} y={ys(v) + 3} fontSize={10} textAnchor="end" fill="var(--muted)">
          {fmtNum(v, 1)}
        </text>
      ))}
      <path d={stepPath(match.xg_race.home, xs, ys)} fill="none" stroke="var(--accent)" strokeWidth={2} />
      <path d={stepPath(match.xg_race.away, xs, ys)} fill="none" stroke="var(--muted)" strokeWidth={2} />
      {goals.map((g, i) => {
        const race = g.team_side === "h" ? match.xg_race.home : match.xg_race.away;
        const near = race.reduce((a, b) => (Math.abs(b.minute - g.minute) < Math.abs(a.minute - g.minute) ? b : a), race[0] ?? { minute: 0, xg: 0 });
        return (
          <circle key={i} cx={xs(g.minute)} cy={ys(near.xg)} r={4} fill={g.team_side === "h" ? "var(--accent)" : "var(--text)"}>
            <title>
              {g.minute}&#39; {g.player ?? ""} ({g.team_side === "h" ? match.home : match.away})
            </title>
          </circle>
        );
      })}
      <text x={W - PAD.r} y={PAD.t + 10} fontSize={11} textAnchor="end" fill="var(--accent)">
        {match.home}
      </text>
      <text x={W - PAD.r} y={PAD.t + 24} fontSize={11} textAnchor="end" fill="var(--muted)">
        {match.away}
      </text>
    </svg>
  );
}
