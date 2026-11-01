"use client";
import { useState } from "react";
import { flushSync } from "react-dom";
import type { TableRow } from "@/lib/data";
import { fmtInt, fmtNum, fmtSigned, fmtSignedInt, luckPillBg, slugify } from "@/lib/format";
import { teamName } from "@/lib/teamColors";
import Link from "next/link";
import { PositionOverTime } from "./charts/PositionOverTime";
import { Reveal } from "./motion/Reveal";
import { Explainer } from "./Explainer";
import { GLOSSARY } from "@/lib/glossary";
import { TeamChip } from "./TeamChip";
import { DataTable, type Col, type ColumnSet } from "./DataTable";

type View = "points" | "xg" | "luck";

const VIEWS: { id: View; label: string; blurb: string }[] = [
  {
    id: "points",
    label: "Tabelle",
    blurb: "Die echte Tabelle. Δ-Rang zeigt, wie viele Plätze das Team nach xPunkten besser oder schlechter stünde.",
  },
  {
    id: "xg",
    label: "xG-Tabelle",
    blurb: "Rangiert nach xPunkten — wo das Team nach Chancenqualität stünde. Die farbige Kante bleibt der echte Tabellenplatz.",
  },
  {
    id: "luck",
    label: "Glücksfaktor",
    blurb: "Rangiert nach Punkte − xPunkte. Oben: mehr Punkte, als die Chancen hergaben (Regressionsgefahr). Unten: Pech.",
  },
];

// Δ-Rang at or above this many places gets a tinted chip
const STRONG_SHIFT = 4;
// |luck| above this (points) counts as a real misfit
const STRONG_LUCK = 5;

function zone(pos: number): string | undefined {
  if (pos <= 4) return "cl";
  if (pos <= 6) return "el";
  if (pos === 16) return "relegation";
  if (pos >= 17) return "drop";
  return undefined;
}

function luckHue(luck: number): string {
  if (luck > 0.05) return "var(--luck-hot)";
  if (luck < -0.05) return "var(--luck-cold)";
  return "var(--text-muted)";
}

function RankShift({ shift }: { shift: number }) {
  const dir = shift > 0 ? "up" : shift < 0 ? "down" : "flat";
  const n = Math.abs(shift);
  const label =
    shift === 0
      ? "Rang entspricht den xPunkten"
      : `Verdient ${n} ${n === 1 ? "Platz" : "Plätze"} ${shift > 0 ? "besser" : "schlechter"}`;
  return (
    <span
      className="rank-shift"
      data-dir={dir}
      data-strong={n >= STRONG_SHIFT}
      title={label}
      aria-label={label}
    >
      {shift === 0 ? "–" : `${shift > 0 ? "▲" : "▼"} ${n}`}
    </span>
  );
}

export function TableToggle({
  table,
  history,
}: {
  table: TableRow[];
  history: { matchday: number; team: string; position: number }[];
}) {
  const [view, setViewState] = useState<View>("points");

  // rows glide to their new positions where view transitions are supported
  const setView = (v: View) => {
    const doc = document as Document & {
      startViewTransition?: (cb: () => void) => unknown;
    };
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!doc.startViewTransition || reduce) {
      setViewState(v);
      return;
    }
    doc.startViewTransition(() => flushSync(() => setViewState(v)));
  };

  // ranks under each ordering — computed once, independent of the active view
  const byPoints = [...table].sort(
    (a, b) => b.points - a.points || b.goal_diff - a.goal_diff || b.goals_for - a.goals_for,
  );
  const byXpts = [...table].sort((a, b) => b.xpoints - a.xpoints || b.xg_diff - a.xg_diff);
  const realRank = new Map(byPoints.map((t, i) => [t.team, i + 1]));
  const xRank = new Map(byXpts.map((t, i) => [t.team, i + 1]));

  type R = TableRow & { id: string; pos: number; real: number; shift: number };
  const rowsAll: R[] = table.map((r) => ({
    ...r,
    id: r.team,
    pos: 0,
    real: realRank.get(r.team)!,
    // > 0: the xPunkte rank is better than the real one (deserves more)
    shift: realRank.get(r.team)! - xRank.get(r.team)!,
  }));
  const ordered = [...rowsAll].sort((a, b) => {
    if (view === "xg") return xRank.get(a.team)! - xRank.get(b.team)!;
    if (view === "luck") return b.luck - a.luck || a.real - b.real;
    return a.real - b.real;
  });
  const rows: R[] = ordered.map((r, i) => ({ ...r, pos: i + 1 }));

  const maxAbsLuck = Math.max(...table.map((t) => Math.abs(t.luck)), 0.01);
  const ptsVals = table.flatMap((t) => [t.points, t.xpoints]);
  const lo = Math.min(...ptsVals);
  const hi = Math.max(...ptsVals);
  const scale = (v: number) => 4 + ((v - lo) / Math.max(hi - lo, 0.01)) * 92;

  const dumbbell = (r: R) => {
    const a = scale(r.xpoints);
    const b = scale(r.points);
    const c = luckHue(r.luck);
    return (
      <span
        className="dumbbell"
        style={{ ["--c" as any]: c, display: "block" }}
        role="img"
        aria-label={`${fmtInt(r.points)} Punkte, ${fmtNum(r.xpoints, 1)} xPunkte`}
      >
        <span className="dumbbell-track" />
        <span className="dumbbell-link" style={{ left: `${Math.min(a, b)}%`, width: `${Math.abs(a - b)}%` }} />
        <span className="dumbbell-dot" data-k="x" style={{ left: `${a}%` }} />
        <span className="dumbbell-dot" data-k="p" style={{ left: `${b}%` }} />
      </span>
    );
  };

  const luckBar = (r: R) => {
    const half = (Math.abs(r.luck) / maxAbsLuck) * 50;
    const c = luckHue(r.luck);
    const strong = Math.abs(r.luck) > STRONG_LUCK;
    return (
      <span className="luckbar" style={{ ["--c" as any]: c }}>
        <span className="luckbar-track">
          <span
            className="luckbar-fill"
            style={r.luck >= 0 ? { left: "50%", width: `${half}%` } : { right: "50%", width: `${half}%` }}
          />
        </span>
        <span
          className="luckbar-val"
          style={{
            color: c,
            ...(strong ? { background: luckPillBg(r.luck), borderRadius: "999px", padding: "0.1rem 0.4rem" } : {}),
          }}
        >
          {fmtSigned(r.luck, 1)}
        </span>
      </span>
    );
  };

  const col = {
    played: { key: "played", label: "Sp", numeric: true, render: (r: R) => fmtInt(r.played) },
    won: { key: "won", label: "S", numeric: true, render: (r: R) => fmtInt(r.won) },
    drawn: { key: "drawn", label: "U", numeric: true, render: (r: R) => fmtInt(r.drawn) },
    lost: { key: "lost", label: "N", numeric: true, render: (r: R) => fmtInt(r.lost) },
    goals: {
      key: "goals",
      label: "Tore",
      numeric: true,
      render: (r: R) => `${fmtInt(r.goals_for)}:${fmtInt(r.goals_against)}`,
    },
    goal_diff: { key: "goal_diff", label: "Diff", numeric: true, render: (r: R) => fmtSignedInt(r.goal_diff) },
    points: {
      key: "points",
      label: "Pkt",
      numeric: true,
      render: (r: R) => <span style={{ fontWeight: 700 }}>{fmtInt(r.points)}</span>,
    },
    xg_for: { key: "xg_for", label: "xG", numeric: true, render: (r: R) => fmtNum(r.xg_for, 1) },
    xg_against: { key: "xg_against", label: "xGA", numeric: true, render: (r: R) => fmtNum(r.xg_against, 1) },
    xg_diff: { key: "xg_diff", label: "xG-Diff", numeric: true, render: (r: R) => fmtSigned(r.xg_diff, 1) },
    xpoints: {
      key: "xpoints",
      label: "xPkt",
      numeric: true,
      render: (r: R) => <span style={{ fontWeight: view === "points" ? 400 : 700 }}>{fmtNum(r.xpoints, 1)}</span>,
    },
    real: { key: "real", label: "Tab.", numeric: true, render: (r: R) => <span className="muted">{r.real}.</span> },
    shift: { key: "shift", label: "Δ-Rang", numeric: true, render: (r: R) => <RankShift shift={r.shift} /> },
    dumbbell: { key: "dumbbell", label: "Pkt vs. xPkt", render: dumbbell },
    luckbar: { key: "luckbar", label: "Glück", render: luckBar },
  } satisfies Record<string, Col<R>>;

  const sets: Record<View, { desktop: (keyof typeof col)[]; mobile: (keyof typeof col)[] }> = {
    points: {
      desktop: ["played", "won", "drawn", "lost", "goals", "goal_diff", "points", "shift"],
      mobile: ["goal_diff", "points", "shift"],
    },
    xg: {
      desktop: ["played", "real", "xg_for", "xg_against", "xg_diff", "xpoints", "dumbbell", "shift"],
      mobile: ["real", "xg_diff", "xpoints", "shift"],
    },
    luck: {
      desktop: ["played", "real", "points", "xpoints", "luckbar", "shift"],
      mobile: ["real", "points", "xpoints", "luckbar"],
    },
  };
  const columns: Col<R>[] = Object.values(col);
  const columnSets: ColumnSet[] = [{ label: view, keys: sets[view].mobile }];

  // the expanded card always carries every value, in plain form
  const cardCols: Col<R>[] = [
    { key: "c-real", label: "Tabellenplatz", render: (r) => `${r.real}.` },
    { key: "c-xrank", label: "xPunkte-Rang", render: (r) => `${xRank.get(r.team)}.` },
    { key: "c-shift", label: "Δ-Rang", render: (r) => <RankShift shift={r.shift} /> },
    { key: "c-played", label: "Spiele", render: (r) => fmtInt(r.played) },
    { key: "c-wdl", label: "S / U / N", render: (r) => `${fmtInt(r.won)} / ${fmtInt(r.drawn)} / ${fmtInt(r.lost)}` },
    { key: "c-goals", label: "Tore", render: (r) => `${fmtInt(r.goals_for)}:${fmtInt(r.goals_against)}` },
    { key: "c-gd", label: "Tordifferenz", render: (r) => fmtSignedInt(r.goal_diff) },
    { key: "c-pts", label: "Punkte", render: (r) => <strong>{fmtInt(r.points)}</strong> },
    { key: "c-xg", label: "xG", render: (r) => fmtNum(r.xg_for, 1) },
    { key: "c-xga", label: "xGA", render: (r) => fmtNum(r.xg_against, 1) },
    { key: "c-xgd", label: "xG-Differenz", render: (r) => fmtSigned(r.xg_diff, 1) },
    { key: "c-xpts", label: "xPunkte", render: (r) => fmtNum(r.xpoints, 1) },
    {
      key: "c-luck",
      label: "Glücksfaktor",
      render: (r) => (
        <span className="luck-pill" style={{ background: luckPillBg(r.luck), color: luckHue(r.luck) }}>
          {fmtSigned(r.luck, 1)}
        </span>
      ),
    },
    {
      key: "c-link",
      label: "Team",
      render: (r) => (
        <Link href={`/team/${slugify(r.team)}`} style={{ color: "var(--accent)", fontWeight: 600 }}>
          Teamseite →
        </Link>
      ),
    },
  ];

  // headline misfits: luckiest and unluckiest team
  const byLuck = [...table].sort((a, b) => b.luck - a.luck);
  const luckiest = byLuck[0];
  const unluckiest = byLuck[byLuck.length - 1];
  const regressionTeams = table.filter((t) => Math.abs(t.luck) > STRONG_LUCK);
  const currentView = VIEWS.find((v) => v.id === view)!;

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
        {VIEWS.map((v) => (
          <button
            key={v.id}
            className="toggle-btn"
            data-active={view === v.id}
            onClick={() => setView(v.id)}
          >
            {v.label}
          </button>
        ))}
      </div>

      {luckiest && unluckiest && (
        <div className="surface insight-strip">
          <span>
            Größtes Glück:{" "}
            <Link href={`/team/${slugify(luckiest.team)}`}>{teamName(luckiest.team)}</Link>{" "}
            <span data-dir="hot">{fmtSigned(luckiest.luck, 1)}</span>
          </span>
          <span>
            Größtes Pech:{" "}
            <Link href={`/team/${slugify(unluckiest.team)}`}>{teamName(unluckiest.team)}</Link>{" "}
            <span data-dir="cold">{fmtSigned(unluckiest.luck, 1)}</span>
          </span>
          {regressionTeams.length > 0 && (
            <span>
              {regressionTeams.length} {regressionTeams.length === 1 ? "Team" : "Teams"} mit über {STRONG_LUCK} Punkten
              Abweichung — solche Lücken gleichen sich meist aus.
            </span>
          )}
        </div>
      )}

      <p className="muted" style={{ margin: "0 0 0.6rem", fontSize: "var(--fs-small)" }}>
        {currentView.blurb}
      </p>
      <div
        className="label"
        style={{ display: "flex", flexWrap: "wrap", gap: "1rem 1.25rem", marginBottom: "0.85rem" }}
      >
        {view !== "points" && <Explainer label="xPunkte">{GLOSSARY.xpunkte}</Explainer>}
        {view === "xg" && <Explainer label="xG">{GLOSSARY.xg}</Explainer>}
        {view === "xg" && <Explainer label="xG-Tabelle">{GLOSSARY.xgtabelle}</Explainer>}
        {view === "luck" && <Explainer label="Glücksfaktor">{GLOSSARY.gluecksfaktor}</Explainer>}
        {view === "points" && <Explainer label="Δ-Rang">{GLOSSARY.xgtabelle}</Explainer>}
      </div>

      <DataTable
        columns={columns}
        desktopKeys={sets[view].desktop}
        cardColumns={cardCols}
        expandOnDesktop
        rows={rows}
        columnSets={columnSets}
        identifierHeader={identifierHeader}
        renderIdentifier={renderIdentifier}
        rowProps={(r) => ({
          "data-zone": zone(r.real),
          style: { viewTransitionName: `row-${slugify(r.team)}` },
        })}
      />

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
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: "0.35rem 1.1rem",
          marginTop: "0.4rem",
          fontSize: "var(--fs-small)",
          color: "var(--text-muted)",
        }}
      >
        <span>
          <span style={{ color: "var(--luck-cold)", fontWeight: 700 }}>▲</span> verdient einen besseren Rang (Pech)
        </span>
        <span>
          <span style={{ color: "var(--luck-hot)", fontWeight: 700 }}>▼</span> verdient einen schlechteren Rang (Glück)
        </span>
        <span>Kante = echte Tabellenzone · Zeile antippen für alle Werte</span>
      </div>

      <h2 className="sticky-h" style={{ margin: "2.5rem 0 0.75rem" }}>
        Tabellenplatz im Verlauf
      </h2>
      <Reveal className="surface" style={{ padding: "1rem" }}>
        <PositionOverTime history={history} />
      </Reveal>

    </>
  );
}
