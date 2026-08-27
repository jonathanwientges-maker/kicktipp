"""
Rolling-xG lambdas (B2) and promoted-team priors.

Port of the validated R rolling-window logic:
  - For each team, rolling mean of npxG-for and npxG-against over the last
    XG_WINDOW_N matches AT THE SAME VENUE (home matches feed the home
    rate, away matches feed the away rate), strictly before the current
    match (no leakage).
  - lambda_h = LAMBDA_BLEND * home_attack_rolling
               + (1 - LAMBDA_BLEND) * away_conceded_rolling
    symmetric for lambda_a.
  - Expected penalty xG is added back using the league-mean penalty xG per
    team-match, computed from the shots data over the training window
    (never hardcoded).
  - Promoted teams (no Bundesliga history in the data) get a synthetic
    rolling-window seed from a once-fit linear regression: their final
    2. Bundesliga season stats (from D2.csv) -> their first-Bundesliga
    npxG for/against. The prediction seeds pseudo-matches that decay
    linearly out of the rolling window as real matches are played
    (each real match replaces one pseudo-match).
"""
import numpy as np
import pandas as pd

import config

# NOTE: requirements.txt intentionally excludes scikit-learn (not in the
# allowed dependency list). The promoted-team regression is small (a
# handful of promotion events, 2 features -> 2 targets) and is implemented
# below with plain numpy least squares (see fit_promotion_regression).


def _venue_rolling(matches_df, team_col, opp_col, npxg_for_col, npxg_against_col,
                    venue_label, window_n):
    """
    Build a long frame: one row per (team, match at `venue_label`), with
    the rolling mean of npxG-for and npxG-against over the trailing
    `window_n` matches at that same venue, computed strictly before the
    match (shift(1) after sort by datetime).
    """
    sub = matches_df[["match_id", "season", "datetime", team_col, opp_col,
                       npxg_for_col, npxg_against_col]].copy()
    sub = sub.rename(columns={team_col: "team", opp_col: "opponent",
                               npxg_for_col: "npxg_for", npxg_against_col: "npxg_against"})
    sub["venue"] = venue_label
    sub = sub.sort_values(["team", "datetime"])

    grp = sub.groupby("team", group_keys=False)
    sub["roll_npxg_for"] = grp["npxg_for"].apply(
        lambda s: s.shift(1).rolling(window_n, min_periods=1).mean()
    )
    sub["roll_npxg_against"] = grp["npxg_against"].apply(
        lambda s: s.shift(1).rolling(window_n, min_periods=1).mean()
    )
    sub["n_prior_matches"] = grp["npxg_for"].apply(
        lambda s: s.shift(1).expanding().count()
    )
    return sub


def build_rolling_table(matches_df, window_n=config.XG_WINDOW_N):
    """
    Compute same-venue rolling npxG-for/against for every team, for both
    home and away matches. Returns a long DataFrame keyed by
    (match_id, team, venue) with roll_npxg_for / roll_npxg_against /
    n_prior_matches.
    """
    home_roll = _venue_rolling(
        matches_df, "home_team", "away_team", "home_npxG", "away_npxG",
        "home", window_n,
    )
    away_roll = _venue_rolling(
        matches_df, "away_team", "home_team", "away_npxG", "home_npxG",
        "away", window_n,
    )
    return pd.concat([home_roll, away_roll], ignore_index=True)


def league_mean_penalty_xg(shots_df, matches_df, season, train_seasons=None):
    """
    League-mean penalty xG per team-match, computed from shots data over
    the training window (seasons < `season`, or `train_seasons` if given).
    Used to add back expected penalty xG onto the non-penalty rolling
    lambda. Never hardcoded.
    """
    if train_seasons is None:
        train_seasons = [s for s in matches_df["season"].unique() if s < season]
    train_match_ids = set(matches_df[matches_df["season"].isin(train_seasons)]["match_id"])
    pens = shots_df[
        shots_df["match_id"].isin(train_match_ids) & shots_df["is_penalty"]
    ]
    n_team_matches = 2 * len(train_match_ids)  # each match has a home and away team-match
    if n_team_matches == 0:
        return 0.0
    total_pen_xg = pens["xG"].sum()
    return float(total_pen_xg / n_team_matches)


def compute_lambda_xg(matches_df, shots_df, lambda_blend=config.LAMBDA_BLEND,
                       window_n=config.XG_WINDOW_N):
    """
    Full B2 pipeline: rolling npxG table + penalty add-back -> per-match
    (lambda_h, lambda_a) for every match in matches_df, using only data
    strictly before that match (rolling window is inherently
    out-of-sample; penalty prior for a match's season uses only earlier
    seasons).

    Returns matches_df with columns lambda_xg_h, lambda_xg_a appended.
    """
    roll = build_rolling_table(matches_df, window_n=window_n)

    home_roll = roll[roll["venue"] == "home"][
        ["match_id", "team", "roll_npxg_for", "roll_npxg_against", "n_prior_matches"]
    ].rename(columns={
        "roll_npxg_for": "home_attack_roll",
        "roll_npxg_against": "home_conceded_roll_asvenue",
        "n_prior_matches": "home_n_prior",
    })
    away_roll = roll[roll["venue"] == "away"][
        ["match_id", "team", "roll_npxg_for", "roll_npxg_against", "n_prior_matches"]
    ].rename(columns={
        "roll_npxg_for": "away_attack_roll",
        "roll_npxg_against": "away_conceded_roll_asvenue",
        "n_prior_matches": "away_n_prior",
    })

    out = matches_df.merge(
        home_roll, left_on=["match_id", "home_team"], right_on=["match_id", "team"], how="left"
    ).drop(columns=["team"])
    out = out.merge(
        away_roll, left_on=["match_id", "away_team"], right_on=["match_id", "team"], how="left"
    ).drop(columns=["team"])

    # lambda_h = LAMBDA_BLEND * home_attack_rolling
    #            + (1-LAMBDA_BLEND) * away_conceded_rolling
    # "away_conceded_rolling" = the away team's rolling npxG conceded,
    # computed over ITS away matches (home_conceded_roll_asvenue/
    # away_conceded_roll_asvenue below carry that same-venue semantics).
    out["lambda_xg_h_raw"] = (
        lambda_blend * out["home_attack_roll"]
        + (1 - lambda_blend) * out["away_conceded_roll_asvenue"]
    )
    out["lambda_xg_a_raw"] = (
        lambda_blend * out["away_attack_roll"]
        + (1 - lambda_blend) * out["home_conceded_roll_asvenue"]
    )

    # Penalty add-back, computed per-season from strictly prior seasons.
    pen_by_season = {}
    for season in sorted(out["season"].unique()):
        pen_by_season[season] = league_mean_penalty_xg(shots_df, out, season)
    out["penalty_addback"] = out["season"].map(pen_by_season).fillna(0.0)

    out["lambda_xg_h"] = out["lambda_xg_h_raw"] + out["penalty_addback"]
    out["lambda_xg_a"] = out["lambda_xg_a_raw"] + out["penalty_addback"]

    return out


# ---------------------------------------------------------------------------
# Promoted-team prior
# ---------------------------------------------------------------------------

def build_promotion_training_pairs(promotions, d2_stats_by_team_season, first_bl_npxg_by_team_season):
    """
    Build (X, Y) training pairs for the promoted-team regression.

    promotions: list of dicts {team, d2_season, bl_season} -- one row per
        promotion event 2015-2025 (a team's final 2. Bundesliga season and
        their first Bundesliga season).
    d2_stats_by_team_season: dict (team, d2_season) -> dict with keys
        gf_mean, ga_mean, shots_for_mean, shots_against_mean (from D2.csv).
    first_bl_npxg_by_team_season: dict (team, bl_season) -> dict with keys
        npxg_for_mean, npxg_against_mean (from the project's own Bundesliga
        matches data, first season only).

    Returns (X, Y) numpy arrays: X has 4 columns (gf, ga, shots_for,
    shots_against), Y has 2 columns (npxg_for, npxg_against).
    """
    X_rows, Y_rows = [], []
    for promo in promotions:
        key_d2 = (promo["team"], promo["d2_season"])
        key_bl = (promo["team"], promo["bl_season"])
        if key_d2 not in d2_stats_by_team_season or key_bl not in first_bl_npxg_by_team_season:
            continue
        d2 = d2_stats_by_team_season[key_d2]
        bl = first_bl_npxg_by_team_season[key_bl]
        X_rows.append([d2["gf_mean"], d2["ga_mean"], d2["shots_for_mean"], d2["shots_against_mean"]])
        Y_rows.append([bl["npxg_for_mean"], bl["npxg_against_mean"]])
    if not X_rows:
        return None, None
    return np.array(X_rows, dtype=float), np.array(Y_rows, dtype=float)


def fit_promotion_regression(X, Y):
    """
    Plain OLS via numpy lstsq (with intercept), fit once on all historical
    promotion events. Returns a callable predict(x_row) -> [npxg_for,
    npxg_against], and the fitted coefficient matrix for inspection.
    """
    n = X.shape[0]
    X_design = np.hstack([np.ones((n, 1)), X])
    coefs, _, _, _ = np.linalg.lstsq(X_design, Y, rcond=None)

    def predict(x_row):
        x_design = np.concatenate([[1.0], x_row])
        return x_design.dot(coefs)

    return predict, coefs


def promoted_team_prior_seed(predict_fn, d2_row, window_n=config.XG_WINDOW_N):
    """
    Given the fitted regression's predict function and a promoted team's
    final-D2-season stats row (dict with gf_mean, ga_mean, shots_for_mean,
    shots_against_mean), return the pseudo-match seed values
    (npxg_for_seed, npxg_against_seed) to pre-fill the rolling window.

    Consequently the seed is used as the constant rolling value until real
    same-venue matches accumulate; each real match played replaces one
    pseudo-match in a window of size `window_n`, i.e. the prior's weight
    decays linearly to zero over the team's first `window_n` same-venue
    matches (implemented by the caller via a weighted average, see
    `blend_prior_with_real`).
    """
    x_row = np.array([
        d2_row["gf_mean"], d2_row["ga_mean"],
        d2_row["shots_for_mean"], d2_row["shots_against_mean"],
    ], dtype=float)
    pred = predict_fn(x_row)
    return {"npxg_for_seed": max(pred[0], 0.05), "npxg_against_seed": max(pred[1], 0.05)}


def blend_prior_with_real(prior_value, real_values, window_n=config.XG_WINDOW_N):
    """
    real_values: list of realised npxG values (for or against) at this
    venue so far, oldest first, length k (0 <= k <= window_n).

    Returns the rolling estimate using (window_n - k) pseudo-matches at
    `prior_value` and k real matches, i.e. exactly a decaying linear blend:
        estimate = ((window_n - k) * prior_value + sum(real_values)) / window_n
    For k >= window_n, this reduces to a plain mean of the last window_n
    real values (prior weight = 0), matching the "decays linearly over the
    first 8 same-venue matches" requirement.
    """
    k = len(real_values)
    if k >= window_n:
        recent = real_values[-window_n:]
        return float(np.mean(recent))
    pseudo_n = window_n - k
    total = pseudo_n * prior_value + sum(real_values)
    return float(total / window_n)
