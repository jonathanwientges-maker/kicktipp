"""
Market-implied lambdas (B1).

1. Odds column priority: Pinnacle (PS*) -> Average (Avg*) -> Bet365, same
   priority for O/U.
2. 1X2 margin removal via Shin's method (insider-trading proportion z,
   fixed-point/bisection). Falls back to proportional normalisation if
   iteration fails.
3. O/U margin removal: proportional normalisation only (two outcomes).
4. Inversion: (lambda_h, lambda_a) minimizing squared error between model
   probabilities (independent-Poisson grid, no tau) and de-margined market
   probabilities, via scipy L-BFGS-B.
5. Missing O/U -> invert on 1X2 alone + soft penalty toward
   TOTAL_GOALS_PRIOR. Missing all odds -> NaN (blend.py handles it).
6. Asian-handicap columns are never used.
"""
import numpy as np
from scipy.optimize import minimize
from scipy.stats import poisson

import config

Z_LO, Z_HI = 0.0, 0.2
Z_ITERS = 50
Z_TOL = 1e-10


def pick_1x2_odds(row):
    """Priority: Pinnacle (PSH/PSD/PSA) -> Avg -> B365. Returns (oH, oD, oA)
    or None if none of the triples are fully present."""
    for prefix in ("PS", "Avg", "B365"):
        h, d, a = row.get(prefix + "H"), row.get(prefix + "D"), row.get(prefix + "A")
        if _all_valid(h, d, a):
            return float(h), float(d), float(a)
    return None


def pick_ou_odds(row):
    """Priority: Pinnacle (P>2.5/P<2.5) -> Avg -> B365. Returns (o_over,
    o_under) or None."""
    for prefix in ("P", "Avg", "B365"):
        over_key = prefix + ">2.5"
        under_key = prefix + "<2.5"
        o, u = row.get(over_key), row.get(under_key)
        if _all_valid(o, u):
            return float(o), float(u)
    return None


def _all_valid(*vals):
    for v in vals:
        if v is None:
            return False
        try:
            if np.isnan(v):
                return False
        except TypeError:
            return False
        if v <= 1.0:
            return False
    return True


# ---------------------------------------------------------------------------
# Shin's method
# ---------------------------------------------------------------------------

def _shin_probs_for_z(pis, z):
    """Given inverse-odds pis (sum = booksum B) and insider proportion z,
    compute Shin probabilities p_i for each outcome."""
    B = np.sum(pis)
    inner = z ** 2 + 4.0 * (1.0 - z) * (pis ** 2) / B
    inner = np.clip(inner, 0.0, None)
    num = np.sqrt(inner) - z
    denom = 2.0 * (1.0 - z)
    if denom <= 0:
        return None
    return num / denom


def shin_probabilities(decimal_odds):
    """
    decimal_odds: iterable of decimal odds for mutually exclusive outcomes.
    Returns de-margined probabilities summing to 1, via Shin's method with
    z found by bisection on sum(p_i(z)) - 1 = 0, z in [Z_LO, Z_HI].
    Falls back to proportional normalisation (p_i = pi_i / B) if the
    bisection does not converge to a valid probability vector.
    """
    pis = np.array([1.0 / o for o in decimal_odds], dtype=float)
    B = np.sum(pis)

    def f(z):
        p = _shin_probs_for_z(pis, z)
        if p is None or np.any(np.isnan(p)):
            return None
        return np.sum(p) - 1.0

    lo, hi = Z_LO, Z_HI
    f_lo, f_hi = f(lo), f(hi)

    if f_lo is None or f_hi is None:
        return pis / B

    # z=0 (proportional normalisation) is already an exact root when the
    # book is fair (booksum B == 1): f_lo == 0 in that case. Handle this
    # before the bracketing check below, since a product-sign test can't
    # distinguish "root exactly at lo" from "no root in range" when
    # f_lo == 0.
    if abs(f_lo) < Z_TOL:
        return pis / B

    # sum(p_i(z)) is decreasing in z typically starting from B-1 (>=0 when
    # book has overround) down toward <=0; if signs don't bracket a root,
    # fall back.
    if f_lo * f_hi > 0:
        # No sign change in range -- use the endpoint closest to zero, but
        # only if it gives a sane probability vector; else fall back.
        z_best = lo if abs(f_lo) < abs(f_hi) else hi
        p = _shin_probs_for_z(pis, z_best)
        if p is not None and np.all(p > 0) and abs(np.sum(p) - 1.0) < 1e-3:
            return p / np.sum(p)
        return pis / B

    z = lo
    for _ in range(Z_ITERS):
        mid = 0.5 * (lo + hi)
        f_mid = f(mid)
        if f_mid is None:
            return pis / B
        if abs(f_mid) < Z_TOL:
            z = mid
            break
        if f_lo * f_mid < 0:
            hi = mid
            f_hi = f_mid
        else:
            lo = mid
            f_lo = f_mid
        z = mid

    p = _shin_probs_for_z(pis, z)
    if p is None or np.any(np.isnan(p)) or np.any(p < 0):
        return pis / B
    return p / np.sum(p)


def ou_probabilities(decimal_odds):
    """Two-outcome proportional (overround) normalisation only."""
    pis = np.array([1.0 / o for o in decimal_odds], dtype=float)
    return pis / np.sum(pis)


# ---------------------------------------------------------------------------
# Model probabilities from (lambda_h, lambda_a) -- plain independent
# Poisson grid, NO tau correction (inversion stays well-defined).
# ---------------------------------------------------------------------------

def _score_grid(lam_h, lam_a, max_goals=config.GRID_MAX_GOALS):
    hg = np.arange(0, max_goals + 1)
    ph = poisson.pmf(hg, lam_h)
    pa = poisson.pmf(hg, lam_a)
    grid = np.outer(ph, pa)
    grid = grid / grid.sum()
    return grid


def model_1x2_probs(lam_h, lam_a, max_goals=config.GRID_MAX_GOALS):
    grid = _score_grid(lam_h, lam_a, max_goals)
    n = grid.shape[0]
    idx = np.arange(n)
    p_home = grid[np.greater.outer(idx, idx)].sum()
    p_draw = np.trace(grid)
    p_away = grid[np.less.outer(idx, idx)].sum()
    return p_home, p_draw, p_away


def model_over_2_5(lam_h, lam_a, max_goals=config.GRID_MAX_GOALS):
    grid = _score_grid(lam_h, lam_a, max_goals)
    n = grid.shape[0]
    total = np.add.outer(np.arange(n), np.arange(n))
    p_over = grid[total >= 3].sum()
    return p_over


# ---------------------------------------------------------------------------
# Inversion
# ---------------------------------------------------------------------------

def invert_lambdas(market_1x2, market_ou, start=(1.5, 1.2)):
    """
    market_1x2: (p_home, p_draw, p_away) de-margined market probabilities,
        or None if 1X2 odds are unavailable.
    market_ou: de-margined market P(over 2.5), or None if O/U unavailable.

    Returns (lambda_h, lambda_a), or (nan, nan) if market_1x2 is None
    (no odds at all -- blend.py substitutes other estimates / fallback).
    """
    if market_1x2 is None:
        return float("nan"), float("nan")

    p_home_mkt, p_draw_mkt, p_away_mkt = market_1x2

    def objective(x):
        lam_h, lam_a = x
        p_home, p_draw, p_away = model_1x2_probs(lam_h, lam_a)
        err = (
            (p_home - p_home_mkt) ** 2
            + (p_draw - p_draw_mkt) ** 2
            + (p_away - p_away_mkt) ** 2
        )
        if market_ou is not None:
            p_over = model_over_2_5(lam_h, lam_a)
            err += (p_over - market_ou) ** 2
        else:
            err += 0.25 * (lam_h + lam_a - config.TOTAL_GOALS_PRIOR) ** 2
        return err

    res = minimize(
        objective, x0=np.array(start, dtype=float),
        method="L-BFGS-B", bounds=[(0.05, 5.0), (0.05, 5.0)],
    )
    return float(res.x[0]), float(res.x[1])


def compute_market_lambdas(row):
    """
    End-to-end per-match market lambda computation from a raw odds row
    (dict-like with COLS_1X2 / COLS_OU keys). Returns (lambda_h, lambda_a).
    NaN, NaN if no 1X2 odds are available at all (AH columns never used).
    """
    odds_1x2 = pick_1x2_odds(row)
    odds_ou = pick_ou_odds(row)

    if odds_1x2 is None:
        return float("nan"), float("nan")

    market_1x2 = tuple(shin_probabilities(odds_1x2))
    market_ou = None
    if odds_ou is not None:
        p_over, _p_under = ou_probabilities(odds_ou)
        market_ou = float(p_over)

    return invert_lambdas(market_1x2, market_ou)
