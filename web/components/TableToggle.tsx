"use client";
import { useState } from "react";
import type { TableRow } from "@/lib/data";
import { fmtInt, fmtNum, fmtSigned, fmtSignedInt, luckColor, luckPillBg, slugify } from "@/lib/format";
import { teamColor, teamName } from "@/lib/teamColors";
import Link from "next/link";
import { PositionOverTime } from "./charts/PositionOverTime";
import { Reveal } from "./motion/Reveal";
import { Explainer } from "./Explainer";
import { GLOSSARY } from "@/lib/glossary";
import { TeamChip } from "./TeamChip";
import { DataTable, type Col, type ColumnSet } from "./DataTable";

type View = "points" | "xg" | "xgdiff";

function zone(pos: number): string | undefined {
  if (pos <= 4) return "cl";
  if (pos <= 6) return "el";
  if (pos === 16) return "relegation";
  if (pos >= 17) return "drop";
  return undefined;
}

export function TableToggle({
  table,
  history,
}: {
  table: TableRow[];
  history: { matchday: number; team: string; position: number }[];
}) {
  const [view, setView] = useState<View>("points");

  const sorted = [...table].sort((a, b) => {
    if (view === "xg") return b.xg_for - a.xg_for || b.xg_diff - a.xg_diff;
    if (view === "xgdiff") return b.xg_diff - a.xg_diff;
    return b.points - a.points || b.goal_diff - a.goal_diff || b.goals_for - a.goals_for;
  });

  const maxXgFor = Math.max(...table.map((t) => t.xg_for), 0.01);
  const maxXgAgainst = Math.max(...table.map((t) => t.xg_against), 0.01);
  const maxXpts = Math.max(...table.map((t) => t.xpoints), 0.01);

  const regressionTeams = table.filter((t) => Math.abs(t.luck) > 5);

  type R = TableRow & { id: string; pos: number };
  const rows: R[] = sorted.map((r, i) => ({ ...r, id: r.team, pos: i + 1 }));

  const barCell = (val: number, max: number, tc: string, dp = 1) => (
    <span className="bar-cell" style={{ ["--tc" as any]: tc, display: "block", position: "relative" }}>
      <span className="bar-fill" style={{ width: `${(val / max) * 100}%` }} />
      <span className="bar-val">{fmtNum(val, dp)}</span>
    </span>
  );

  const columns: Col<R>[] = [
    { key: "played", label: "Sp", numeric: true, render: (r) => fmtInt(r.played) },
    { key: "won", label: "S", numeric: true, render: (r) => fmtInt(r.won) },
    { key: "drawn", label: "U", numeric: true, render: (r) => fmtInt(r.drawn) },
    { key: "lost", label: "N", numeric: true, render: (r) => fmtInt(r.lost) },
    {
      key: "goals",
      label: "Tore",
      numeric: true,
      render: (r) => `${fmtInt(r.goals_for)}:${fmtInt(r.goals_against)}`,
    },
    { key: "goal_diff", label: "Diff", numeric: true, render: (r) => fmtSignedInt(r.goal_diff) },
    {
      key: "points",
      label: "Pkt",
      numeric: true,
      render: (r) => <span style={{ fontWeight: 700 }}>{fmtInt(r.points)}</span>,
    },
    {
      key: "xg_for",
      label: "xG",
      numeric: true,
      render: (r) => barCell(r.xg_for, maxXgFor, teamColor(r.team).color),
    },
    {
      key: "xg_against",
      label: "xGA",
      numeric: true,
      render: (r) => barCell(r.xg_against, maxXgAgainst, teamColor(r.team).color),
    },
    { key: "xg_diff", label: "xG-Diff", numeric: true, render: (r) => fmtSigned(r.xg_diff, 1) },
    {
      key: "xpoints",
      label: "xPunkte",
      numeric: true,
      render: (r) => barCell(r.xpoints, maxXpts, teamColor(r.team).color),
    },
    {
      key: "luck",
      label: "Glücksfaktor",
      numeric: true,
      render: (r) => (
        <span
          className="luck-pill"
          style={{ background: luckPillBg(r.luck), color: luckColor(r.luck) }}
        >
          {fmtSigned(r.luck, 1)}
        </span>
      ),
    },
  ];

  const columnSets: ColumnSet[] = [
    { label: "Basis", keys: ["played", "won", "drawn", "lost", "goals", "goal_diff", "points"] },
    { label: "xG", keys: ["played", "xg_for", "xg_against", "xg_diff", "xpoints"] },
    { label: "Form", keys: ["played", "points", "xpoints", "luck"] },
  ];

  const identifierHeader = (
    <>
      <th className="pos-cell">#</th>
      <th>Team</th>
    </>
  );

  const renderIdentifier = (r: R) => (
    <>
      <td className="pos-cell">{r.pos}</td>
      <td>
        <Link href={`/team/${slugify(r.team)}`} className="team-cell" style={{ minWidth: 0 }}>
          <span className="dt-full">
            <TeamChip team={r.team} variant="full" />
          </span>
          <span className="dt-code">
            <TeamChip team={r.team} variant="code" />
          </span>
        </Link>
      </td>
    </>
  );

  return (
    <>
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem", flexWrap: "wrap" }}>
        {(
          [
            ["points", "Tabelle"],
            ["xg", "xG-Tabelle"],
            ["xgdiff", "xG-Differenz"],
          ] as [View, string][]
        ).map(([v, label]) => (
          <button
            key={v}
            className="toggle-btn"
            data-active={view === v}
            onClick={() => setView(v)}
          >
            {label}
          </button>
        ))}
      </div>

      <div
        className="label"
        style={{ display: "flex", flexWrap: "wrap", gap: "1rem 1.25rem", marginBottom: "0.85rem" }}
      >
        <Explainer label="xG">{GLOSSARY.xg}</Explainer>
        <Explainer label="xPunkte">{GLOSSARY.xpunkte}</Explainer>
        <Explainer label="Glücksfaktor">{GLOSSARY.gluecksfaktor}</Explainer>
        {view !== "points" && <Explainer label="xG-Tabelle">{GLOSSARY.xgtabelle}</Explainer>}
      </div>

      <DataTable
        columns={columns}
        rows={rows}
        columnSets={columnSets}
        identifierHeader={identifierHeader}
        renderIdentifier={renderIdentifier}
        rowProps={(r) => ({
          "data-zone": view === "points" ? zone(r.pos) : undefined,
        })}
      />

      {view === "points" && (
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: "0.35rem 1.1rem",
            marginTop: "0.7rem",
            fontSize: "var(--fs-small)",
            color: "var(--text-muted)",
          }}
        >
          {[
            ["var(--accent)", "Plätze 1–4: Champions League"],
            ["var(--text-dim)", "Plätze 5–6: Europa / Conference League"],
            ["var(--warning)", "Platz 16: Relegation"],
            ["var(--negative)", "Plätze 17–18: Abstieg"],
          ].map(([c, txt]) => (
            <span key={txt as string} style={{ display: "inline-flex", alignItems: "center", gap: "0.4rem" }}>
              <span style={{ width: 3, height: 14, borderRadius: 999, background: c as string }} />
              {txt}
            </span>
          ))}
        </div>
      )}

      <h2 className="sticky-h" style={{ margin: "2.5rem 0 0.75rem" }}>
        Tabellenplatz im Verlauf
      </h2>
      <Reveal className="surface" style={{ padding: "1rem" }}>
        <PositionOverTime history={history} />
      </Reveal>

      {regressionTeams.length > 0 && (
        <>
          <h2 className="sticky-h" style={{ margin: "2.5rem 0 0.75rem" }}>
            Regressionswarnung
          </h2>
          <div className="surface" style={{ padding: "1.25rem" }}>
            <p style={{ margin: "0 0 0.5rem", fontWeight: 500 }}>
              {regressionTeams
                .sort((a, b) => Math.abs(b.luck) - Math.abs(a.luck))
                .map((t) => `${teamName(t.team)} (${fmtSigned(t.luck, 1)})`)
                .join(", ")}
            </p>
            <p className="muted" style={{ margin: 0, fontSize: "var(--fs-small)" }}>
              Große Abweichungen zwischen Punkten und xPunkten gleichen sich über eine Saison
              meist aus — Chancenverwertung schwankt stärker als Spielkontrolle.
            </p>
          </div>
        </>
      )}
    </>
  );
}
