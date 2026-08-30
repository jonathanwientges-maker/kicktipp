import Link from "next/link";
import { getManifest, getTeamPage, getTeamSlugs } from "@/lib/data";
import { Section } from "@/components/Section";
import { fmtNum, fmtSigned } from "@/lib/format";
import { RollingToggle } from "@/components/RollingToggle";
import { Sparkline } from "@/components/charts/Sparkline";

export const dynamicParams = false;

export function generateStaticParams() {
  const manifest = getManifest();
  return getTeamSlugs(manifest.current_season).map((slug) => ({ slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  try {
    const { slug } = await params;
    const t = getTeamPage(getManifest().current_season, slug);
    return { title: `${t.team} — Bundesliga Hub` };
  } catch {
    return { title: "Team — Bundesliga Hub" };
  }
}

export default async function TeamDetail({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const season = getManifest().current_season;
  const t = getTeamPage(season, slug);
  const teamStats = getManifest().team_stats_available;
  const gs = t.game_state_xg_totals;
  const luckSeries = t.luck_by_matchday.map((x) => x.luck);

  return (
    <>
      <h1 style={{ fontSize: "1.5rem", marginBottom: "1rem" }}>{t.team}</h1>

      <Section title="Rollender xG-Schnitt">
        <RollingToggle team={t} />
      </Section>

      <Section title="Spielstand-xG" sub="xG-Summe nach Spielsituation über die Saison.">
        <div className="surface" style={{ padding: "1rem", display: "flex", gap: "2rem", flexWrap: "wrap" }}>
          <div>
            <div className="muted" style={{ fontSize: "0.8rem" }}>unentschieden</div>
            <div className="num" style={{ fontSize: "1.3rem" }}>{fmtNum(gs.level)}</div>
          </div>
          <div>
            <div className="muted" style={{ fontSize: "0.8rem" }}>in Führung</div>
            <div className="num" style={{ fontSize: "1.3rem" }}>{fmtNum(gs.winning)}</div>
          </div>
          <div>
            <div className="muted" style={{ fontSize: "0.8rem" }}>in Rückstand</div>
            <div className="num" style={{ fontSize: "1.3rem" }}>{fmtNum(gs.losing)}</div>
          </div>
        </div>
      </Section>

      <Section title="Glücksfaktor im Verlauf">
        <div className="surface" style={{ padding: "0.75rem" }}>
          <Sparkline values={luckSeries} width={320} height={40} />
        </div>
      </Section>

      <Section title="Ergebnisse">
        <div className="surface table-scroll">
          <table>
            <thead>
              <tr>
                <th>Sp</th>
                <th>Gegner</th>
                <th>Ort</th>
                <th>Ergebnis</th>
                <th>xG</th>
                <th>xPunkte</th>
              </tr>
            </thead>
            <tbody>
              {t.results.map((r) => (
                <tr key={r.match_id}>
                  <td className="num muted">{r.matchday}</td>
                  <td style={{ textAlign: "left" }}>
                    <Link href={`/spiel/${r.match_id}`}>{r.opponent}</Link>
                  </td>
                  <td>{r.venue === "home" ? "H" : "A"}</td>
                  <td className="num">
                    {r.goals_for}:{r.goals_against}
                  </td>
                  <td className="num">
                    {fmtNum(r.xg_for)} : {fmtNum(r.xg_against)}
                  </td>
                  <td className="num">{fmtNum(r.xpoints)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      {teamStats && t.ppda_trend && (
        <Section title="PPDA im Verlauf">
          <div className="surface" style={{ padding: "0.75rem" }}>
            <Sparkline values={t.ppda_trend.map((x) => x.ppda ?? 0)} width={320} height={40} />
          </div>
        </Section>
      )}

      {t.upcoming.length > 0 && (
        <Section title="Als Nächstes">
          <ul>
            {t.upcoming.map((u, i) => (
              <li key={i}>
                {u.opponent} — {u.date}
              </li>
            ))}
          </ul>
        </Section>
      )}
    </>
  );
}
