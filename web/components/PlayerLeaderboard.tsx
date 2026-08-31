"use client";
import { useState } from "react";
import Link from "next/link";
import type { PlayerAgg } from "@/lib/data";
import { fmtInt, fmtNum, fmtSigned } from "@/lib/format";
import { Explainer } from "@/components/Explainer";
import { GLOSSARY } from "@/lib/glossary";

export function PlayerLeaderboard({ players, season }: { players: PlayerAgg[]; season: number }) {
  const [includeLow, setIncludeLow] = useState(false);
  const rows = (includeLow ? players : players.filter((p) => !p.low_minutes)).slice(0, 60);
  const maxNpxg = Math.max(...players.map((p) => p.npxg), 0.01);

  return (
    <>
      <label
        style={{
          display: "flex",
          alignItems: "center",
          gap: "0.5rem",
          marginBottom: "1rem",
          fontSize: "var(--fs-small)",
        }}
      >
        <input
          type="checkbox"
          checked={includeLow}
          onChange={(e) => setIncludeLow(e.target.checked)}
          style={{ accentColor: "var(--accent)" }}
        />
        Spieler mit wenig Spielzeit einbeziehen
      </label>

      <div
        className="label"
        style={{ display: "flex", flexWrap: "wrap", gap: "1rem 1.25rem", marginBottom: "0.85rem" }}
      >
        <Explainer label="npxG">{GLOSSARY.npxg}</Explainer>
        <Explainer label="xA">
          <strong>xA (expected assists)</strong> summiert die xG-Werte der Schüsse, die auf einen
          Pass dieses Spielers folgten — wie viele Tore seine Vorlagen im Schnitt wert waren.
        </Explainer>
        <Explainer label="pro 90 Minuten">
          Auf 90 Spielminuten hochgerechnet, damit Ein- und Auswechselspieler vergleichbar sind.
          Erst ab 450 Minuten (fünf volle Spiele) ausgewiesen.
        </Explainer>
        <Explainer label="Δ Tore−npxG">
          Tore minus npxG. Positiv = der Spieler trifft häufiger, als seine Chancen erwarten
          lassen (starke Verwertung oder Glück); negativ = er lässt Chancen liegen.
        </Explainer>
      </div>

      <div className="surface table-scroll">
        <table>
          <thead>
            <tr>
              <th>Spieler</th>
              <th className="num">Min</th>
              <th className="num">Tore</th>
              <th className="num">npxG</th>
              <th className="num">xA</th>
              <th className="num">npxG/90</th>
              <th className="num">Δ Tore−npxG</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((p) => (
              <tr key={p.player_id}>
                <td style={{ fontWeight: 500 }}>
                  <Link href={`/spieler/${p.player_id}?s=${season}`}>{p.player}</Link>
                </td>
                <td className="num">{fmtInt(p.minutes)}</td>
                <td className="num">{fmtInt(p.goals)}</td>
                <td
                  className="num bar-cell"
                  style={{ ["--tc" as any]: "var(--accent-dim)" }}
                >
                  <span className="bar-fill" style={{ width: `${(p.npxg / maxNpxg) * 100}%` }} />
                  <span className="bar-val">{fmtNum(p.npxg)}</span>
                </td>
                <td className="num">{fmtNum(p.xa)}</td>
                <td className="num">{p.minutes >= 450 ? fmtNum(p.npxg_per_90) : "–"}</td>
                <td
                  className="num"
                  style={{
                    color:
                      p.npxg_overperformance > 0.05
                        ? "var(--positive)"
                        : p.npxg_overperformance < -0.05
                          ? "var(--negative)"
                          : "var(--text-muted)",
                  }}
                >
                  {fmtSigned(p.npxg_overperformance)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
