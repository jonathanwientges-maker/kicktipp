// Everything the team page charts need, derived at build time from the
// exported JSON: this team's games (with opponent, venue, round), plus the
// league context (average, middle 50 %, rank) that makes a number readable.
import {
  getMatch,
  getSeasonMatches,
  type MatchDetail,
  type TeamPage,
} from "./data";
import { fmtNum, fmtSigned } from "./format";

export type TeamGame = {
  round: number;
  opponent: string;
  venue: "home" | "away";
  gf: number;
  ga: number;
  xgf: number;
  xga: number;
  pts: number;
  xpts: number;
  ppda: number | null;
  deep: number | null;
  cumPts: number;
  cumXpts: number;
};

export type LeagueStat = {
  /** mean over every team-game in the league */
  mean: number;
  /** middle 50 % of team-games */
  p25: number;
  p75: number;
  /** this team's own average, its rank (1 = best) and the number of teams ranked */
  team: number | null;
  rank: number | null;
  teams: number;
};

export type Sources = { open: number; set: number; pen: number };

export type TeamAnalysis = {
  games: TeamGame[];
  ppda: LeagueStat | null;
  deep: LeagueStat | null;
  /** xG per game by game state, this team vs. league average */
  gameState: { key: "level" | "winning" | "losing"; label: string; team: number; league: number }[];
  /** xG per game by source */
  sourcesFor: { team: Sources; league: Sources };
  sourcesAgainst: { team: Sources; league: Sources };
  takeaways: {
    luck: string;
    matches: string;
    ppda: string | null;
    deep: string | null;
    sources: string;
  };
};

type TeamGameRow = {
  team: string;
  ppda: number | null;
  deep: number | null;
  spFor: Sources;
  spAgainst: Sources;
  gs: { level: number; winning: number; losing: number };
};

function safe<T>(fn: () => T): T | null {
  try {
    return fn();
  } catch {
    return null;
  }
}

function sum(xs: number[]) {
  return xs.reduce((s, x) => s + x, 0);
}
function mean(xs: number[]) {
  return xs.length ? sum(xs) / xs.length : 0;
}
function quantile(sorted: number[], q: number) {
  if (!sorted.length) return 0;
  const pos = (sorted.length - 1) * q;
  const lo = Math.floor(pos);
  const hi = Math.ceil(pos);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo);
}

// one pass over the season's match files, shared by all 18 team pages
const cache = new Map<number, { byMatch: Map<number, { round: number; rows: TeamGameRow[] }>; rows: TeamGameRow[] }>();

function league(season: number) {
  const hit = cache.get(season);
  if (hit) return hit;
  const byMatch = new Map<number, { round: number; rows: TeamGameRow[] }>();
  const rows: TeamGameRow[] = [];
  for (const m of getSeasonMatches(season).matches) {
    const d: MatchDetail | null = safe(() => getMatch(m.match_id));
    if (!d) continue;
    const gs = d.game_state_xg ?? {};
    const sp = d.set_piece_split;
    const mk = (side: "home" | "away"): TeamGameRow => {
      const h = side === "home";
      const k = h ? "h" : "a";
      const own = sp?.[side];
      const opp = sp?.[h ? "away" : "home"];
      return {
        team: h ? m.home : m.away,
        ppda: d.ppda?.[side] ?? null,
        deep: d.deep?.[side] ?? null,
        spFor: { open: own?.open_play ?? 0, set: own?.set_piece ?? 0, pen: own?.penalty ?? 0 },
        spAgainst: { open: opp?.open_play ?? 0, set: opp?.set_piece ?? 0, pen: opp?.penalty ?? 0 },
        gs: {
          level: gs[`xg_while_level_${k}`] ?? 0,
          winning: gs[`xg_while_winning_${k}`] ?? 0,
          losing: gs[`xg_while_losing_${k}`] ?? 0,
        },
      };
    };
    const pair = [mk("home"), mk("away")];
    byMatch.set(m.match_id, { round: m.round, rows: pair });
    rows.push(...pair);
  }
  const out = { byMatch, rows };
  cache.set(season, out);
  return out;
}

function leagueStat(
  all: TeamGameRow[],
  pick: (r: TeamGameRow) => number | null,
  team: string,
  better: "low" | "high",
): LeagueStat | null {
  const vals = all.map(pick).filter((v): v is number => v !== null).sort((a, b) => a - b);
  if (!vals.length) return null;
  const perTeam = new Map<string, number[]>();
  for (const r of all) {
    const v = pick(r);
    if (v === null) continue;
    perTeam.set(r.team, [...(perTeam.get(r.team) ?? []), v]);
  }
  const avgs = [...perTeam.entries()].map(([t, v]) => [t, mean(v)] as const);
  avgs.sort((a, b) => (better === "low" ? a[1] - b[1] : b[1] - a[1]));
  const idx = avgs.findIndex(([t]) => t === team);
  return {
    mean: mean(vals),
    p25: quantile(vals, 0.25),
    p75: quantile(vals, 0.75),
    team: idx >= 0 ? avgs[idx][1] : null,
    rank: idx >= 0 ? idx + 1 : null,
    teams: avgs.length,
  };
}

function srcPerGame(rows: TeamGameRow[], key: "spFor" | "spAgainst"): Sources {
  const n = rows.length || 1;
  return {
    open: sum(rows.map((r) => r[key].open)) / n,
    set: sum(rows.map((r) => r[key].set)) / n,
    pen: sum(rows.map((r) => r[key].pen)) / n,
  };
}

export function analyzeTeam(season: number, page: TeamPage): TeamAnalysis {
  const lg = league(season);
  const mine = lg.rows.filter((r) => r.team === page.team);

  let cumPts = 0;
  let cumXpts = 0;
  const games: TeamGame[] = [...page.results]
    .sort((a, b) => a.matchday - b.matchday)
    .map((r) => {
      const m = lg.byMatch.get(r.match_id);
      const row = m?.rows.find((x) => x.team === page.team);
      cumPts += r.points;
      cumXpts += r.xpoints;
      return {
        round: m?.round ?? r.matchday,
        opponent: r.opponent,
        venue: r.venue,
        gf: r.goals_for,
        ga: r.goals_against,
        xgf: r.xg_for,
        xga: r.xg_against,
        pts: r.points,
        xpts: r.xpoints,
        ppda: row?.ppda ?? null,
        deep: row?.deep ?? null,
        cumPts,
        cumXpts,
      };
    });

  const ppda = leagueStat(lg.rows, (r) => r.ppda, page.team, "low");
  const deep = leagueStat(lg.rows, (r) => r.deep, page.team, "high");

  const gsAvg = (rows: TeamGameRow[], k: "level" | "winning" | "losing") => mean(rows.map((r) => r.gs[k]));
  const gameState = (
    [
      ["level", "Bei Gleichstand"],
      ["winning", "In Führung"],
      ["losing", "Im Rückstand"],
    ] as const
  ).map(([key, label]) => ({
    key,
    label,
    team: gsAvg(mine, key),
    league: gsAvg(lg.rows, key),
  }));

  const sourcesFor = { team: srcPerGame(mine, "spFor"), league: srcPerGame(lg.rows, "spFor") };
  const sourcesAgainst = { team: srcPerGame(mine, "spAgainst"), league: srcPerGame(lg.rows, "spAgainst") };

  // ---- one-line readings shown above each chart ----
  const n = games.length;
  const last = games[n - 1];
  const luck = last ? last.cumPts - last.cumXpts : 0;
  const ahead = games.filter((g) => g.xgf > g.xga).length;
  const goalsFor = sum(games.map((g) => g.gf));
  const xgFor = sum(games.map((g) => g.xgf));
  const totalSrc = (s: Sources) => s.open + s.set + s.pen;
  const setShare = totalSrc(sourcesFor.team) ? (sourcesFor.team.set + sourcesFor.team.pen) / totalSrc(sourcesFor.team) : 0;
  const leagueSetShare = totalSrc(sourcesFor.league)
    ? (sourcesFor.league.set + sourcesFor.league.pen) / totalSrc(sourcesFor.league)
    : 0;

  const statLine = (s: LeagueStat | null, dp: number, what: string) =>
    s && s.team !== null && s.rank !== null
      ? `Ø ${fmtNum(s.team, dp)} — ${what} Rang ${s.rank} von ${s.teams} (Liga Ø ${fmtNum(s.mean, dp)}).`
      : null;

  return {
    games,
    ppda,
    deep,
    gameState,
    sourcesFor,
    sourcesAgainst,
    takeaways: {
      luck:
        n === 0
          ? "Noch keine Spiele."
          : `Nach ${n} ${n === 1 ? "Spiel" : "Spielen"}: ${last.cumPts} Punkte bei ${fmtNum(last.cumXpts, 1)} xPunkten (${fmtSigned(luck, 1)}) — ${
              Math.abs(luck) < 1 ? "Ergebnisse und Chancen passen zusammen." : luck > 0 ? "mehr Punkte, als die Chancen hergaben." : "weniger Punkte, als die Chancen hergaben."
            }`,
      matches:
        n === 0
          ? "Noch keine Spiele."
          : `In ${ahead} von ${n} Spielen mehr xG als der Gegner · ${goalsFor} Tore bei ${fmtNum(xgFor, 1)} xG.`,
      ppda: statLine(ppda, 1, "aggressivstes Pressing:"),
      deep: statLine(deep, 1, "meiste Zuspiele in Tornähe:"),
      sources: `${fmtNum(setShare * 100, 0)} % der eigenen xG kommen aus Standards und Elfmetern (Liga Ø ${fmtNum(leagueSetShare * 100, 0)} %).`,
    },
  };
}
