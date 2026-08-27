"""
Understat scraper: league-season match list (xG/npxG/forecast) and
per-match shot data.

Understat embeds its data as JSON inside <script> tags on each page:
  - league page:  https://understat.com/league/Bundesliga/{year}
        -> `datesData` JSON: one row per match (id, datetime, teams,
           goals, xG, forecast).
  - match page:   https://understat.com/match/{id}
        -> `shotsData` JSON: {'h': [...], 'a': [...]} per-shot detail
           (minute, X, Y, xG, result, situation, shotType, player,
           lastAction).

Rate limiting: one request every config.UNDERSTAT_DELAY_S seconds minimum.
3 retries with exponential backoff; on persistent failure the run aborts
(raises -> non-zero exit at the caller).
"""
import json
import re
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


def _fetch_html(url):
    last_err = None
    for attempt in range(_RETRIES):
        _throttle()
        try:
            resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
            resp.raise_for_status()
            return resp.text
        except Exception as exc:  # noqa: BLE001 - deliberate broad retry
            last_err = exc
            if attempt < _RETRIES - 1:
                time.sleep(_BACKOFF_BASE ** attempt)
    raise RuntimeError(
        "Understat request to {0} failed after {1} retries: {2}".format(
            url, _RETRIES, last_err
        )
    )


def _extract_json_var(html, var_name):
    """
    Understat encodes its embedded JSON as a JS-escaped string literal:
        var datesData = JSON.parse('...\\x7B...');
    Extract the quoted literal for `var_name`, unescape the \\xHH hex
    escapes, and json.loads the result.
    """
    pattern = r"var\s+{0}\s*=\s*JSON\.parse\('(.*?)'\)".format(re.escape(var_name))
    m = re.search(pattern, html, re.DOTALL)
    if not m:
        raise ValueError(
            "Could not find embedded variable '{0}' in Understat page.".format(var_name)
        )
    raw = m.group(1)
    decoded = raw.encode("utf-8").decode("unicode_escape").encode("latin1").decode("utf-8")
    return json.loads(decoded)


def fetch_league_season(league, year):
    """Fetch the datesData match list for a league-season page."""
    url = "{0}/league/{1}/{2}".format(config.UNDERSTAT_BASE, league, year)
    html = _fetch_html(url)
    return _extract_json_var(html, "datesData")


def fetch_match_shots(match_id):
    """Fetch shotsData for a single match page."""
    url = "{0}/match/{1}".format(config.UNDERSTAT_BASE, match_id)
    html = _fetch_html(url)
    return _extract_json_var(html, "shotsData")


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
