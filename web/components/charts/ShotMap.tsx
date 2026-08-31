// Vertical half-pitch shot map.
// Understat coords: X along the length toward the attacked goal (0..1),
// Y across the width (0..1). Vertical half-pitch, goal at the top;
// dot radius scales with sqrt(xg).
import type { Shot } from "@/lib/data";

const W = 300;
const H = 380;

export function ShotMap({
  shots,
  side,
  label,
  color = "var(--accent)",
}: {
  shots: Shot[];
  side: "h" | "a";
  label: string;
  color?: string;
}) {
  const own = shots.filter((s) => s.team_side === side);

  const px = (y: number) => (side === "a" ? 1 - y : y) * W;
  const py = (x: number) => H - (Math.max(0, x - 0.5) / 0.5) * H;

  const paW = 0.403 * W;
  const paX0 = (W - paW) / 2;
  const paH = 0.165 * H;
  const sixW = 0.183 * W;
  const sixX0 = (W - sixW) / 2;
  const sixH = 0.06 * H;
  const spotY = H - (0.11 / 0.5) * H;

  return (
    <figure style={{ margin: 0 }}>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet" style={{ width: "100%", height: "auto" }} role="img">
        <title>Schusskarte {label}</title>
        <rect x={0} y={0} width={W} height={H} fill="var(--surface-sunken)" rx={10} />
        <rect x={paX0} y={0} width={paW} height={paH} fill="none" stroke="var(--border-strong)" strokeWidth={1.5} />
        <rect x={sixX0} y={0} width={sixW} height={sixH} fill="none" stroke="var(--border-strong)" strokeWidth={1.5} />
        <circle cx={W / 2} cy={spotY} r={2} fill="var(--border-strong)" />
        <rect x={W / 2 - 0.09 * W} y={0} width={0.18 * W} height={4} fill="var(--border-strong)" />
        {own.map((s, i) => {
          const isGoal = s.result === "Goal" || s.result === "OwnGoal";
          return (
            <circle
              key={i}
              cx={px(s.y)}
              cy={py(s.x)}
              r={Math.max(2.5, Math.sqrt(s.xg) * 22)}
              fill={color}
              fillOpacity={isGoal ? 0.95 : 0.35}
              stroke={isGoal ? "var(--text)" : "none"}
              strokeWidth={isGoal ? 1.5 : 0}
            >
              <title>
                {s.minute}&#39; {s.player ?? ""} — xG {s.xg.toFixed(2)} ({s.result})
              </title>
            </circle>
          );
        })}
      </svg>
      <figcaption className="label" style={{ textAlign: "center", marginTop: "0.4rem" }}>
        {label}
      </figcaption>
    </figure>
  );
}
