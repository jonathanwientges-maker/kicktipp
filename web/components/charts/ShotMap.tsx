// Vertical half-pitch shot map (BUILD BLUEPRINT §7.2).
// Understat coords: X is along the length toward the goal being attacked
// (0..1), Y across the width (0..1). We draw a vertical half-pitch with
// the goal at the top; dot radius scales with sqrt(xg).
import type { Shot } from "@/lib/data";

const W = 300;
const H = 380;

function resultColor(result: string): string {
  if (result === "Goal" || result === "OwnGoal") return "var(--accent)";
  if (result === "SavedShot") return "var(--text)";
  if (result === "BlockedShot") return "var(--border)";
  return "var(--muted)"; // MissedShots / ShotOnPost
}

export function ShotMap({
  shots,
  side,
  label,
}: {
  shots: Shot[];
  side: "h" | "a";
  label: string;
}) {
  const own = shots.filter((s) => s.team_side === side);

  // Map understat (X,Y) -> pitch pixels. X in [0.5,1] is the attacking
  // half; scale that to the full height. Y across the width.
  const px = (y: number) => (side === "a" ? 1 - y : y) * W;
  const py = (x: number) => H - (Math.max(0, x - 0.5) / 0.5) * H;

  // penalty area 40.3% of width, 6-yard box 18.3%, spot at 11m (~0.88 X)
  const paW = 0.403 * W;
  const paX0 = (W - paW) / 2;
  const paH = 0.165 * H; // ~16.5m of ~50m half
  const sixW = 0.183 * W;
  const sixX0 = (W - sixW) / 2;
  const sixH = 0.06 * H;
  const spotY = H - (0.11 / 0.5) * H;

  return (
    <figure style={{ margin: 0 }}>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet" style={{ width: "100%", height: "auto" }} role="img">
        <title>Schusskarte {label}</title>
        <rect x={0.5} y={0.5} width={W - 1} height={H - 1} fill="var(--surface-2)" stroke="var(--border)" />
        {/* penalty area */}
        <rect x={paX0} y={0} width={paW} height={paH} fill="none" stroke="var(--border)" />
        <rect x={sixX0} y={0} width={sixW} height={sixH} fill="none" stroke="var(--border)" />
        <circle cx={W / 2} cy={spotY} r={2} fill="var(--border)" />
        {/* goal */}
        <rect x={W / 2 - 0.09 * W} y={0} width={0.18 * W} height={4} fill="var(--border)" />
        {own.map((s, i) => (
          <circle
            key={i}
            cx={px(s.y)}
            cy={py(s.x)}
            r={Math.max(2.5, Math.sqrt(s.xg) * 22)}
            fill={resultColor(s.result)}
            fillOpacity={s.result === "Goal" || s.result === "OwnGoal" ? 0.9 : 0.55}
            stroke="var(--bg)"
            strokeWidth={0.5}
          >
            <title>
              {s.minute}&#39; {s.player ?? ""} — xG {s.xg.toFixed(2)} ({s.result})
            </title>
          </circle>
        ))}
      </svg>
      <figcaption className="muted" style={{ fontSize: "0.82rem", textAlign: "center" }}>
        {label}
      </figcaption>
    </figure>
  );
}
