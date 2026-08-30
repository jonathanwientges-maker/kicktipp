// A labelled horizontal probability bar, reused on the simulation and
// model pages (BUILD BLUEPRINT §7.7).
import { fmtNum } from "@/lib/format";

export function BarRow({
  label,
  value,
  max = 1,
  color = "var(--accent)",
  suffix = "%",
  showValue = true,
}: {
  label: string;
  value: number;
  max?: number;
  color?: string;
  suffix?: string;
  showValue?: boolean;
}) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  const display = suffix === "%" ? fmtNum(value * 100, 1) : fmtNum(value, 1);
  return (
    <div style={{ display: "grid", gridTemplateColumns: "9rem 1fr 3.2rem", alignItems: "center", gap: "0.5rem", padding: "2px 0" }}>
      <span style={{ fontSize: "0.88rem", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
        {label}
      </span>
      <span style={{ background: "var(--surface-2)", borderRadius: 4, height: 14, position: "relative", overflow: "hidden" }}>
        <span
          style={{
            position: "absolute",
            left: 0,
            top: 0,
            bottom: 0,
            width: `${pct}%`,
            background: color,
            borderRadius: 4,
          }}
        />
      </span>
      <span className="num muted" style={{ fontSize: "0.82rem", textAlign: "right" }}>
        {showValue ? `${display}${suffix}` : ""}
      </span>
    </div>
  );
}
