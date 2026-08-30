"""
Tests for src/web_metrics.py (BUILD BLUEPRINT §9, tests 1-3, 6-8).
New file -- does not modify any existing test.
"""
import numpy as np
import pandas as pd
import pytest

from src import web_metrics as wm


# ---------------------------------------------------------------------------
# 9.1 shot_goal_distribution
# ---------------------------------------------------------------------------
def test_shot_goal_distribution_sums_to_one():
    d = wm.shot_goal_distribution([0.1, 0.2, 0.3, 0.4, 0.5])
    assert d.sum() == pytest.approx(1.0)
    assert len(d) == 11


def test_shot_goal_distribution_single_half_chance():
    d = wm.shot_goal_distribution([0.5])
    assert d[0] == pytest.approx(0.5)
    assert d[1] == pytest.approx(0.5)
    assert d[2:].sum() == pytest.approx(0.0)


def test_shot_goal_distribution_three_certain_shots_put_mass_on_three():
    d = wm.shot_goal_distribution([1.0, 1.0, 1.0])
    assert int(np.argmax(d)) == 3
    assert d[3] == pytest.approx(1.0, abs=1e-2)  # 0.999 clip -> ~0.997


# ---------------------------------------------------------------------------
# 9.2 match_xpoints
# ---------------------------------------------------------------------------
def test_match_xpoints_dominant_vs_nothing():
    home = [0.9, 0.8, 0.8, 0.7, 0.6, 0.6]
    away = [0.01]
    xph, xpa = wm.match_xpoints(home, away)
    assert xph == pytest.approx(3.0, abs=0.05)
    assert xpa == pytest.approx(0.0, abs=0.05)


def test_match_xpoints_identical_inputs_equal_and_sub_three():
    xph, xpa = wm.match_xpoints([0.3, 0.3, 0.2], [0.3, 0.3, 0.2])
    assert xph == pytest.approx(xpa)
    assert xph + xpa < 3.0


# ---------------------------------------------------------------------------
# 9.3 reconstruct_shot_context
# ---------------------------------------------------------------------------
def _shot(shot_id, minute, side, result, npxg):
    return {
        "shot_id": shot_id, "minute": minute, "home_away": side,
        "result": result, "xG": npxg, "npxG": npxg,
    }


def test_reconstruct_shot_context_running_score_and_state_with_own_goal():
    # before shot 1: 0-0            -> home shooter: level
    # before shot 2: 0-0            -> away shooter: level ; shot 2 is a GOAL -> away 1
    # before shot 3: home 0 - away 1 -> home shooter: losing
    # before shot 4: home 0 - away 1 -> away shooter: winning ; OWN GOAL credits HOME -> 1-1
    # before shot 5: home 1 - away 1 -> home shooter: level ; GOAL -> home 2-1
    df = pd.DataFrame([
        _shot(1, 5, "h", "MissedShots", 0.1),
        _shot(2, 20, "a", "Goal", 0.4),
        _shot(3, 35, "h", "SavedShot", 0.2),
        _shot(4, 55, "a", "OwnGoal", 0.0),
        _shot(5, 70, "h", "Goal", 0.6),
    ])
    ctx = wm.reconstruct_shot_context(df).sort_values("shot_id").reset_index(drop=True)

    assert list(ctx["score_home_before_shot"]) == [0, 0, 0, 0, 1]
    assert list(ctx["score_away_before_shot"]) == [0, 0, 1, 1, 1]
    assert list(ctx["game_state"]) == ["level", "level", "losing", "winning", "level"]
    # cumulative xG recorded BEFORE each shot
    assert ctx["cumulative_xG_home"].tolist() == pytest.approx([0.0, 0.1, 0.1, 0.3, 0.3])
    assert ctx["cumulative_xG_away"].tolist() == pytest.approx([0.0, 0.0, 0.4, 0.4, 0.4])


def test_game_state_xg_six_keys():
    df = pd.DataFrame([
        _shot(1, 5, "h", "Goal", 0.5),
        _shot(2, 20, "h", "MissedShots", 0.3),   # home now winning
        _shot(3, 30, "a", "SavedShot", 0.2),     # away losing
    ])
    gsx = wm.game_state_xg(df)
    assert set(gsx.keys()) == {
        "xg_while_level_h", "xg_while_winning_h", "xg_while_losing_h",
        "xg_while_level_a", "xg_while_winning_a", "xg_while_losing_a",
    }
    assert gsx["xg_while_level_h"] == pytest.approx(0.5)
    assert gsx["xg_while_winning_h"] == pytest.approx(0.3)
    assert gsx["xg_while_losing_a"] == pytest.approx(0.2)


# ---------------------------------------------------------------------------
# 9.6 season_table
# ---------------------------------------------------------------------------
def test_season_table_three_team_round_robin():
    # A beats B 2-0, A beats C 1-0, B beats C 3-1
    matches = pd.DataFrame([
        {"match_id": 1, "season": 2025, "datetime": pd.Timestamp("2025-08-01"),
         "home_team": "A", "away_team": "B", "home_goals": 2, "away_goals": 0},
        {"match_id": 2, "season": 2025, "datetime": pd.Timestamp("2025-08-08"),
         "home_team": "A", "away_team": "C", "home_goals": 1, "away_goals": 0},
        {"match_id": 3, "season": 2025, "datetime": pd.Timestamp("2025-08-15"),
         "home_team": "B", "away_team": "C", "home_goals": 3, "away_goals": 1},
    ])
    shots = pd.DataFrame(columns=["match_id", "season", "home_away", "xG", "npxG",
                                  "result", "minute", "shot_id"])
    t = wm.season_table(matches, shots)
    t = t.set_index("team")
    assert list(t.index) == ["A", "B", "C"]  # A 6pts, B 3pts, C 0pts
    assert t.loc["A", "points"] == 6
    assert t.loc["B", "points"] == 3
    assert t.loc["C", "points"] == 0
    # A: GF 3 (2+1), GA 0            -> +3
    # B: GF 3 (0 vs A, 3 vs C), GA 3 -> 0
    # C: GF 1, GA 4 (1 vs A, 3 vs B) -> -3
    assert t.loc["A", "goal_diff"] == 3
    assert t.loc["B", "goal_diff"] == 0
    assert t.loc["C", "goal_diff"] == -3
    assert t.loc["A", "goals_for"] == 3
    assert t.loc["C", "goals_against"] == 4
    assert t.loc["A", "played"] == 2
    assert t.loc["C", "lost"] == 2


# ---------------------------------------------------------------------------
# 9.7 simulate_season
# ---------------------------------------------------------------------------
class _FakeDCFit(dict):
    pass


def _fake_dc_fit(teams):
    return {
        "attack": {t: 0.0 for t in teams},
        "defence": {t: 0.0 for t in teams},
        "gamma": 0.2, "rho": 0.0, "teams": list(teams),
    }


def test_simulate_season_reproducible_and_probabilities_sum_to_one():
    teams = ["A", "B", "C", "D"]
    fit = _fake_dc_fit(teams)
    fixtures = [(h, a) for h in teams for a in teams if h != a]

    df1 = wm.simulate_season(fixtures, fit, n_runs=500, seed=123)
    df2 = wm.simulate_season(fixtures, fit, n_runs=500, seed=123)
    pd.testing.assert_frame_equal(
        df1.sort_values("team").reset_index(drop=True),
        df2.sort_values("team").reset_index(drop=True),
    )

    pos_cols = [c for c in df1.columns if c.startswith("p_pos_")]
    for _, row in df1.iterrows():
        assert sum(row[c] for c in pos_cols) == pytest.approx(1.0, abs=1e-9)


# ---------------------------------------------------------------------------
# 9.8 matchday_number matches the stored lambda_table exactly
# ---------------------------------------------------------------------------
def test_matchday_number_matches_stored_lambda_table():
    import os
    import config
    from src import storage

    lt_path = os.path.join(config.STATE_DIR, "lambda_table.parquet")
    if not os.path.exists(lt_path):
        pytest.skip("lambda_table.parquet not present in this checkout")

    lt = pd.read_parquet(lt_path)
    all_matches = storage.all_understat_matches().sort_values("datetime").reset_index(drop=True)
    md = wm.matchday_number(all_matches)
    got = all_matches.assign(md=md.values)[["match_id", "md"]]
    merged = lt.merge(got, on="match_id", how="left")
    assert len(merged) == len(lt)
    assert (merged["matchday"] == merged["md"]).all()
