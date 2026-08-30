import Link from "next/link";
import { getManifest, getSeasonTable, slugify } from "@/lib/data";

export const metadata = { title: "Teams — Bundesliga Hub" };

export default function TeamsIndex() {
  const manifest = getManifest();
  const { table } = getSeasonTable(manifest.current_season);
  return (
    <>
      <h1 style={{ fontSize: "1.4rem", marginBottom: "1rem" }}>Teams</h1>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(200px,1fr))", gap: "0.5rem" }}>
        {[...table]
          .sort((a, b) => a.team.localeCompare(b.team, "de"))
          .map((t) => (
            <Link key={t.team} href={`/team/${slugify(t.team)}`} className="surface" style={{ padding: "0.75rem 1rem" }}>
              {t.team}
            </Link>
          ))}
      </div>
    </>
  );
}
