// Horizontal bars with a league-average tick. Server component, CSS only.
import { fmtNum } from "@/lib/format";

export function CompareBars({
  rows,
  color,
  unit,
}: {
  rows: { label: string; team: number; league: number }[];
  color: string;
  unit: string;
}) {
  const max = Math.max(...rows.flatMap((r) => [r.team, r.league]), 0.01) * 1.1;
  return (
    <div className="cbars">
      {rows.map((r) => (
        <div key={r.label} className="cbar-row">
          <span className="cbar-label">{r.label}</span>
          <span className="cbar-track" role="img" aria-label={`${r.label}: ${fmtNum(r.team, 2)} ${unit}, Liga Ø ${fmtNum(r.league, 2)}`}>
            <span className="cbar-fill" style={{ width: `${(r.team / max) * 100}%`, background: color }} />
            <span className="cbar-tick" style={{ left: `${(r.league / max) * 100}%` }} title={`Liga Ø ${fmtNum(r.league, 2)}`} />
          </span>
          <span className="cbar-val num">
            {fmtNum(r.team, 2)} <span className="muted">· Liga Ø {fmtNum(r.league, 2)}</span>
          </span>
        </div>
      ))}
      <div className="chart-legend" style={{ marginTop: "0.5rem" }}>
        <span><i className="lg-box" style={{ background: color }} /> Team ({unit})</span>
        <span><i className="lg-tick" /> Ligadurchschnitt</span>
      </div>
    </div>
  );
}
