// "Die Zahlen" — the standard football-app three-column comparison
// (BRIEF §3). One row per stat:
//   [ home value ]   [ centered label ]   [ away value ]
//        1fr               auto                1fr
// with a diverging bar beneath, split at the centre, each side sized as
// value / (home + away). Sticky mini-header with both code chips.
//
// Server component — no client JS.
import { teamColor } from "@/lib/teamColors";
import { TeamChip } from "./TeamChip";
import { StatRow } from "./StatRow";
import { GLOSSARY } from "@/lib/glossary";

export type CmpRow = {
  /** one short label, shown once */
  label: string;
  /** one-line hint under the label */
  hint?: string;
  /** explanation opened by the "?" (inline); falls back to GLOSSARY[info] */
  explain?: React.ReactNode;
  home: number;
  away: number;
  /** raw display strings; default to the numbers themselves */
  homeText?: string;
  awayText?: string;
  /** glossary key for the "?" affordance */
  info?: keyof typeof GLOSSARY;
};

export function CompareBlock({
  home,
  away,
  rows,
}: {
  home: string;
  away: string;
  rows: CmpRow[];
}) {
  const homeColor = teamColor(home).color;
  const awayColor = teamColor(away).color;

  return (
    <div className="surface cmp">
      <div className="cmp-head">
        <TeamChip team={home} variant="code" />
        <span className="label">Die Zahlen</span>
        <TeamChip team={away} variant="code" />
      </div>

      {rows.map((r) => {
        const total = r.home + r.away;
        return (
          <StatRow
            key={r.label}
            label={r.label}
            hint={r.hint}
            explain={r.explain ?? (r.info ? GLOSSARY[r.info] : undefined)}
            homeText={r.homeText ?? String(r.home)}
            awayText={r.awayText ?? String(r.away)}
            homePct={total > 0 ? (r.home / total) * 100 : 0}
            awayPct={total > 0 ? (r.away / total) * 100 : 0}
            homeColor={homeColor}
            awayColor={awayColor}
            homeBigger={r.home >= r.away}
          />
        );
      })}
    </div>
  );
}
