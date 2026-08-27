"""
Tip optimizer (B5): expected-points tip selection under the Kicktipp
4/3/2 rule.

For every candidate tip (h, a) with h+a <= 8:
    EV(h,a) = 4*P(h,a)
              + 3*[P(GD = h-a) - P(h,a)]
              + 2*[P(tendency(h,a)) - P(GD = h-a)]
For a drawn tip, the GD term covers ALL draws (goal difference 0), and the
tendency term is therefore zero by construction (tendency(draw) IS "GD=0"
already counted at the 3-point level; there's no additional 2-point
region beyond the draws already paid at 3 points).

Recommend argmax EV. Also output the top-5 tips with EVs, the full grid,
P(H/D/A), and a close-call flag when EV(top) - EV(second) < CLOSE_CALL_EV_MARGIN.
"""
import numpy as np

import config


def _tendency(h, a):
    if h > a:
        return "H"
    if h < a:
        return "A"
    return "D"


def compute_ev_grid(grid, max_sum=8):
    """
    grid: (N+1, N+1) score-probability matrix, grid[h, a] = P(home=h, away=a).
    Returns a dict {(h, a): EV} for every candidate tip with h+a <= max_sum
    and h, a within the grid's bounds.
    """
    n = grid.shape[0] - 1  # max goals per side in the grid
    idx = np.arange(n + 1)

    diff_matrix = np.subtract.outer(idx, idx)   # diff_matrix[h, a] = h - a
    # P(GD = d) for every integer d, precomputed once.
    gd_prob = {}
    for d in range(-n, n + 1):
        gd_prob[d] = grid[diff_matrix == d].sum()

    p_home_tendency = grid[diff_matrix > 0].sum()
    p_draw_tendency = grid[diff_matrix == 0].sum()
    p_away_tendency = grid[diff_matrix < 0].sum()
    tendency_prob = {"H": p_home_tendency, "D": p_draw_tendency, "A": p_away_tendency}

    ev = {}
    for h in range(n + 1):
        for a in range(n + 1):
            if h + a > max_sum:
                continue
            p_exact = grid[h, a]
            d = h - a
            p_gd = gd_prob[d]
            tend = _tendency(h, a)
            p_tend = tendency_prob[tend]

            score = (
                config.POINTS_EXACT * p_exact
                + config.POINTS_GOALDIFF * (p_gd - p_exact)
                + config.POINTS_TENDENCY * (p_tend - p_gd)
            )
            ev[(h, a)] = float(score)
    return ev


def recommend_tip(grid, max_sum=8, close_call_margin=config.CLOSE_CALL_EV_MARGIN):
    """
    Full B5 output: recommended tip, top-5 tips with EVs, P(H/D/A), and a
    close-call flag.

    Returns dict:
        {
          'tip': (h, a), 'ev': float,
          'top5': [((h, a), ev), ...]  (sorted desc, len <= 5),
          'runner_up': ((h, a), ev) or None,
          'close_call': bool,
          'p_home': float, 'p_draw': float, 'p_away': float,
          'ev_grid': {(h, a): ev, ...},
        }
    """
    ev_map = compute_ev_grid(grid, max_sum=max_sum)
    ranked = sorted(ev_map.items(), key=lambda kv: kv[1], reverse=True)

    top_tip, top_ev = ranked[0]
    top5 = ranked[:5]
    runner_up = ranked[1] if len(ranked) > 1 else None

    close_call = False
    if runner_up is not None:
        close_call = (top_ev - runner_up[1]) < close_call_margin

    n = grid.shape[0] - 1
    idx = np.arange(n + 1)
    diff_matrix = np.subtract.outer(idx, idx)
    p_home = grid[diff_matrix > 0].sum()
    p_draw = grid[diff_matrix == 0].sum()
    p_away = grid[diff_matrix < 0].sum()

    return {
        "tip": top_tip,
        "ev": top_ev,
        "top5": top5,
        "runner_up": runner_up,
        "close_call": close_call,
        "p_home": float(p_home),
        "p_draw": float(p_draw),
        "p_away": float(p_away),
        "ev_grid": ev_map,
    }


def score_tip(tip, result):
    """
    Score a single tip against the real result under Kicktipp 4/3/2.
    tip, result: (home_goals, away_goals) tuples.
    """
    th, ta = tip
    rh, ra = result
    if (th, ta) == (rh, ra):
        return config.POINTS_EXACT
    if (th - ta) == (rh - ra):
        return config.POINTS_GOALDIFF
    if _tendency(th, ta) == _tendency(rh, ra):
        return config.POINTS_TENDENCY
    return config.POINTS_WRONG
