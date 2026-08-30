import { allMatchIds, getMatch, getManifest } from "@/lib/data";
import { XgRace } from "@/components/charts/XgRace";
import { ShotMap } from "@/components/charts/ShotMap";
import { fmtDate, fmtInt, fmtNum, fmtTime } from "@/lib/format";
import { Section } from "@/components/Section";

export const dynamicParams = false;

export function generateStaticParams() {
  return allMatchIds().map((id) => ({ matchId: String(id) }));
}

export async function generateMetadata({ params }: { params: Promise<{ matchId: string }> }) {
  try {
    const { matchId } = await params;
    const m = getMatch(parseInt(matchId, 10));
    return { title: `${m.home} ${m.home_goals}:${m.away_goals} ${m.away} — Spielbericht` };
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
    <div className="surface table-scroll">
      <table>
        <thead>
          <tr>
            <th></th>
            <th>{m.home}</th>
            <th>{m.away}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r[0]}>
              <td>{r[0]}</td>
              <td className="num">{r[1]}</td>
              <td className="num">{r[2]}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function GameStateBar({ gsx }: { gsx: Record<string, number> }) {
  const seg = (side: "h" | "a") => [
    { k: "level", label: "unentschieden", v: gsx[`xg_while_level_${side}`] ?? 0 },
    { k: "winning", label: "in Führung", v: gsx[`xg_while_winning_${side}`] ?? 0 },
    { k: "losing", label: "in Rückstand", v: gsx[`xg_while_losing_${side}`] ?? 0 },
  ];
  const colors: Record<string, string> = {
    level: "var(--muted)",
    winning: "var(--positive)",
    losing: "var(--negative)",
  };
  const Row = ({ side, name }: { side: "h" | "a"; name: string }) => {
    const s = seg(side);
    const total = s.reduce((a, b) => a + b.v, 0) || 1;
    return (
      <div style={{ marginBottom: "0.6rem" }}>
        <div style={{ fontSize: "0.85rem", marginBottom: 3 }}>{name}</div>
        <div style={{ display: "flex", height: 16, borderRadius: 4, overflow: "hidden", background: "var(--surface-2)" }}>
          {s.map((x) => (
            <span
              key={x.k}
              title={`${x.label}: xG ${fmtNum(x.v)}`}
              style={{ width: `${(x.v / total) * 100}%`, background: colors[x.k] }}
            />
          ))}
        </div>
      </div>
    );
  };
  return (
    <div className="surface" style={{ padding: "1rem" }}>
      <Row side="h" name="Heim" />
      <Row side="a" name="Auswärts" />
      <p className="muted" style={{ fontSize: "0.8rem", margin: 0 }}>
        xG nach Spielstand: <span style={{ color: "var(--muted)" }}>unentschieden</span> ·{" "}
        <span style={{ color: "var(--positive)" }}>in Führung</span> ·{" "}
        <span style={{ color: "var(--negative)" }}>in Rückstand</span>
      </p>
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
      <p className="muted" style={{ marginBottom: "0.25rem", fontSize: "0.9rem" }}>
        Spieltag {m.round} · {fmtDate(m.date)}
        {time ? ` · ${time}` : ""}
      </p>
      <h1 style={{ fontSize: "1.5rem", margin: "0 0 1rem" }}>
        {m.home} <span className="num">{m.home_goals}:{m.away_goals}</span> {m.away}
      </h1>

      <Section title="xG-Verlauf">
        <div className="surface" style={{ padding: "0.75rem" }}>
          <XgRace match={m} />
        </div>
      </Section>

      <Section title="Schusskarten">
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
          <ShotMap shots={m.shots} side="h" label={m.home} />
          <ShotMap shots={m.shots} side="a" label={m.away} />
        </div>
      </Section>

      <Section title="Die Zahlen">
        <NumBlock m={m} />
      </Section>

      <Section title="Fazit">
        <div className="surface" style={{ padding: "1rem" }}>
          <p style={{ margin: 0 }}>{m.verdict}</p>
        </div>
      </Section>

      {m.players.length > 0 && (
        <Section title="Aufstellungen">
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
            {[
              { name: m.home, list: home },
              { name: m.away, list: away },
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

      <Section title="Spielstand">
        <GameStateBar gsx={m.game_state_xg} />
      </Section>

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
