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

      <div className="surface table-scroll">
        <table>
          <thead>
            <tr>
              <th className="pos-cell">#</th>
              <th>Team</th>
              <th className="num">Sp</th>
              <th className="num">S</th>
              <th className="num">U</th>
              <th className="num">N</th>
              <th className="num">Tore</th>
              <th className="num">Diff</th>
              <th className="num">Pkt</th>
              <th className="num">xG</th>
              <th className="num">xGA</th>
              <th className="num">xG-Diff</th>
              <th className="num">xPunkte</th>
              <th className="num">Glücksfaktor</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((r, i) => {
              const tc = teamColor(r.team).color;
              return (
                <tr key={r.team} data-zone={view === "points" ? zone(i + 1) : undefined}>
                  <td className="pos-cell">{i + 1}</td>
                  <td>
                    <Link href={`/team/${slugify(r.team)}`} className="team-cell">
                      <span className="team-bar" style={{ ["--tc" as any]: tc }} />
                      {teamName(r.team)}
                    </Link>
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
                  <td className="num bar-cell" style={{ ["--tc" as any]: tc }}>
                    <span className="bar-fill" style={{ width: `${(r.xg_for / maxXgFor) * 100}%` }} />
                    <span className="bar-val">{fmtNum(r.xg_for, 1)}</span>
                  </td>
                  <td className="num bar-cell" style={{ ["--tc" as any]: tc }}>
                    <span
                      className="bar-fill"
                      style={{ width: `${(r.xg_against / maxXgAgainst) * 100}%` }}
                    />
                    <span className="bar-val">{fmtNum(r.xg_against, 1)}</span>
                  </td>
                  <td className="num">{fmtSigned(r.xg_diff, 1)}</td>
                  <td className="num bar-cell" style={{ ["--tc" as any]: tc }}>
                    <span className="bar-fill" style={{ width: `${(r.xpoints / maxXpts) * 100}%` }} />
                    <span className="bar-val">{fmtNum(r.xpoints, 1)}</span>
                  </td>
                  <td className="num">
                    <span
                      className="luck-pill"
                      style={{ background: luckPillBg(r.luck), color: luckColor(r.luck) }}
                    >
                      {fmtSigned(r.luck, 1)}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

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

      <h2 style={{ margin: "2.5rem 0 0.75rem" }}>Tabellenplatz im Verlauf</h2>
      <Reveal className="surface" style={{ padding: "1rem" }}>
        <PositionOverTime history={history} />
      </Reveal>

      {regressionTeams.length > 0 && (
        <>
          <h2 style={{ margin: "2.5rem 0 0.75rem" }}>Regressionswarnung</h2>
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
