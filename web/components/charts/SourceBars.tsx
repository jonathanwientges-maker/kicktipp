// Where chances come from: open play / set pieces / penalties, stacked, for
// the team and the league average, scored and conceded. Server component.
import type { Sources } from "@/lib/teamAnalysis";
import { fmtNum } from "@/lib/format";

const SEGS: { key: keyof Sources; label: string; opacity: number }[] = [
  { key: "open", label: "Aus dem Spiel", opacity: 1 },
  { key: "set", label: "Standards", opacity: 0.6 },
  { key: "pen", label: "Elfmeter", opacity: 0.3 },
];
const total = (s: Sources) => s.open + s.set + s.pen;

export function SourceBars({
  groups,
  color,
}: {
  groups: { title: string; team: Sources; league: Sources }[];
  color: string;
}) {
  const max = Math.max(...groups.flatMap((g) => [total(g.team), total(g.league)]), 0.01) * 1.08;
  const bar = (s: Sources, label: string, ghost: boolean) => (
    <div className="sbar-row" data-ghost={ghost}>
      <span className="sbar-label">{label}</span>
      <span
        className="sbar-track"
        role="img"
        aria-label={`${label}: ${SEGS.map((x) => `${x.label} ${fmtNum(s[x.key], 2)}`).join(", ")}`}
      >
        {SEGS.map((x) => (
          <span
            key={x.key}
            className="sbar-seg"
            style={{
              width: `${(s[x.key] / max) * 100}%`,
              background: ghost ? "var(--text-dim)" : color,
              opacity: ghost ? x.opacity * 0.55 : x.opacity,
            }}
            title={`${x.label}: ${fmtNum(s[x.key], 2)}`}
          />
        ))}
      </span>
      <span className="sbar-val num">{fmtNum(total(s), 2)}</span>
    </div>
  );
  return (
    <div className="sbars">
      {groups.map((g) => (
        <div key={g.title} className="sbar-group">
          <div className="label" style={{ marginBottom: "0.35rem" }}>{g.title}</div>
          {bar(g.team, "Team", false)}
          {bar(g.league, "Liga Ø", true)}
        </div>
      ))}
      <div className="chart-legend">
        {SEGS.map((x) => (
          <span key={x.key}>
            <i className="lg-box" style={{ background: color, opacity: x.opacity }} /> {x.label}
          </span>
        ))}
        <span className="muted">xG pro Spiel</span>
      </div>
    </div>
  );
}
