// Static data loading: read the exported JSON directly off the
// filesystem at build time. No client fetching, no API routes
// (BUILD BLUEPRINT §5.3).
import fs from "node:fs";
import path from "node:path";

const DATA_DIR = path.join(process.cwd(), "public", "data");

function readJson<T>(rel: string): T {
  const p = path.join(DATA_DIR, rel);
  return JSON.parse(fs.readFileSync(p, "utf-8")) as T;
}

function exists(rel: string): boolean {
  return fs.existsSync(path.join(DATA_DIR, rel));
}

// ---- manifest ------------------------------------------------------------
export interface Manifest {
  generated_at: string;
  current_season: number;
  /** internal date-index matchday (~99/season) -- not the football Spieltag */
  latest_matchday: number;
  /** true 1..34 Bundesliga Spieltag of the most recent played round */
  latest_round: number;
  /** the next unplayed round (0 when the season is over / not started) */
  next_round: number;
  seasons: number[];
  team_stats_available: boolean;
  warnings: string[];
}
export function getManifest(): Manifest {
  return readJson<Manifest>("manifest.json");
}

// ---- season table ------------------------------------------------------
export interface TableRow {
  team: string;
  played: number;
  won: number;
  drawn: number;
  lost: number;
  goals_for: number;
  goals_against: number;
  goal_diff: number;
  points: number;
  xg_for: number;
  xg_against: number;
  xg_diff: number;
  xpoints: number;
  luck: number;
}
export interface SeasonTable {
  season: number;
  table: TableRow[];
  history: { matchday: number; team: string; position: number }[];
}
export function getSeasonTable(season: number): SeasonTable {
  return readJson<SeasonTable>(`season/${season}/table.json`);
}

// ---- matches ---------------------------------------------------------
export interface MatchEntry {
  match_id: number;
  /** internal date-index matchday -- not the football Spieltag */
  matchday: number;
  /** true 1..34 Bundesliga Spieltag */
  round: number;
  date: string;
  time: string | null;
  home: string;
  away: string;
  home_goals: number;
  away_goals: number;
  home_xg: number;
  away_xg: number;
  home_npxg: number;
  away_npxg: number;
  home_xpoints: number;
  away_xpoints: number;
  home_shots: number;
  away_shots: number;
  home_big_chances: number;
  away_big_chances: number;
}
export interface UpcomingFixture {
  match_id: number;
  round: number;
  date: string;
  time: string | null;
  home: string;
  away: string;
}
export function getSeasonMatches(season: number): {
  season: number;
  matches: MatchEntry[];
  upcoming?: UpcomingFixture[];
} {
  return readJson(`season/${season}/matches.json`);
}

// ---- single match --------------------------------------------------
export interface Shot {
  minute: number;
  x: number;
  y: number;
  xg: number;
  npxg: number;
  result: string;
  situation: string;
  shot_type: string | null;
  player: string | null;
  team_side: "h" | "a";
  is_penalty: boolean;
}
export interface MatchDetail extends MatchEntry {
  shots: Shot[];
  xg_race: { home: { minute: number; xg: number }[]; away: { minute: number; xg: number }[] };
  game_state_xg: Record<string, number>;
  set_piece_split: {
    home: { open_play: number; set_piece: number; penalty: number };
    away: { open_play: number; set_piece: number; penalty: number };
  };
  players: PlayerLine[];
  verdict: string;
  ppda?: { home: number | null; away: number | null };
  deep?: { home: number | null; away: number | null };
  model: { tip: [number, number]; points: number; result: [number, number] } | null;
}
export interface PlayerLine {
  player_id: number;
  player: string;
  team_side: "h" | "a";
  position: string | null;
  minutes: number;
  is_starter: boolean;
  goals: number;
  shots: number;
  xg: number;
  xa: number;
  key_passes: number;
  assists: number;
  yellow_card: number;
  red_card: number;
}
export function getMatch(matchId: number): MatchDetail {
  return readJson<MatchDetail>(`match/${matchId}.json`);
}
export function allMatchIds(): number[] {
  const dir = path.join(DATA_DIR, "match");
  return fs
    .readdirSync(dir)
    .filter((f) => f.endsWith(".json"))
    .map((f) => parseInt(f.replace(".json", ""), 10));
}

// ---- predicted table / model performance -------------------------
export interface PredictedRow {
  team: string;
  played: number;
  won: number;
  drawn: number;
  lost: number;
  goals_for: number;
  goals_against: number;
  goal_diff: number;
  points: number;
  points_actual: number;
}
export function getPredictedTable(season: number): { season: number; table: PredictedRow[] } {
  return readJson(`season/${season}/predicted_table.json`);
}

export interface ModelPerfRow {
  matchday: number;
  exact: number;
  gd: number;
  tendency: number;
  miss: number;
  points: number;
  always21_points: number;
  cum_points: number;
  cum_always21_points: number;
  cum_exact: number;
  cum_gd: number;
  cum_tendency: number;
  cum_miss: number;
}
export function getModelPerformance(season: number): { season: number; by_matchday: ModelPerfRow[] } {
  return readJson(`season/${season}/model_performance.json`);
}

// ---- simulation --------------------------------------------------
export interface SimTeam {
  team: string;
  p_title: number;
  p_cl: number;
  p_el: number;
  p_conf: number;
  p_relegation_playoff: number;
  p_relegation: number;
  mean_points: number;
  [k: string]: number | string;
}
export interface Simulation {
  season: number;
  available: boolean;
  teams?: SimTeam[];
  n_runs?: number;
}
export function getSimulation(season: number): Simulation {
  return readJson<Simulation>(`season/${season}/simulation.json`);
}

// ---- records ---------------------------------------------------
export function getRecords(season: number): { season: number; records: Record<string, unknown> } {
  return readJson(`season/${season}/records.json`);
}

// ---- leaders -------------------------------------------------
export function getLeaders(season: number): {
  season: number;
  teams: { overperformers: TableRow[]; underperformers: TableRow[] };
  players: { overperformers: PlayerAgg[]; underperformers: PlayerAgg[] };
} {
  return readJson(`season/${season}/leaders.json`);
}

// ---- players -----------------------------------------------
export interface PlayerAgg {
  player_id: number;
  player: string;
  minutes: number;
  appearances: number;
  starts: number;
  goals: number;
  npxg: number;
  xa: number;
  shots: number;
  npxg_per_90: number;
  xa_per_90: number;
  npxg_per_shot: number;
  npxg_overperformance: number;
  low_minutes: boolean;
}
export function getPlayerIndex(season: number): { season: number; players: PlayerAgg[] } {
  return readJson(`player/${season}/index.json`);
}
export function getPlayer(season: number, id: number): PlayerDetail | null {
  const rel = `player/${season}/${id}.json`;
  if (!exists(rel)) return null;
  return readJson<PlayerDetail>(rel);
}
export interface PlayerDetail {
  season: number;
  player_id: number;
  player: string;
  aggregates: PlayerAgg;
  per_match: { match_id: number; npxg: number; goals: number; shots: number }[];
  shot_map: { x: number; y: number; xg: number; result: string; match_id: number }[];
  cumulative: { match_id: number; cum_npxg: number; cum_goals: number }[];
  best_matches: { match_id: number; npxg: number; goals: number; shots: number }[];
}

// ---- teams ----------------------------------------------
export interface TeamPage {
  season: number;
  team: string;
  slug: string;
  results: {
    match_id: number;
    matchday: number;
    opponent: string;
    venue: "home" | "away";
    goals_for: number;
    goals_against: number;
    xg_for: number;
    xg_against: number;
    points: number;
    xpoints: number;
  }[];
  luck_by_matchday: { matchday: number; luck: number }[];
  game_state_xg_totals: { level: number; winning: number; losing: number };
  rolling_xg: {
    home: { for: number[]; against: number[] };
    away: { for: number[]; against: number[] };
  };
  upcoming: { opponent: string; date: string; venue?: "home" | "away"; round?: number; match_id?: number }[];
  ppda_trend?: { date: string; ppda: number | null }[];
  deep_trend?: { date: string; deep: number | null }[];
}
export function getTeamSlugs(season: number): string[] {
  const dir = path.join(DATA_DIR, "team", String(season));
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir).filter((f) => f.endsWith(".json")).map((f) => f.replace(".json", ""));
}
export function getTeamPage(season: number, slug: string): TeamPage {
  return readJson<TeamPage>(`team/${season}/${slug}.json`);
}

// ---- h2h ----------------------------------------------
export interface H2H {
  team_a: string;
  team_b: string;
  meetings: {
    match_id: number;
    date: string;
    season: number;
    home_team: string;
    away_team: string;
    home_goals: number;
    away_goals: number;
  }[];
  record: { a_wins: number; b_wins: number; draws: number; played: number };
  aggregate_goals: { a: number; b: number };
  recent: H2H["meetings"];
}
export function h2hSlug(a: string, b: string): string {
  return `${a}__${b}`;
}
export function getH2H(fileSlug: string): H2H | null {
  const rel = `h2h/${fileSlug}.json`;
  if (!exists(rel)) return null;
  return readJson<H2H>(rel);
}
export function allH2HSlugs(): string[] {
  const dir = path.join(DATA_DIR, "h2h");
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir).filter((f) => f.endsWith(".json")).map((f) => f.replace(".json", ""));
}

// ---- stat of the week -------------------------------
export interface StatOfWeek {
  matchday: number;
  headline: string;
  value: number | null;
  context: string;
  link: string;
}
export function getStatOfWeek(): StatOfWeek {
  return readJson<StatOfWeek>("stat_of_the_week.json");
}

// ---- team slug helper --------------------------------
export { slugify } from "./format";
