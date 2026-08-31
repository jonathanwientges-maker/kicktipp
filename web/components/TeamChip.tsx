// A club identifier that stays legible where a full name will not fit.
// Three variants (BRIEF §1):
//   "code"       — 32×32 rounded square, team colour @18%, 1.5px full-colour
//                  border, the 3-letter code centred. Total cell width 44px.
//                  Used in every table below 768px. Always carries title +
//                  aria-label with the full club name.
//   "full"       — the 3px colour bar + full club name (as the old team cell).
//   "code-name"  — the code chip followed by the full club name.
//
// This component adds no client JS: it is a plain server component.
import { teamColor, teamName } from "@/lib/teamColors";
import { teamCode } from "@/lib/teamCodes";

type Variant = "code" | "full" | "code-name";

export function TeamChip({
  team,
  variant = "full",
  className,
  style,
}: {
  team: string;
  variant?: Variant;
  className?: string;
  style?: React.CSSProperties;
}) {
  const color = teamColor(team).color;
  const full = teamName(team);
  const code = teamCode(team);

  const chip = (
    <span
      aria-hidden="true"
      style={{
        flex: "0 0 auto",
        width: 32,
        height: 32,
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        borderRadius: "var(--r-sm)",
        background: `color-mix(in srgb, ${color} 18%, transparent)`,
        border: `1.5px solid ${color}`,
        color,
        fontFamily: "var(--font-display), sans-serif",
        fontWeight: 700,
        fontSize: 12,
        lineHeight: 1,
        letterSpacing: "0.01em",
      }}
    >
      {code}
    </span>
  );

  if (variant === "code") {
    return (
      <span
        className={className}
        title={full}
        aria-label={full}
        style={{
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          width: 44,
          padding: "0 6px",
          ...style,
        }}
      >
        {chip}
      </span>
    );
  }

  if (variant === "code-name") {
    return (
      <span
        className={className}
        style={{ display: "inline-flex", alignItems: "center", gap: "0.55rem", minWidth: 0, ...style }}
      >
        {chip}
        <span style={{ fontFamily: "var(--font-display), sans-serif", fontWeight: 500 }}>{full}</span>
      </span>
    );
  }

  // "full"
  return (
    <span
      className={className}
      style={{ display: "inline-flex", alignItems: "center", gap: "0.6rem", minWidth: 0, ...style }}
    >
      <span
        aria-hidden="true"
        style={{
          flex: "0 0 3px",
          width: 3,
          height: 20,
          borderRadius: "var(--r-full)",
          background: color,
        }}
      />
      <span style={{ fontWeight: 500 }}>{full}</span>
    </span>
  );
}
