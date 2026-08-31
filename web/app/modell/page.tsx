import { getManifest, getModelPerformance, getPredictedTable, getSeasonTable } from "@/lib/data";
import { Section } from "@/components/Section";
import { fmtInt, fmtSignedInt } from "@/lib/format";
import { teamColor, teamName } from "@/lib/teamColors";
import { ModelPointsChart } from "@/components/charts/ModelPointsChart";
import { CountUp } from "@/components/motion/CountUp";
import { Explainer } from "@/components/Explainer";
import { GLOSSARY } from "@/lib/glossary";

export const metadata = { title: "Modell — Bundesliga Hub" };

export default function ModellPage() {
  const season = getManifest().current_season;
  const pred = getPredictedTable(season).table;
  const real = getSeasonTable(season).table;
  const perf = getModelPerformance(season).by_matchday;

  const realPos = new Map(real.map((r, i) => [r.team, i + 1]));
  const predWithReal = pred.map((p, i) => ({
    ...p,
    predPos: i + 1,
    realPos: realPos.get(p.team) ?? i + 1,
  }));

  const last = perf[perf.length - 1];

  return (
    <>
      <p className="label" style={{ marginBottom: "0.4rem" }}>Rückblick</p>
      <h1 style={{ marginBottom: "0.35rem" }}>Modell</h1>
      <p className="muted" style={{ marginTop: 0, marginBottom: "1.5rem", fontSize: "var(--fs-small)" }}>
        Wie gut hat das Modell die Realität getroffen? Nur abgeschlossene Spieltage.
      </p>

      <Section
        title="Modell-Tabelle"
        sub="Tabelle, wenn jeder Modell-Tipp das Ergebnis gewesen wäre."
        info={<Explainer label="">{GLOSSARY.modelltabelle}</Explainer>}
      >
        <div className="surface table-scroll">
          <table>
            <thead>
              <tr>
                <th className="pos-cell">#</th>
                <th>Team</th>
                <th className="num">Pkt (Modell)</th>
                <th className="num">Pkt (real)</th>
                <th className="num">Differenz</th>
                <th className="num">Platz real</th>
              </tr>
            </thead>
            <tbody>
              {predWithReal.map((r) => {
                const d = r.points - r.points_actual;
                return (
                  <tr key={r.team}>
                    <td className="pos-cell">{r.predPos}</td>
                    <td>
                      <span className="team-cell">
                        <span className="team-bar" style={{ ["--tc" as any]: teamColor(r.team).color }} />
                        {teamName(r.team)}
                      </span>
                    </td>
                    <td className="num" style={{ fontWeight: 700 }}>{fmtInt(r.points)}</td>
                    <td className="num">{fmtInt(r.points_actual)}</td>
                    <td
                      className="num"
                      style={{ color: d > 0 ? "var(--positive)" : d < 0 ? "var(--negative)" : "var(--text-muted)" }}
                    >
                      {fmtSignedInt(d)}
                    </td>
                    <td className="num">{r.realPos}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Section>

      {last && (
        <Section
          title="Trefferquote"
          sub="Kicktipp-Wertung je Tipp: exakt getroffenes Ergebnis 4 Punkte, richtige Tordifferenz 3, nur richtige Tendenz (Sieg/Unentschieden/Niederlage) 2, sonst 0. „Basis immer 2:1“ = wie viele Punkte man mit dem Dauer-Tipp 2:1 geholt hätte."
        >
          <div
            className="surface"
            style={{
              padding: "1.5rem",
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit,minmax(120px,1fr))",
              gap: "1.5rem 2rem",
            }}
          >
            {[
              ["Ergebnis", last.cum_exact],
              ["Tordifferenz", last.cum_gd],
              ["Tendenz", last.cum_tendency],
              ["daneben", last.cum_miss],
              ["Punkte gesamt", last.cum_points],
              ["Basis „immer 2:1“", last.cum_always21_points],
            ].map(([label, v]) => (
              <div key={label as string}>
                <div className="label" style={{ marginBottom: "0.35rem" }}>{label}</div>
                <div className="display-m num">
                  <CountUp value={v as number} fmt="int" />
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}

      <Section title="Punkte kumuliert vs. „immer 2:1“">
        <div className="surface" style={{ padding: "1rem" }}>
          <ModelPointsChart rows={perf} />
        </div>
      </Section>
    </>
  );
}
