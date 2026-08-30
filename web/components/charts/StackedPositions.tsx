// Per team, an 18-segment horizontal bar of finishing-position
// probabilities, coloured by outcome band (BUILD BLUEPRINT §7.5).
import type { SimTeam } from "@/lib/data";

function bandColor(pos: number): string {
  if (pos === 1) return "var(--accent)";
  if (pos <= 4) return "#5b7cff";
  if (pos === 5) return "#3fb0b9";
  if (pos === 6) return "#3fb95a";
  if (pos === 16) return "var(--warning)";
  if (pos >= 17) return "var(--negative)";
  return "var(--surface-2)";
}

export function StackedPositions({ teams }: { teams: SimTeam[] }) {
  const rowH = 20;
  const labelW = 130;
  const W = 640;
  const H = teams.length * rowH + 24;
  const barW = W - labelW - 8;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet" style={{ width: "100%", height: "auto" }} role="img">
      <title>Wahrscheinlichkeit je Abschlussplatzierung</title>
      {teams.map((t, ri) => {
        let x = labelW + 4;
        return (
          <g key={t.team} transform={`translate(0 ${ri * rowH + 4})`}>
            <text x={labelW} y={rowH - 7} fontSize={10} textAnchor="end" fill="var(--text)">
              {t.team}
            </text>
            {Array.from({ length: 18 }, (_, i) => i + 1).map((pos) => {
              const p = (t[`p_pos_${pos}`] as number) ?? 0;
              const w = p * barW;
              const seg = (
                <rect key={pos} x={x} y={2} width={Math.max(0, w)} height={rowH - 6} fill={bandColor(pos)}>
                  <title>
                    Platz {pos}: {(p * 100).toFixed(1)}%
                  </title>
                </rect>
              );
              x += w;
              return seg;
            })}
          </g>
        );
      })}
    </svg>
  );
}
