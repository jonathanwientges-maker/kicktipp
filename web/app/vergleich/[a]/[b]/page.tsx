import { allH2HSlugs, getH2H } from "@/lib/data";
import { fmtDate } from "@/lib/format";
import { teamColor, teamName } from "@/lib/teamColors";

export const dynamicParams = false;

export function generateStaticParams() {
  return allH2HSlugs().map((slug) => {
    const [a, b] = slug.split("__");
    return { a, b };
  });
}

export function generateMetadata() {
  return { title: `Direkter Vergleich — Bundesliga Hub` };
}

export default async function VergleichPage({ params }: { params: Promise<{ a: string; b: string }> }) {
  const { a, b } = await params;
  const h2h = getH2H(`${a}__${b}`) ?? getH2H(`${b}__${a}`);
  if (!h2h) return <p className="muted">Keine Begegnungen gefunden.</p>;

  return (
    <>
      <div style={{ display: "flex", alignItems: "center", gap: "0.9rem", marginBottom: "0.6rem" }}>
        <span style={{ width: 5, height: 34, borderRadius: 999, background: teamColor(h2h.team_a).color }} />
        <h1 style={{ margin: 0 }}>
          {teamName(h2h.team_a)} <span className="muted" style={{ fontWeight: 400 }}>gegen</span> {teamName(h2h.team_b)}
        </h1>
        <span style={{ width: 5, height: 34, borderRadius: 999, background: teamColor(h2h.team_b).color }} />
      </div>
      <p className="muted num" style={{ marginTop: 0, marginBottom: "2rem", fontSize: "var(--fs-small)" }}>
        {h2h.record.played} Begegnungen · {h2h.record.a_wins}–{h2h.record.draws}–{h2h.record.b_wins} ·
        Tore {h2h.aggregate_goals.a}:{h2h.aggregate_goals.b}
      </p>

      <h2 style={{ margin: "0 0 0.75rem" }}>Letzte Begegnungen</h2>
      <div className="surface table-scroll">
        <table>
          <thead>
            <tr>
              <th>Datum</th>
              <th>Begegnung</th>
              <th className="num">Ergebnis</th>
            </tr>
          </thead>
          <tbody>
            {[...h2h.meetings].reverse().map((m) => (
              <tr key={m.match_id}>
                <td className="num muted">{fmtDate(m.date)}</td>
                <td>
                  <span className="team-cell">
                    <span className="team-bar" style={{ ["--tc" as any]: teamColor(m.home_team).color }} />
                    {teamName(m.home_team)} <span className="muted">–</span> {teamName(m.away_team)}
                  </span>
                </td>
                <td className="num" style={{ fontWeight: 700 }}>
                  {m.home_goals}:{m.away_goals}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
