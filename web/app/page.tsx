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
import { fmtDate, fmtNum, fmtSigned, fmtTime, luckColor } from "@/lib/format";
// slugify comes from @/lib/data (above)
import { Sparkline } from "@/components/charts/Sparkline";

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
      <h1 style={{ fontSize: "1.4rem", marginBottom: "1rem" }}>Spieltag {md} im Rückblick</h1>

      <Section title="Zahlen der Woche">
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: "0.75rem" }}>
          {stat && stat.headline && (
            <Link href={stat.link || "#"} className="surface" style={{ padding: "1rem", display: "block" }}>
              <div className="muted" style={{ fontSize: "0.8rem" }}>{stat.headline}</div>
              <div className="num" style={{ fontSize: "1.6rem", fontWeight: 700 }}>
                {stat.value === null ? "–" : fmtNum(stat.value)}
              </div>
              <div className="muted" style={{ fontSize: "0.85rem" }}>{stat.context}</div>
            </Link>
          )}
          {standout.map((m) => (
            <Link key={m.match_id} href={`/spiel/${m.match_id}`} className="surface" style={{ padding: "1rem", display: "block" }}>
              <div className="muted" style={{ fontSize: "0.8rem" }}>Auffälliges Spiel</div>
              <div style={{ fontWeight: 600 }}>
                {m.home} {m.home_goals}:{m.away_goals} {m.away}
              </div>
              <div className="muted num" style={{ fontSize: "0.85rem" }}>
                xG {fmtNum(m.home_xg)} : {fmtNum(m.away_xg)}
              </div>
            </Link>
          ))}
        </div>
      </Section>

      <Section title="Glücksfaktor" sub="Top 5 und Flop 5 nach Abweichung Punkte − xPunkte.">
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
          {[
            { name: "Überperformer", rows: top5 },
            { name: "Unterperformer", rows: bottom5 },
          ].map((grp) => (
            <div key={grp.name} className="surface" style={{ padding: "0.75rem" }}>
              <div className="muted" style={{ fontSize: "0.85rem", marginBottom: "0.4rem" }}>{grp.name}</div>
              {grp.rows.map((r) => (
                <div key={r.team} style={{ display: "flex", justifyContent: "space-between", padding: "3px 0" }}>
                  <Link href={`/team/${slugify(r.team)}`}>{r.team}</Link>
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
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(260px,1fr))", gap: "0.75rem" }}>
            {upcoming.map((m) => {
              const h2h = safe(() => getH2H(h2hSlug(slugify(m.home), slugify(m.away)))) ||
                safe(() => getH2H(h2hSlug(slugify(m.away), slugify(m.home))));
              const prev = h2h?.meetings
                .filter((x) => x.season === season - 1)
                .slice(-1)[0];
              const h = teamLast5(m.home);
              const a = teamLast5(m.away);
              return (
                <div key={m.match_id} className="surface" style={{ padding: "0.9rem" }}>
                  <div className="muted" style={{ fontSize: "0.8rem" }}>
                    {fmtDate(m.date)}
                    {m.time ? ` · ${fmtTime(m.time)}` : ""}
                  </div>
                  <div style={{ fontWeight: 600, margin: "0.2rem 0" }}>
                    {m.home} – {m.away}
                  </div>
                  {prev && (
                    <div className="muted" style={{ fontSize: "0.82rem" }}>
                      Vorsaison: {prev.home_team} {prev.home_goals}:{prev.away_goals} {prev.away_team}
                    </div>
                  )}
                  {h2h && (
                    <div className="muted" style={{ fontSize: "0.82rem" }}>
                      Direkter Vergleich: {h2h.record.a_wins}–{h2h.record.draws}–{h2h.record.b_wins}
                    </div>
                  )}
                  <div style={{ display: "flex", gap: "1rem", marginTop: "0.4rem" }}>
                    <div>
                      <div className="muted" style={{ fontSize: "0.72rem" }}>{m.home}</div>
                      <Sparkline values={h.xgFor} />
                    </div>
                    <div>
                      <div className="muted" style={{ fontSize: "0.72rem" }}>{m.away}</div>
                      <Sparkline values={a.xgFor} color="var(--muted)" />
                    </div>
                  </div>
                </div>
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
