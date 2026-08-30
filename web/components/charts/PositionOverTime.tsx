"use client";
// 18 thin lines, y-axis inverted (1 at top), hover highlights one team
// (BUILD BLUEPRINT §7.3).
import { useState } from "react";

const W = 680;
const H = 340;
const PAD = { l: 26, r: 120, t: 12, b: 24 };

export function PositionOverTime({
  history,
}: {
  history: { matchday: number; team: string; position: number }[];
}) {
  const [hover, setHover] = useState<string | null>(null);
  const teams = Array.from(new Set(history.map((h) => h.team)));
  const mds = Array.from(new Set(history.map((h) => h.matchday))).sort((a, b) => a - b);
  if (!mds.length) return null;
  const maxMd = mds[mds.length - 1];

  const xs = (md: number) => PAD.l + ((md - mds[0]) / Math.max(1, maxMd - mds[0])) * (W - PAD.l - PAD.r);
  const ys = (pos: number) => PAD.t + ((pos - 1) / 17) * (H - PAD.t - PAD.b);

  const byTeam = new Map<string, { matchday: number; position: number }[]>();
  for (const h of history) {
    if (!byTeam.has(h.team)) byTeam.set(h.team, []);
    byTeam.get(h.team)!.push({ matchday: h.matchday, position: h.position });
  }

  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet" style={{ width: "100%", height: "auto" }} role="img">
      <title>Tabellenplatz im Saisonverlauf</title>
      {[1, 4, 6, 16, 18].map((p) => (
        <line key={p} x1={PAD.l} y1={ys(p)} x2={W - PAD.r} y2={ys(p)} stroke="var(--border)" strokeDasharray="2 3" />
      ))}
      {[1, 4, 6, 16, 18].map((p) => (
        <text key={p} x={PAD.l - 6} y={ys(p) + 3} fontSize={9} textAnchor="end" fill="var(--muted)">
          {p}
        </text>
      ))}
      {teams.map((team) => {
        const pts = (byTeam.get(team) ?? []).sort((a, b) => a.matchday - b.matchday);
        const d = pts.map((p, i) => `${i === 0 ? "M" : "L"} ${xs(p.matchday)} ${ys(p.position)}`).join(" ");
        const active = hover === team;
        const last = pts[pts.length - 1];
        return (
          <g key={team} onMouseEnter={() => setHover(team)} onMouseLeave={() => setHover(null)}>
            <path
              d={d}
              fill="none"
              stroke={active ? "var(--accent)" : "var(--muted)"}
              strokeWidth={active ? 2.2 : 1}
              strokeOpacity={hover && !active ? 0.2 : 0.9}
            />
            {last && (
              <text
                x={W - PAD.r + 4}
                y={ys(last.position) + 3}
                fontSize={9}
                fill={active ? "var(--accent)" : "var(--muted)"}
                opacity={hover && !active ? 0.3 : 1}
              >
                {team}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}
