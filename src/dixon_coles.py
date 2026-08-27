"""
Dixon-Coles ratings (B3): classic Dixon & Coles (1997), fitted by maximum
likelihood on goals.

Parameters: attack_i, defence_i per team (identifiability: sum(attack)=0),
home advantage gamma, low-score correction rho.

lambda_h = exp(attack_home - defence_away + gamma)
lambda_a = exp(attack_away - defence_home)

Likelihood weights: w = exp(-ln(2) * delta_days / halflife), halflife
tuned from config.DC_HALFLIFE_GRID in the backtest.

Tau correction multiplies the four cells (0,0),(1,0),(0,1),(1,1) exactly
as in the paper:
    tau(0,0) = 1 - lambda_h*lambda_a*rho
    tau(1,0) = 1 + lambda_a*rho
    tau(0,1) = 1 + lambda_h*rho
    tau(1,1) = 1 - rho
renormalise the grid after applying.

Fit on the trailing DC_TRAIN_SEASONS seasons + current season to date,
refit on every run. Teams entering with no history are initialised at the
promoted-prior equivalent (mapped through the DC link -- see
init_promoted_team_rating).
"""
import numpy as np
from scipy.optimize import minimize
from scipy.stats import poisson

import config

LN2 = np.log(2.0)


def time_weight(delta_days, halflife):
    """w = exp(-ln(2) * delta_days / halflife). delta_days >= 0 (match is
    in the past relative to the fit date)."""
    return np.exp(-LN2 * np.asarray(delta_days, dtype=float) / halflife)


def tau_correction(home_goals, away_goals, lam_h, lam_a, rho):
    """Dixon-Coles low-score correction factor for a single (or array of)
    (home_goals, away_goals) outcome(s)."""
    hg = np.asarray(home_goals)
    ag = np.asarray(away_goals)
    tau = np.ones_like(hg, dtype=float) if hg.shape else 1.0

    is_00 = (hg == 0) & (ag == 0)
    is_10 = (hg == 1) & (ag == 0)
    is_01 = (hg == 0) & (ag == 1)
    is_11 = (hg == 1) & (ag == 1)

    tau = np.where(is_00, 1.0 - lam_h * lam_a * rho, tau)
    tau = np.where(is_10, 1.0 + lam_a * rho, tau)
    tau = np.where(is_01, 1.0 + lam_h * rho, tau)
    tau = np.where(is_11, 1.0 - rho, tau)
    return tau


def _unpack_params(x, teams):
    n = len(teams)
    attack = dict(zip(teams, x[:n]))
    defence = dict(zip(teams, x[n:2 * n]))
    gamma = x[2 * n]
    rho = x[2 * n + 1]
    return attack, defence, gamma, rho


def _pack_params(attack, defence, gamma, rho, teams):
    return np.concatenate([
        np.array([attack[t] for t in teams]),
        np.array([defence[t] for t in teams]),
        np.array([gamma, rho]),
    ])


def negative_log_likelihood(x, teams, home_idx, away_idx, home_goals, away_goals, weights):
    n = len(teams)
    attack = x[:n]
    defence = x[n:2 * n]
    gamma = x[2 * n]
    rho = x[2 * n + 1]

    lam_h = np.exp(attack[home_idx] - defence[away_idx] + gamma)
    lam_a = np.exp(attack[away_idx] - defence[home_idx])

    log_pmf_h = poisson.logpmf(home_goals, lam_h)
    log_pmf_a = poisson.logpmf(away_goals, lam_a)

    tau = tau_correction(home_goals, away_goals, lam_h, lam_a, rho)
    tau = np.clip(tau, 1e-10, None)  # guard against invalid rho region
    log_tau = np.log(tau)

    ll = weights * (log_pmf_h + log_pmf_a + log_tau)
    return -np.sum(ll)


def fit_dixon_coles(matches_df, as_of_date, halflife, init_ratings=None):
    """
    Fit Dixon-Coles on `matches_df` (must have home_team, away_team,
    home_goals, away_goals, datetime columns), weighting each match by
    time_weight(delta_days, halflife) where delta_days = (as_of_date -
    match.datetime).days.

    `init_ratings`: optional dict {team: {'attack': x, 'defence': y}} used
    to seed teams with no/little history (promoted teams) -- see
    init_promoted_team_rating. Teams not in init_ratings start at 0.

    Returns dict: {'attack': {team: val}, 'defence': {team: val},
                   'gamma': val, 'rho': val, 'teams': [...]}
    """
    df = matches_df.copy()
    df["delta_days"] = (as_of_date - df["datetime"]).dt.total_seconds() / 86400.0
    df = df[df["delta_days"] >= 0]

    teams = sorted(set(df["home_team"]).union(df["away_team"]))
    team_idx = {t: i for i, t in enumerate(teams)}
    n = len(teams)

    home_idx = df["home_team"].map(team_idx).values
    away_idx = df["away_team"].map(team_idx).values
    home_goals = df["home_goals"].values.astype(int)
    away_goals = df["away_goals"].values.astype(int)
    weights = time_weight(df["delta_days"].values, halflife)

    x0_attack = np.zeros(n)
    x0_defence = np.zeros(n)
    if init_ratings:
        for t, i in team_idx.items():
            if t in init_ratings:
                x0_attack[i] = init_ratings[t].get("attack", 0.0)
                x0_defence[i] = init_ratings[t].get("defence", 0.0)
    x0 = np.concatenate([x0_attack, x0_defence, [0.2, -0.05]])  # gamma, rho starts

    # Identifiability constraint sum(attack) = 0 enforced via a soft
    # penalty added to the objective (keeps the optimizer unconstrained
    # and simple; equivalent up to a global attack/defence shift which
    # the penalty drives to zero).
    def objective(x):
        base = negative_log_likelihood(
            x, teams, home_idx, away_idx, home_goals, away_goals, weights
        )
        attack_sum = np.sum(x[:n])
        return base + 1000.0 * attack_sum ** 2

    bounds = (
        [(-3.0, 3.0)] * n + [(-3.0, 3.0)] * n
        + [(-1.0, 1.0)] + [(-0.3, 0.3)]
    )
    res = minimize(objective, x0, method="L-BFGS-B", bounds=bounds)
    attack, defence, gamma, rho = _unpack_params(res.x, teams)

    return {
        "attack": attack, "defence": defence, "gamma": float(gamma), "rho": float(rho),
        "teams": teams, "halflife": halflife, "as_of_date": as_of_date,
        "converged": bool(res.success),
    }


def dc_lambdas(fit, home_team, away_team):
    """Compute (lambda_h, lambda_a) for a fixture from a fitted DC model."""
    attack, defence, gamma = fit["attack"], fit["defence"], fit["gamma"]
    a_h = attack.get(home_team, 0.0)
    a_a = attack.get(away_team, 0.0)
    d_h = defence.get(home_team, 0.0)
    d_a = defence.get(away_team, 0.0)
    lam_h = np.exp(a_h - d_a + gamma)
    lam_a = np.exp(a_a - d_h)
    return float(lam_h), float(lam_a)


def init_promoted_team_rating(npxg_for_seed, npxg_against_seed, league_mean_npxg=1.4):
    """
    Map the B2 promoted-team prior (npxg_for_seed, npxg_against_seed) onto
    the DC attack/defence link scale, so a newly-promoted team's DC rating
    starts from the same information rather than at the league-average 0.

    Uses the DC identity lambda ~ exp(attack - defence) around a
    league-mean baseline: attack = log(npxg_for_seed / league_mean_npxg),
    defence = -log(npxg_against_seed / league_mean_npxg) (defence is
    "goals prevented", so a low npxg_against_seed => high/positive
    defence contribution in the lambda_a formula, hence the sign).
    """
    npxg_for_seed = max(npxg_for_seed, 0.05)
    npxg_against_seed = max(npxg_against_seed, 0.05)
    attack = float(np.log(npxg_for_seed / league_mean_npxg))
    defence = float(-np.log(npxg_against_seed / league_mean_npxg))
    return {"attack": attack, "defence": defence}


def score_grid_from_dc(fit, home_team, away_team, max_goals=config.GRID_MAX_GOALS):
    """Full DC score grid (independent Poisson outer product with the DC
    lambdas, tau-corrected and renormalised) for a fixture."""
    lam_h, lam_a = dc_lambdas(fit, home_team, away_team)
    hg = np.arange(0, max_goals + 1)
    ph = poisson.pmf(hg, lam_h)
    pa = poisson.pmf(hg, lam_a)
    grid = np.outer(ph, pa)

    rho = fit["rho"]
    for i in (0, 1):
        for j in (0, 1):
            grid[i, j] *= tau_correction(i, j, lam_h, lam_a, rho)

    grid = np.clip(grid, 0.0, None)
    grid = grid / grid.sum()
    return grid, lam_h, lam_a
