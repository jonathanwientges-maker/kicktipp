import { getManifest, getSeasonTable } from "@/lib/data";
import { TableToggle } from "@/components/TableToggle";

export const metadata = { title: "Tabelle — Bundesliga Hub" };

export default function TabellePage() {
  const manifest = getManifest();
  const season = manifest.current_season;
  const { table, history } = getSeasonTable(season);

  return (
    <>
      <h1 style={{ fontSize: "1.4rem", marginBottom: "0.25rem" }}>Tabelle</h1>
      <p className="muted" style={{ marginTop: 0 }}>
        Saison {season}/{(season + 1) % 100} — inklusive xG-Tabelle, xPunkte und Glücksfaktor.
      </p>
      <TableToggle table={table} history={history} />
    </>
  );
}
