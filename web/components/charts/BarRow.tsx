// A labelled horizontal probability bar, reused on the simulation and
// model pages. Fill is the team colour when the row is team-attributed.
import { fmtNum } from "@/lib/format";
import { teamColor, teamName } from "@/lib/teamColors";

export function BarRow({
  label,
  value,
  max = 1,
  color,
  suffix = "%",
  showValue = true,
  team = true,
}: {
  label: string;
  value: number;
  max?: number;
  color?: string;
  suffix?: string;
  showValue?: boolean;
  /** when true (default), `label` is treated as a team name and the fill
      is that club's colour */
  team?: boolean;
}) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  const display = suffix === "%" ? fmtNum(value * 100, 1) : fmtNum(value, 1);
  const fill = color ?? (team ? teamColor(label).color : "var(--accent)");
  const shown = team ? teamName(label) : label;
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "9rem 1fr 3.4rem",
        alignItems: "center",
        gap: "0.6rem",
        padding: "3px 0",
      }}
    >
      <span
        style={{
          fontSize: "var(--fs-small)",
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {shown}
      </span>
      <span
        style={{
          background: "var(--surface-raised)",
          borderRadius: "var(--r-full)",
          height: 8,
          position: "relative",
          overflow: "hidden",
        }}
      >
        <span
          style={{
            position: "absolute",
            inset: "0 auto 0 0",
            width: `${pct}%`,
            background: fill,
            borderRadius: "var(--r-full)",
          }}
        />
      </span>
      <span
        className="num"
        style={{ fontSize: "var(--fs-small)", textAlign: "right", color: "var(--text-muted)" }}
      >
        {showValue ? `${display}${suffix}` : ""}
      </span>
    </div>
  );
}
