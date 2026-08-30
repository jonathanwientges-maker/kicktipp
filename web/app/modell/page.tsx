import { getManifest, getModelPerformance, getPredictedTable, getSeasonTable } from "@/lib/data";
import { Section } from "@/components/Section";
import { fmtInt, fmtSignedInt } from "@/lib/format";
import { ModelPointsChart } from "@/components/charts/ModelPointsChart";

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
      <h1 style={{ fontSize: "1.4rem", marginBottom: "0.25rem" }}>Modell</h1>
      <p className="muted" style={{ marginTop: 0 }}>
        Wie gut hat das Modell die Realität getroffen? Nur abgeschlossene Spieltage.
      </p>

      <Section title="Modell-Tabelle" sub="Tabelle, wenn jeder Modell-Tipp das Ergebnis gewesen wäre.">
        <div className="surface table-scroll">
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Team</th>
                <th>Pkt (Modell)</th>
                <th>Pkt (real)</th>
                <th>Differenz</th>
                <th>Platz real</th>
              </tr>
            </thead>
            <tbody>
              {predWithReal.map((r) => (
                <tr key={r.team}>
                  <td className="num muted">{r.predPos}</td>
                  <td style={{ textAlign: "left" }}>{r.team}</td>
                  <td className="num" style={{ fontWeight: 700 }}>{fmtInt(r.points)}</td>
                  <td className="num">{fmtInt(r.points_actual)}</td>
                  <td className="num">{fmtSignedInt(r.points - r.points_actual)}</td>
                  <td className="num">{r.realPos}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      {last && (
        <Section title="Trefferquote" sub="Ergebnis (4) / Tordifferenz (3) / Tendenz (2) / daneben (0).">
          <div className="surface" style={{ padding: "1rem", display: "flex", gap: "2rem", flexWrap: "wrap" }}>
            {[
              ["Ergebnis", last.cum_exact],
              ["Tordifferenz", last.cum_gd],
              ["Tendenz", last.cum_tendency],
              ["daneben", last.cum_miss],
            ].map(([label, v]) => (
              <div key={label as string}>
                <div className="muted" style={{ fontSize: "0.8rem" }}>{label}</div>
                <div className="num" style={{ fontSize: "1.4rem" }}>{fmtInt(v as number)}</div>
              </div>
            ))}
            <div>
              <div className="muted" style={{ fontSize: "0.8rem" }}>Punkte gesamt</div>
              <div className="num" style={{ fontSize: "1.4rem" }}>{fmtInt(last.cum_points)}</div>
            </div>
            <div>
              <div className="muted" style={{ fontSize: "0.8rem" }}>Basis „immer 2:1“</div>
              <div className="num" style={{ fontSize: "1.4rem" }}>{fmtInt(last.cum_always21_points)}</div>
            </div>
          </div>
        </Section>
      )}

      <Section title="Punkte kumuliert vs. „immer 2:1“">
        <div className="surface" style={{ padding: "0.75rem" }}>
          <ModelPointsChart rows={perf} />
        </div>
      </Section>
    </>
  );
}
