"use client";
import { useState } from "react";
import type { TeamPage } from "@/lib/data";
import { teamColor } from "@/lib/teamColors";
import { RollingDual } from "./charts/RollingDual";

export function RollingToggle({ team }: { team: TeamPage }) {
  const [venue, setVenue] = useState<"home" | "away">("home");
  const r = team.rolling_xg[venue];
  const tc = teamColor(team.team).color;
  return (
    <>
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.75rem" }}>
        {(["home", "away"] as const).map((v) => (
          <button
            key={v}
            className="toggle-btn"
            data-active={venue === v}
            onClick={() => setVenue(v)}
          >
            {v === "home" ? "Heim" : "Auswärts"}
          </button>
        ))}
      </div>
      <div className="surface" style={{ padding: "1rem" }}>
        <RollingDual forVals={r.for} againstVals={r.against} teamColor={tc} />
      </div>
    </>
  );
}
