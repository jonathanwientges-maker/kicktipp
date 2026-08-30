import Link from "next/link";
import { getManifest, getRecords } from "@/lib/data";
import { fmtNum } from "@/lib/format";

export const metadata = { title: "Rekorde & Serien — Bundesliga Hub" };

type Rec = Record<string, any>;

export default function RekordePage() {
  const season = getManifest().current_season;
  const { records } = getRecords(season) as { season: number; records: Rec };

  const card = (title: string, body: React.ReactNode) => (
    <div className="surface" style={{ padding: "1rem" }}>
      <div className="muted" style={{ fontSize: "0.82rem", marginBottom: "0.35rem" }}>{title}</div>
      <div>{body}</div>
    </div>
  );

  const link = (id: number | undefined, label: string) =>
    id ? <Link href={`/spiel/${id}`} style={{ color: "var(--accent)" }}>{label}</Link> : label;

  return (
    <>
      <h1 style={{ fontSize: "1.4rem", marginBottom: "1rem" }}>Rekorde &amp; Serien</h1>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(260px,1fr))", gap: "0.75rem" }}>
        {records.longest_unbeaten &&
          card(
            "Längste Serie ohne Niederlage",
            `${records.longest_unbeaten.team ?? "–"} — ${records.longest_unbeaten.length} Spiele`,
          )}
        {records.longest_winless &&
          card(
            "Längste sieglose Serie",
            `${records.longest_winless.team ?? "–"} — ${records.longest_winless.length} Spiele`,
          )}
        {records.biggest_xg_win &&
          card(
            "Größter xG-Vorsprung",
            <>
              {link(
                records.biggest_xg_win.match_id,
                `${records.biggest_xg_win.home_team} – ${records.biggest_xg_win.away_team}`,
              )}
              <div className="muted num" style={{ fontSize: "0.85rem" }}>
                xG {fmtNum(records.biggest_xg_win.home_xg)} : {fmtNum(records.biggest_xg_win.away_xg)}
              </div>
            </>,
          )}
        {records.most_one_sided &&
          card(
            "Einseitigstes Spiel",
            <>
              {link(
                records.most_one_sided.match_id,
                `${records.most_one_sided.home_team} – ${records.most_one_sided.away_team}`,
              )}
              <div className="muted num" style={{ fontSize: "0.85rem" }}>
                xG-Verhältnis {fmtNum(records.most_one_sided.xg_ratio, 1)}
              </div>
            </>,
          )}
        {records.highest_combined_xg &&
          card(
            "Höchster Gesamt-xG",
            <>
              {link(
                records.highest_combined_xg.match_id,
                `${records.highest_combined_xg.home_team} – ${records.highest_combined_xg.away_team}`,
              )}
              <div className="muted num" style={{ fontSize: "0.85rem" }}>
                {fmtNum(records.highest_combined_xg.combined_xg)} xG gesamt
              </div>
            </>,
          )}
        {records.highest_xg_no_goal &&
          card(
            "Größte vergebene Einzelchance",
            <>
              {link(records.highest_xg_no_goal.match_id, records.highest_xg_no_goal.player ?? "–")}
              <div className="muted num" style={{ fontSize: "0.85rem" }}>
                xG {fmtNum(records.highest_xg_no_goal.xg)}, {records.highest_xg_no_goal.minute}&#39;
              </div>
            </>,
          )}
        {records.biggest_luck_swing &&
          card(
            "Größter Glücksfaktor-Ausschlag",
            <>
              {link(
                records.biggest_luck_swing.match_id,
                `${records.biggest_luck_swing.home_team} – ${records.biggest_luck_swing.away_team}`,
              )}
            </>,
          )}
      </div>
    </>
  );
}
