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
import { Explainer } from "./Explainer";
import { GLOSSARY } from "@/lib/glossary";

export type CmpRow = {
  /** long label (>=480px) */
  label: string;
  /** short label (<480px); defaults to `label` */
  short?: string;
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
        const homePct = total > 0 ? (r.home / total) * 100 : 0;
        const awayPct = total > 0 ? (r.away / total) * 100 : 0;
        const homeBigger = r.home >= r.away;
        return (
          <div className="cmp-row" key={r.label}>
            <div className="cmp-vals">
              <span className="cmp-val home" data-bigger={homeBigger}>
                {r.homeText ?? r.home}
              </span>
              <span className="cmp-label">
                {r.info ? (
                  <Explainer label="">{GLOSSARY[r.info]}</Explainer>
                ) : null}
                <span className="cmp-full">{r.label}</span>
                <span className="cmp-short">{r.short ?? r.label}</span>
              </span>
              <span className="cmp-val away" data-bigger={!homeBigger}>
                {r.awayText ?? r.away}
              </span>
            </div>
            <div className="cmp-bar" aria-hidden="true">
              <span className="cmp-bar-half home">
                <span
                  className="cmp-bar-fill"
                  style={{ width: `${homePct}%`, background: homeColor }}
                />
              </span>
              <span className="cmp-bar-half away">
                <span
                  className="cmp-bar-fill"
                  style={{ width: `${awayPct}%`, background: awayColor }}
                />
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
