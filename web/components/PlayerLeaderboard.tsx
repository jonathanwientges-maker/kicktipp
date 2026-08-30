"use client";
import { useState } from "react";
import Link from "next/link";
import type { PlayerAgg } from "@/lib/data";
import { fmtInt, fmtNum, fmtSigned } from "@/lib/format";

export function PlayerLeaderboard({ players, season }: { players: PlayerAgg[]; season: number }) {
  const [includeLow, setIncludeLow] = useState(false);
  const rows = (includeLow ? players : players.filter((p) => !p.low_minutes)).slice(0, 60);

  return (
    <>
      <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.75rem", fontSize: "0.88rem" }}>
        <input type="checkbox" checked={includeLow} onChange={(e) => setIncludeLow(e.target.checked)} />
        Spieler mit wenig Spielzeit einbeziehen
      </label>
      <div className="surface table-scroll">
        <table>
          <thead>
            <tr>
              <th>Spieler</th>
              <th>Min</th>
              <th>Tore</th>
              <th>npxG</th>
              <th>xA</th>
              <th>npxG/90</th>
              <th>Δ Tore−npxG</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((p) => (
              <tr key={p.player_id}>
                <td style={{ textAlign: "left" }}>
                  <Link href={`/spieler/${p.player_id}?s=${season}`}>{p.player}</Link>
                </td>
                <td className="num">{fmtInt(p.minutes)}</td>
                <td className="num">{fmtInt(p.goals)}</td>
                <td className="num">{fmtNum(p.npxg)}</td>
                <td className="num">{fmtNum(p.xa)}</td>
                <td className="num">{p.minutes >= 450 ? fmtNum(p.npxg_per_90) : "–"}</td>
                <td className="num">{fmtSigned(p.npxg_overperformance)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
