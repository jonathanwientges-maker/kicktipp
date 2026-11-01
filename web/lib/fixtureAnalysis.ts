// Pre-match analysis for an upcoming fixture, built only from data the web
// export already carries (table, team pages, h2h, simulation). The export
// deliberately has no model tips or odds for unplayed matches, so nothing
// here is a prediction -- it is a profile of both teams.
import {
  getH2H,
  getSimulation,
  getTeamPage,
  h2hSlug,
  slugify,
  type H2H,
  type TableRow,
  type TeamPage,
  type UpcomingFixture,
} from "./data";
import { fmtNum } from "./format";
import { teamName } from "./teamColors";

export type FormGame = {
  opponent: string;
  venue: "home" | "away";
  gf: number;
  ga: number;
  xgf: number;
  xga: number;
  res: "W" | "D" | "L";
};

export type VenueSplit = {
  label: "Heim" | "Auswärts";
  games: number;
  ppg: number;
  gf: number;
  ga: number;
  xgf: number;
  xga: number;
};

export type SideAnalysis = {
  team: string;
  rank: number;
  xRank: number;
  row: TableRow;
  ppg: number;
  xppg: number;
  xgfPg: number;
  xgaPg: number;
  venue: VenueSplit | null;
  form: FormGame[];
  formPts: number;
  formXpts: number;
  formXgDiff: number;
  ppda: number | null;
  deep: number | null;
  sim: { title: number; cl: number; relegation: number } | null;
};

export type FixtureAnalysis = {
  home: SideAnalysis;
  away: SideAnalysis;
  h2h: {
    record: { home: number; draw: number; away: number; played: number };
    meetings: H2H["meetings"];
  } | null;
  /** simple xG profile (attack vs. opposing defence) -- not a model tip */
  expectedXg: { home: number; away: number };
  insights: string[];
};

const FORM_N = 5;

function safe<T>(fn: () => T): T | null {
  try {
    return fn();
  } catch {
    return null;
  }
}

function avg(xs: (number | null | undefined)[]): number | null {
  const v = xs.filter((x): x is number => typeof x === "number");
  return v.length ? v.reduce((s, x) => s + x, 0) / v.length : null;
}

function sum(xs: number[]): number {
  return xs.reduce((s, x) => s + x, 0);
}

function side(
  team: string,
  venue: "home" | "away",
  table: TableRow[],
  season: number,
  ranks: { real: Map<string, number>; x: Map<string, number> },
  sim: ReturnType<typeof getSimulation> | null,
): SideAnalysis | null {
  const row = table.find((t) => t.team === team);
  if (!row) return null;
  const page: TeamPage | null = safe(() => getTeamPage(season, slugify(team)));
  const results = [...(page?.results ?? [])].sort((a, b) => a.matchday - b.matchday);

  const toGame = (r: TeamPage["results"][number]): FormGame => ({
    opponent: r.opponent,
    venue: r.venue,
    gf: r.goals_for,
    ga: r.goals_against,
    xgf: r.xg_for,
    xga: r.xg_against,
    res: r.points === 3 ? "W" : r.points === 1 ? "D" : "L",
  });
  const form = results.slice(-FORM_N);
  const split = results.filter((r) => r.venue === venue);
  const n = row.played || 1;

  const simRow = sim?.available ? sim.teams?.find((t) => t.team === team) : undefined;
  return {
    team,
    rank: ranks.real.get(team)!,
    xRank: ranks.x.get(team)!,
    row,
    ppg: row.points / n,
    xppg: row.xpoints / n,
    xgfPg: row.xg_for / n,
    xgaPg: row.xg_against / n,
    venue: split.length
      ? {
          label: venue === "home" ? "Heim" : "Auswärts",
          games: split.length,
          ppg: sum(split.map((r) => r.points)) / split.length,
          gf: sum(split.map((r) => r.goals_for)) / split.length,
          ga: sum(split.map((r) => r.goals_against)) / split.length,
          xgf: sum(split.map((r) => r.xg_for)) / split.length,
          xga: sum(split.map((r) => r.xg_against)) / split.length,
        }
      : null,
    form: form.map(toGame),
    formPts: sum(form.map((r) => r.points)),
    formXpts: sum(form.map((r) => r.xpoints)),
    formXgDiff: sum(form.map((r) => r.xg_for - r.xg_against)),
    ppda: avg((page?.ppda_trend ?? []).map((p) => p.ppda)),
    deep: avg((page?.deep_trend ?? []).map((p) => p.deep)),
    sim: simRow
      ? {
          title: simRow.p_title,
          cl: simRow.p_cl,
          relegation: simRow.p_relegation + simRow.p_relegation_playoff,
        }
      : null,
  };
}

export function analyzeFixture(
  season: number,
  fx: UpcomingFixture,
  table: TableRow[],
): FixtureAnalysis | null {
  const byPoints = [...table].sort(
    (a, b) => b.points - a.points || b.goal_diff - a.goal_diff || b.goals_for - a.goals_for,
  );
  const byXpts = [...table].sort((a, b) => b.xpoints - a.xpoints || b.xg_diff - a.xg_diff);
  const ranks = {
    real: new Map(byPoints.map((t, i) => [t.team, i + 1])),
    x: new Map(byXpts.map((t, i) => [t.team, i + 1])),
  };
  const sim = safe(() => getSimulation(season));
  const home = side(fx.home, "home", table, season, ranks, sim);
  const away = side(fx.away, "away", table, season, ranks, sim);
  if (!home || !away) return null;

  // head-to-head, re-oriented so "home" is THIS fixture's home team
  const h2h =
    safe(() => getH2H(h2hSlug(slugify(fx.home), slugify(fx.away)))) ||
    safe(() => getH2H(h2hSlug(slugify(fx.away), slugify(fx.home))));
  let h2hOut: FixtureAnalysis["h2h"] = null;
  if (h2h && h2h.record.played > 0) {
    const homeIsA = h2h.team_a === fx.home;
    h2hOut = {
      record: {
        home: homeIsA ? h2h.record.a_wins : h2h.record.b_wins,
        draw: h2h.record.draws,
        away: homeIsA ? h2h.record.b_wins : h2h.record.a_wins,
        played: h2h.record.played,
      },
      meetings: [...h2h.meetings].sort((a, b) => b.date.localeCompare(a.date)).slice(0, 5),
    };
  }

  // league average xG per team and game, to judge "strong attack / leaky defence"
  const games = sum(table.map((t) => t.played));
  const leagueXg = games ? sum(table.map((t) => t.xg_for)) / games : 1.4;

  const expectedXg = {
    home: (home.xgfPg + away.xgaPg) / 2,
    away: (away.xgfPg + home.xgaPg) / 2,
  };

  return {
    home,
    away,
    h2h: h2hOut,
    expectedXg,
    insights: buildInsights(home, away, h2hOut, leagueXg),
  };
}

function buildInsights(
  h: SideAnalysis,
  a: SideAnalysis,
  h2h: FixtureAnalysis["h2h"],
  leagueXg: number,
): string[] {
  const out: string[] = [];
  const hn = teamName(h.team);
  const an = teamName(a.team);

  const minPlayed = Math.min(h.row.played, a.row.played);
  if (minPlayed < 8) {
    out.push(`Erst ${minPlayed} Spiele gespielt — alle Werte sind noch eine kleine Stichprobe.`);
  }

  // luck: points above/below what the chances earned
  for (const s of [h, a]) {
    const l = s.row.luck;
    if (Math.abs(l) >= 3) {
      out.push(
        l > 0
          ? `${teamName(s.team)} hat ${fmtNum(l, 1)} Punkte mehr geholt, als die Chancen hergaben (xPunkte ${fmtNum(s.row.xpoints, 1)}) — Rückschlagsgefahr.`
          : `${teamName(s.team)} liegt ${fmtNum(-l, 1)} Punkte unter den xPunkten (${fmtNum(s.row.xpoints, 1)}) — die Leistung war besser als die Tabelle.`,
      );
    }
  }

  // form vs. season level
  for (const s of [h, a]) {
    if (s.form.length >= 3) {
      const formPpg = s.formPts / s.form.length;
      const d = formPpg - s.ppg;
      if (d >= 0.7) out.push(`${teamName(s.team)} ist in Form: ${fmtNum(formPpg, 1)} Punkte pro Spiel zuletzt (Saison ${fmtNum(s.ppg, 1)}).`);
      else if (d <= -0.7) out.push(`${teamName(s.team)} kriselt: ${fmtNum(formPpg, 1)} Punkte pro Spiel zuletzt (Saison ${fmtNum(s.ppg, 1)}).`);
    }
  }

  // attack meets defence
  if (h.xgfPg >= leagueXg * 1.15 && a.xgaPg >= leagueXg * 1.1) {
    out.push(`${hn} hat einen starken Angriff (${fmtNum(h.xgfPg, 2)} xG/Spiel) gegen eine anfällige Abwehr (${an}: ${fmtNum(a.xgaPg, 2)} xGA/Spiel).`);
  }
  if (a.xgfPg >= leagueXg * 1.15 && h.xgaPg >= leagueXg * 1.1) {
    out.push(`${an} hat einen starken Angriff (${fmtNum(a.xgfPg, 2)} xG/Spiel) gegen eine anfällige Abwehr (${hn}: ${fmtNum(h.xgaPg, 2)} xGA/Spiel).`);
  }
  if (h.xgfPg <= leagueXg * 0.85 && a.xgfPg <= leagueXg * 0.85) {
    out.push("Beide Teams erspielen wenig Chancen — tendenziell ein torarmes Spiel.");
  }

  // venue strength
  if (h.venue && h.venue.games >= 2 && a.venue && a.venue.games >= 2) {
    const gap = h.venue.ppg - a.venue.ppg;
    if (gap >= 1.2) out.push(`Heimstärke gegen Auswärtsschwäche: ${hn} ${fmtNum(h.venue.ppg, 1)} P/Spiel zuhause, ${an} ${fmtNum(a.venue.ppg, 1)} auswärts.`);
    else if (gap <= -1.2) out.push(`${an} punktet auswärts (${fmtNum(a.venue.ppg, 1)} P/Spiel) stärker als ${hn} zuhause (${fmtNum(h.venue.ppg, 1)}).`);
  }

  // quality gap in chance terms
  const gap = (h.row.xg_diff / (h.row.played || 1)) - (a.row.xg_diff / (a.row.played || 1));
  if (Math.abs(gap) >= 0.8) {
    out.push(`Klarer Qualitätsunterschied bei den Chancen: ${gap > 0 ? hn : an} liegt ${fmtNum(Math.abs(gap), 2)} xG-Diff pro Spiel vorne.`);
  }

  if (h2h && h2h.record.played >= 4) {
    const share = Math.max(h2h.record.home, h2h.record.away) / h2h.record.played;
    if (share >= 0.6) {
      const homeLeads = h2h.record.home > h2h.record.away;
      const wins = homeLeads ? h2h.record.home : h2h.record.away;
      const losses = homeLeads ? h2h.record.away : h2h.record.home;
      out.push(`${homeLeads ? hn : an} dominiert die Bilanz (${wins} S, ${h2h.record.draw} U, ${losses} N aus ${h2h.record.played} Spielen).`);
    }
  }
  return out;
}
