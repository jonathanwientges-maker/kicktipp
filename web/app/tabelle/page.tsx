import { getManifest, getSeasonTable } from "@/lib/data";
import { TableToggle } from "@/components/TableToggle";

export const metadata = { title: "Tabelle — Bundesliga Hub" };

export default function TabellePage() {
  const manifest = getManifest();
  const season = manifest.current_season;
  const { table, history } = getSeasonTable(season);

  return (
    <>
      <p className="label" style={{ marginBottom: "0.4rem" }}>
        Saison {season}/{String((season + 1) % 100).padStart(2, "0")}
      </p>
      <h1 style={{ marginBottom: "0.35rem" }}>Tabelle</h1>
      <p className="muted" style={{ marginTop: 0, marginBottom: "1.5rem", fontSize: "var(--fs-small)" }}>
        Inklusive xG-Tabelle, xPunkte und Glücksfaktor.
      </p>
      <TableToggle table={table} history={history} />
    </>
  );
}
