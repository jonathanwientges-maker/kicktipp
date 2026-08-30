"use client";
import { useState } from "react";
import type { TableRow } from "@/lib/data";
import { fmtInt, fmtNum, fmtSigned, fmtSignedInt, luckColor, slugify } from "@/lib/format";
import Link from "next/link";
import { PositionOverTime } from "./charts/PositionOverTime";

type View = "points" | "xg" | "xgdiff";

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

  const regressionTeams = table.filter((t) => Math.abs(t.luck) > 5);

  return (
    <>
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.75rem", flexWrap: "wrap" }}>
        {(
          [
            ["points", "Tabelle"],
            ["xg", "xG-Tabelle"],
            ["xgdiff", "xG-Differenz"],
          ] as [View, string][]
        ).map(([v, label]) => (
          <button
            key={v}
            onClick={() => setView(v)}
            style={{
              padding: "0.35rem 0.8rem",
              borderRadius: 8,
              border: "1px solid var(--border)",
              background: view === v ? "var(--accent)" : "var(--surface)",
              color: view === v ? "#fff" : "var(--text)",
              cursor: "pointer",
              fontSize: "0.88rem",
            }}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="surface table-scroll">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Team</th>
              <th>Sp</th>
              <th>S</th>
              <th>U</th>
              <th>N</th>
              <th>Tore</th>
              <th>Diff</th>
              <th>Pkt</th>
              <th>xG</th>
              <th>xGA</th>
              <th>xG-Diff</th>
              <th>xPunkte</th>
              <th>Glücksfaktor</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((r, i) => (
              <tr key={r.team}>
                <td className="num muted">{i + 1}</td>
                <td>
                  <Link href={`/team/${slugify(r.team)}`}>{r.team}</Link>
                </td>
                <td className="num">{fmtInt(r.played)}</td>
                <td className="num">{fmtInt(r.won)}</td>
                <td className="num">{fmtInt(r.drawn)}</td>
                <td className="num">{fmtInt(r.lost)}</td>
                <td className="num">
                  {fmtInt(r.goals_for)}:{fmtInt(r.goals_against)}
                </td>
                <td className="num">{fmtSignedInt(r.goal_diff)}</td>
                <td className="num" style={{ fontWeight: 700 }}>
                  {fmtInt(r.points)}
                </td>
                <td className="num">{fmtNum(r.xg_for, 1)}</td>
                <td className="num">{fmtNum(r.xg_against, 1)}</td>
                <td className="num">{fmtSigned(r.xg_diff, 1)}</td>
                <td className="num">{fmtNum(r.xpoints, 1)}</td>
                <td className="num" style={{ color: luckColor(r.luck), fontWeight: 600 }}>
                  {fmtSigned(r.luck, 1)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2 style={{ fontSize: "1.05rem", margin: "2rem 0 0.5rem" }}>Tabellenplatz im Verlauf</h2>
      <div className="surface" style={{ padding: "0.75rem" }}>
        <PositionOverTime history={history} />
      </div>

      {regressionTeams.length > 0 && (
        <>
          <h2 style={{ fontSize: "1.05rem", margin: "2rem 0 0.5rem" }}>Regressionswarnung</h2>
          <div className="surface" style={{ padding: "1rem" }}>
            <p style={{ margin: "0 0 0.5rem" }}>
              {regressionTeams
                .sort((a, b) => Math.abs(b.luck) - Math.abs(a.luck))
                .map((t) => `${t.team} (${fmtSigned(t.luck, 1)})`)
                .join(", ")}
            </p>
            <p className="muted" style={{ margin: 0, fontSize: "0.9rem" }}>
              Große Abweichungen zwischen Punkten und xPunkten gleichen sich über eine Saison
              meist aus — Chancenverwertung schwankt stärker als Spielkontrolle.
            </p>
          </div>
        </>
      )}
    </>
  );
}
