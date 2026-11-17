"""
Understat outage fallback (Nov 2026: understat.com served a "We will come
back soon" page on every URL for 2+ weeks, and the old "abort on a failed
scrape" rule stopped all tipping, scoring and site updates).

Guards:
  * refresh_current_season_data() records the outage and continues
    (degraded, loud) instead of raising -- and still refreshes D1.csv;
  * the old hard abort is still available via the config switch;
  * a good scrape flips the status back to ok;
  * source_status keeps `down_since` across repeated failures;
  * augment_with_fd_results() adds football-data-only results with the
    Understat fixture id, skips ones Understat already has, and warns
    (never invents an id) when no fixture matches;
  * export_web publishes the status for the site banner.
"""
from datetime import datetime, timezone

import pandas as pd
import pytest

import config
from src import predict, source_status


@pytest.fixture
def status_path(tmp_path, monkeypatch):
    p = str(tmp_path / "source_status.json")
    monkeypatch.setattr(source_status, "SOURCE_STATUS_PATH", p)
    return p


@pytest.fixture
def offline_understat(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("Understat request failed after 3 retries: "
                           "Expecting value: line 1 column 1 (char 0)")
    monkeypatch.setattr(predict.scrape_understat, "scrape_season_enriched", boom)
    monkeypatch.setattr(predict.storage, "understat_matches", lambda s: None)
    d1_calls = []
    monkeypatch.setattr(predict, "_refresh_d1",
                        lambda season, warnings: d1_calls.append(season))
    drift_calls = []
    monkeypatch.setattr(predict, "run_drift_check",
                        lambda warnings: drift_calls.append(1) or True)
    return d1_calls, drift_calls


# --------------------------------------------------------------------------
# refresh_current_season_data
# --------------------------------------------------------------------------

def test_outage_degrades_instead_of_aborting(status_path, offline_understat):
    d1_calls, drift_calls = offline_understat
    warnings = []
    out = predict.refresh_current_season_data(2026, warnings)

    assert out == {"understat_ok": False}
    assert any(w.startswith("UNDERSTAT_OUTAGE") for w in warnings)
    assert d1_calls == [2026], "odds/results must still refresh during the outage"
    assert drift_calls == [], "drift check needs Understat -- skip it while down"
    assert source_status.load(status_path)["understat"]["ok"] is False


def test_outage_hard_abort_still_available(status_path, offline_understat, monkeypatch):
    monkeypatch.setattr(config, "UNDERSTAT_OUTAGE_FALLBACK", False)
    with pytest.raises(RuntimeError, match="no silent fallback"):
        predict.refresh_current_season_data(2026, [])


def test_down_since_is_kept_across_failures_and_cleared_on_recovery(status_path):
    t1 = datetime(2026, 11, 2, 9, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 11, 9, 9, 0, tzinfo=timezone.utc)
    t3 = datetime(2026, 11, 20, 16, 30, tzinfo=timezone.utc)
    source_status.mark_down("understat", "err 1", now=t1)
    e = source_status.mark_down("understat", "err 2", now=t2)
    assert e["down_since"] == "2026-11-02T09:00:00Z"
    assert e["last_checked"] == "2026-11-09T09:00:00Z"
    assert e["last_error"] == "err 2"

    e = source_status.mark_ok("understat", now=t3)
    assert e["ok"] is True and e["down_since"] is None
    assert source_status.is_ok("understat")


def test_unknown_source_counts_as_ok(status_path):
    assert source_status.is_ok("understat")


# --------------------------------------------------------------------------
# augment_with_fd_results
# --------------------------------------------------------------------------

def _understat_matches():
    return pd.DataFrame([{
        "match_id": 1, "season": 2026, "league": "Bundesliga",
        "datetime": pd.Timestamp("2026-10-25 14:30"),
        "home_team": "Hoffenheim", "away_team": "Bayer Leverkusen",
        "home_goals": 3, "away_goals": 0, "home_xG": 3.19, "away_xG": 0.42,
    }])


def _fixtures():
    return pd.DataFrame([
        # already in the Understat store -> must not be duplicated
        {"match_id": 1, "season": 2026, "league": "Bundesliga",
         "datetime": pd.Timestamp("2026-10-25 14:30"),
         "home_team": "Hoffenheim", "away_team": "Bayer Leverkusen"},
        {"match_id": 2, "season": 2026, "league": "Bundesliga",
         "datetime": pd.Timestamp("2026-11-08 14:30"),
         "home_team": "FC Cologne", "away_team": "Bayer Leverkusen"},
        {"match_id": 3, "season": 2026, "league": "Bundesliga",
         "datetime": pd.Timestamp("2026-11-29 14:30"),
         "home_team": "Borussia M.Gladbach", "away_team": "RasenBallsport Leipzig"},
    ])


def _odds(rows):
    return pd.DataFrame([
        {"Date": pd.Timestamp(d), "HomeTeam": h, "AwayTeam": a,
         "FTHG": hg, "FTAG": ag}
        for d, h, a, hg, ag in rows
    ])


def test_augment_adds_missing_results_with_understat_ids(monkeypatch):
    odds = _odds([
        ("2026-10-25", "Hoffenheim", "Leverkusen", 3, 0),   # Understat has it
        ("2026-11-08", "FC Koln", "Leverkusen", 1, 2),      # missing -> add
        ("2026-11-29", "M'gladbach", "RB Leipzig", None, None),  # not played
    ])
    monkeypatch.setattr(predict.storage, "odds_d1", lambda s: odds)
    monkeypatch.setattr(predict.storage, "understat_fixtures", lambda s: _fixtures())

    warnings = []
    out = predict.augment_with_fd_results(_understat_matches(), 2026, warnings)

    assert list(out["match_id"]) == [1, 2]
    added = out[out["match_id"] == 2].iloc[0]
    assert (added["home_team"], added["away_team"]) == ("FC Cologne", "Bayer Leverkusen")
    assert (added["home_goals"], added["away_goals"]) == (1, 2)
    assert added["result_source"] == "football-data"
    assert pd.isna(added["home_xG"]), "never invent xG for fallback rows"
    assert out[out["match_id"] == 1].iloc[0]["result_source"] == "understat"
    assert warnings == []


def test_augment_handles_many_to_one_name_map(monkeypatch):
    """Understat now says "Freiburg", but the crosswalk also maps the old
    "SC Freiburg" -> "Freiburg"; a reverse FD->Understat lookup picked
    "SC Freiburg" and wrongly re-added matches Understat already had."""
    um = pd.DataFrame([{
        "match_id": 10, "season": 2026, "league": "Bundesliga",
        "datetime": pd.Timestamp("2026-10-25 16:30"),
        "home_team": "Freiburg", "away_team": "Bayern Munich",
        "home_goals": 1, "away_goals": 3,
    }])
    fx = pd.DataFrame([
        {"match_id": 10, "season": 2026, "league": "Bundesliga",
         "datetime": pd.Timestamp("2026-10-25 16:30"),
         "home_team": "Freiburg", "away_team": "Bayern Munich"},
        {"match_id": 11, "season": 2026, "league": "Bundesliga",
         "datetime": pd.Timestamp("2026-11-08 14:30"),
         "home_team": "Freiburg", "away_team": "Union Berlin"},
    ])
    odds = _odds([
        ("2026-10-25", "Freiburg", "Bayern Munich", 1, 3),
        ("2026-11-08", "Freiburg", "Union Berlin", 2, 0),
    ])
    monkeypatch.setattr(predict.storage, "odds_d1", lambda s: odds)
    monkeypatch.setattr(predict.storage, "understat_fixtures", lambda s: fx)

    warnings = []
    out = predict.augment_with_fd_results(um, 2026, warnings)
    assert list(out["match_id"]) == [10, 11]
    assert out.iloc[1]["home_team"] == "Freiburg"
    assert warnings == []


def test_augment_warns_instead_of_inventing_an_id(monkeypatch):
    odds = _odds([("2026-11-08", "Freiburg", "Union Berlin", 2, 0)])
    monkeypatch.setattr(predict.storage, "odds_d1", lambda s: odds)
    monkeypatch.setattr(predict.storage, "understat_fixtures", lambda s: _fixtures())

    warnings = []
    out = predict.augment_with_fd_results(_understat_matches(), 2026, warnings)

    assert list(out["match_id"]) == [1]
    assert len(warnings) == 1 and "Freiburg v Union Berlin" in warnings[0]


def test_augment_noop_without_odds(monkeypatch):
    monkeypatch.setattr(predict.storage, "odds_d1", lambda s: None)
    monkeypatch.setattr(predict.storage, "understat_fixtures", lambda s: _fixtures())
    out = predict.augment_with_fd_results(_understat_matches(), 2026, [])
    assert list(out["match_id"]) == [1]


# --------------------------------------------------------------------------
# export_web manifest
# --------------------------------------------------------------------------

def test_export_publishes_outage_status(status_path):
    from src import export_web

    source_status.mark_down("understat", "down",
                            now=datetime(2026, 11, 2, 9, 0, tzinfo=timezone.utc))

    class B:
        matches = _understat_matches()

    st = export_web._data_status(B())["understat"]
    assert st["ok"] is False
    assert st["down_since"] == "2026-11-02T09:00:00Z"
    assert st["last_data_date"] == "2026-10-25"
