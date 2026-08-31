"""
Tests for src/scrape_understat.py's JSON-API fetch layer (rewritten
after Understat restructured their site to render match/league pages
client-side -- see the module docstring and the code comment history for
the discovery process: the old approach regex-scraped a `datesData`
variable embedded in server-rendered HTML, which stopped existing
entirely; the new approach calls Understat's own AJAX JSON endpoints
directly, verified against the live site).

These tests mock requests.get so they don't depend on network access or
Understat's actual current data; the live-data shape itself was
validated manually against https://understat.com/getLeagueData/... and
https://understat.com/getMatchData/... before this rewrite landed.
"""
from unittest.mock import MagicMock, patch

import pytest

from src import scrape_understat as su


def _mock_response(json_data=None, status=200, raise_for_status_error=None):
    resp = MagicMock()
    resp.status_code = status
    if raise_for_status_error:
        resp.raise_for_status.side_effect = raise_for_status_error
    else:
        resp.raise_for_status.return_value = None
    resp.json.return_value = json_data
    return resp


@patch("src.scrape_understat.requests.get")
def test_fetch_league_season_calls_correct_endpoint_with_ajax_headers(mock_get):
    mock_get.return_value = _mock_response({"dates": [{"id": "1", "isResult": True}]})
    result = su.fetch_league_season("Bundesliga", 2024)

    assert result == [{"id": "1", "isResult": True}]
    called_url = mock_get.call_args[0][0]
    called_headers = mock_get.call_args[1]["headers"]
    assert called_url == "https://understat.com/getLeagueData/Bundesliga/2024"
    assert called_headers["X-Requested-With"] == "XMLHttpRequest"
    assert called_headers["Referer"] == "https://understat.com/league/Bundesliga/2024"


@patch("src.scrape_understat.requests.get")
def test_fetch_match_shots_calls_correct_endpoint_with_ajax_headers(mock_get):
    mock_get.return_value = _mock_response({"shots": {"h": [], "a": []}})
    result = su.fetch_match_shots(27742)

    assert result == {"h": [], "a": []}
    called_url = mock_get.call_args[0][0]
    called_headers = mock_get.call_args[1]["headers"]
    assert called_url == "https://understat.com/getMatchData/27742"
    assert called_headers["Referer"] == "https://understat.com/match/27742"


@patch("src.scrape_understat.requests.get")
def test_fetch_league_season_raises_loudly_on_unexpected_shape(mock_get):
    """If Understat's response shape changes again (e.g. 'dates' renamed
    or removed), this must raise -- not silently return something wrong
    -- per the project's no-silent-fallback hard rule."""
    mock_get.return_value = _mock_response({"teams": {}, "players": []})  # no 'dates' key
    with pytest.raises(ValueError, match="missing the 'dates' key"):
        su.fetch_league_season("Bundesliga", 2024)


@patch("src.scrape_understat.requests.get")
def test_fetch_match_shots_raises_loudly_on_unexpected_shape(mock_get):
    mock_get.return_value = _mock_response({"rosters": {}})  # no 'shots' key
    with pytest.raises(ValueError, match="missing the 'shots' key"):
        su.fetch_match_shots(27742)


@patch("src.scrape_understat.time.sleep", lambda *a, **k: None)  # skip real backoff waits
@patch("src.scrape_understat.requests.get")
def test_fetch_retries_and_raises_after_persistent_failure(mock_get):
    mock_get.return_value = _mock_response(raise_for_status_error=RuntimeError("boom"))
    with pytest.raises(RuntimeError, match="failed after 3 retries"):
        su.fetch_league_season("Bundesliga", 2024)
    assert mock_get.call_count == 3


def test_parse_league_matches_handles_new_api_string_numerics():
    """The new API returns numeric fields as JSON strings (except
    isResult, a real bool) -- parse_league_matches must coerce them
    correctly, exactly as it always has for the old embedded-JSON shape."""
    dates_data = [
        {
            "id": "27742", "isResult": True,
            "h": {"id": "130", "title": "Borussia M.Gladbach"},
            "a": {"id": "119", "title": "Bayer Leverkusen"},
            "goals": {"h": "2", "a": "3"},
            "xG": {"h": "1.51665", "a": "3.23588"},
            "datetime": "2024-08-23 18:30:00",
            "forecast": {"w": "0.074", "d": "0.1487", "l": "0.7773"},
        },
        {"id": "27743", "isResult": False},  # future fixture, skipped
    ]
    df = su.parse_league_matches(dates_data, 2024)
    assert len(df) == 1
    row = df.iloc[0]
    assert row["match_id"] == 27742
    assert row["home_goals"] == 2
    assert row["away_goals"] == 3
    assert row["home_xG"] == pytest.approx(1.51665)
    assert row["forecast_win"] == pytest.approx(0.074)


def test_parse_upcoming_fixtures_only_unplayed_and_no_forward_numbers():
    """parse_upcoming_fixtures returns exactly the isResult == False rows,
    carrying teams + kickoff only -- never goals/xG/forecast (those are
    null for unplayed games and must not reach the website)."""
    dates_data = [
        {
            "id": "1", "isResult": True,
            "h": {"id": "1", "title": "A"}, "a": {"id": "2", "title": "B"},
            "goals": {"h": "2", "a": "1"}, "xG": {"h": "1.9", "a": "0.7"},
            "datetime": "2026-08-28 18:30:00",
        },
        {
            "id": "2", "isResult": False,
            "h": {"id": "3", "title": "C"}, "a": {"id": "4", "title": "D"},
            "goals": {"h": None, "a": None}, "xG": {"h": None, "a": None},
            "datetime": "2026-09-04 20:30:00",
        },
    ]
    fx = su.parse_upcoming_fixtures(dates_data, 2026)
    assert list(fx["match_id"]) == [2]
    assert fx.iloc[0]["home_team"] == "C"
    assert fx.iloc[0]["away_team"] == "D"
    assert set(fx.columns) == {
        "match_id", "season", "league", "datetime", "home_team", "away_team",
    }
    forbidden = {"goals", "xg", "xG", "forecast", "home_goals", "home_xG"}
    assert forbidden.isdisjoint(set(fx.columns))


def test_parse_upcoming_fixtures_empty_when_season_complete():
    dates_data = [
        {"id": "1", "isResult": True, "h": {"title": "A"}, "a": {"title": "B"},
         "goals": {"h": "0", "a": "0"}, "xG": {"h": "1", "a": "1"},
         "datetime": "2026-08-28 18:30:00"},
    ]
    fx = su.parse_upcoming_fixtures(dates_data, 2026)
    assert len(fx) == 0
    assert list(fx.columns) == [
        "match_id", "season", "league", "datetime", "home_team", "away_team",
    ]


def test_parse_match_shots_handles_new_api_string_numerics():
    shots_data = {
        "h": [{
            "id": "585721", "minute": "3", "result": "MissedShots",
            "X": "0.757", "Y": "0.421", "xG": "0.02001", "player": "Julian Weigl",
            "situation": "OpenPlay", "shotType": "RightFoot",
        }],
        "a": [],
    }
    df = su.parse_match_shots(shots_data, 27742, 2024)
    assert len(df) == 1
    row = df.iloc[0]
    assert row["shot_id"] == 585721
    assert row["minute"] == 3
    assert row["xG"] == pytest.approx(0.02001)
    assert row["home_away"] == "h"
    assert bool(row["is_penalty"]) is False  # numpy bool_, not Python bool -- compare by value
    assert row["npxG"] == pytest.approx(0.02001)


def test_build_match_npxg_and_shots_with_empty_match_ids_keeps_match_id_column():
    """Regression test: found via a real GitHub Actions bootstrap failure
    (KeyError: 'match_id' at the merge in scrape_season). When match_ids
    is empty -- e.g. every match in a season was already scraped in a
    prior incremental run -- pd.DataFrame([]) (an empty list of row-dicts)
    produces a DataFrame with NO COLUMNS AT ALL, not an empty-but-
    correctly-shaped one. scrape_season always merges the result on
    "match_id", so a columnless npxg_df crashes that merge with a
    confusing KeyError instead of a clear no-op. build_match_npxg_and_shots
    must always return a DataFrame with the match_id column present, even
    when there are zero matches to fetch (no network calls made)."""
    npxg_df, shots_df = su.build_match_npxg_and_shots([], 2024)
    assert list(npxg_df.columns) == [
        "match_id", "home_npxG", "away_npxG", "home_shots", "away_shots",
    ]
    assert len(npxg_df) == 0
    assert len(shots_df) == 0


def test_scrape_season_merge_survives_empty_to_fetch():
    """End-to-end: scrape_season's matches_df.merge(npxg_df, on='match_id')
    must not raise even when every match_id in matches_df is already in
    existing_match_ids (to_fetch is empty)."""
    import pandas as pd
    from unittest.mock import patch

    fake_dates = [
        {
            "id": "1", "isResult": True,
            "h": {"id": "1", "title": "Home Team"}, "a": {"id": "2", "title": "Away Team"},
            "goals": {"h": "1", "a": "0"}, "xG": {"h": "1.1", "a": "0.5"},
            "datetime": "2024-08-23 18:30:00", "forecast": {"w": "0.5", "d": "0.3", "l": "0.2"},
        },
    ]
    with patch("src.scrape_understat.fetch_league_season", return_value=fake_dates):
        matches_df, shots_df = su.scrape_season("Bundesliga", 2024, existing_match_ids={1})
    assert len(matches_df) == 1
    assert "home_npxG" in matches_df.columns
    assert pd.isna(matches_df.iloc[0]["home_npxG"])  # not fetched, correctly NaN not a crash
