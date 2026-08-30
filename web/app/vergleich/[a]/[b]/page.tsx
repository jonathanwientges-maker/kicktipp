import { allH2HSlugs, getH2H } from "@/lib/data";
import { fmtDate } from "@/lib/format";

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
      <h1 style={{ fontSize: "1.4rem", marginBottom: "0.5rem" }}>
        {h2h.team_a} <span className="muted">gegen</span> {h2h.team_b}
      </h1>
      <p className="muted" style={{ marginTop: 0 }}>
        {h2h.record.played} Begegnungen · {h2h.record.a_wins}–{h2h.record.draws}–{h2h.record.b_wins} ·
        Tore {h2h.aggregate_goals.a}:{h2h.aggregate_goals.b}
      </p>

      <h2 style={{ fontSize: "1.05rem", margin: "1.5rem 0 0.5rem" }}>Letzte Begegnungen</h2>
      <div className="surface table-scroll">
        <table>
          <thead>
            <tr>
              <th>Datum</th>
              <th>Begegnung</th>
              <th>Ergebnis</th>
            </tr>
          </thead>
          <tbody>
            {[...h2h.meetings].reverse().map((m) => (
              <tr key={m.match_id}>
                <td>{fmtDate(m.date)}</td>
                <td style={{ textAlign: "left" }}>
                  {m.home_team} – {m.away_team}
                </td>
                <td className="num">
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
