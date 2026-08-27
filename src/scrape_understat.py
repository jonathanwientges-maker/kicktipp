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


def fetch_match_shots(match_id):
    """Fetch the shots dict ({'h': [...], 'a': [...]}) for a single match."""
    referer = "{0}/match/{1}".format(config.UNDERSTAT_BASE, match_id)
    url = "{0}/getMatchData/{1}".format(config.UNDERSTAT_BASE, match_id)
    data = _fetch_json(url, referer)
    if "shots" not in data:
        raise ValueError(
            "Understat getMatchData response for match {0} is missing the "
            "'shots' key -- response shape may have changed again: keys "
            "present were {1}".format(match_id, list(data.keys()))
        )
    return data["shots"]


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
            rows.append({
                "shot_id": int(sh["id"]),
                "match_id": match_id,
                "season": season,
                "league": config.LEAGUE,
                "player": sh.get("player"),
                "minute": int(sh.get("minute", 0)),
                "result": sh.get("result"),
                "xG": float(sh.get("xG", 0.0)),
                "X": float(sh.get("X", 0.0)),
                "Y": float(sh.get("Y", 0.0)),
                "home_away": side,
                "situation": situation,
                "shotType": sh.get("shotType"),
                "is_penalty": situation == "Penalty",
            })
    df = pd.DataFrame(rows)
    if len(df) > 0:
        df["npxG"] = df["xG"].where(~df["is_penalty"], 0.0)
    return df


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
    npxg_df = pd.DataFrame(npxg_rows)
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
