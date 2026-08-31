import Link from "next/link";
import { getManifest, getTeamPage, getTeamSlugs } from "@/lib/data";
import { Section } from "@/components/Section";
import { fmtNum, fmtSigned } from "@/lib/format";
import { teamColor, teamName } from "@/lib/teamColors";
import { RollingToggle } from "@/components/RollingToggle";
import { Sparkline } from "@/components/charts/Sparkline";
import { CountUp } from "@/components/motion/CountUp";
import { TrendGuard } from "@/components/charts/TrendGuard";
import { Explainer } from "@/components/Explainer";
import { GLOSSARY } from "@/lib/glossary";

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
  const teamStats = getManifest().team_stats_available;
  const gs = t.game_state_xg_totals;
  const luckSeries = t.luck_by_matchday.map((x) => x.luck);

  const tc = teamColor(t.team).color;

  return (
    <>
      <div style={{ display: "flex", alignItems: "center", gap: "0.9rem", marginBottom: "1.5rem" }}>
        <span style={{ width: 6, height: 40, borderRadius: 999, background: tc }} />
        <h1 style={{ margin: 0 }}>{teamName(t.team)}</h1>
      </div>

      <Section
        title="Rollender xG-Schnitt"
        info={<Explainer label="">{GLOSSARY.rollingxg}</Explainer>}
      >
        <RollingToggle team={t} />
      </Section>

      <Section title="Spielstand-xG" sub="xG-Summe nach Spielsituation über die Saison.">
        <div
          className="surface"
          style={{
            padding: "1.5rem",
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit,minmax(130px,1fr))",
            gap: "1.5rem",
          }}
        >
          {[
            ["unentschieden", gs.level],
            ["in Führung", gs.winning],
            ["in Rückstand", gs.losing],
          ].map(([label, v]) => (
            <div key={label as string}>
              <div className="label" style={{ marginBottom: "0.35rem" }}>{label}</div>
              <div className="display-m num">
                <CountUp value={v as number} dp={2} />
              </div>
            </div>
          ))}
        </div>
      </Section>

      <Section
        title="Glücksfaktor im Verlauf"
        info={<Explainer label="">{GLOSSARY.gluecksfaktor}</Explainer>}
      >
        <div className="surface" style={{ padding: "1rem" }}>
          <TrendGuard
            points={luckSeries.length}
            lastValue={luckSeries[luckSeries.length - 1]}
            dp={1}
          >
            <Sparkline values={luckSeries} width={320} height={40} color={tc} />
          </TrendGuard>
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
                    <Link href={`/spiel/${r.match_id}`} className="team-cell">
                      <span className="team-bar" style={{ ["--tc" as any]: teamColor(r.opponent).color }} />
                      {teamName(r.opponent)}
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

      {teamStats && t.ppda_trend && (
        <Section
          title="PPDA im Verlauf"
          info={<Explainer label="">{GLOSSARY.ppda}</Explainer>}
        >
          <div className="surface" style={{ padding: "1rem" }}>
            <TrendGuard
              points={t.ppda_trend.length}
              lastValue={t.ppda_trend[t.ppda_trend.length - 1]?.ppda ?? null}
              dp={1}
            >
              <Sparkline
                values={t.ppda_trend.map((x) => x.ppda ?? 0)}
                width={320}
                height={40}
                color={tc}
              />
            </TrendGuard>
          </div>
        </Section>
      )}

      {teamStats && t.deep_trend && (
        <Section
          title="Zuspiele in Tornähe im Verlauf"
          info={<Explainer label="">{GLOSSARY.deep}</Explainer>}
        >
          <div className="surface" style={{ padding: "1rem" }}>
            <TrendGuard
              points={t.deep_trend.length}
              lastValue={t.deep_trend[t.deep_trend.length - 1]?.deep ?? null}
              dp={0}
            >
              <Sparkline
                values={t.deep_trend.map((x) => x.deep ?? 0)}
                width={320}
                height={40}
                color={tc}
              />
            </TrendGuard>
          </div>
        </Section>
      )}

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
