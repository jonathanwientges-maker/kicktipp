// Per team, an 18-segment horizontal bar of finishing-position
// probabilities, coloured by outcome band (BUILD BLUEPRINT §7.5).
import type { SimTeam } from "@/lib/data";
import { teamName } from "@/lib/teamColors";

// outcome-band colours (match the legend on the Simulation page)
function bandColor(pos: number): string {
  if (pos === 1) return "var(--accent)";
  if (pos <= 4) return "#5b7cff";
  if (pos === 5) return "#3fb0b9";
  if (pos === 6) return "#3fb95a";
  if (pos === 16) return "var(--warning)";
  if (pos >= 17) return "var(--negative)";
  return "var(--surface-raised)";
}

export function StackedPositions({ teams }: { teams: SimTeam[] }) {
  const rowH = 22;
  const labelW = 132;
  const W = 640;
  const H = teams.length * rowH + 24;
  const barW = W - labelW - 8;
  const GAP = 2;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet" style={{ width: "100%", height: "auto" }} role="img">
      <title>Wahrscheinlichkeit je Abschlussplatzierung</title>
      {teams.map((t, ri) => {
        let x = labelW + 4;
        const segs = Array.from({ length: 18 }, (_, i) => i + 1).map((pos, idx, arr) => {
          const p = (t[`p_pos_${pos}`] as number) ?? 0;
          const w = Math.max(0, p * barW - GAP);
          const rx = idx === 0 || idx === arr.length - 1 ? 3 : 0;
          const seg = (
            <rect key={pos} x={x} y={2} width={w} height={rowH - 6} rx={rx} fill={bandColor(pos)}>
              <title>
                {teamName(String(t.team))} — Platz {pos}: {(p * 100).toFixed(1)}%
              </title>
            </rect>
          );
          x += p * barW;
          return seg;
        });
        return (
          <g key={String(t.team)} transform={`translate(0 ${ri * rowH + 4})`}>
            <text x={labelW} y={rowH - 8} fontSize={10} textAnchor="end" fill="var(--text)">
              {teamName(String(t.team))}
            </text>
            {segs}
          </g>
        );
      })}
    </svg>
  );
}
