import { getManifest, getSimulation } from "@/lib/data";
import { Section } from "@/components/Section";
import { BarRow } from "@/components/charts/BarRow";
import { StackedPositions } from "@/components/charts/StackedPositions";
import { Explainer } from "@/components/Explainer";
import { GLOSSARY } from "@/lib/glossary";

export const metadata = { title: "Simulation — Bundesliga Hub" };

const BANDS: { c: string; txt: string }[] = [
  { c: "var(--accent)", txt: "Platz 1 (Meister)" },
  { c: "#5b7cff", txt: "Plätze 2–4 (Champions League)" },
  { c: "#3fb0b9", txt: "Platz 5 (Europa League)" },
  { c: "#3fb95a", txt: "Platz 6 (Conference League)" },
  { c: "var(--warning)", txt: "Platz 16 (Relegation)" },
  { c: "var(--negative)", txt: "Plätze 17–18 (Abstieg)" },
  { c: "var(--surface-raised)", txt: "Mittelfeld (7–15)" },
];

export default function SimulationPage() {
  const season = getManifest().current_season;
  const sim = getSimulation(season);

  if (!sim.available || !sim.teams) {
    return (
      <>
        <h1>Saisonsimulation</h1>
        <p className="muted">
          Die Simulation läuft, sobald noch ausstehende Spiele der laufenden Saison vorliegen.
        </p>
      </>
    );
  }

  const teams = [...sim.teams].sort((a, b) => b.mean_points - a.mean_points);

  return (
    <>
      <p className="label" style={{ marginBottom: "0.4rem" }}>Prognose</p>
      <h1 style={{ marginBottom: "0.35rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
        Saisonsimulation
        <Explainer label="">{GLOSSARY.simulation}</Explainer>
      </h1>
      <p className="muted" style={{ marginTop: 0, marginBottom: "1.5rem", fontSize: "var(--fs-small)" }}>
        {sim.n_runs?.toLocaleString("de-DE")} Durchläufe auf Basis der Dixon-Coles-Stärken. Jede Zahl
        ist der Anteil der Durchläufe, in denen das Team dort landet.
        <br />
        <strong style={{ color: "var(--text)" }}>Abstieg</strong> = Platz 17/18,{" "}
        <strong style={{ color: "var(--text)" }}>Relegation</strong> = Platz 16.
      </p>

      {(
        [
          ["Meisterschaft", "p_title", "Wahrscheinlichkeit, die Saison als Erster zu beenden."],
          ["Champions-League-Plätze", "p_cl", "Wahrscheinlichkeit für Platz 1–4."],
          ["Europa League", "p_el", "Wahrscheinlichkeit für Platz 5."],
          ["Conference League", "p_conf", "Wahrscheinlichkeit für Platz 6."],
          ["Relegation", "p_relegation_playoff", "Wahrscheinlichkeit für Platz 16 (Relegations-Playoff)."],
          ["Abstieg", "p_relegation", "Wahrscheinlichkeit für Platz 17 oder 18 (direkter Abstieg)."],
        ] as [string, keyof (typeof teams)[number], string][]
      ).map(([label, key, sub]) => (
        <Section key={label} title={label} sub={sub}>
          <div className="surface" style={{ padding: "1rem" }}>
            {teams
              .filter((t) => (t[key] as number) > 0.001)
              .sort((a, b) => (b[key] as number) - (a[key] as number))
              .map((t) => (
                <BarRow key={String(t.team)} label={String(t.team)} value={t[key] as number} />
              ))}
          </div>
        </Section>
      ))}

      <Section
        title="Abschlussplatzierung"
        sub="Pro Team ein Balken über alle 18 Plätze: je breiter ein Segment, desto häufiger landet das Team auf diesem Platz. Von links (Platz 1) nach rechts (Platz 18)."
      >
        <div className="surface" style={{ padding: "1rem" }}>
          <StackedPositions teams={teams} />
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: "0.35rem 1.1rem",
              marginTop: "0.85rem",
              fontSize: "var(--fs-small)",
              color: "var(--text-muted)",
            }}
          >
            {BANDS.map((b) => (
              <span key={b.txt} style={{ display: "inline-flex", alignItems: "center", gap: "0.4rem" }}>
                <span style={{ width: 12, height: 12, borderRadius: 3, background: b.c }} />
                {b.txt}
              </span>
            ))}
          </div>
          <p className="muted" style={{ fontSize: "var(--fs-small)", marginTop: "0.6rem", marginBottom: 0 }}>
            Die Farbe eines Segments steht für die Ergebniszone dieses Platzes.
          </p>
        </div>
      </Section>
    </>
  );
}
