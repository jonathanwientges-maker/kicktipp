import { getManifest, getPlayer, getPlayerIndex } from "@/lib/data";
import { Section } from "@/components/Section";
import { fmtInt, fmtNum, fmtSigned } from "@/lib/format";
import { ShotMap } from "@/components/charts/ShotMap";
import { Sparkline } from "@/components/charts/Sparkline";
import Link from "next/link";

export const dynamicParams = false;

export function generateStaticParams() {
  const season = getManifest().current_season;
  const { players } = getPlayerIndex(season);
  const ids = players
    .filter((p) => getPlayer(season, p.player_id) !== null)
    .map((p) => ({ id: String(p.player_id) }));
  // output: export needs at least one param to emit the route; when there
  // are no per-player pages yet (rosters not backfilled) emit a single
  // placeholder that renders the "no data" state.
  return ids.length ? ids : [{ id: "0" }];
}

export default async function PlayerPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const season = getManifest().current_season;
  const p = getPlayer(season, parseInt(id, 10));
  if (!p) {
    return <p className="muted">Keine Daten zu diesem Spieler.</p>;
  }
  const agg = p.aggregates;
  const enoughMinutes = agg.minutes >= 450;

  return (
    <>
      <h1 style={{ fontSize: "1.5rem", marginBottom: "0.5rem" }}>{p.player}</h1>
      <p className="muted" style={{ marginTop: 0 }}>
        {fmtInt(agg.minutes)} Minuten · {fmtInt(agg.appearances)} Spiele · {fmtInt(agg.goals)} Tore ·
        npxG {fmtNum(agg.npxg)} ({fmtSigned(agg.npxg_overperformance)})
      </p>

      {enoughMinutes ? (
        <div className="surface" style={{ padding: "1rem", display: "flex", gap: "2rem", flexWrap: "wrap", marginBottom: "1.5rem" }}>
          <div>
            <div className="muted" style={{ fontSize: "0.8rem" }}>npxG pro 90 Minuten</div>
            <div className="num" style={{ fontSize: "1.3rem" }}>{fmtNum(agg.npxg_per_90)}</div>
          </div>
          <div>
            <div className="muted" style={{ fontSize: "0.8rem" }}>xA pro 90 Minuten</div>
            <div className="num" style={{ fontSize: "1.3rem" }}>{fmtNum(agg.xa_per_90)}</div>
          </div>
          <div>
            <div className="muted" style={{ fontSize: "0.8rem" }}>npxG pro Schuss</div>
            <div className="num" style={{ fontSize: "1.3rem" }}>{fmtNum(agg.npxg_per_shot)}</div>
          </div>
        </div>
      ) : (
        <p className="muted">Zu wenig Spielzeit für Werte pro 90 Minuten.</p>
      )}

      <Section title="Schusskarte">
        <div style={{ maxWidth: 320 }}>
          <ShotMap
            side="h"
            label={p.player}
            shots={p.shot_map.map((s) => ({
              minute: 0,
              x: s.x,
              y: s.y,
              xg: s.xg,
              npxg: s.xg,
              result: s.result,
              situation: "",
              shot_type: null,
              player: p.player,
              team_side: "h",
              is_penalty: false,
            }))}
          />
        </div>
      </Section>

      <Section title="npxG gegen Tore (kumuliert)">
        <div className="surface" style={{ padding: "0.75rem", display: "flex", gap: "2rem", alignItems: "center" }}>
          <div>
            <div className="muted" style={{ fontSize: "0.75rem" }}>npxG</div>
            <Sparkline values={p.cumulative.map((c) => c.cum_npxg)} width={280} height={44} />
          </div>
          <div>
            <div className="muted" style={{ fontSize: "0.75rem" }}>Tore</div>
            <Sparkline values={p.cumulative.map((c) => c.cum_goals)} width={280} height={44} color="var(--positive)" />
          </div>
        </div>
      </Section>

      <Section title="Spiele">
        <div className="surface table-scroll">
          <table>
            <thead>
              <tr>
                <th>Spiel</th>
                <th>npxG</th>
                <th>Tore</th>
                <th>Schüsse</th>
              </tr>
            </thead>
            <tbody>
              {p.per_match.map((m) => (
                <tr key={m.match_id}>
                  <td style={{ textAlign: "left" }}>
                    <Link href={`/spiel/${m.match_id}`}>Spiel {m.match_id}</Link>
                  </td>
                  <td className="num">{fmtNum(m.npxg)}</td>
                  <td className="num">{fmtInt(m.goals)}</td>
                  <td className="num">{fmtInt(m.shots)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
    </>
  );
}
