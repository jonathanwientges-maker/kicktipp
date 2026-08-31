import { fmtNum } from "@/lib/format";

/**
 * Renders `children` (a line/area chart) only when there are at least
 * `min` data points. With fewer, a line is meaningless — show the single
 * value plus a "Verlauf ab Spieltag N" note instead.
 */
export function TrendGuard({
  points,
  min = 2,
  lastValue,
  unit = "",
  dp = 2,
  children,
}: {
  points: number;
  min?: number;
  lastValue?: number | null;
  unit?: string;
  dp?: number;
  children: React.ReactNode;
}) {
  if (points >= min) return <>{children}</>;
  return (
    <div style={{ display: "flex", alignItems: "baseline", gap: "0.75rem", flexWrap: "wrap" }}>
      {lastValue != null && (
        <span className="display-m num">
          {fmtNum(lastValue, dp)}
          {unit ? <span style={{ fontSize: "var(--fs-small)", color: "var(--text-dim)" }}> {unit}</span> : null}
        </span>
      )}
      <span className="muted" style={{ fontSize: "var(--fs-small)" }}>
        {points === 0
          ? "Noch keine Werte."
          : `Bisher 1 Spiel — der Verlauf wird ab dem 2. Spieltag angezeigt.`}
      </span>
    </div>
  );
}
