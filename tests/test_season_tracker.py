"""
Season tracker aggregation (src/report.py).

Regression: once season_points.csv finally held data (after the
2026-08-31 scoring crash was cleared), the weekly email read
"Matchdays played: 9 / Points per matchday: 1.33" for a single completed
Bundesliga matchday worth 12 model points. season_points.csv is one row
per MATCH; the tracker must report per MATCHDAY (9 matches per round).
"""
import pandas as pd
import pytest

from src import report


def _points(rows, start="2026-08-28"):
    """rows: list of model_points ints, in kickoff order. Fills the other
    columns with plausible values; dates step by 1 day so sort is stable."""
    base = pd.Timestamp(start)
    return pd.DataFrame([
        {
            "match_id": 100 + i,
            "datetime": base + pd.Timedelta(days=i),
            "model_points": p,
            "always21_points": 2,
            "market_ev_points": 1,
            "exact_hit": 1 if p == 4 else 0,
            "gd_hit": 1 if p >= 2 else 0,
        }
        for i, p in enumerate(rows)
    ])


def test_nine_matches_collapse_to_one_matchday():
    df = _points([4, 2, 2, 0, 0, 2, 0, 2, 0])  # 12 pts, 1 exact
    md = report.matchday_points(df)

    assert list(md.index) == [1]
    assert md.loc[1, "model_points"] == 12
    assert md.loc[1, "exact_hit"] == 1


def test_summary_stats_are_per_matchday_not_per_match():
    df = _points([4, 2, 2, 0, 0, 2, 0, 2, 0])
    stats = report.season_summary_stats(df)

    assert stats["matchdays"] == 1
    assert stats["points_per_matchday"] == 12.0
    assert stats["exact_hits"] == 1
    assert stats["gd_hits"] == 5  # p>=2 at 5 of the 9 positions (incl. the 4)


def test_two_full_matchdays_average_correctly():
    # MD1 = 12 pts, MD2 = 9 pts -> 2 matchdays, mean 10.5
    df = _points([4, 2, 2, 0, 0, 2, 0, 2, 0] + [3, 3, 3, 0, 0, 0, 0, 0, 0])
    stats = report.season_summary_stats(df)

    assert stats["matchdays"] == 2
    assert stats["points_per_matchday"] == pytest.approx(10.5)


def test_in_progress_final_matchday_is_its_own_smaller_group():
    # 9 + 3 rows -> matchday 2 exists with just 3 matches
    df = _points([2] * 9 + [4, 2, 0])
    md = report.matchday_points(df)

    assert list(md.index) == [1, 2]
    assert md.loc[1, "model_points"] == 18
    assert md.loc[2, "model_points"] == 6
    # points_per_matchday divides by number of matchday groups, not rounds-completed
    assert report.season_summary_stats(df)["points_per_matchday"] == pytest.approx(12.0)


def test_rows_are_ordered_by_kickoff_before_grouping():
    df = _points([4, 2, 2, 0, 0, 2, 0, 2, 0])
    shuffled = df.iloc[[5, 0, 8, 2, 7, 1, 4, 3, 6]].reset_index(drop=True)
    assert report.matchday_points(shuffled).loc[1, "model_points"] == 12


def test_empty_input_yields_zero_stats_and_empty_frame():
    empty = pd.DataFrame(columns=["model_points", "always21_points", "market_ev_points"])
    assert report.matchday_points(empty).empty
    assert report.matchday_points(pd.DataFrame()).empty
    assert report.matchday_points(None).empty

    stats = report.season_summary_stats(empty)
    assert stats == {
        "matchdays": 0, "points_per_matchday": 0.0,
        "exact_hits": 0, "gd_hits": 0,
    }


def test_tracker_html_renders_and_mentions_matchday_axis():
    df = _points([2] * 18)
    html = report.season_tracker_html(df, div_id="season-tracker")
    assert "Matchday" in html
    assert "season-tracker" in html


def test_tracker_html_survives_empty_input():
    html = report.season_tracker_html(pd.DataFrame(columns=["model_points"]),
                                      div_id="season-tracker")
    assert "season-tracker" in html
