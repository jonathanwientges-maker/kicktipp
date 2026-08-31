"use client";
// Aufstellungen (BRIEF §4). A team toggle (segmented control with both
// code-name chips) shows one lineup at a time, full width. Each player is
// a single full-width row — no nested grid, which is what caused minutes
// to render on top of names. Starters under "Startelf", subs under
// "Eingewechselt".
//
// Above 1024px both teams sit side by side, each column still using this
// same single-column row layout internally.
import { useState } from "react";
import type { PlayerLine } from "@/lib/data";
import { fmtInt, fmtNum } from "@/lib/format";
import { TeamChip } from "./TeamChip";

function PlayerRow({ p }: { p: PlayerLine }) {
  return (
    <li className="lineup-row">
      <span className="lineup-pos">{p.position ?? "–"}</span>
      <span className="lineup-name">{p.player}</span>
      <span className="lineup-metrics">
        <span className="lineup-metric">
          <span className="v">{fmtInt(p.minutes)}</span>
          <span className="u">Min</span>
        </span>
        <span className="lineup-metric">
          <span className="v">{fmtInt(p.goals)}</span>
          <span className="u">Tore</span>
        </span>
        <span className="lineup-metric">
          <span className="v">{fmtNum(p.xg)}</span>
          <span className="u">xG</span>
        </span>
        <span className="lineup-metric">
          <span className="v">{fmtNum(p.xa)}</span>
          <span className="u">xA</span>
        </span>
      </span>
    </li>
  );
}

function TeamLineup({ players }: { players: PlayerLine[] }) {
  const sorted = [...players].sort(
    (a, b) => Number(b.is_starter) - Number(a.is_starter) || b.minutes - a.minutes,
  );
  const starters = sorted.filter((p) => p.is_starter);
  const subs = sorted.filter((p) => !p.is_starter);
  return (
    <div>
      {starters.length > 0 && (
        <>
          <div className="lineup-heading">Startelf</div>
          <ul className="lineup-list">
            {starters.map((p) => (
              <PlayerRow key={p.player_id} p={p} />
            ))}
          </ul>
        </>
      )}
      {subs.length > 0 && (
        <>
          <div className="lineup-heading">Eingewechselt</div>
          <ul className="lineup-list">
            {subs.map((p) => (
              <PlayerRow key={p.player_id} p={p} />
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

export function Lineups({
  home,
  away,
  homePlayers,
  awayPlayers,
}: {
  home: string;
  away: string;
  homePlayers: PlayerLine[];
  awayPlayers: PlayerLine[];
}) {
  const [side, setSide] = useState<"h" | "a">("h");

  return (
    <div className="surface" style={{ padding: "1rem" }}>
      {/* below 1024px: toggle + one team */}
      <div className="lineup-seg" role="tablist" aria-label="Mannschaft wählen">
        <button
          role="tab"
          aria-selected={side === "h"}
          className="lineup-seg-btn"
          data-active={side === "h"}
          onClick={() => setSide("h")}
        >
          <TeamChip team={home} variant="code-name" />
        </button>
        <button
          role="tab"
          aria-selected={side === "a"}
          className="lineup-seg-btn"
          data-active={side === "a"}
          onClick={() => setSide("a")}
        >
          <TeamChip team={away} variant="code-name" />
        </button>
      </div>

      {/* mobile / tablet view */}
      <div className="lineup-cols-hidden-lg">
        <TeamLineup players={side === "h" ? homePlayers : awayPlayers} />
      </div>

      {/* >=1024px: both side by side */}
      <div className="lineup-cols lineup-cols-lg-only">
        <div>
          <div className="label" style={{ marginBottom: "0.4rem" }}>
            <TeamChip team={home} variant="code-name" />
          </div>
          <TeamLineup players={homePlayers} />
        </div>
        <div>
          <div className="label" style={{ marginBottom: "0.4rem" }}>
            <TeamChip team={away} variant="code-name" />
          </div>
          <TeamLineup players={awayPlayers} />
        </div>
      </div>
    </div>
  );
}
