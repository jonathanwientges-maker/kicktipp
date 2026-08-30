import { getManifest, getSimulation } from "@/lib/data";
import { Section } from "@/components/Section";
import { BarRow } from "@/components/charts/BarRow";
import { StackedPositions } from "@/components/charts/StackedPositions";

export const metadata = { title: "Simulation — Bundesliga Hub" };

export default function SimulationPage() {
  const season = getManifest().current_season;
  const sim = getSimulation(season);

  if (!sim.available || !sim.teams) {
    return (
      <>
        <h1 style={{ fontSize: "1.4rem" }}>Saisonsimulation</h1>
        <p className="muted">
          Die Simulation läuft, sobald noch ausstehende Spiele der laufenden Saison vorliegen.
        </p>
      </>
    );
  }

  const teams = [...sim.teams].sort((a, b) => b.mean_points - a.mean_points);

  return (
    <>
      <h1 style={{ fontSize: "1.4rem", marginBottom: "0.25rem" }}>Saisonsimulation</h1>
      <p className="muted" style={{ marginTop: 0 }}>
        {sim.n_runs?.toLocaleString("de-DE")} Durchläufe auf Basis der Dixon-Coles-Stärken.
        <br />
        <strong>Abstieg</strong> = Platz 17/18, <strong>Relegation</strong> = Platz 16.
      </p>

      {(
        [
          ["Meisterschaft", "p_title"],
          ["Champions-League-Plätze", "p_cl"],
          ["Europa League", "p_el"],
          ["Conference League", "p_conf"],
          ["Relegation", "p_relegation_playoff"],
          ["Abstieg", "p_relegation"],
        ] as [string, keyof (typeof teams)[number]][]
      ).map(([label, key]) => (
        <Section key={label} title={label}>
          <div className="surface" style={{ padding: "0.75rem" }}>
            {teams
              .filter((t) => (t[key] as number) > 0.001)
              .sort((a, b) => (b[key] as number) - (a[key] as number))
              .map((t) => (
                <BarRow key={t.team} label={t.team} value={t[key] as number} />
              ))}
          </div>
        </Section>
      ))}

      <Section title="Abschlussplatzierung">
        <div className="surface" style={{ padding: "0.75rem" }}>
          <StackedPositions teams={teams} />
        </div>
      </Section>
    </>
  );
}
