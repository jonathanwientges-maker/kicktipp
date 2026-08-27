"""
Fix round F4 (data/reports/diagnosis.md T5c): wire the promoted-team
prior (build plan Section 4, B2) into the live pipeline.

The regression/seed/decay functions already existed in features.py
(fit_promotion_regression, build_promotion_training_pairs,
promoted_team_prior_seed, blend_prior_with_real) but were never called
from anywhere -- a newly-promoted team's rolling window simply produced
NaN until real matches accumulated, falling back to
config.FALLBACK_LAMBDAS. This module assembles the actual training data
(D2.csv stats -> first-Bundesliga-season npxG) and exposes one entry
point, `promoted_team_seeds`, that features.compute_lambda_xg calls to
seed each promoted team's rolling window with a D2-informed value
instead of leaving it NaN.

Data availability note: football-data.co.uk D2 files only carry shot
counts (HS/AS) from the 2017/18 season onward; 2014/15-2016/17 have
goals only. The regression is fit on whichever promotion events have the
full 4-feature set (goals-for/against + shots-for/against) available --
per the current data (D2 2014-2023), that is 7 of the 10 promotion
events in the 2014-2023 window. A promoted team whose own most recent D2
season lacks shots data (or has no D2 history in our data at all) is
NOT given a fabricated shots figure -- it falls through to
config.FALLBACK_LAMBDAS, exactly as the "last resort only when D2
history is also unavailable" wording specifies, since shots-incomplete
history is treated as unavailable for this feature set.
"""
import numpy as np
import pandas as pd

import config
from src import crosswalk, features, storage


def _d2_team_season_stats(d2_df):
    """
    Per-team-season means of goals for/against and shots for/against from
    one D2.csv season. Returns dict {team_name: {'gf_mean':.., 'ga_mean':..,
    'shots_for_mean':.., 'shots_against_mean':..}}. Teams whose season
    lacks HS/AS columns get shots_for_mean/shots_against_mean = None.
    """
    has_shots = "HS" in d2_df.columns and "AS" in d2_df.columns

    home = d2_df[["HomeTeam", "FTHG", "FTAG"]].rename(
        columns={"HomeTeam": "team", "FTHG": "gf", "FTAG": "ga"}
    )
    away = d2_df[["AwayTeam", "FTAG", "FTHG"]].rename(
        columns={"AwayTeam": "team", "FTAG": "gf", "FTHG": "ga"}
    )
    if has_shots:
        home["shots_for"] = d2_df["HS"]
        home["shots_against"] = d2_df["AS"]
        away["shots_for"] = d2_df["AS"]
        away["shots_against"] = d2_df["HS"]

    long_df = pd.concat([home, away], ignore_index=True)
    grouped = long_df.groupby("team").mean(numeric_only=True)

    out = {}
    for team, row in grouped.iterrows():
        entry = {"gf_mean": float(row["gf"]), "ga_mean": float(row["ga"])}
        if has_shots:
            entry["shots_for_mean"] = float(row["shots_for"])
            entry["shots_against_mean"] = float(row["shots_against"])
        else:
            entry["shots_for_mean"] = None
            entry["shots_against_mean"] = None
        out[team] = entry
    return out


def detect_promotions(matches_df):
    """
    Detect every promotion event in matches_df: a team whose FIRST
    appearance (as home or away) in the Bundesliga data is in season S >
    the earliest season present. Returns list of dicts
    {team (Understat name), bl_season, d2_season (= bl_season - 1)}.
    """
    seasons = sorted(matches_df["season"].unique())
    if not seasons:
        return []
    first_season = seasons[0]

    teams_by_season = {}
    for s in seasons:
        s_matches = matches_df[matches_df["season"] == s]
        teams_by_season[s] = set(s_matches["home_team"]).union(s_matches["away_team"])

    seen = set(teams_by_season.get(first_season, set()))
    promotions = []
    for s in seasons:
        if s == first_season:
            continue
        new_teams = teams_by_season[s] - seen
        for t in sorted(new_teams):
            promotions.append({"team": t, "bl_season": s, "d2_season": s - 1})
        seen |= teams_by_season[s]
    return promotions


def first_bl_season_npxg(matches_df, team, bl_season):
    """Mean npxG-for/against for `team` (Understat name) over its FIRST
    Bundesliga season only (bl_season), from matches_df (which must
    already have home_npxG/away_npxG columns, i.e. the raw ingested
    matches, not the rolling-enriched frame)."""
    sub = matches_df[matches_df["season"] == bl_season]
    home = sub[sub["home_team"] == team]
    away = sub[sub["away_team"] == team]
    npxg_for = pd.concat([home["home_npxG"], away["away_npxG"]])
    npxg_against = pd.concat([home["away_npxG"], away["home_npxG"]])
    if len(npxg_for) == 0:
        return None
    return {
        "npxg_for_mean": float(npxg_for.mean()),
        "npxg_against_mean": float(npxg_against.mean()),
    }


def _promotion_xy_row(promo, matches_df, d2_cache):
    """
    For one promotion event, resolve its D2 team-season stats and its
    first-Bundesliga-season npxG outcome. Returns (x_row, y_row,
    team_stats) or None if either is unavailable (shots-incomplete D2
    season, team not found in D2 at all, or no matches found in its
    first Bundesliga season).
    """
    d2_season = promo["d2_season"]
    if d2_season not in d2_cache:
        d2_df = storage.odds_d2(d2_season)
        d2_cache[d2_season] = _d2_team_season_stats(d2_df) if d2_df is not None else {}
    d2_stats = d2_cache[d2_season]

    fd_name = crosswalk.UNDERSTAT_TO_FD.get(promo["team"], promo["team"])
    if fd_name not in d2_stats:
        return None
    team_stats = d2_stats[fd_name]
    if team_stats["shots_for_mean"] is None:
        return None  # shots-incomplete D2 season -- cannot use this feature set

    bl_npxg = first_bl_season_npxg(matches_df, promo["team"], promo["bl_season"])
    if bl_npxg is None:
        return None

    x_row = [
        team_stats["gf_mean"], team_stats["ga_mean"],
        team_stats["shots_for_mean"], team_stats["shots_against_mean"],
    ]
    y_row = [bl_npxg["npxg_for_mean"], bl_npxg["npxg_against_mean"]]
    return x_row, y_row, team_stats


def build_regression_and_seeds(matches_df, as_of_season=None):
    """
    Full F4 pipeline: fit the promotion regression on historical
    promotion events strictly before `as_of_season` (train_seasons =
    bl_season < as_of_season), then produce seeds for EVERY promotion
    event in matches_df regardless of its own bl_season (as_of_season
    only restricts what's used for TRAINING, never which teams can
    receive a seed) -- this lets `promoted_team_seeds_leakage_safe`
    below correctly ask "give me a seed for this season's promoted teams,
    using only strictly-earlier promotions to fit the regression."

    If as_of_season is None, all available promotions train the
    regression (used by the live predict.py path, where there's no
    "held-out future" concern -- the regression itself is fit once on
    all history, matching "fit once on all historical data" in the build
    plan).

    Returns dict: {understat_team_name: {'npxg_for_seed':.., 'npxg_against_seed':..}}
    for every promoted team whose D2 season had the full 4-feature set
    available AND whose bl_season's promotion fit within the training
    window logic above. Teams not in the returned dict should fall back
    to config.FALLBACK_LAMBDAS at the caller.
    """
    promotions = detect_promotions(matches_df)
    train_promotions = (
        [p for p in promotions if p["bl_season"] < as_of_season]
        if as_of_season is not None else promotions
    )

    d2_cache = {}
    X_rows, Y_rows = [], []
    for promo in train_promotions:
        resolved = _promotion_xy_row(promo, matches_df, d2_cache)
        if resolved is None:
            continue
        x_row, y_row, _team_stats = resolved
        X_rows.append(x_row)
        Y_rows.append(y_row)

    if len(X_rows) < 4:
        # Not enough complete training pairs to fit a stable 4-feature
        # regression (identifiability needs at least as many points as
        # coefficients: intercept + 4 = 5). Return no seeds -- callers
        # fall back to config.FALLBACK_LAMBDAS.
        return {}

    X = np.array(X_rows, dtype=float)
    Y = np.array(Y_rows, dtype=float)
    predict_fn, _coefs = features.fit_promotion_regression(X, Y)

    # Seeds are produced for every promotion whose D2 stats resolve,
    # independent of whether that promotion trained the regression --
    # for as_of_season=None (live path) that's the same set; for a
    # specific as_of_season it deliberately includes THAT season's
    # promotions too (they need a seed; they just didn't train on
    # themselves).
    seeds = {}
    for promo in promotions:
        resolved = _promotion_xy_row(promo, matches_df, d2_cache)
        if resolved is None:
            continue
        _x_row, _y_row, team_stats = resolved
        seeds[promo["team"]] = features.promoted_team_prior_seed(predict_fn, team_stats)
    return seeds


def promoted_team_seeds_for_live(matches_df):
    """Convenience wrapper for predict.py: fit on ALL available
    promotion history (no held-out season), used to seed any
    currently-promoted team's rolling window for live prediction."""
    return build_regression_and_seeds(matches_df, as_of_season=None)


def promoted_team_seeds_leakage_safe(matches_df):
    """
    Convenience wrapper for lambda_table.py (the historical backtest
    table, which spans many predicted seasons at once): each promoted
    team's seed is computed from a regression fit using ONLY promotion
    events strictly before THAT team's own bl_season -- i.e. distinct
    from `build_regression_and_seeds`'s single global as_of_season cutoff,
    this recomputes the regression once per distinct bl_season present
    among the promotions, so an early promotion's seed can never be
    influenced by a later promotion's first-Bundesliga-season npxG
    outcome (which would otherwise be a genuine look-ahead leak in a
    lambda table meant to serve every predicted season out-of-sample).

    Returns the same shape as build_regression_and_seeds: dict
    {understat_team_name: {'npxg_for_seed':.., 'npxg_against_seed':..}}.
    """
    promotions = detect_promotions(matches_df)
    distinct_bl_seasons = sorted(set(p["bl_season"] for p in promotions))

    seeds = {}
    for bl_season in distinct_bl_seasons:
        # Regression fit using only promotions from earlier bl_seasons;
        # applied only to this bl_season's promoted teams.
        season_seeds = build_regression_and_seeds(matches_df, as_of_season=bl_season)
        this_season_teams = {p["team"] for p in promotions if p["bl_season"] == bl_season}
        for team in this_season_teams:
            if team in season_seeds:
                seeds[team] = season_seeds[team]
    return seeds
