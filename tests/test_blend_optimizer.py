import numpy as np
import pytest
from scipy.stats import poisson

import config
from src import blend, optimizer


def _toy_grid(lam_h=1.4, lam_a=1.1, rho=0.0, max_goals=6):
    return blend.build_final_grid(lam_h, lam_a, rho, use_negbin=False, max_goals=max_goals)


def test_simplex_grid_size_and_sums():
    combos = blend.simplex_grid(step=0.1)
    assert len(combos) == 66
    for w in combos:
        assert abs(sum(w) - 1.0) < 1e-9


def test_blend_log_lambda_with_all_sources():
    lam = blend.blend_log_lambda((1.5, 1.2), (1.4, 1.3), (1.6, 1.1), (1 / 3, 1 / 3, 1 / 3))
    assert lam[0] > 0 and lam[1] > 0


def test_blend_log_lambda_missing_market_renormalises():
    lam_with_market = blend.blend_log_lambda(
        (1.5, 1.2), (1.4, 1.3), (1.6, 1.1), (0.5, 0.25, 0.25)
    )
    lam_without_market = blend.blend_log_lambda(
        (float("nan"), float("nan")), (1.4, 1.3), (1.6, 1.1), (0.5, 0.25, 0.25)
    )
    # Without market, should equal a 50/50 blend of xG/DC (renormalised
    # from 0.25/0.25).
    expected_h = np.exp(0.5 * np.log(1.4) + 0.5 * np.log(1.6))
    assert lam_without_market[0] == pytest.approx(expected_h, abs=1e-9)
    assert lam_with_market != lam_without_market


def test_build_final_grid_sums_to_one():
    grid = _toy_grid()
    assert grid.sum() == pytest.approx(1.0, abs=1e-9)


def test_build_final_grid_negbin_sums_to_one():
    grid = blend.build_final_grid(1.4, 1.1, rho=-0.05, use_negbin=True,
                                   dispersion=(0.1, 0.1), max_goals=6)
    assert grid.sum() == pytest.approx(1.0, abs=1e-9)


def test_ev_of_tip_2_1_hand_computed():
    """Hand-build a small toy grid and verify optimizer.compute_ev_grid's
    EV(2,1) matches a manually computed value."""
    max_goals = 3
    n = max_goals + 1
    grid = np.zeros((n, n))
    # Assign some arbitrary but valid probabilities.
    grid[2, 1] = 0.10
    grid[3, 2] = 0.05  # same GD (+1) as 2-1
    grid[1, 0] = 0.08  # same GD (+1) as 2-1
    grid[1, 1] = 0.15  # tendency H? no -> draw. Not part of H tendency.
    grid[2, 0] = 0.07  # GD +2, tendency H
    grid[0, 0] = 0.20  # draw
    grid[1, 2] = 0.10  # tendency A
    grid[0, 1] = 0.15  # tendency A
    grid[3, 0] = 0.10  # GD +3, tendency H
    remaining = 1.0 - grid.sum()
    grid[3, 3] += remaining  # pad to sum to 1 (draw, doesn't affect H tendency calc)

    ev_map = optimizer.compute_ev_grid(grid, max_sum=8)

    p_exact = grid[2, 1]
    gd = 2 - 1
    p_gd = 0.0
    for h in range(n):
        for a in range(n):
            if h - a == gd:
                p_gd += grid[h, a]
    p_tendency_home = 0.0
    for h in range(n):
        for a in range(n):
            if h > a:
                p_tendency_home += grid[h, a]

    expected_ev = (
        config.POINTS_EXACT * p_exact
        + config.POINTS_GOALDIFF * (p_gd - p_exact)
        + config.POINTS_TENDENCY * (p_tendency_home - p_gd)
    )
    assert ev_map[(2, 1)] == pytest.approx(expected_ev, abs=1e-9)


def test_optimizer_never_prefers_00_over_11_when_11_more_likely():
    """Symmetric grid where P(1-1) > P(0-0): optimizer must not recommend
    0-0 over 1-1."""
    lam_h, lam_a = 1.3, 1.3  # symmetric, mean > 1 so P(1,1) > P(0,0)
    grid = _toy_grid(lam_h, lam_a, rho=0.0, max_goals=6)
    assert grid[1, 1] > grid[0, 0]  # sanity check on the toy setup

    result = optimizer.recommend_tip(grid)
    ev_map = result["ev_grid"]
    assert ev_map[(1, 1)] >= ev_map[(0, 0)]


def test_recommend_tip_close_call_flag():
    grid = _toy_grid()
    result = optimizer.recommend_tip(grid)
    assert "close_call" in result
    assert isinstance(result["close_call"], (bool, np.bool_))
    assert len(result["top5"]) <= 5
    assert abs(result["p_home"] + result["p_draw"] + result["p_away"] - 1.0) < 1e-6


def test_score_tip_all_outcomes():
    assert optimizer.score_tip((2, 1), (2, 1)) == config.POINTS_EXACT
    assert optimizer.score_tip((2, 1), (3, 2)) == config.POINTS_GOALDIFF
    assert optimizer.score_tip((2, 1), (3, 1)) == config.POINTS_TENDENCY
    assert optimizer.score_tip((2, 1), (0, 0)) == config.POINTS_WRONG
    # Draw tip scoring any other draw = 3 points (GD=0 covers all draws).
    assert optimizer.score_tip((1, 1), (2, 2)) == config.POINTS_GOALDIFF
