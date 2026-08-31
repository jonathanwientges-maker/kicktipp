import { allMatchIds, getMatch, getManifest } from "@/lib/data";
import { XgRace } from "@/components/charts/XgRace";
import { ShotMap } from "@/components/charts/ShotMap";
import { fmtDate, fmtInt, fmtNum, fmtTime } from "@/lib/format";
import { teamColor, teamName, withTeamNames } from "@/lib/teamColors";
import { Section } from "@/components/Section";
import { Explainer } from "@/components/Explainer";
import { GLOSSARY } from "@/lib/glossary";

const ROW_INFO: Record<string, keyof typeof GLOSSARY> = {
  xG: "xg",
  npxG: "npxg",
  xPunkte: "xpunkte",
  "Großchancen": "grosschancen",
  "Offenes Spiel (xG)": "standardanteil",
  "Standard (xG)": "standardanteil",
  PPDA: "ppda",
  "Zuspiele in Tornähe": "deep",
};

export const dynamicParams = false;

export function generateStaticParams() {
  return allMatchIds().map((id) => ({ matchId: String(id) }));
}

export async function generateMetadata({ params }: { params: Promise<{ matchId: string }> }) {
  try {
    const { matchId } = await params;
    const m = getMatch(parseInt(matchId, 10));
    return { title: `${teamName(m.home)} ${m.home_goals}:${m.away_goals} ${teamName(m.away)} — Spielbericht` };
  } catch {
    return { title: "Spielbericht — Bundesliga Hub" };
  }
}

function NumBlock({ m }: { m: ReturnType<typeof getMatch> }) {
  const sp = m.set_piece_split;
  const teamStats = getManifest().team_stats_available;
  const rows: [string, string, string][] = [
    ["Endstand", `${m.home_goals}`, `${m.away_goals}`],
    ["xG", fmtNum(m.home_xg), fmtNum(m.away_xg)],
    ["npxG", fmtNum(m.home_npxg), fmtNum(m.away_npxg)],
    ["xPunkte", fmtNum(m.home_xpoints), fmtNum(m.away_xpoints)],
    ["Schüsse", fmtInt(m.home_shots), fmtInt(m.away_shots)],
    ["Großchancen", fmtInt(m.home_big_chances), fmtInt(m.away_big_chances)],
    ["Offenes Spiel (xG)", fmtNum(sp.home.open_play), fmtNum(sp.away.open_play)],
    ["Standard (xG)", fmtNum(sp.home.set_piece), fmtNum(sp.away.set_piece)],
    ["Elfmeter (xG)", fmtNum(sp.home.penalty), fmtNum(sp.away.penalty)],
  ];
  if (teamStats && m.ppda) {
    rows.push(["PPDA", fmtNum(m.ppda.home ?? NaN, 1), fmtNum(m.ppda.away ?? NaN, 1)]);
  }
  if (teamStats && m.deep) {
    rows.push(["Zuspiele in Tornähe", fmtNum(m.deep.home ?? NaN, 0), fmtNum(m.deep.away ?? NaN, 0)]);
  }
  return (
    <div className="surface" style={{ padding: "0.25rem 1rem", overflow: "visible" }}>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr>
            <th style={{ textAlign: "left" }}></th>
            <th className="num" style={{ color: "var(--text)", textAlign: "right", padding: "0.6rem 0.7rem" }}>{teamName(m.home)}</th>
            <th className="num" style={{ color: "var(--text)", textAlign: "right", padding: "0.6rem 0.7rem" }}>{teamName(m.away)}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => {
            const infoKey = ROW_INFO[r[0]];
            const cell: React.CSSProperties = {
              padding: "0.55rem 0.7rem",
              borderTop: i === 0 ? "none" : "1px solid var(--border)",
            };
            return (
              <tr key={r[0]}>
                <td className="label" style={{ ...cell, textAlign: "left" }}>
                  {infoKey ? (
                    <Explainer label={r[0]}>{GLOSSARY[infoKey]}</Explainer>
                  ) : (
                    r[0]
                  )}
                </td>
                <td className="num" style={{ ...cell, textAlign: "right" }}>{r[1]}</td>
                <td className="num" style={{ ...cell, textAlign: "right" }}>{r[2]}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}


export default async function SpielberichtPage({ params }: { params: Promise<{ matchId: string }> }) {
  const { matchId } = await params;
  const m = getMatch(parseInt(matchId, 10));
  const time = fmtTime(m.time);
  const home = m.players.filter((p) => p.team_side === "h");
  const away = m.players.filter((p) => p.team_side === "a");

  return (
    <>
      <p className="label" style={{ marginBottom: "0.75rem" }}>
        Spieltag {m.round} · {fmtDate(m.date)}
        {time ? ` · ${time}` : ""}
      </p>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr auto 1fr",
          alignItems: "center",
          gap: "1rem",
          margin: "0 0 2rem",
        }}
      >
        <div style={{ textAlign: "right", display: "flex", alignItems: "center", justifyContent: "flex-end", gap: "0.6rem" }}>
          <span style={{ fontFamily: "var(--font-display)", fontWeight: 600, fontSize: "var(--fs-h3)" }}>{teamName(m.home)}</span>
          <span style={{ width: 4, height: 44, borderRadius: 999, background: teamColor(m.home).color }} />
        </div>
        <div className="display-xl num" style={{ letterSpacing: "-0.03em" }}>
          {m.home_goals}<span style={{ color: "var(--text-dim)", margin: "0 0.15em" }}>:</span>{m.away_goals}
        </div>
        <div style={{ textAlign: "left", display: "flex", alignItems: "center", gap: "0.6rem" }}>
          <span style={{ width: 4, height: 44, borderRadius: 999, background: teamColor(m.away).color }} />
          <span style={{ fontFamily: "var(--font-display)", fontWeight: 600, fontSize: "var(--fs-h3)" }}>{teamName(m.away)}</span>
        </div>
      </div>
      <h1 style={{ position: "absolute", width: 1, height: 1, overflow: "hidden", clip: "rect(0 0 0 0)" }}>
        {teamName(m.home)} {m.home_goals}:{m.away_goals} {teamName(m.away)}
      </h1>

      <Section title="xG-Verlauf" info={<Explainer label="">{GLOSSARY.xarace}</Explainer>}>
        <div className="surface" style={{ padding: "0.75rem" }}>
          <XgRace match={m} />
        </div>
      </Section>

      <Section title="Schusskarten" info={<Explainer label="">{GLOSSARY.schusskarte}</Explainer>}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
          <ShotMap shots={m.shots} side="h" label={teamName(m.home)} color={teamColor(m.home).color} />
          <ShotMap shots={m.shots} side="a" label={teamName(m.away)} color={teamColor(m.away).color} />
        </div>
      </Section>

      <Section title="Die Zahlen">
        <NumBlock m={m} />
      </Section>

      <Section title="Fazit">
        <div className="surface" style={{ padding: "1rem" }}>
          <p style={{ margin: 0 }}>{withTeamNames(m.verdict)}</p>
        </div>
      </Section>

      {m.players.length > 0 && (
        <Section title="Aufstellungen">
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
            {[
              { name: teamName(m.home), list: home },
              { name: teamName(m.away), list: away },
            ].map((t) => (
              <div key={t.name} className="surface table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>{t.name}</th>
                      <th>Min</th>
                      <th>Tore</th>
                      <th>xG</th>
                      <th>xA</th>
                    </tr>
                  </thead>
                  <tbody>
                    {t.list
                      .sort((a, b) => Number(b.is_starter) - Number(a.is_starter) || b.minutes - a.minutes)
                      .map((p) => (
                        <tr key={p.player_id}>
                          <td>{p.player}</td>
                          <td className="num">{fmtInt(p.minutes)}</td>
                          <td className="num">{fmtInt(p.goals)}</td>
                          <td className="num">{fmtNum(p.xg)}</td>
                          <td className="num">{fmtNum(p.xa)}</td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            ))}
          </div>
        </Section>
      )}

      {m.model && (
        <Section title="Modell">
          <div className="surface" style={{ padding: "1rem" }}>
            <p style={{ margin: "0 0 0.35rem" }}>
              Modell-Tipp: <strong className="num">{m.model.tip[0]}:{m.model.tip[1]}</strong> — dafür{" "}
              <strong className="num">{m.model.points}</strong>{" "}
              {m.model.points === 1 ? "Punkt" : "Punkte"}
            </p>
            <p className="muted" style={{ margin: 0 }}>
              Tatsächliches Ergebnis: {m.model.result[0]}:{m.model.result[1]}
            </p>
          </div>
        </Section>
      )}
    </>
  );
}
