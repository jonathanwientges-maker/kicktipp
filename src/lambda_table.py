"""
Precomputed lambda table for the backtest.

One row per Bundesliga match (2017-2025 predicted seasons, plus enough
warmup history before them), with:
    match_id, season, matchday, kickoff, home_team, away_team,
    home_goals, away_goals,
    lam_market_h, lam_market_a,
    lam_xg_h, lam_xg_a,
    lam_dc_h_{halflife}, lam_dc_a_{halflife}, rho_{halflife}   (per halflife)

Every value is out-of-sample by construction:
  - lam_market: pure function of the pre-match odds row for that match
    (never depends on other matches) -- computed exactly once per match,
    ever.
  - lam_xg: the rolling window (features.compute_lambda_xg) already only
    looks strictly before each match (shift(1)).
  - lam_dc_*: from a DC fit using only matches strictly before that
    match's matchday (see fill_dc_columns / warm-started sequential fit).

Persisted to data/state/lambda_table.parquet, keyed by a hash of the
config values that affect its contents, so re-runs and crashes skip
straight past completed work.
"""
import hashlib
import json
import os

import numpy as np
import pandas as pd

import config
from src import dixon_coles as dc, features, market, storage

LAMBDA_TABLE_PATH = os.path.join(config.STATE_DIR, "lambda_table.parquet")
LAMBDA_TABLE_META_PATH = os.path.join(config.STATE_DIR, "lambda_table_meta.json")


def _config_hash():
    """Hash of every config value that affects the table's contents --
    if any of these change, the cached table is stale and must be rebuilt."""
    payload = {
        "XG_WINDOW_N": config.XG_WINDOW_N,
        "LAMBDA_BLEND": config.LAMBDA_BLEND,
        "GRID_MAX_GOALS": config.GRID_MAX_GOALS,
        "DC_HALFLIFE_GRID": config.DC_HALFLIFE_GRID,
        "DC_TRAIN_SEASONS": config.DC_TRAIN_SEASONS,
        "FALLBACK_LAMBDAS": config.FALLBACK_LAMBDAS,
        "TOTAL_GOALS_PRIOR": config.TOTAL_GOALS_PRIOR,
        "BACKTEST_FIRST": config.BACKTEST_FIRST,
        "COLS_1X2": config.COLS_1X2,
        "COLS_OU": config.COLS_OU,
    }
    blob = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def _log(msg):
    print("[lambda_table] {0}".format(msg), flush=True)


def load_cached_table():
    """Return the cached lambda table if it exists AND matches the
    current config hash; otherwise None (forces a rebuild)."""
    if not os.path.exists(LAMBDA_TABLE_PATH) or not os.path.exists(LAMBDA_TABLE_META_PATH):
        return None
    with open(LAMBDA_TABLE_META_PATH) as f:
        meta = json.load(f)
    if meta.get("config_hash") != _config_hash():
        _log("Cached lambda table config hash mismatch -- rebuilding.")
        return None
    df = pd.read_parquet(LAMBDA_TABLE_PATH)
    _log("Loaded cached lambda table: {0} rows (config hash {1}).".format(
        len(df), meta["config_hash"]
    ))
    return df


def save_table(df):
    os.makedirs(config.STATE_DIR, exist_ok=True)
    df.to_parquet(LAMBDA_TABLE_PATH, index=False)
    with open(LAMBDA_TABLE_META_PATH, "w") as f:
        json.dump({"config_hash": _config_hash(), "n_rows": len(df)}, f, indent=2)


def _matchday_number(matches_df):
    """Assign a 1-indexed matchday number within each season, grouping
    matches by kickoff date proximity (Bundesliga matchdays cluster
    within a Fri-Mon window). Approximated by rank of distinct kickoff
    dates within the season -- sufficient for reporting/diagnostics, not
    used in any leakage-sensitive computation."""
    out = matches_df.copy()
    out["kickoff_date"] = out["datetime"].dt.date
    md = (
        out.groupby("season")["kickoff_date"]
        .rank(method="dense")
        .astype(int)
    )
    return md


def compute_lam_market_column(matches_df, odds_by_match_id):
    """Compute lam_market once per match (pure function of that match's
    odds row). ~2.7ms each per the profiling; 3060 matches ~= 8s."""
    lam_h_col = np.full(len(matches_df), np.nan)
    lam_a_col = np.full(len(matches_df), np.nan)
    for i, mid in enumerate(matches_df["match_id"].values):
        odds_row = odds_by_match_id.get(mid)
        if odds_row is None:
            continue
        lam_h, lam_a = market.compute_market_lambdas(odds_row)
        lam_h_col[i] = lam_h
        lam_a_col[i] = lam_a
    return lam_h_col, lam_a_col


def compute_lam_xg_columns(matches_df, shots_df):
    enriched = features.compute_lambda_xg(matches_df, shots_df)
    enriched = enriched.set_index("match_id")
    lam_h = matches_df["match_id"].map(enriched["lambda_xg_h"]).values
    lam_a = matches_df["match_id"].map(enriched["lambda_xg_a"]).values
    return lam_h, lam_a


def fill_dc_columns(matches_df, halflife):
    """
    Sequential, warm-started per-matchday DC fits for one halflife.

    Processes matchdays in chronological order; each matchday's fit is
    initialized from the PREVIOUS matchday's solution (attack/defence/
    gamma/rho barely move week to week, so convergence needs only a
    handful of L-BFGS-B iterations instead of a cold start every time).

    Each matchday's fit uses only matches strictly before that matchday's
    earliest kickoff -- the matchday being predicted is NEVER included in
    its own training window (this is the exact leakage failure mode the
    regression guard in tests/test_lambda_table.py checks for).

    Crash/resume granularity is at the halflife level, not the matchday
    level: build_lambda_table() persists the table to disk after each
    halflife's columns are filled (see the checkpoint call there), so a
    crash mid-build re-does at most one halflife's worth of sequential
    fits, not the whole table. A per-matchday checkpoint would require
    persisting the warm-start rating state itself (not just the output
    lambdas), which added complexity this doesn't currently need given
    one halflife's full sequential fit takes well under a minute.

    Returns dict match_id -> (lam_h, lam_a, rho).
    """
    matches_df = matches_df.sort_values("datetime")
    matchdays = sorted(matches_df["datetime"].dt.date.unique())

    out = {}
    prior_fit_ratings = None  # warm-start seed for the next fit

    for i, day in enumerate(matchdays):
        day_matches = matches_df[matches_df["datetime"].dt.date == day]

        as_of = pd.Timestamp(day)
        train = matches_df[matches_df["datetime"] < as_of]
        if len(train) < 50:
            continue

        init_ratings = None
        if prior_fit_ratings is not None:
            init_ratings = {
                t: {"attack": prior_fit_ratings["attack"].get(t, 0.0),
                    "defence": prior_fit_ratings["defence"].get(t, 0.0)}
                for t in set(prior_fit_ratings["attack"]) | set(prior_fit_ratings["defence"])
            }

        fit = dc.fit_dixon_coles(train, as_of, halflife=halflife, init_ratings=init_ratings)
        prior_fit_ratings = fit

        for _, m in day_matches.iterrows():
            lam_h, lam_a = dc.dc_lambdas(fit, m["home_team"], m["away_team"])
            out[m["match_id"]] = (lam_h, lam_a, fit["rho"])

        if (i + 1) % 20 == 0 or (i + 1) == len(matchdays):
            _log("  halflife={0}: matchday {1}/{2} ({3}) fit, converged={4}".format(
                halflife, i + 1, len(matchdays), day, fit["converged"]
            ))

    return out


def build_lambda_table(first_season=None, force_rebuild=False):
    """
    Build (or load from cache) the full lambda table covering every
    match from (BACKTEST_FIRST - DC_TRAIN_SEASONS - 3) through the last
    completed season -- i.e. enough warmup history plus every predicted
    season.
    """
    if not force_rebuild:
        cached = load_cached_table()
        if cached is not None:
            return cached

    all_matches = storage.all_understat_matches().sort_values("datetime").reset_index(drop=True)
    all_shots = storage.all_understat_shots()
    all_odds = storage.all_odds_d1()

    from src.backtest import _join_odds_to_matches
    odds_by_match_id = _join_odds_to_matches(all_matches, all_odds)

    _log("Computing lam_market for {0} matches...".format(len(all_matches)))
    lam_market_h, lam_market_a = compute_lam_market_column(all_matches, odds_by_match_id)

    _log("Computing lam_xg for {0} matches...".format(len(all_matches)))
    lam_xg_h, lam_xg_a = compute_lam_xg_columns(all_matches, all_shots)

    table = pd.DataFrame({
        "match_id": all_matches["match_id"].values,
        "season": all_matches["season"].values,
        "matchday": _matchday_number(all_matches).values,
        "kickoff": all_matches["datetime"].values,
        "home_team": all_matches["home_team"].values,
        "away_team": all_matches["away_team"].values,
        "home_goals": all_matches["home_goals"].values,
        "away_goals": all_matches["away_goals"].values,
        "lam_market_h": lam_market_h, "lam_market_a": lam_market_a,
        "lam_xg_h": lam_xg_h, "lam_xg_a": lam_xg_a,
    })

    # Resume support: if an incomplete checkpoint from a crashed run
    # exists on disk (no meta file, since save_table() only writes meta
    # once ALL halflives are done) and already has a given halflife's
    # columns fully populated, reuse them instead of re-running ~300
    # sequential L-BFGS-B fits for that halflife.
    checkpoint_cols = {}
    if not force_rebuild and os.path.exists(LAMBDA_TABLE_PATH) and not os.path.exists(LAMBDA_TABLE_META_PATH):
        try:
            checkpoint = pd.read_parquet(LAMBDA_TABLE_PATH)
            checkpoint_cols = {
                c: checkpoint.set_index("match_id")[c]
                for c in checkpoint.columns if c.startswith("lam_dc_") or c.startswith("rho_")
            }
            if checkpoint_cols:
                _log("Found partial checkpoint from an interrupted run with columns: {0}".format(
                    sorted(checkpoint_cols.keys())
                ))
        except Exception as exc:  # noqa: BLE001
            _log("Could not read partial checkpoint ({0}); rebuilding from scratch.".format(exc))

    for halflife in config.DC_HALFLIFE_GRID:
        h_col, a_col, r_col = (
            "lam_dc_h_{0}".format(halflife), "lam_dc_a_{0}".format(halflife), "rho_{0}".format(halflife),
        )
        if h_col in checkpoint_cols and a_col in checkpoint_cols and r_col in checkpoint_cols \
                and checkpoint_cols[h_col].notna().sum() == len(table):
            _log("halflife={0}: reusing complete checkpointed columns.".format(halflife))
            table[h_col] = table["match_id"].map(checkpoint_cols[h_col])
            table[a_col] = table["match_id"].map(checkpoint_cols[a_col])
            table[r_col] = table["match_id"].map(checkpoint_cols[r_col])
            continue

        _log("Filling DC columns for halflife={0} ({1} matchdays)...".format(
            halflife, all_matches["datetime"].dt.date.nunique()
        ))
        dc_map = fill_dc_columns(all_matches, halflife)
        table["lam_dc_h_{0}".format(halflife)] = table["match_id"].map(
            lambda mid: dc_map.get(mid, (np.nan, np.nan, np.nan))[0]
        )
        table["lam_dc_a_{0}".format(halflife)] = table["match_id"].map(
            lambda mid: dc_map.get(mid, (np.nan, np.nan, np.nan))[1]
        )
        table["rho_{0}".format(halflife)] = table["match_id"].map(
            lambda mid: dc_map.get(mid, (np.nan, np.nan, np.nan))[2]
        )
        _log("halflife={0} done: {1}/{2} matches have DC lambdas.".format(
            halflife, table["lam_dc_h_{0}".format(halflife)].notna().sum(), len(table)
        ))

        # Checkpoint after each halflife: a crash on halflife #2 or #3
        # loses at most one halflife's worth of sequential DC fits, not
        # the whole table (lam_market/lam_xg and any earlier halflife's
        # DC columns are already safely persisted). Note this partial
        # save intentionally has a config_hash matching the FINAL table
        # only once all halflives are done -- write the checkpoint
        # without the meta file so load_cached_table() never picks up an
        # incomplete table as if it were finished.
        table.to_parquet(LAMBDA_TABLE_PATH, index=False)

    save_table(table)
    _log("Lambda table built and cached: {0} rows.".format(len(table)))
    return table


if __name__ == "__main__":
    df = build_lambda_table(force_rebuild=False)
    print(df.describe(include="all"))
