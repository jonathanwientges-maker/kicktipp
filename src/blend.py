"""
Blend (B4): combine market / rolling-xG / Dixon-Coles lambdas into a
single final score grid.

log(lambda_final) = w_m*log(lambda_market) + w_x*log(lambda_xG)
                     + w_d*log(lambda_DC)
with (w_m, w_x, w_d) on the simplex, grid-searched in BLEND_STEP
increments (66 combos for step=0.1) in the backtest. If lambda_market is
NaN, renormalise remaining weights over the available estimates.

Final score grid: independent Poisson (or negative-binomial, if
USE_NEGBIN) outer product on lambda_final (0..GRID_MAX_GOALS), then the DC
tau is applied with the fitted rho, renormalised. Cells must sum to 1
within 1e-9.
"""
import numpy as np
from scipy.stats import nbinom, poisson

import config
from src.dixon_coles import tau_correction


def simplex_grid(step=config.BLEND_STEP):
    """
    All (w_m, w_x, w_d) triples on the simplex with each weight a multiple
    of `step` and summing to 1.0. For step=0.1 this yields the 66 combos
    referenced in the spec (C(10+2,2) = 66).
    """
    n_steps = int(round(1.0 / step))
    combos = []
    for i in range(n_steps + 1):
        for j in range(n_steps + 1 - i):
            k = n_steps - i - j
            combos.append((i * step, j * step, k * step))
    return combos


def market_anchored_simplex_grid(step=config.BLEND_STEP,
                                  min_market_weight=config.MIN_MARKET_WEIGHT):
    """
    Fix round F2 (data/reports/diagnosis.md T1): the same simplex as
    simplex_grid, but constrained to w_market >= min_market_weight. The
    market is the sharpest single source of the three (T4: small
    inversion residuals; T1's key table: every unconstrained-search
    alternative -- pooled, fixed, pure-market -- beat the per-season
    "optimal" tuned weights out of sample); xG and DC are meant to enter
    as corrections on top of the market signal, not as replacements for
    it. For step=0.1 and min_market_weight=0.5, this yields 21 combos
    (w_m in {0.5..1.0}, C(n+1,2) triangular counts summing to 21).
    """
    return [w for w in simplex_grid(step=step) if w[0] >= min_market_weight - 1e-9]


def blend_log_lambda(lam_market, lam_xg, lam_dc, weights):
    """
    lam_market/lam_xg/lam_dc: each a (lambda_h, lambda_a) pair (may
    contain NaN for lam_market if odds were unavailable).
    weights: (w_m, w_x, w_d).

    Returns blended (lambda_h, lambda_a). If lam_market is NaN, drops the
    market term and renormalises (w_x, w_d) to sum to 1.
    """
    w_m, w_x, w_d = weights
    lam_m_h, lam_m_a = lam_market
    lam_x_h, lam_x_a = lam_xg
    lam_d_h, lam_d_a = lam_dc

    market_valid = not (np.isnan(lam_m_h) or np.isnan(lam_m_a))

    if not market_valid:
        total = w_x + w_d
        if total <= 0:
            # Degenerate: all weight was on market and it's missing.
            # Fall back to an even split of xG/DC.
            w_x, w_d = 0.5, 0.5
        else:
            w_x, w_d = w_x / total, w_d / total
        log_h = w_x * np.log(lam_x_h) + w_d * np.log(lam_d_h)
        log_a = w_x * np.log(lam_x_a) + w_d * np.log(lam_d_a)
    else:
        log_h = w_m * np.log(lam_m_h) + w_x * np.log(lam_x_h) + w_d * np.log(lam_d_h)
        log_a = w_m * np.log(lam_m_a) + w_x * np.log(lam_x_a) + w_d * np.log(lam_d_a)

    return float(np.exp(log_h)), float(np.exp(log_a))


def _poisson_marginal(lam, max_goals):
    hg = np.arange(0, max_goals + 1)
    return poisson.pmf(hg, lam)


def _negbin_marginal(lam, dispersion, max_goals):
    """
    Negative-binomial marginal parameterised by mean `lam` and dispersion
    `dispersion` (variance = lam + dispersion*lam^2, dispersion > 0
    recovers overdispersion relative to Poisson; dispersion -> 0 recovers
    Poisson). Uses the standard mean/dispersion -> (n, p) reparameterisation:
        r = 1 / dispersion
        p = r / (r + lam)
    """
    dispersion = max(dispersion, 1e-6)
    r = 1.0 / dispersion
    p = r / (r + lam)
    hg = np.arange(0, max_goals + 1)
    return nbinom.pmf(hg, r, p)


def build_final_grid(lam_h, lam_a, rho, use_negbin=False, dispersion=None,
                      max_goals=config.GRID_MAX_GOALS):
    """
    Independent marginals (Poisson or NegBin) outer product on
    (lam_h, lam_a), tau-corrected with `rho` on the four low-score cells,
    renormalised so the grid sums to 1 within 1e-9.
    """
    if use_negbin:
        if dispersion is None:
            raise ValueError("dispersion must be provided when use_negbin=True")
        disp_h, disp_a = dispersion
        ph = _negbin_marginal(lam_h, disp_h, max_goals)
        pa = _negbin_marginal(lam_a, disp_a, max_goals)
    else:
        ph = _poisson_marginal(lam_h, max_goals)
        pa = _poisson_marginal(lam_a, max_goals)

    grid = np.outer(ph, pa)

    for i in (0, 1):
        for j in (0, 1):
            grid[i, j] *= tau_correction(i, j, lam_h, lam_a, rho)

    grid = np.clip(grid, 0.0, None)
    total = grid.sum()
    if total <= 0:
        raise ValueError("Degenerate score grid (sum <= 0) for lam_h={0}, "
                          "lam_a={1}, rho={2}".format(lam_h, lam_a, rho))
    grid = grid / total

    assert abs(grid.sum() - 1.0) < 1e-9, "score grid does not sum to 1"
    return grid


def fit_negbin_dispersion(residuals_for, residuals_against=None):
    """
    Fit a single dispersion parameter via method-of-moments on training
    residuals: dispersion = (var(residuals) - mean(residuals)) /
    mean(residuals)^2, clipped to >= 0 (falls back to ~0, i.e. Poisson, if
    the data is under-dispersed).

    `residuals_for` is an array of realised goal counts minus the fitted
    Poisson mean for the training set (used to estimate the marginal
    over/under-dispersion of the goal-scoring process).
    """
    resid = np.asarray(residuals_for, dtype=float)
    mean_r = np.mean(resid)
    var_r = np.var(resid)
    if mean_r <= 0:
        return 1e-6
    dispersion = (var_r - mean_r) / (mean_r ** 2)
    return float(max(dispersion, 1e-6))
