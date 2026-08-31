import { allMatchIds, getMatch, getManifest } from "@/lib/data";
import { XgRace } from "@/components/charts/XgRace";
import { ShotMap } from "@/components/charts/ShotMap";
import { fmtDate, fmtInt, fmtNum, fmtTime } from "@/lib/format";
import { teamColor, teamName, withTeamNames } from "@/lib/teamColors";
import { Section } from "@/components/Section";
import { Explainer } from "@/components/Explainer";
import { GLOSSARY } from "@/lib/glossary";
import { CompareBlock, type CmpRow } from "@/components/CompareBlock";
import { Lineups } from "@/components/Lineups";

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
  const rows: CmpRow[] = [
    { label: "Endstand", home: m.home_goals, away: m.away_goals },
    { label: "xG", home: m.home_xg, away: m.away_xg, homeText: fmtNum(m.home_xg), awayText: fmtNum(m.away_xg), info: "xg" },
    { label: "npxG", home: m.home_npxg, away: m.away_npxg, homeText: fmtNum(m.home_npxg), awayText: fmtNum(m.away_npxg), info: "npxg" },
    { label: "xPunkte", home: m.home_xpoints, away: m.away_xpoints, homeText: fmtNum(m.home_xpoints), awayText: fmtNum(m.away_xpoints), info: "xpunkte" },
    { label: "Schüsse", home: m.home_shots, away: m.away_shots, homeText: fmtInt(m.home_shots), awayText: fmtInt(m.away_shots) },
    { label: "Großchancen", short: "Großch.", home: m.home_big_chances, away: m.away_big_chances, homeText: fmtInt(m.home_big_chances), awayText: fmtInt(m.away_big_chances), info: "grosschancen" },
    { label: "Offenes Spiel (xG)", home: sp.home.open_play, away: sp.away.open_play, homeText: fmtNum(sp.home.open_play), awayText: fmtNum(sp.away.open_play), info: "standardanteil" },
    { label: "Standard (xG)", home: sp.home.set_piece, away: sp.away.set_piece, homeText: fmtNum(sp.home.set_piece), awayText: fmtNum(sp.away.set_piece), info: "standardanteil" },
    { label: "Elfmeter (xG)", home: sp.home.penalty, away: sp.away.penalty, homeText: fmtNum(sp.home.penalty), awayText: fmtNum(sp.away.penalty) },
  ];
  if (teamStats && m.ppda) {
    rows.push({
      label: "PPDA",
      home: m.ppda.home ?? 0,
      away: m.ppda.away ?? 0,
      homeText: fmtNum(m.ppda.home ?? NaN, 1),
      awayText: fmtNum(m.ppda.away ?? NaN, 1),
      info: "ppda",
    });
  }
  if (teamStats && m.deep) {
    rows.push({
      label: "Zuspiele in Tornähe",
      short: "Tornähe",
      home: m.deep.home ?? 0,
      away: m.deep.away ?? 0,
      homeText: fmtNum(m.deep.home ?? NaN, 0),
      awayText: fmtNum(m.deep.away ?? NaN, 0),
      info: "deep",
    });
  }
  return <CompareBlock home={m.home} away={m.away} rows={rows} />;
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
        <div className="shotmap-grid">
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
          <Lineups
            home={m.home}
            away={m.away}
            homePlayers={home}
            awayPlayers={away}
          />
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
