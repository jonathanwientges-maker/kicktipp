import Link from "next/link";
import {
  getH2H,
  getManifest,
  getSeasonMatches,
  getSeasonTable,
  getStatOfWeek,
  h2hSlug,
  slugify,
} from "@/lib/data";
import { Section } from "@/components/Section";
import { Explainer } from "@/components/Explainer";
import { GLOSSARY } from "@/lib/glossary";
import { fmtDate, fmtNum, fmtSigned, fmtTime, luckColor } from "@/lib/format";
import { teamColor, teamName, withTeamNames } from "@/lib/teamColors";
import { Sparkline } from "@/components/charts/Sparkline";
import { Reveal } from "@/components/motion/Reveal";
import { CountUp } from "@/components/motion/CountUp";

export default function StartPage() {
  const manifest = getManifest();
  const season = manifest.current_season;
  const md = manifest.latest_round;
  const stat = safe(() => getStatOfWeek());
  const { matches } = getSeasonMatches(season);
  const { table, history } = getSeasonTable(season);

  const played = matches.filter((m) => m.round <= md);
  const lastWeek = played.filter((m) => m.round === md);
  const standout = [...lastWeek]
    .sort((a, b) => b.home_xg + b.away_xg - (a.home_xg + a.away_xg))
    .slice(0, 2);

  // luck movement: position change vs previous matchday
  const luckSorted = [...table].sort((a, b) => b.luck - a.luck);
  const top5 = luckSorted.slice(0, 5);
  const bottom5 = luckSorted.slice(-5).reverse();

  const upcoming = matches
    .filter((m) => m.round === md + 1)
    .slice(0, 9);

  const teamLast5 = (team: string) => {
    const ms = played
      .filter((m) => m.home === team || m.away === team)
      .sort((a, b) => a.round - b.round)
      .slice(-5);
    return {
      xgFor: ms.map((m) => (m.home === team ? m.home_xg : m.away_xg)),
      xgAgainst: ms.map((m) => (m.home === team ? m.away_xg : m.home_xg)),
    };
  };

  return (
    <>
      <div className="hero-wash" aria-hidden="true" />
      <p className="label" style={{ marginBottom: "0.4rem" }}>Rückblick</p>
      <h1 style={{ marginBottom: "1.5rem" }}>
        <span className="display-l num" style={{ marginRight: "0.4rem" }}>{md}.</span>
        Spieltag
      </h1>

      <Section title="Zahlen der Woche">
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: "0.85rem" }}>
          {stat && stat.headline && (
            <Reveal index={0}>
              <Link href={stat.link || "#"} className="surface surface-hover" style={{ padding: "1.15rem", display: "block", height: "100%" }}>
                <div className="label" style={{ marginBottom: "0.5rem" }}>{stat.headline}</div>
                <div className="display-m num">
                  {stat.value === null ? "–" : <CountUp value={stat.value} dp={2} />}
                </div>
                <div className="muted" style={{ fontSize: "var(--fs-small)", marginTop: "0.25rem" }}>{withTeamNames(stat.context)}</div>
              </Link>
            </Reveal>
          )}
          {standout.map((m, i) => (
            <Reveal key={m.match_id} index={i + 1}>
              <Link
                href={`/spiel/${m.match_id}`}
                className="surface surface-hover"
                style={{ padding: "1.15rem", display: "block", height: "100%", borderLeft: `3px solid ${teamColor(m.home_xg >= m.away_xg ? m.home : m.away).color}` }}
              >
                <div className="label" style={{ marginBottom: "0.5rem" }}>Auffälliges Spiel</div>
                <div style={{ fontWeight: 600, fontFamily: "var(--font-display)" }}>
                  {teamName(m.home)} <span className="num">{m.home_goals}:{m.away_goals}</span> {teamName(m.away)}
                </div>
                <div className="muted num" style={{ fontSize: "var(--fs-small)", marginTop: "0.2rem" }}>
                  xG {fmtNum(m.home_xg)} : {fmtNum(m.away_xg)}
                </div>
              </Link>
            </Reveal>
          ))}
        </div>
      </Section>

      <Section
        title="Glücksfaktor"
        sub="Top 5 und Flop 5 nach Abweichung Punkte − xPunkte."
        info={<Explainer label="">{GLOSSARY.gluecksfaktor}</Explainer>}
      >
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
          {[
            { name: "Überperformer", rows: top5 },
            { name: "Unterperformer", rows: bottom5 },
          ].map((grp) => (
            <div key={grp.name} className="surface" style={{ padding: "1rem" }}>
              <div className="label" style={{ marginBottom: "0.6rem" }}>{grp.name}</div>
              {grp.rows.map((r) => (
                <div key={r.team} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "5px 0" }}>
                  <Link href={`/team/${slugify(r.team)}`} className="team-cell">
                    <span className="team-bar" style={{ ["--tc" as any]: teamColor(r.team).color }} />
                    {teamName(r.team)}
                  </Link>
                  <span className="num" style={{ color: luckColor(r.luck), fontWeight: 600 }}>
                    {fmtSigned(r.luck, 1)}
                  </span>
                </div>
              ))}
            </div>
          ))}
        </div>
      </Section>

      {upcoming.length > 0 && (
        <Section title="Als Nächstes">
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(260px,1fr))", gap: "0.85rem" }}>
            {upcoming.map((m, i) => {
              const h2h = safe(() => getH2H(h2hSlug(slugify(m.home), slugify(m.away)))) ||
                safe(() => getH2H(h2hSlug(slugify(m.away), slugify(m.home))));
              const prev = h2h?.meetings
                .filter((x) => x.season === season - 1)
                .slice(-1)[0];
              const h = teamLast5(m.home);
              const a = teamLast5(m.away);
              return (
                <Reveal key={m.match_id} index={i} className="surface surface-hover" style={{ padding: "1.05rem", borderLeft: `3px solid ${teamColor(m.home).color}` }}>
                  <div className="label">
                    {fmtDate(m.date)}
                    {m.time ? ` · ${fmtTime(m.time)}` : ""}
                  </div>
                  <div style={{ fontWeight: 600, margin: "0.35rem 0", fontFamily: "var(--font-display)" }}>
                    {teamName(m.home)} <span className="muted">–</span> {teamName(m.away)}
                  </div>
                  {prev && (
                    <div className="muted num" style={{ fontSize: "var(--fs-small)" }}>
                      Vorsaison: {teamName(prev.home_team)} {prev.home_goals}:{prev.away_goals} {teamName(prev.away_team)}
                    </div>
                  )}
                  {h2h && (
                    <div className="muted num" style={{ fontSize: "var(--fs-small)" }}>
                      Direkter Vergleich: {h2h.record.a_wins}–{h2h.record.draws}–{h2h.record.b_wins}
                    </div>
                  )}
                  <div style={{ display: "flex", gap: "1.25rem", marginTop: "0.6rem" }}>
                    <div>
                      <div className="label">{teamName(m.home)}</div>
                      <Sparkline values={h.xgFor} color={teamColor(m.home).color} />
                    </div>
                    <div>
                      <div className="label">{teamName(m.away)}</div>
                      <Sparkline values={a.xgFor} color={teamColor(m.away).color} />
                    </div>
                  </div>
                </Reveal>
              );
            })}
          </div>
        </Section>
      )}
    </>
  );
}

function safe<T>(fn: () => T): T | null {
  try {
    return fn();
  } catch {
    return null;
  }
}
