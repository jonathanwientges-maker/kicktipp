import Link from "next/link";
import { getManifest, getSeasonTable, slugify } from "@/lib/data";
import { teamColor, teamName } from "@/lib/teamColors";

export const metadata = { title: "Teams — Bundesliga Hub" };

export default function TeamsIndex() {
  const manifest = getManifest();
  const { table } = getSeasonTable(manifest.current_season);
  return (
    <>
      <h1 style={{ marginBottom: "1.5rem" }}>Teams</h1>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(210px,1fr))", gap: "0.6rem" }}>
        {[...table]
          .sort((a, b) => a.team.localeCompare(b.team, "de"))
          .map((t) => (
            <Link
              key={t.team}
              href={`/team/${slugify(t.team)}`}
              className="surface surface-hover"
              style={{ padding: "0.9rem 1.1rem", display: "flex", alignItems: "center", gap: "0.7rem" }}
            >
              <span className="team-bar" style={{ ["--tc" as any]: teamColor(t.team).color }} />
              <span style={{ fontFamily: "var(--font-display)", fontWeight: 500 }}>{teamName(t.team)}</span>
            </Link>
          ))}
      </div>
    </>
  );
}
