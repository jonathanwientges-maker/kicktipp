"use client";
import { useState } from "react";
import Link from "next/link";
import type { PlayerAgg } from "@/lib/data";
import { fmtInt, fmtNum, fmtSigned } from "@/lib/format";
import { Explainer } from "@/components/Explainer";
import { GLOSSARY } from "@/lib/glossary";
import { DataTable, type Col, type ColumnSet } from "@/components/DataTable";

export function PlayerLeaderboard({ players, season }: { players: PlayerAgg[]; season: number }) {
  const [includeLow, setIncludeLow] = useState(false);
  const rows = (includeLow ? players : players.filter((p) => !p.low_minutes)).slice(0, 60);
  const maxNpxg = Math.max(...players.map((p) => p.npxg), 0.01);

  type R = PlayerAgg & { id: number };
  const data: R[] = rows.map((p) => ({ ...p, id: p.player_id }));

  const columns: Col<R>[] = [
    { key: "minutes", label: "Min", numeric: true, render: (p) => fmtInt(p.minutes) },
    { key: "goals", label: "Tore", numeric: true, render: (p) => fmtInt(p.goals) },
    {
      key: "npxg",
      label: "npxG",
      numeric: true,
      render: (p) => (
        <span
          className="bar-cell"
          style={{ ["--tc" as any]: "var(--accent-dim)", display: "block", position: "relative" }}
        >
          <span className="bar-fill" style={{ width: `${(p.npxg / maxNpxg) * 100}%` }} />
          <span className="bar-val">{fmtNum(p.npxg)}</span>
        </span>
      ),
    },
    { key: "xa", label: "xA", numeric: true, render: (p) => fmtNum(p.xa) },
    {
      key: "npxg_per_90",
      label: "npxG/90",
      numeric: true,
      render: (p) => (p.minutes >= 450 ? fmtNum(p.npxg_per_90) : "–"),
    },
    {
      key: "npxg_overperformance",
      label: "Δ Tore−npxG",
      numeric: true,
      render: (p) => (
        <span
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
        </span>
      ),
    },
  ];

  // identifier column pinned; remaining 6 columns split into groups of ≤5
  const columnSets: ColumnSet[] = [
    { label: "Torgefahr", keys: ["minutes", "goals", "npxg", "xa", "npxg_per_90"] },
    { label: "Δ", keys: ["minutes", "goals", "npxg_overperformance"] },
  ];

  return (
    <>
      <label
        style={{
          display: "flex",
          alignItems: "center",
          gap: "0.5rem",
          marginBottom: "1rem",
          fontSize: "var(--fs-small)",
          minHeight: 44,
        }}
      >
        <input
          type="checkbox"
          checked={includeLow}
          onChange={(e) => setIncludeLow(e.target.checked)}
          style={{ accentColor: "var(--accent)", width: 18, height: 18 }}
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

      <DataTable
        columns={columns}
        rows={data}
        columnSets={columnSets}
        identifierColSpan={1}
        identifierHeader={<th>Spieler</th>}
        renderIdentifier={(p) => (
          <td style={{ fontWeight: 500, textAlign: "left" }}>
            <Link href={`/spieler/${p.player_id}?s=${season}`}>{p.player}</Link>
          </td>
        )}
      />
    </>
  );
}
