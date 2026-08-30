"use client";
import { useState } from "react";
import type { TeamPage } from "@/lib/data";
import { RollingDual } from "./charts/RollingDual";

export function RollingToggle({ team }: { team: TeamPage }) {
  const [venue, setVenue] = useState<"home" | "away">("home");
  const r = team.rolling_xg[venue];
  return (
    <>
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.6rem" }}>
        {(["home", "away"] as const).map((v) => (
          <button
            key={v}
            onClick={() => setVenue(v)}
            style={{
              padding: "0.3rem 0.75rem",
              borderRadius: 8,
              border: "1px solid var(--border)",
              background: venue === v ? "var(--accent)" : "var(--surface)",
              color: venue === v ? "#fff" : "var(--text)",
              cursor: "pointer",
              fontSize: "0.85rem",
            }}
          >
            {v === "home" ? "Heim" : "Auswärts"}
          </button>
        ))}
      </div>
      <div className="surface" style={{ padding: "0.75rem" }}>
        <RollingDual forVals={r.for} againstVals={r.against} />
      </div>
    </>
  );
}
