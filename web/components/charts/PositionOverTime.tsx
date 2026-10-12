"use client";
// 18 thin lines, y-axis inverted (1 at top). Mouse hover, touch/pen tap and
// keyboard focus each highlight one team.
import { useRef, useState } from "react";
import { teamColor, teamName } from "@/lib/teamColors";

const W = 680;
const H = 340;
const PAD = { l: 26, r: 120, t: 12, b: 24 };

export function PositionOverTime({
  history,
}: {
  history: { matchday: number; team: string; position: number }[];
}) {
  const [hover, setHover] = useState<string | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);
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

  // nearest line to the pointer, measured at the closest matchday
  const pick = (e: React.PointerEvent<SVGSVGElement>): string | null => {
    const svg = svgRef.current;
    const ctm = svg?.getScreenCTM();
    if (!svg || !ctm) return null;
    const pt = svg.createSVGPoint();
    pt.x = e.clientX;
    pt.y = e.clientY;
    const { x, y } = pt.matrixTransform(ctm.inverse());
    let md = mds[0];
    for (const m of mds) if (Math.abs(xs(m) - x) < Math.abs(xs(md) - x)) md = m;
    let best: string | null = null;
    let bestD = Infinity;
    for (const [team, pts] of byTeam) {
      const p = pts.find((q) => q.matchday === md) ?? pts[pts.length - 1];
      if (!p) continue;
      const d = Math.abs(ys(p.position) - y);
      if (d < bestD) {
        bestD = d;
        best = team;
      }
    }
    return best;
  };

  return (
    <svg
      ref={svgRef}
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="xMidYMid meet"
      style={{ width: "100%", height: "auto" }}
      role="group"
      aria-label="Tabellenplatz im Saisonverlauf"
      onPointerMove={(e) => {
        if (e.pointerType === "mouse") setHover(pick(e));
      }}
      onPointerLeave={(e) => {
        if (e.pointerType === "mouse") setHover(null);
      }}
      onPointerDown={(e) => {
        // touch/pen: tap selects (page scroll stays native); tap again to switch
        if (e.pointerType !== "mouse") setHover(pick(e));
      }}
    >
      <title>Tabellenplatz im Saisonverlauf</title>
      {[1, 4, 6, 16, 18].map((p) => (
        <line key={p} className="chart-grid" x1={PAD.l} y1={ys(p)} x2={W - PAD.r} y2={ys(p)} strokeDasharray="2 3" />
      ))}
      {[1, 4, 6, 16, 18].map((p) => (
        <text key={p} x={PAD.l - 6} y={ys(p) + 3} className="chart-axis-label" textAnchor="end">
          {p}
        </text>
      ))}
      {teams.map((team) => {
        const pts = (byTeam.get(team) ?? []).sort((a, b) => a.matchday - b.matchday);
        const d = pts.map((p, i) => `${i === 0 ? "M" : "L"} ${xs(p.matchday)} ${ys(p.position)}`).join(" ");
        const active = hover === team;
        const last = pts[pts.length - 1];
        const tc = teamColor(team).color;
        return (
          <g
            key={team}
            tabIndex={0}
            role="img"
            aria-label={`${teamName(team)}, aktuell Platz ${last?.position ?? "–"}`}
            onFocus={() => setHover(team)}
            onBlur={() => setHover((h) => (h === team ? null : h))}
          >
            <path
              d={d}
              fill="none"
              stroke={active ? tc : "var(--text-muted)"}
              strokeWidth={active ? 3 : 1.5}
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeOpacity={hover ? (active ? 1 : 0.08) : 0.25}
              style={{ transition: "stroke-opacity var(--dur-fast) var(--ease-out), stroke-width var(--dur-fast) var(--ease-out)" }}
            />
            {last && (
              <text
                x={W - PAD.r + 4}
                y={ys(last.position) + 3}
                fontSize={9}
                fill={active ? tc : "var(--text-dim)"}
                opacity={hover && !active ? 0.25 : 1}
              >
                {teamName(team)}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}
