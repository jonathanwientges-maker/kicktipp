"""
Understat scraper: league-season match list (xG/npxG/forecast) and
per-match shot data.

Understat used to embed this data as JSON inside <script> tags on each
page (`var datesData = JSON.parse('...')`), which is what the original
version of this module regex-scraped. Understat has since restructured
the site so that the league/match pages ship as a near-empty HTML shell
and fetch their data client-side, via jQuery AJAX calls to a JSON API:
  - league page:  GET https://understat.com/getLeagueData/{league}/{year}
        -> {"teams": {...}, "players": [...], "dates": [...]}. The
           `dates` list has the exact schema the old `datesData` had:
           one row per match (id, datetime, h/a team info, goals, xG,
           forecast).
  - match page:   GET https://understat.com/getMatchData/{match_id}
        -> {"rosters": {...}, "shots": {"h": [...], "a": [...]}, "tmpl": ...}.
           The `shots` value has the exact schema the old `shotsData`
           had (minute, X, Y, xG, result, situation, shotType, player,
           lastAction).

Both endpoints require the request to look like the page's own AJAX call
(X-Requested-With: XMLHttpRequest + a Referer pointing at the
corresponding page) -- without those headers they 404 rather than
silently degrading, so a change in that behavior surfaces loudly as an
HTTP error, not a wrong answer. All fields in both payloads come back as
JSON strings rather than native numbers (except `isResult`, a real
bool); the existing parse_league_matches/parse_match_shots functions
already coerce every field with explicit int()/float() calls, so numeric
strings work with them unmodified -- verified directly against a live
2024/25 Bundesliga match before this rewrite.

Rate limiting: one request every config.UNDERSTAT_DELAY_S seconds minimum.
3 retries with exponential backoff; on persistent failure the run aborts
(raises -> non-zero exit at the caller).
"""
import math
import time

import pandas as pd
import requests

import config

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

_RETRIES = 3
_BACKOFF_BASE = 2.0

_last_request_ts = [0.0]  # mutable cell so _throttle can update across calls


def _throttle():
    elapsed = time.time() - _last_request_ts[0]
    wait = config.UNDERSTAT_DELAY_S - elapsed
    if wait > 0:
        time.sleep(wait)
    _last_request_ts[0] = time.time()


def _fetch_json(url, referer):
    """
    GET `url` as Understat's own front-end AJAX calls do: with
    X-Requested-With + Referer set so the endpoint serves real data
    instead of 404'ing. Retries on any failure, including a non-2xx
    status or a body that doesn't parse as JSON (Understat returns an
    HTML error page on 404, not JSON, so a decode failure here is a real
    signal something is wrong, not a transient hiccup to swallow).
    """
    last_err = None
    headers = {
        "User-Agent": USER_AGENT,
        "X-Requested-With": "XMLHttpRequest",
        "Referer": referer,
    }
    for attempt in range(_RETRIES):
        _throttle()
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # noqa: BLE001 - deliberate broad retry
            last_err = exc
            if attempt < _RETRIES - 1:
                time.sleep(_BACKOFF_BASE ** attempt)
    raise RuntimeError(
        "Understat request to {0} failed after {1} retries: {2}".format(
            url, _RETRIES, last_err
        )
    )


def fetch_league_season(league, year):
    """Fetch the match list (the `dates` array) for a league-season."""
    referer = "{0}/league/{1}/{2}".format(config.UNDERSTAT_BASE, league, year)
    url = "{0}/getLeagueData/{1}/{2}".format(config.UNDERSTAT_BASE, league, year)
    data = _fetch_json(url, referer)
    if "dates" not in data:
        raise ValueError(
            "Understat getLeagueData response for {0}/{1} is missing the "
            "'dates' key -- response shape may have changed again: keys "
            "present were {2}".format(league, year, list(data.keys()))
        )
    return data["dates"]


def fetch_league_data(league, year):
    """
    Fetch the full getLeagueData payload with ONE request. Both the match
    list ('dates') and the per-team block ('teams'/'teamsData') live in
    this response -- reuse this dict, do not fetch the page twice.
    """
    referer = "{0}/league/{1}/{2}".format(config.UNDERSTAT_BASE, league, year)
    url = "{0}/getLeagueData/{1}/{2}".format(config.UNDERSTAT_BASE, league, year)
    return _fetch_json(url, referer)


# Priority order for the per-team block key inside getLeagueData.
_TEAM_BLOCK_KEYS = ("teams", "teamsData", "teams_data")


def fetch_league_teams(league, year):
    """
    Best-effort: return the per-team block from getLeagueData if present,
    else None. Never raises on a missing block -- team-stats (PPDA, deep
    completions) are an optional enrichment; the site builds without
    them (see parse_league_teams and the export manifest's
    team_stats_available flag).
    """
    data = fetch_league_data(league, year)
    for key in _TEAM_BLOCK_KEYS:
        if key in data and data[key]:
            return data[key]
    return None


def fetch_match_data(match_id):
    """
    Fetch the full getMatchData payload for a single match with ONE
    request. Both the shots and the rosters live in this response --
    callers that need both must reuse this dict, not fetch the page
    twice (Understat rate-limits and every extra request costs
    UNDERSTAT_DELAY_S).
    """
    referer = "{0}/match/{1}".format(config.UNDERSTAT_BASE, match_id)
    url = "{0}/getMatchData/{1}".format(config.UNDERSTAT_BASE, match_id)
    return _fetch_json(url, referer)


def fetch_match_shots(match_id):
    """Fetch the shots dict ({'h': [...], 'a': [...]}) for a single match."""
    data = fetch_match_data(match_id)
    if "shots" not in data:
        raise ValueError(
            "Understat getMatchData response for match {0} is missing the "
            "'shots' key -- response shape may have changed again: keys "
            "present were {1}".format(match_id, list(data.keys()))
        )
    return data["shots"]


def fetch_match_rosters(match_id):
    """
    Fetch the rosters dict ({'h': {...}, 'a': {...}}) for a single match.
    Reuses fetch_match_data -- when a caller needs shots AND rosters it
    must call fetch_match_data once and pass its "shots"/"rosters" keys
    to the two parsers, never call both fetch_* helpers (that doubles the
    HTTP requests).
    """
    data = fetch_match_data(match_id)
    if "rosters" not in data:
        raise ValueError(
            "Understat getMatchData response for match {0} is missing the "
            "'rosters' key -- response shape may have changed again: keys "
            "present were {1}".format(match_id, list(data.keys()))
        )
    return data["rosters"]


def _goals_and_xg(side_dict):
    return {
        "goals": int(side_dict["goals"]),
        "xG": float(side_dict["xG"]),
    }


def parse_league_matches(dates_data, season):
    """
    Convert raw datesData (list of dicts) into the project's matches
    schema. npxG/shots are NOT available on the league page -- they are
    filled in later from the shots data (see build_matches_from_shots).
    """
    rows = []
    for m in dates_data:
        if not m.get("isResult", False):
            continue  # future fixture, no result yet
        home = m["h"]
        away = m["a"]
        goals = m["goals"]
        xg = m["xG"]
        forecast = m.get("forecast", {})
        rows.append({
            "match_id": int(m["id"]),
            "season": season,
            "league": config.LEAGUE,
            "datetime": pd.to_datetime(m["datetime"]),
            "home_team": home["title"],
            "away_team": away["title"],
            "home_goals": int(goals["h"]),
            "away_goals": int(goals["a"]),
            "home_xG": float(xg["h"]),
            "away_xG": float(xg["a"]),
            "forecast_win": float(forecast.get("w", "nan")) if forecast else float("nan"),
            "forecast_draw": float(forecast.get("d", "nan")) if forecast else float("nan"),
            "forecast_loss": float(forecast.get("l", "nan")) if forecast else float("nan"),
        })
    return pd.DataFrame(rows)


def parse_match_shots(shots_data, match_id, season):
    """Flatten shotsData {'h': [...], 'a': [...]} into one row per shot."""
    rows = []
    for side, shots in (("h", shots_data.get("h", [])), ("a", shots_data.get("a", []))):
        for sh in shots:
            situation = sh.get("situation", "")
            player_id_raw = sh.get("player_id")
            try:
                player_id = int(player_id_raw) if player_id_raw not in (None, "") else -1
            except (TypeError, ValueError):
                player_id = -1
            rows.append({
                "shot_id": int(sh["id"]),
                "match_id": match_id,
                "season": season,
                "league": config.LEAGUE,
                "player": sh.get("player"),
                "player_id": player_id,
                "player_assisted": sh.get("player_assisted"),
                "minute": int(sh.get("minute", 0)),
                "result": sh.get("result"),
                "xG": float(sh.get("xG", 0.0)),
                "X": float(sh.get("X", 0.0)),
                "Y": float(sh.get("Y", 0.0)),
                "home_away": side,
                "situation": situation,
                "shotType": sh.get("shotType"),
                "lastAction": sh.get("lastAction"),
                "is_penalty": situation == "Penalty",
            })
    df = pd.DataFrame(rows)
    if len(df) > 0:
        df["npxG"] = df["xG"].where(~df["is_penalty"], 0.0)
        df["player_id"] = df["player_id"].astype("int64")
    return df


# ---------------------------------------------------------------------------
# Rosters (§1.2)
# ---------------------------------------------------------------------------

# column -> (source key, python caster, missing default). Casters run on
# the raw JSON string; on ValueError/TypeError the default is substituted
# and the occurrence counted into a warnings list.
_ROSTER_INT_FIELDS = [
    ("player_id", "player_id", -1),
    ("position_order", "positionOrder", -1),
    ("minutes", "time", 0),
    ("goals", "goals", 0),
    ("own_goals", "own_goals", 0),
    ("shots", "shots", 0),
    ("key_passes", "key_passes", 0),
    ("assists", "assists", 0),
    ("yellow_card", "yellow_card", 0),
    ("red_card", "red_card", 0),
]
_ROSTER_FLOAT_FIELDS = [
    ("xG", "xG", 0.0),
    ("xA", "xA", 0.0),
]


def _cast_num(raw, caster, default, col, warnings):
    if raw is None or raw == "":
        return default
    try:
        return caster(raw)
    except (TypeError, ValueError):
        if warnings is not None:
            warnings.append("roster field {0!r}: could not cast {1!r}, using {2}".format(
                col, raw, default))
        return default


def parse_match_rosters(rosters_data, match_id, season, warnings=None):
    """
    Flatten getMatchData['rosters'] ({'h': {player_key: {...}}, 'a': {...}})
    into one row per player. All numeric source values arrive as strings;
    every cast is defensive -- a malformed value never crashes, the
    "if missing" default is substituted and the occurrence appended to
    `warnings`.
    """
    rows = []
    for side in ("h", "a"):
        block = rosters_data.get(side, {}) or {}
        for _key, p in block.items():
            row = {
                "match_id": int(match_id),
                "season": int(season),
                "player": p.get("player") if p.get("player") is not None else "",
                "team_side": side,
                "position": p.get("position"),
            }
            for col, src, default in _ROSTER_INT_FIELDS:
                row[col] = _cast_num(p.get(src), lambda v: int(float(v)), default, col, warnings)
            for col, src, default in _ROSTER_FLOAT_FIELDS:
                row[col] = _cast_num(p.get(src), float, default, col, warnings)
            row["is_starter"] = row["position_order"] < 12
            rows.append(row)

    cols = [
        "match_id", "season", "player_id", "player", "team_side", "position",
        "position_order", "minutes", "is_starter", "goals", "own_goals",
        "shots", "xG", "xA", "key_passes", "assists", "yellow_card", "red_card",
    ]
    df = pd.DataFrame(rows, columns=cols)
    if len(df) > 0:
        for c in ("match_id", "season", "player_id", "position_order", "minutes",
                  "goals", "own_goals", "shots", "key_passes", "assists",
                  "yellow_card", "red_card"):
            df[c] = df[c].astype("int64")
        df["xG"] = df["xG"].astype("float64")
        df["xA"] = df["xA"].astype("float64")
        df["is_starter"] = df["is_starter"].astype(bool)
    return df


# ---------------------------------------------------------------------------
# Best-effort team stats: PPDA, deep completions (§1.3)
# ---------------------------------------------------------------------------

_TEAM_STATS_COLUMNS = [
    "season", "team", "match_date", "h_a", "ppda", "deep", "xpts_understat",
]


def _empty_team_stats():
    return pd.DataFrame(columns=_TEAM_STATS_COLUMNS)


def _ppda_ratio(ppda_entry):
    """PPDA = att / def, guarding division by zero with NaN."""
    if not isinstance(ppda_entry, dict):
        return float("nan")
    try:
        att = float(ppda_entry.get("att", "nan"))
        def_ = float(ppda_entry.get("def", "nan"))
    except (TypeError, ValueError):
        return float("nan")
    if def_ == 0 or math.isnan(def_):
        return float("nan")
    return att / def_


def parse_league_teams(teams_data, season):
    """
    One row per (team, match) from getLeagueData's per-team block. Each
    team entry is expected to carry a `history` list, one entry per match
    with at least `ppda` ({'att','def'}), `deep`, `xpts`, `h_a`, `date`.

    Fallback (mandatory): if `teams_data` is falsy or no history entry
    carries `ppda`/`deep`, return an empty frame with the correct schema
    -- never raise. The caller sets team_stats_available: false in the
    export manifest and the site hides the PPDA / deep-completion panels.
    """
    if not teams_data:
        return _empty_team_stats()

    rows = []
    saw_ppda_or_deep = False
    entries = teams_data.values() if isinstance(teams_data, dict) else teams_data
    for team_entry in entries:
        if not isinstance(team_entry, dict):
            continue
        team_name = team_entry.get("title") or team_entry.get("team") or ""
        history = team_entry.get("history", []) or []
        for h in history:
            if not isinstance(h, dict):
                continue
            has_ppda = "ppda" in h
            has_deep = "deep" in h
            if has_ppda or has_deep:
                saw_ppda_or_deep = True
            try:
                deep_val = float(h.get("deep")) if h.get("deep") not in (None, "") else float("nan")
            except (TypeError, ValueError):
                deep_val = float("nan")
            try:
                xpts_val = float(h.get("xpts")) if h.get("xpts") not in (None, "") else float("nan")
            except (TypeError, ValueError):
                xpts_val = float("nan")
            rows.append({
                "season": int(season),
                "team": team_name,
                "match_date": h.get("date"),
                "h_a": h.get("h_a"),
                "ppda": _ppda_ratio(h.get("ppda")),
                "deep": deep_val,
                "xpts_understat": xpts_val,
            })

    if not rows or not saw_ppda_or_deep:
        return _empty_team_stats()
    return pd.DataFrame(rows, columns=_TEAM_STATS_COLUMNS)


def build_match_npxg_shots_rosters(match_ids, season, warnings=None):
    """
    Enriched variant of build_match_npxg_and_shots: for each match_id make
    ONE getMatchData request and derive BOTH the shots (§1.1 enriched
    columns) and the rosters (§1.2) from that single response. Returns
    (npxg_df, shots_df, rosters_df).
    """
    all_shots = []
    all_rosters = []
    npxg_rows = []
    for mid in match_ids:
        data = fetch_match_data(mid)
        if "shots" not in data:
            raise ValueError(
                "Understat getMatchData response for match {0} is missing the "
                "'shots' key -- response shape may have changed again: keys "
                "present were {1}".format(mid, list(data.keys()))
            )
        shots_df = parse_match_shots(data["shots"], mid, season)
        all_shots.append(shots_df)
        rosters_df = parse_match_rosters(data.get("rosters", {}), mid, season, warnings)
        all_rosters.append(rosters_df)
        if len(shots_df) > 0:
            home = shots_df[shots_df["home_away"] == "h"]
            away = shots_df[shots_df["home_away"] == "a"]
            npxg_rows.append({
                "match_id": mid,
                "home_npxG": home["npxG"].sum(),
                "away_npxG": away["npxG"].sum(),
                "home_shots": len(home),
                "away_shots": len(away),
            })
        else:
            npxg_rows.append({
                "match_id": mid, "home_npxG": 0.0, "away_npxG": 0.0,
                "home_shots": 0, "away_shots": 0,
            })
    shots_all_df = pd.concat(all_shots, ignore_index=True) if all_shots else pd.DataFrame()
    rosters_all_df = (
        pd.concat(all_rosters, ignore_index=True) if all_rosters else pd.DataFrame()
    )
    npxg_df = pd.DataFrame(
        npxg_rows,
        columns=["match_id", "home_npxG", "away_npxG", "home_shots", "away_shots"],
    )
    return npxg_df, shots_all_df, rosters_all_df


def build_match_npxg_and_shots(match_ids, season):
    """
    For each match_id, fetch shotsData, return (per_match_npxg_df,
    all_shots_df). per_match_npxg_df has one row per match with
    home_npxG/away_npxG/home_shots/away_shots derived by summing shots.
    """
    all_shots = []
    npxg_rows = []
    for mid in match_ids:
        shots_data = fetch_match_shots(mid)
        shots_df = parse_match_shots(shots_data, mid, season)
        all_shots.append(shots_df)
        if len(shots_df) > 0:
            home = shots_df[shots_df["home_away"] == "h"]
            away = shots_df[shots_df["home_away"] == "a"]
            npxg_rows.append({
                "match_id": mid,
                "home_npxG": home["npxG"].sum(),
                "away_npxG": away["npxG"].sum(),
                "home_shots": len(home),
                "away_shots": len(away),
            })
        else:
            npxg_rows.append({
                "match_id": mid, "home_npxG": 0.0, "away_npxG": 0.0,
                "home_shots": 0, "away_shots": 0,
            })
    shots_all_df = pd.concat(all_shots, ignore_index=True) if all_shots else pd.DataFrame()
    # pd.DataFrame([]) (an empty list of row-dicts, i.e. match_ids was
    # empty -- e.g. every match in this season was already scraped in a
    # prior incremental run) produces a DataFrame with NO COLUMNS AT ALL,
    # not an empty-but-correctly-shaped one. The caller (scrape_season)
    # always merges on "match_id", so a columnless npxg_df blows up that
    # merge with a confusing KeyError instead of a clear "nothing to add"
    # outcome. Pin the schema explicitly so it's always mergeable, even
    # when there were zero matches to fetch.
    npxg_df = pd.DataFrame(
        npxg_rows,
        columns=["match_id", "home_npxG", "away_npxG", "home_shots", "away_shots"],
    )
    return npxg_df, shots_all_df


def scrape_season(league, season, existing_match_ids=None):
    """
    Full scrape of one season: match list + shots for matches not already
    present (incremental mode support via `existing_match_ids`).

    Returns (matches_df, shots_df) with matches_df fully populated
    (home/away goals, xG, npxG, shots, forecast).
    """
    dates_data = fetch_league_season(league, season)
    matches_df = parse_league_matches(dates_data, season)
    if len(matches_df) == 0:
        return matches_df, pd.DataFrame()

    existing_match_ids = existing_match_ids or set()
    to_fetch = [mid for mid in matches_df["match_id"] if mid not in existing_match_ids]

    npxg_df, shots_df = build_match_npxg_and_shots(to_fetch, season)
    matches_df = matches_df.merge(npxg_df, on="match_id", how="left")
    return matches_df, shots_df


def scrape_season_enriched(league, season, existing_match_ids=None, warnings=None):
    """
    Full scrape of one season producing matches + enriched shots + rosters
    + best-effort team-stats, using ONE getMatchData request per match and
    ONE getLeagueData request for the season.

    Returns (matches_df, shots_df, rosters_df, team_stats_df).
    team_stats_df is empty (correct schema) when Understat does not expose
    the per-team PPDA/deep block for this season -- never raises for that.
    """
    if warnings is None:
        warnings = []
    league_data = fetch_league_data(league, season)
    if "dates" not in league_data:
        raise ValueError(
            "Understat getLeagueData response for {0}/{1} is missing the "
            "'dates' key -- response shape may have changed again: keys "
            "present were {2}".format(league, season, list(league_data.keys()))
        )
    matches_df = parse_league_matches(league_data["dates"], season)

    team_block = None
    for key in _TEAM_BLOCK_KEYS:
        if key in league_data and league_data[key]:
            team_block = league_data[key]
            break
    team_stats_df = parse_league_teams(team_block, season)
    if len(team_stats_df) == 0:
        warnings.append(
            "team_stats unavailable for season {0}: Understat getLeagueData "
            "carries no per-team PPDA/deep block".format(season)
        )

    if len(matches_df) == 0:
        return matches_df, pd.DataFrame(), pd.DataFrame(), team_stats_df

    existing_match_ids = existing_match_ids or set()
    to_fetch = [mid for mid in matches_df["match_id"] if mid not in existing_match_ids]

    npxg_df, shots_df, rosters_df = build_match_npxg_shots_rosters(
        to_fetch, season, warnings
    )
    matches_df = matches_df.merge(npxg_df, on="match_id", how="left")
    return matches_df, shots_df, rosters_df, team_stats_df
