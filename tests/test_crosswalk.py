"""
Team-name harmonisation (src/crosswalk.py).

Regression focus: the 2026-08-31 results_refresh crash. football-data's
current-season D1.csv was not yet published (HTTP 300), so the odds frame
had no 2026 rows, so `known_fd_names` (built only from odds team columns)
did not contain "Elversberg" -- a promoted club whose Understat and
football-data spellings are identical. to_fd_name() then hard-failed on
it, and results scoring for a completed matchday never ran.

Fix: crosswalk carries IDENTITY_FD_NAMES, its own odds-independent roster
of identical-spelling clubs; an identity match against that set is always
valid, `known_fd_names` only ever widens what is accepted.
"""
import pandas as pd
import pytest

from src import crosswalk


# --------------------------------------------------------------------------
# to_fd_name
# --------------------------------------------------------------------------

def test_explicit_rename_is_applied():
    assert crosswalk.to_fd_name("Borussia M.Gladbach") == "M'gladbach"
    assert crosswalk.to_fd_name("RasenBallsport Leipzig") == "RB Leipzig"


def test_identity_roster_resolves_without_any_known_fd_names():
    """The core regression: a promoted identical-spelling club resolves
    with no odds file present (known_fd_names=None)."""
    assert crosswalk.to_fd_name("Elversberg") == "Elversberg"
    assert crosswalk.to_fd_name("Union Berlin", known_fd_names=None) == "Union Berlin"


def test_identity_roster_resolves_even_when_known_fd_names_omits_it():
    """known_fd_names widens, never narrows: a name in IDENTITY_FD_NAMES
    but absent from a passed known set still resolves (this is exactly the
    Monday shape -- odds present but for other seasons only)."""
    other_seasons_only = {"Dortmund", "Bayern Munich", "Hannover"}
    assert crosswalk.to_fd_name("Elversberg", known_fd_names=other_seasons_only) == "Elversberg"


def test_unknown_name_still_hard_fails_when_validated():
    with pytest.raises(crosswalk.UnresolvedTeamNameError):
        crosswalk.to_fd_name("Wattenscheid 09", known_fd_names={"Dortmund"})


def test_unknown_name_passes_through_when_not_validated():
    """known_fd_names=None keeps the lenient identity-assumption path for
    callers that do not need strict validation."""
    assert crosswalk.to_fd_name("Some New Club") == "Some New Club"


def test_all_known_fd_names_is_union_of_renames_and_identity_roster():
    known = crosswalk._all_known_fd_names()
    assert "M'gladbach" in known           # rename value
    assert "Elversberg" in known           # identity roster
    assert set(crosswalk.UNDERSTAT_TO_FD.values()) <= known
    assert set(crosswalk.IDENTITY_FD_NAMES) <= known


def test_identity_roster_and_rename_keys_do_not_overlap():
    """A club is either a rename (Understat != football-data) or an
    identity (equal) -- never both, or to_fd_name() is ambiguous."""
    assert not (set(crosswalk.UNDERSTAT_TO_FD) & set(crosswalk.IDENTITY_FD_NAMES))


# --------------------------------------------------------------------------
# backtest._join_odds_to_matches: no crash when the current-season odds
# file is missing
# --------------------------------------------------------------------------

def _matches(rows):
    """rows: (season, 'YYYY-MM-DD', home_understat, away_understat)."""
    return pd.DataFrame([
        {
            "match_id": 1000 + i, "season": s,
            "datetime": pd.Timestamp(d),
            "home_team": h, "away_team": a,
            "home_goals": 1, "away_goals": 0,
        }
        for i, (s, d, h, a) in enumerate(rows)
    ])


def _odds(rows):
    """rows: (home_fd, away_fd, 'YYYY-MM-DD'). Minimal columns
    _join_odds_to_matches touches."""
    return pd.DataFrame([
        {"HomeTeam": h, "AwayTeam": a, "Date": pd.Timestamp(d),
         "AvgH": 2.0, "AvgD": 3.3, "AvgA": 3.5}
        for h, a, d in rows
    ])


def test_join_does_not_crash_when_promoted_club_absent_from_odds():
    """The Monday scenario reduced: a 2026 fixture featuring a promoted
    club, and an odds frame with only older seasons (current D1.csv
    failed to download). Must degrade to 0 matched rows, not raise."""
    from src.backtest import _join_odds_to_matches

    matches = _matches([
        (2026, "2026-08-29", "Elversberg", "Bayer Leverkusen"),
        (2024, "2024-05-01", "Borussia Dortmund", "Mainz 05"),
    ])
    odds_older_only = _odds([("Dortmund", "Mainz", "2024-05-01")])

    result = _join_odds_to_matches(matches, odds_older_only)
    # 2024 match joins; 2026 match simply has no odds -- no exception.
    assert 1001 in result
    assert 1000 not in result
