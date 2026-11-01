import Link from "next/link";
import { getManifest, getSeasonTable, getTeamPage, getTeamSlugs } from "@/lib/data";
import { Section } from "@/components/Section";
import { fmtNum, fmtSigned } from "@/lib/format";
import { teamColor, teamName } from "@/lib/teamColors";
import { teamCode } from "@/lib/teamCodes";
import { TeamChip } from "@/components/TeamChip";
import { Explainer } from "@/components/Explainer";
import { GLOSSARY } from "@/lib/glossary";
import { analyzeTeam } from "@/lib/teamAnalysis";
import { PointsVsXpts } from "@/components/charts/PointsVsXpts";
import { MatchBars } from "@/components/charts/MatchBars";
import { LeagueTrend } from "@/components/charts/LeagueTrend";
import { CompareBars } from "@/components/charts/CompareBars";
import { SourceBars } from "@/components/charts/SourceBars";

export const dynamicParams = false;

export function generateStaticParams() {
  const manifest = getManifest();
  return getTeamSlugs(manifest.current_season).map((slug) => ({ slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  try {
    const { slug } = await params;
    const t = getTeamPage(getManifest().current_season, slug);
    return { title: `${teamName(t.team)} — Bundesliga Hub` };
  } catch {
    return { title: "Team — Bundesliga Hub" };
  }
}

export default async function TeamDetail({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const season = getManifest().current_season;
  const t = getTeamPage(season, slug);
  const an = analyzeTeam(season, t);
  const { table } = getSeasonTable(season);
  const row = table.find((r) => r.team === t.team);
  const rankBy = (cmp: (a: (typeof table)[number], b: (typeof table)[number]) => number) =>
    [...table].sort(cmp).findIndex((r) => r.team === t.team) + 1;
  const rank = rankBy((a, b) => b.points - a.points || b.goal_diff - a.goal_diff || b.goals_for - a.goals_for);
  const xRank = rankBy((a, b) => b.xpoints - a.xpoints || b.xg_diff - a.xg_diff);
  const form = an.games.slice(-5);
  const gs = an.gameState;

  const tc = teamColor(t.team).color;
  const hasPressing = an.ppda && an.games.some((g) => g.ppda !== null);
  const hasDeep = an.deep && an.games.some((g) => g.deep !== null);

  return (
    <>
      <div style={{ display: "flex", alignItems: "center", gap: "0.9rem", marginBottom: "1.5rem" }}>
        <span style={{ width: 6, height: 40, borderRadius: 999, background: tc }} />
        <h1 style={{ margin: 0 }}>{teamName(t.team)}</h1>
      </div>

      {row && (
        <div className="surface team-kpis">
          <div>
            <div className="label">Platz</div>
            <div className="kpi-val">{rank}.</div>
            <div className="kpi-sub">nach xPunkten {xRank}.</div>
          </div>
          <div>
            <div className="label">Punkte</div>
            <div className="kpi-val">{row.points}</div>
            <div className="kpi-sub">{fmtNum(row.xpoints, 1)} xPunkte</div>
          </div>
          <div>
            <div className="label">Bilanz</div>
            <div className="kpi-val">{row.won}–{row.drawn}–{row.lost}</div>
            <div className="kpi-sub">Tore {row.goals_for}:{row.goals_against}</div>
          </div>
          <div>
            <div className="label">xG-Diff / Spiel</div>
            <div className="kpi-val">{fmtSigned(row.xg_diff / (row.played || 1), 2)}</div>
            <div className="kpi-sub">{fmtNum(row.xg_for / (row.played || 1), 2)} : {fmtNum(row.xg_against / (row.played || 1), 2)}</div>
          </div>
          {form.length > 0 && (
            <div style={{ gridColumn: "1 / -1" }}>
              <div className="label" style={{ marginBottom: "0.4rem" }}>Form (letzte {form.length})</div>
              <div className="fx-form" style={{ maxWidth: 360 }}>
                {form.map((g, i) => {
                  const res = g.pts === 3 ? "W" : g.pts === 1 ? "D" : "L";
                  return (
                    <span key={i} className="fx-game" data-res={res} title={`${teamName(g.opponent)} ${g.gf}:${g.ga}`}>
                      <span className="fx-res">{res === "W" ? "S" : res === "D" ? "U" : "N"}</span>
                      <span className="fx-opp">{g.venue === "away" ? "@" : ""}{teamCode(g.opponent)}</span>
                      <span className="fx-score num">{g.gf}:{g.ga}</span>
                    </span>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      <Section
        title="Punkte vs. xPunkte"
        info={<Explainer label="">{GLOSSARY.gluecksfaktor}</Explainer>}
      >
        <div className="surface" style={{ padding: "1rem" }}>
          <p className="chart-take">{an.takeaways.luck}</p>
          <PointsVsXpts games={an.games} color={tc} />
        </div>
      </Section>

      <Section
        title="Spiel für Spiel"
        info={<Explainer label="">{GLOSSARY.xg}</Explainer>}
      >
        <div className="surface" style={{ padding: "1rem" }}>
          <p className="chart-take">{an.takeaways.matches}</p>
          <MatchBars games={an.games} color={tc} />
        </div>
      </Section>

      {hasPressing && an.ppda && (
        <Section
          title="Pressing (PPDA)"
          sub="Niedriger = aggressiver. Das Band zeigt, wo die mittleren 50 % der Liga liegen."
          info={<Explainer label="">{GLOSSARY.ppda}</Explainer>}
        >
          <div className="surface" style={{ padding: "1rem" }}>
            {an.takeaways.ppda && <p className="chart-take">{an.takeaways.ppda}</p>}
            <LeagueTrend games={an.games} values={an.games.map((g) => g.ppda)} league={an.ppda} color={tc} dp={1} unit="PPDA" />
          </div>
        </Section>
      )}

      {hasDeep && an.deep && (
        <Section
          title="Zuspiele in Tornähe"
          sub="Höher = öfter in der Gefahrenzone. Das Band zeigt, wo die mittleren 50 % der Liga liegen."
          info={<Explainer label="">{GLOSSARY.deep}</Explainer>}
        >
          <div className="surface" style={{ padding: "1rem" }}>
            {an.takeaways.deep && <p className="chart-take">{an.takeaways.deep}</p>}
            <LeagueTrend games={an.games} values={an.games.map((g) => g.deep)} league={an.deep} color={tc} dp={0} unit="Zuspiele in Tornähe" />
          </div>
        </Section>
      )}

      <Section title="Chancen nach Spielstand" sub="xG pro Spiel, getrennt nach Spielstand.">
        <div className="surface" style={{ padding: "1.15rem" }}>
          <CompareBars rows={gs} color={tc} unit="xG/Spiel" />
        </div>
      </Section>

      <Section title="Woher kommen die Chancen?" sub="xG pro Spiel nach Entstehung — eigene und zugelassene.">
        <div className="surface" style={{ padding: "1.15rem" }}>
          <p className="chart-take">{an.takeaways.sources}</p>
          <SourceBars
            color={tc}
            groups={[
              { title: "Erzielt", ...an.sourcesFor },
              { title: "Zugelassen", ...an.sourcesAgainst },
            ]}
          />
        </div>
      </Section>

      <Section title="Ergebnisse">
        <div className="surface table-scroll">
          <table>
            <thead>
              <tr>
                <th className="pos-cell">Sp</th>
                <th>Gegner</th>
                <th>Ort</th>
                <th className="num">Ergebnis</th>
                <th className="num">xG</th>
                <th className="num">xPunkte</th>
              </tr>
            </thead>
            <tbody>
              {t.results.map((r) => (
                <tr key={r.match_id}>
                  <td className="pos-cell">{r.matchday}</td>
                  <td>
                    <Link href={`/spiel/${r.match_id}`} className="team-cell" style={{ minWidth: 0 }}>
                      <span className="dt-full">
                        <TeamChip team={r.opponent} variant="full" />
                      </span>
                      <span className="dt-code">
                        <TeamChip team={r.opponent} variant="code" />
                      </span>
                    </Link>
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

      {t.upcoming.length > 0 && (
        <Section title="Als Nächstes">
          <ul>
            {t.upcoming.map((u, i) => (
              <li key={i}>
                {teamName(u.opponent)} — {u.date}
              </li>
            ))}
          </ul>
        </Section>
      )}
    </>
  );
}
