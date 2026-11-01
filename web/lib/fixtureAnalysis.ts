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

  const expectedXg = {
    home: (home.xgfPg + away.xgaPg) / 2,
    away: (away.xgfPg + home.xgaPg) / 2,
  };

  return {
    home,
    away,
    h2h: h2hOut,
    expectedXg,
  };
}
