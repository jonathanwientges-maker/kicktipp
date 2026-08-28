"""
Tests for src/bootstrap_gap.py, focused on a real data-corruption bug
found in production: a re-run of scrape_understat_gap_seasons() against
a repo that already had a COMPLETE prior scrape committed silently wiped
every match's home_npxG/away_npxG/home_shots/away_shots to NaN.

Root cause: scrape_understat.scrape_season() only fetches those 4
columns for match_ids NOT already in existing_match_ids (to avoid
redundant network calls) -- for already-existing match_ids they come
back NaN from the merge, which is correct AS AN INTERMEDIATE RESULT
(the caller is expected to preserve the old values for those matches).
scrape_understat_gap_seasons() already did this correctly for shots
(pd.concat with prior_shots) but NOT for matches_df's npxG/shots
columns -- it just overwrote the file with the freshly-parsed-but-NaN
matches_df. This was caught via a real GitHub Actions run: a
checkpoint-commit landed mid-job, so a later step's "scrape the gap
seasons" call saw a fully-populated `existing` and treated all 612
matches (2024+2025) as already-scraped, corrupting their npxG to NaN
(discovered when the promoted-team-prior regression, which needs real
npxG, started returning NaN seeds for every promoted team).
"""
import numpy as np
import pandas as pd
import pytest

from src import bootstrap_gap


def _matches_df(match_ids, with_npxg=True):
    rows = []
    for mid in match_ids:
        row = {
            "match_id": mid, "season": 2024, "league": "Bundesliga",
            "datetime": pd.Timestamp("2024-08-23") + pd.Timedelta(days=mid),
            "home_team": "Team A", "away_team": "Team B",
            "home_goals": 2, "away_goals": 1,
            "home_xG": 1.5, "away_xG": 1.1,
            "forecast_win": 0.5, "forecast_draw": 0.3, "forecast_loss": 0.2,
        }
        if with_npxg:
            row["home_npxG"] = 1.3
            row["away_npxG"] = 0.9
            row["home_shots"] = 12
            row["away_shots"] = 8
        else:
            row["home_npxG"] = np.nan
            row["away_npxG"] = np.nan
            row["home_shots"] = np.nan
            row["away_shots"] = np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def test_rerun_against_fully_existing_data_preserves_npxg(monkeypatch):
    """Regression test: re-running the gap scrape against a season where
    every match already exists (freshly re-fetched matches_df has NaN
    npxG for all of them, since nothing new was fetched) must NOT wipe
    the previously-good npxG/shots values -- it must preserve them."""
    good_existing = _matches_df([1, 2, 3], with_npxg=True)
    # Simulate scrape_understat.scrape_season()'s real behavior: the
    # freshly re-parsed match list has fresh goals/xG but NaN npxG for
    # every match, because to_fetch was empty (all match_ids already
    # "existed").
    freshly_fetched_with_nan_npxg = _matches_df([1, 2, 3], with_npxg=False)

    written = {}

    def fake_understat_matches(season):
        return good_existing

    def fake_understat_shots(season):
        return pd.DataFrame({"match_id": [1, 2, 3], "shot_id": [10, 11, 12]})

    def fake_scrape_season(league, season, existing_match_ids=None):
        return freshly_fetched_with_nan_npxg.copy(), pd.DataFrame(columns=["match_id", "shot_id"])

    def fake_write_matches(df, season):
        written["matches"] = df

    def fake_write_shots(df, season):
        written["shots"] = df

    monkeypatch.setattr(bootstrap_gap.storage, "understat_matches", fake_understat_matches)
    monkeypatch.setattr(bootstrap_gap.storage, "understat_shots", fake_understat_shots)
    monkeypatch.setattr(bootstrap_gap.scrape_understat, "scrape_season", fake_scrape_season)
    monkeypatch.setattr(bootstrap_gap.storage, "write_understat_matches", fake_write_matches)
    monkeypatch.setattr(bootstrap_gap.storage, "write_understat_shots", fake_write_shots)
    monkeypatch.setattr(bootstrap_gap.config, "GAP_SEASONS", [2024])

    bootstrap_gap.scrape_understat_gap_seasons()

    result = written["matches"]
    assert not result[["home_npxG", "away_npxG", "home_shots", "away_shots"]].isna().any().any(), (
        "npxG/shots were wiped to NaN on a re-run against already-existing data -- "
        "the real bug this test guards against."
    )
    # And the preserved values must be the GOOD ones, not zeros or garbage.
    assert (result["home_npxG"] == 1.3).all()
    assert (result["away_npxG"] == 0.9).all()


def test_rerun_with_genuinely_new_matches_still_gets_npxg_for_new_ones(monkeypatch):
    """A mix of already-existing (preserved) and genuinely-new (freshly
    fetched, real npxG) matches must both end up correct."""
    good_existing = _matches_df([1, 2], with_npxg=True)  # only 1,2 existed before

    def fresh_fetch_result():
        # match 1,2 come back NaN (not re-fetched); match 3 is new and
        # genuinely has real npxG from this run's fetch.
        df = _matches_df([1, 2, 3], with_npxg=False)
        df.loc[df["match_id"] == 3, ["home_npxG", "away_npxG", "home_shots", "away_shots"]] = [2.5, 1.8, 15, 9]
        return df

    written = {}

    monkeypatch.setattr(bootstrap_gap.storage, "understat_matches", lambda season: good_existing)
    monkeypatch.setattr(bootstrap_gap.storage, "understat_shots",
                         lambda season: pd.DataFrame({"match_id": [1, 2], "shot_id": [10, 11]}))
    monkeypatch.setattr(bootstrap_gap.scrape_understat, "scrape_season",
                         lambda league, season, existing_match_ids=None: (
                             fresh_fetch_result(), pd.DataFrame(columns=["match_id", "shot_id"])
                         ))
    monkeypatch.setattr(bootstrap_gap.storage, "write_understat_matches",
                         lambda df, season: written.__setitem__("matches", df))
    monkeypatch.setattr(bootstrap_gap.storage, "write_understat_shots",
                         lambda df, season: written.__setitem__("shots", df))
    monkeypatch.setattr(bootstrap_gap.config, "GAP_SEASONS", [2024])

    bootstrap_gap.scrape_understat_gap_seasons()

    result = written["matches"].set_index("match_id")
    assert result.loc[1, "home_npxG"] == 1.3  # preserved from existing
    assert result.loc[2, "home_npxG"] == 1.3
    assert result.loc[3, "home_npxG"] == 2.5  # genuinely fetched fresh
