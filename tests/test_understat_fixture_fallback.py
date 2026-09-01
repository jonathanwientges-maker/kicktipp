"""
Regression tests for predict.py's Understat fixture fallback.

Live failure it guards (2026/27 Matchday 2, Tuesday run): football-data.co.uk
dropped the Bundesliga block from fixtures.csv entirely -- zero D1 rows --
so predict.py found no upcoming fixtures and emailed an empty tip list
for a matchday that WAS being played that weekend. Understat's fixture
partition (written every run by refresh_current_season_data) already had
the full schedule; predict.py now falls back to it.

Also checks the three-way disambiguation of the "no fixtures" warning:
  A. fixtures.csv has no D1 rows at all + Understat empty -> data-source alarm
  B. fixtures.csv has D1 rows, none in window, Understat empty -> matchday break
  C. Understat fallback used -> loud "no market odds" note
"""
import numpy as np
import pandas as pd
import pytest

import config
from src import predict


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

_CSV_COLS = ["Div", "Date", "Time", "HomeTeam", "AwayTeam"]


def _csv_fixtures(rows):
    """rows: (home_fd, away_fd, 'YYYY-MM-DD', 'HH:MM' or None). Mimics the
    D1-filtered fixtures.csv frame load_fixtures() returns -- an empty
    `rows` still yields the full column set, exactly as
    `df[df.Div == 'D1']` does when football-data drops the D1 block."""
    return pd.DataFrame(
        [
            {"Div": "D1", "HomeTeam": h, "AwayTeam": a,
             "Date": pd.Timestamp(d), "Time": t}
            for h, a, d, t in rows
        ],
        columns=_CSV_COLS,
    )


def _understat_fixture_partition(rows):
    """rows: (home_understat, away_understat, naive-UTC 'YYYY-MM-DD HH:MM').
    Mimics storage.understat_fixtures(): tz-naive UTC `datetime`."""
    return pd.DataFrame([
        {
            "match_id": 30000 + i, "season": config.CURRENT_SEASON,
            "league": "Bundesliga", "datetime": pd.Timestamp(dt),
            "home_team": h, "away_team": a,
        }
        for i, (h, a, dt) in enumerate(rows)
    ])


@pytest.fixture
def stub_pipeline(monkeypatch):
    """Stub out the heavy blend so predict_fixtures() can run on fixture
    shape alone. _predict_one_fixture is exercised for real elsewhere;
    here we only care which fixtures reach it and what meta comes back."""
    seen = []

    def fake_predict_one(fx, known_fd_names, xg_enriched, dc_fit, tuned):
        seen.append((fx["HomeTeam"], fx["AwayTeam"], fx["kickoff_ts"]))
        return {"home": fx["HomeTeam"], "away": fx["AwayTeam"]}

    monkeypatch.setattr(predict, "_predict_one_fixture", fake_predict_one)
    return seen


# --------------------------------------------------------------------------
# understat_fixture_fallback: tz conversion, window, crosswalk
# --------------------------------------------------------------------------

def test_fallback_converts_utc_partition_to_german_local(monkeypatch):
    """Understat stores a 20:30 CEST kickoff as 18:30 (naive UTC). The
    fallback must return it as 20:30 local so it lines up with `now`
    computed in Europe/Berlin."""
    part = _understat_fixture_partition([
        ("Bayern Munich", "VfB Stuttgart", "2026-09-04 18:30"),
    ])
    monkeypatch.setattr(predict.storage, "understat_fixtures", lambda season: part)

    now = pd.Timestamp("2026-09-01 12:00:00")
    window_end = now + pd.Timedelta(days=8)
    out = predict.understat_fixture_fallback(now, window_end, {"Bayern Munich", "Stuttgart"}, [])

    assert list(out["kickoff_ts"]) == [pd.Timestamp("2026-09-04 20:30:00")]
    # Time string is the German-local kickoff, so the report shows 20:30
    # (not the date alone, and not the raw 18:30 UTC).
    assert list(out["Time"]) == ["20:30"]


def test_fallback_keeps_only_fixtures_inside_the_window(monkeypatch):
    part = _understat_fixture_partition([
        ("Freiburg", "Werder Bremen", "2026-08-25 12:00"),      # already played
        ("VfB Stuttgart", "FC Cologne", "2026-09-04 18:30"),    # in window
        ("Union Berlin", "Schalke 04", "2026-09-30 18:30"),     # far future
    ])
    monkeypatch.setattr(predict.storage, "understat_fixtures", lambda season: part)

    now = pd.Timestamp("2026-09-01 12:00:00")
    window_end = now + pd.Timedelta(days=8)
    known = {"Stuttgart", "FC Koln", "Freiburg", "Werder Bremen", "Union Berlin", "Schalke 04"}
    out = predict.understat_fixture_fallback(now, window_end, known, [])

    assert list(out["HomeTeam"]) == ["Stuttgart"]
    assert list(out["AwayTeam"]) == ["FC Koln"]


def test_fallback_maps_understat_names_to_football_data_names(monkeypatch):
    part = _understat_fixture_partition([
        ("Borussia M.Gladbach", "RasenBallsport Leipzig", "2026-09-04 18:30"),
    ])
    monkeypatch.setattr(predict.storage, "understat_fixtures", lambda season: part)

    now = pd.Timestamp("2026-09-01 12:00:00")
    out = predict.understat_fixture_fallback(now, now + pd.Timedelta(days=8), set(), [])

    assert list(out["HomeTeam"]) == ["M'gladbach"]
    assert list(out["AwayTeam"]) == ["RB Leipzig"]


def test_fallback_empty_when_partition_missing(monkeypatch):
    monkeypatch.setattr(predict.storage, "understat_fixtures", lambda season: None)
    now = pd.Timestamp("2026-09-01 12:00:00")
    out = predict.understat_fixture_fallback(now, now + pd.Timedelta(days=8), set(), [])
    assert len(out) == 0
    assert list(out.columns) == ["HomeTeam", "AwayTeam", "kickoff_ts", "Time"]


def test_fallback_unresolved_name_warns_and_returns_empty(monkeypatch):
    part = _understat_fixture_partition([
        ("Some Brand New Club", "Bayern Munich", "2026-09-04 18:30"),
    ])
    monkeypatch.setattr(predict.storage, "understat_fixtures", lambda season: part)

    warnings = []
    now = pd.Timestamp("2026-09-01 12:00:00")
    out = predict.understat_fixture_fallback(
        now, now + pd.Timedelta(days=8), {"Bayern Munich"}, warnings
    )
    assert len(out) == 0
    assert any("unresolved team name" in w.lower() for w in warnings)


# --------------------------------------------------------------------------
# predict_fixtures: source selection + meta
# --------------------------------------------------------------------------

def _run_predict_fixtures(monkeypatch, csv_df, understat_part):
    monkeypatch.setattr(predict.storage, "understat_fixtures", lambda season: understat_part)
    # A realistic slice of season history so known_fd_names covers the
    # teams the tests use (crosswalk.to_fd_name hard-fails on an unknown
    # identity-mapped name).
    matches = pd.DataFrame({
        "home_team": [
            "Bayern Munich", "Borussia Dortmund", "SC Freiburg", "Mainz 05",
            "Borussia M.Gladbach", "RasenBallsport Leipzig",
        ],
        "away_team": [
            "Borussia Dortmund", "Bayern Munich", "Mainz 05", "SC Freiburg",
            "RasenBallsport Leipzig", "Borussia M.Gladbach",
        ],
    })
    warnings = []
    contexts, meta = predict.predict_fixtures(
        csv_df, matches, xg_lookup={}, xg_enriched=None, dc_fit=None,
        tuned={"weights": [0.9, 0.0, 0.1]}, warnings=warnings,
    )
    return contexts, meta, warnings


def test_uses_csv_when_it_has_upcoming_fixtures(monkeypatch, stub_pipeline):
    """Happy path: fixtures.csv has a fixture in the window -> Understat
    fallback is never consulted even though the partition is non-empty."""
    soon = (pd.Timestamp.now(tz="Europe/Berlin").tz_localize(None) + pd.Timedelta(days=2))
    csv_df = _csv_fixtures([
        ("Bayern Munich", "Dortmund", soon.strftime("%Y-%m-%d"), "18:30"),
    ])
    understat_part = _understat_fixture_partition([
        ("SC Freiburg", "Mainz 05", (soon + pd.Timedelta(days=1)).strftime("%Y-%m-%d 15:30")),
    ])
    contexts, meta, warnings = _run_predict_fixtures(monkeypatch, csv_df, understat_part)

    assert meta["source"] == "fixtures.csv"
    assert meta["used_understat_fallback"] is False
    assert [ (h, a) for (h, a, _) in stub_pipeline ] == [("Bayern Munich", "Dortmund")]
    assert not any("fallback" in w.lower() for w in warnings)


def test_falls_back_to_understat_when_csv_window_empty(monkeypatch, stub_pipeline):
    now_local = pd.Timestamp.now(tz="Europe/Berlin").tz_localize(None)
    soon_utc = (now_local + pd.Timedelta(days=2)).strftime("%Y-%m-%d 16:30")
    csv_df = _csv_fixtures([])                       # no D1 rows at all
    understat_part = _understat_fixture_partition([
        ("Bayern Munich", "Borussia Dortmund", soon_utc),
    ])
    contexts, meta, warnings = _run_predict_fixtures(monkeypatch, csv_df, understat_part)

    assert meta["used_understat_fallback"] is True
    assert meta["source"] == "understat"
    assert len(contexts) == 1
    assert [ (h, a) for (h, a, _) in stub_pipeline ] == [("Bayern Munich", "Dortmund")]


def test_columnless_empty_csv_frame_does_not_crash(monkeypatch, stub_pipeline):
    """Defensive: a truly columnless empty frame (not the
    columns-retained empty that df[df.Div=='D1'] gives) must fall through
    to the Understat path, not raise KeyError on 'Date'."""
    now_local = pd.Timestamp.now(tz="Europe/Berlin").tz_localize(None)
    soon_utc = (now_local + pd.Timedelta(days=2)).strftime("%Y-%m-%d 16:30")
    understat_part = _understat_fixture_partition([
        ("Bayern Munich", "Borussia Dortmund", soon_utc),
    ])
    contexts, meta, warnings = _run_predict_fixtures(
        monkeypatch, pd.DataFrame(), understat_part
    )
    assert meta["d1_rows_in_csv"] == 0
    assert meta["used_understat_fallback"] is True
    assert len(contexts) == 1


def test_meta_counts_d1_rows_in_csv(monkeypatch, stub_pipeline):
    """d1_rows_in_csv reflects fixtures.csv D1 rows regardless of window,
    so main() can tell 'no D1 block' from 'D1 block, matchday break'."""
    old = "2026-01-01"
    csv_df = _csv_fixtures([
        ("Bayern Munich", "Dortmund", old, "18:30"),
        ("Freiburg", "Mainz", old, "15:30"),
    ])
    contexts, meta, warnings = _run_predict_fixtures(monkeypatch, csv_df, None)

    assert meta["d1_rows_in_csv"] == 2
    assert meta["csv_upcoming"] == 0
    assert meta["used_understat_fallback"] is False


# --------------------------------------------------------------------------
# fixture_source_warning: the three variants + the silent happy path
# --------------------------------------------------------------------------

def test_warning_silent_when_csv_supplied_fixtures():
    w = predict.fixture_source_warning(
        {"used_understat_fallback": False, "d1_rows_in_csv": 9}, n_contexts=6
    )
    assert w == ""


def test_warning_datasource_alarm_when_no_d1_block_and_no_fallback():
    w = predict.fixture_source_warning(
        {"used_understat_fallback": False, "d1_rows_in_csv": 0}, n_contexts=0
    )
    assert "NO Bundesliga (D1) rows at all" in w
    assert "data-source" in w
    assert "matchday break" in w  # explicitly contrasts the two


def test_warning_matchday_break_when_d1_block_present_but_window_empty():
    w = predict.fixture_source_warning(
        {"used_understat_fallback": False, "d1_rows_in_csv": 9}, n_contexts=0
    )
    assert "matchday break" in w
    assert "9 D1 row(s)" in w
    assert "data-source" not in w


def test_warning_fallback_used_flags_missing_market_odds():
    w = predict.fixture_source_warning(
        {"used_understat_fallback": True, "d1_rows_in_csv": 0}, n_contexts=3
    )
    assert "Understat" in w
    assert "NO market odds" in w
    assert "3 fixture(s)" in w
