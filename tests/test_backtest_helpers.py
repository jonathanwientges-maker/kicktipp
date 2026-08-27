"""
Unit tests for backtest.py helper functions that don't require running
the full rolling-origin backtest (that is exercised separately via
`python -m src.backtest`, which is expensive and covered by Acceptance C
manually / in CI on demand, not on every test run).
"""
import numpy as np
import pandas as pd
import pytest

from src import backtest


def test_rps_1x2_perfect_prediction_is_zero():
    """A grid with probability 1 on the correct tendency's cells anywhere
    within the correct third scores RPS 0 only when it's a point mass
    that also gets the cumulative buckets right; sanity check RPS is 0
    for a maximally confident correct call."""
    grid = np.zeros((11, 11))
    grid[2, 0] = 1.0  # certain 2-0 (home win)
    rps = backtest.rps_1x2(grid, (2, 0))
    assert rps == pytest.approx(0.0, abs=1e-9)


def test_rps_1x2_worse_for_confident_wrong_call():
    grid_right = np.zeros((11, 11))
    grid_right[2, 0] = 1.0
    grid_wrong = np.zeros((11, 11))
    grid_wrong[0, 2] = 1.0  # certain away win, but result is home win

    rps_right = backtest.rps_1x2(grid_right, (2, 0))
    rps_wrong = backtest.rps_1x2(grid_wrong, (2, 0))
    assert rps_wrong > rps_right


def test_modal_score_picks_argmax_cell():
    grid = np.zeros((6, 6))
    grid[1, 1] = 0.3
    grid[2, 1] = 0.5
    grid[0, 0] = 0.2
    assert backtest.modal_score(grid) == (2, 1)


def test_market_grid_from_lambdas_falls_back_on_nan():
    grid_nan = backtest.market_grid_from_lambdas(float("nan"), float("nan"))
    grid_fallback = backtest._poisson_grid(*__import__("config").FALLBACK_LAMBDAS)
    assert np.allclose(grid_nan, grid_fallback)


def _synthetic_lambda_table(n=6, halflife=365):
    """A tiny synthetic lambda-table slice with the exact columns
    tune_hyperparams_from_table expects, so the tuning search can be
    exercised without needing a real DC fit / full lambda_table build."""
    rng = np.random.RandomState(3)
    rows = []
    for i in range(n):
        rows.append({
            "match_id": i, "season": 2016,
            "home_goals": 2, "away_goals": 0,  # deterministic home wins
            "lam_market_h": 1.1, "lam_market_a": 1.1,  # uninformative
            "lam_xg_h": 1.1, "lam_xg_a": 1.1,           # uninformative
            "lam_dc_h_{0}".format(halflife): 2.2, "lam_dc_a_{0}".format(halflife): 0.3,  # informative
            "rho_{0}".format(halflife): 0.0,
        })
    df = pd.DataFrame(rows)
    # Fill the OTHER halflife columns as all-NaN so dropna() in the tuning
    # loop correctly skips them (mirrors a real table's shape).
    import config
    for hl in config.DC_HALFLIFE_GRID:
        for col in ("lam_dc_h_{0}".format(hl), "lam_dc_a_{0}".format(hl), "rho_{0}".format(hl)):
            if col not in df.columns:
                df[col] = np.nan
    return df


def test_tune_hyperparams_from_table_prefers_informative_dc_signal():
    """With market/xG lambdas deliberately uninformative (near 1-1, i.e.
    poor at predicting the actual 2-0 results) and DC lambdas that
    exactly match the true result pattern, the (F2) market-anchored
    weight search should push w_DC to the maximum the w_market >= 0.5
    constraint allows (i.e. the boundary (0.5, 0.0, 0.5)), and w_xG
    should get none of the remaining weight since it's equally
    uninformative as the market here."""
    import config
    df = _synthetic_lambda_table(n=8, halflife=config.DC_HALFLIFE_GRID[0])
    best = backtest.tune_hyperparams_from_table(df)
    assert best["halflife"] == config.DC_HALFLIFE_GRID[0]
    w_m, w_x, w_d = best["weights"]
    assert w_m == pytest.approx(config.MIN_MARKET_WEIGHT)
    assert w_d == pytest.approx(1.0 - config.MIN_MARKET_WEIGHT)
    assert w_x == pytest.approx(0.0)

    # The constraint must actually bind here: the unconstrained optimum
    # (recorded for T-FIX transparency, fix round F2) should prefer DC
    # even more heavily than the constrained choice allows.
    unconstrained = best["unconstrained_optimum"]
    assert unconstrained["weights"][2] > w_d  # more DC weight than the constrained pick


def test_tune_hyperparams_from_table_returns_valid_weights():
    import config
    df = _synthetic_lambda_table(n=5, halflife=config.DC_HALFLIFE_GRID[1])
    best = backtest.tune_hyperparams_from_table(df)
    assert best is not None
    assert abs(sum(best["weights"]) - 1.0) < 1e-9
    assert best["halflife"] in config.DC_HALFLIFE_GRID
    assert isinstance(best["use_negbin"], bool)
    # F2: market-anchored constraint must hold on every returned combo.
    assert best["weights"][0] >= config.MIN_MARKET_WEIGHT - 1e-9
    # F3: draw_margin must be one of the tuned grid values.
    assert best["draw_margin"] in config.DRAW_MARGIN_GRID
    # F2 transparency: unconstrained_optimum recorded alongside the pick.
    assert "unconstrained_optimum" in best
    assert best["unconstrained_optimum"] is not None
    assert abs(sum(best["unconstrained_optimum"]["weights"]) - 1.0) < 1e-9


def test_tune_hyperparams_from_table_survives_nan_lam_xg_at_zero_weight():
    """Regression guard: a real bug found while running the full backtest
    -- a row with lam_xg_h/a = NaN (a promoted team's rolling-window
    warmup period, see features.py) crashed build_final_grid's sum-to-1
    assertion at the weight-search vertex (0, 0, 1) where lam_xg gets
    ZERO weight. The naive expectation "0 * NaN contributes nothing" is
    false in IEEE arithmetic (0.0 * nan = nan, not 0.0), so an unguarded
    NaN silently poisons the blended lambda even when its weight is
    exactly zero. tune_hyperparams_from_table must substitute
    config.FALLBACK_LAMBDAS for any NaN lam_xg row before blending, same
    as the main per-season evaluation loop already does."""
    import config

    halflife = config.DC_HALFLIFE_GRID[0]
    rows = [
        {
            "match_id": 1, "season": 2016, "home_goals": 2, "away_goals": 0,
            "lam_market_h": 1.4, "lam_market_a": 1.1,
            "lam_xg_h": np.nan, "lam_xg_a": np.nan,  # promoted-team warmup gap
            "lam_dc_h_{0}".format(halflife): 1.6, "lam_dc_a_{0}".format(halflife): 0.9,
            "rho_{0}".format(halflife): -0.05,
        },
    ]
    df = pd.DataFrame(rows)
    for hl in config.DC_HALFLIFE_GRID:
        for col in ("lam_dc_h_{0}".format(hl), "lam_dc_a_{0}".format(hl), "rho_{0}".format(hl)):
            if col not in df.columns:
                df[col] = np.nan

    # Must not raise (this is exactly what crashed the real backtest run).
    best = backtest.tune_hyperparams_from_table(df)
    assert best is not None
