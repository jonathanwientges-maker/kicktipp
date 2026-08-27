"""
Phase C: rolling-origin historical backtest.

Protocol (Section 5 of the build plan):
  - For each season S in BACKTEST_FIRST..last completed season: all tuning
    and fitting uses data strictly before each predicted match. DC refits
    per matchday within S using data to date. Rolling xG is inherently
    out-of-sample. Blend weights / halflife / rho / USE_NEGBIN are tuned
    ONLY on seasons < S (nested: tune on {BACKTEST_FIRST-3..S-1}, evaluate
    on S). No metric from a predicted season may influence its own
    parameters.
  - For every match in S: produce the recommended tip, score it under 4/3/2.

Baselines computed alongside the model, per match:
  (1) model                      -- full blended ensemble + optimizer
  (2) always "2-1"                -- fixed naive tip
  (3) market modal score          -- argmax cell of the market-only grid
  (4) market-EV                   -- optimizer run on the market-only grid
                                      (key comparison: model must beat this)
  (5) closing-odds EV ceiling      -- optimizer on closing-odds market grid
                                      (evaluation-only, never a feature)
  (6) Understat forecast EV        -- optimizer on a grid built from
                                      forecast_win/draw/loss (amendment pt 5)

Secondary diagnostics: 1X2 RPS, exact-score hit rate, GD hit rate,
tendency hit rate.

PERFORMANCE DESIGN (see src/lambda_table.py):
  All three raw lambda sources (market/xG/DC-per-halflife) are precomputed
  ONCE for the entire match history into a single lambda table -- every
  value in it is out-of-sample by construction (pure function of that
  match's pre-match odds row, or a rolling/DC fit using only strictly
  earlier matches). This backtest module NEVER recomputes lambdas: the
  nested hyperparameter search (tune_hyperparams) is pure vectorized numpy
  over pre-extracted columns, and the final per-season evaluation slices
  the same table by (halflife) column selection. No scipy calls, no DC
  fits, and no per-match dict lookups happen inside the combo-search loop.
"""
import json
import os

import numpy as np
import pandas as pd
from scipy.stats import poisson

import config
from src import blend, lambda_table, market, optimizer, storage

# football-data closing-odds columns (evaluation-only benchmark #5).
CLOSING_COLS_1X2 = ["PSCH", "PSCD", "PSCA"]


def _log(msg):
    print("[backtest] {0}".format(msg), flush=True)


# ---------------------------------------------------------------------------
# Grid construction helpers (evaluation-only benchmarks -- these are NOT
# part of the tuning hot loop and are only run once per match in the
# final per-season evaluation pass, so scipy calls here are fine).
# ---------------------------------------------------------------------------

def _poisson_grid(lam_h, lam_a, max_goals=config.GRID_MAX_GOALS):
    hg = np.arange(0, max_goals + 1)
    ph = poisson.pmf(hg, lam_h)
    pa = poisson.pmf(hg, lam_a)
    grid = np.outer(ph, pa)
    return grid / grid.sum()


def market_grid_from_lambdas(lam_h, lam_a, max_goals=config.GRID_MAX_GOALS):
    """Build a pure market-implied score grid (no DC tau) from
    precomputed market lambdas, for use as the 'market-EV' benchmark grid."""
    if np.isnan(lam_h) or np.isnan(lam_a):
        lam_h, lam_a = config.FALLBACK_LAMBDAS
    return _poisson_grid(lam_h, lam_a, max_goals)


def closing_odds_grid(row, max_goals=config.GRID_MAX_GOALS):
    """Evaluation-only ceiling benchmark: optimizer run on the market grid
    built from CLOSING odds. Never used as a feature anywhere else."""
    vals = [row.get(c) for c in CLOSING_COLS_1X2]
    if any(v is None or (isinstance(v, float) and np.isnan(v)) or v <= 1.0 for v in vals):
        return None
    p = market.shin_probabilities(tuple(vals))
    lam_h, lam_a = market.invert_lambdas(tuple(p), None)
    if np.isnan(lam_h):
        return None
    return _poisson_grid(lam_h, lam_a, max_goals)


def forecast_grid(row, max_goals=config.GRID_MAX_GOALS):
    """Understat forecast_win/draw/loss -> a score grid via lambda
    inversion on those probabilities alone (benchmark #6, amendment pt 5).
    """
    fw, fd, fl = row.get("forecast_win"), row.get("forecast_draw"), row.get("forecast_loss")
    if any(v is None or (isinstance(v, float) and np.isnan(v)) for v in (fw, fd, fl)):
        return None
    lam_h, lam_a = market.invert_lambdas((fw, fd, fl), None)
    if np.isnan(lam_h):
        return None
    return _poisson_grid(lam_h, lam_a, max_goals)


def modal_score(grid):
    idx = np.unravel_index(np.argmax(grid), grid.shape)
    return (int(idx[0]), int(idx[1]))


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------

def rps_1x2(grid, result):
    """Ranked Probability Score for the 3-way (H/D/A) outcome, ordered
    Home > Draw > Away (a natural ordinal ordering by goal difference
    sign). Lower is better; 0 = perfect."""
    n = grid.shape[0]
    idx = np.arange(n)
    diff = np.subtract.outer(idx, idx)
    p_home = grid[diff > 0].sum()
    p_draw = grid[diff == 0].sum()
    p_away = grid[diff < 0].sum()
    probs = [p_home, p_draw, p_away]

    rh, ra = result
    if rh > ra:
        actual = [1, 0, 0]
    elif rh == ra:
        actual = [0, 1, 0]
    else:
        actual = [0, 0, 1]

    cum_p, cum_a = 0.0, 0.0
    rps = 0.0
    for i in range(3):
        cum_p += probs[i]
        cum_a += actual[i]
        rps += (cum_p - cum_a) ** 2
    return rps / (3 - 1)


# ---------------------------------------------------------------------------
# Nested hyperparameter tuning -- pure array math over the lambda table.
# ---------------------------------------------------------------------------

def tune_hyperparams_from_table(tuning_df):
    """
    Grid-search (halflife x blend weights x USE_NEGBIN) on `tuning_df`
    (a slice of the precomputed lambda table for training seasons ONLY,
    strictly < S), maximizing total Kicktipp points. Returns the best
    combo as a dict.

    No scipy calls, no DC fits, no per-match dict lookups: every lambda
    is already a column in tuning_df. The inner loops call
    blend.blend_log_lambda / blend.build_final_grid / optimizer per
    match, which are all cheap numpy array ops (~0.15ms/match combined
    per the profiling), so the full 396-combo search runs in well under
    a minute even over several seasons of tuning data.
    """
    best = None
    weight_combos = blend.simplex_grid(step=config.BLEND_STEP)
    n_combos_done = 0
    total_combos = len(config.DC_HALFLIFE_GRID) * 2 * len(weight_combos)

    for halflife in config.DC_HALFLIFE_GRID:
        h_col, a_col, r_col = (
            "lam_dc_h_{0}".format(halflife), "lam_dc_a_{0}".format(halflife), "rho_{0}".format(halflife),
        )
        sub = tuning_df.dropna(subset=[h_col, a_col, r_col])
        if len(sub) == 0:
            continue

        lam_market = sub[["lam_market_h", "lam_market_a"]].to_numpy(dtype=float)
        lam_xg = sub[["lam_xg_h", "lam_xg_a"]].to_numpy(dtype=float)
        lam_dc = sub[[h_col, a_col]].to_numpy(dtype=float)
        rho = sub[r_col].to_numpy(dtype=float)
        results = list(zip(sub["home_goals"].astype(int), sub["away_goals"].astype(int)))

        for use_negbin in (False, True):
            dispersion = (0.05, 0.05) if use_negbin else None
            for weights in weight_combos:
                total_points = 0
                for i in range(len(sub)):
                    lam_h, lam_a = blend.blend_log_lambda(
                        tuple(lam_market[i]), tuple(lam_xg[i]), tuple(lam_dc[i]), weights
                    )
                    grid = blend.build_final_grid(
                        lam_h, lam_a, rho[i], use_negbin=use_negbin, dispersion=dispersion
                    )
                    rec = optimizer.recommend_tip(grid)
                    total_points += optimizer.score_tip(rec["tip"], results[i])
                if best is None or total_points > best["points"]:
                    best = {
                        "halflife": halflife, "use_negbin": use_negbin,
                        "weights": weights, "points": total_points,
                    }
                n_combos_done += 1
                if n_combos_done % 50 == 0:
                    _log("  tuning progress: {0}/{1} combos evaluated (best so far: {2} pts)".format(
                        n_combos_done, total_combos, best["points"] if best else None
                    ))
    return best


# ---------------------------------------------------------------------------
# Full rolling-origin backtest
# ---------------------------------------------------------------------------

def run_backtest(first_season=config.BACKTEST_FIRST, last_season=None):
    table = lambda_table.build_lambda_table()
    table = table.sort_values("kickoff").reset_index(drop=True)

    odds_full = storage.all_odds_d1()
    matches_full = storage.all_understat_matches()
    odds_by_match_id = _join_odds_to_matches(matches_full, odds_full)
    forecast_by_match_id = matches_full.set_index("match_id")[
        ["forecast_win", "forecast_draw", "forecast_loss"]
    ].to_dict(orient="index")

    if last_season is None:
        last_season = int(table["season"].max())

    season_results = {}
    all_rows = []

    for season in range(first_season, last_season + 1):
        _log("=== Season {0} ===".format(season))
        season_rows = table[table["season"] == season]
        train_seasons_window = [
            s for s in range(season - config.DC_TRAIN_SEASONS - 3, season)
            if s in table["season"].unique()
        ]
        tuning_train_seasons = [s for s in train_seasons_window if s < season]
        tuning_df = table[table["season"].isin(tuning_train_seasons)]

        if len(tuning_df) < 100:
            best_params = {
                "halflife": config.DC_HALFLIFE_GRID[1], "use_negbin": False,
                "weights": (1 / 3, 1 / 3, 1 / 3), "points": None,
            }
            _log("season {0}: insufficient tuning history, using flat defaults.".format(season))
        else:
            # Nested: tune only on the last tuning season as a holdout
            # within the training pool, never on season S itself.
            holdout_season = max(tuning_train_seasons)
            best_params = tune_hyperparams_from_table(
                tuning_df[tuning_df["season"] == holdout_season]
            )
        _log("season {0} tuned params: halflife={1} use_negbin={2} weights={3} (pts={4})".format(
            season, best_params["halflife"], best_params["use_negbin"],
            best_params["weights"], best_params["points"]
        ))

        h_col = "lam_dc_h_{0}".format(best_params["halflife"])
        a_col = "lam_dc_a_{0}".format(best_params["halflife"])
        r_col = "rho_{0}".format(best_params["halflife"])
        dispersion = (0.05, 0.05) if best_params["use_negbin"] else None

        for _, row in season_rows.iterrows():
            mid = row["match_id"]
            result = (int(row["home_goals"]), int(row["away_goals"]))

            if pd.isna(row[h_col]) or pd.isna(row[a_col]) or pd.isna(row[r_col]):
                continue

            lam_market = (row["lam_market_h"], row["lam_market_a"])
            lam_xg = (row["lam_xg_h"], row["lam_xg_a"])
            if pd.isna(lam_xg[0]) or pd.isna(lam_xg[1]):
                lam_xg = config.FALLBACK_LAMBDAS
            lam_dc = (row[h_col], row[a_col])
            rho = row[r_col]

            lam_h, lam_a = blend.blend_log_lambda(lam_market, lam_xg, lam_dc, best_params["weights"])
            model_grid = blend.build_final_grid(
                lam_h, lam_a, rho, use_negbin=best_params["use_negbin"], dispersion=dispersion,
            )
            model_rec = optimizer.recommend_tip(model_grid)
            model_points = optimizer.score_tip(model_rec["tip"], result)
            always21_points = optimizer.score_tip((2, 1), result)

            row_out = {
                "match_id": mid, "season": season, "datetime": row["kickoff"],
                "home_team": row["home_team"], "away_team": row["away_team"],
                "home_goals": result[0], "away_goals": result[1],
                "model_tip": model_rec["tip"], "model_points": model_points,
                "always21_points": always21_points,
                "rps": rps_1x2(model_grid, result),
                "exact_hit": int(model_rec["tip"] == result),
                "gd_hit": int((model_rec["tip"][0] - model_rec["tip"][1]) == (result[0] - result[1])),
                "tendency_hit": int(
                    optimizer.tendency(*model_rec["tip"]) == optimizer.tendency(*result)
                ),
            }

            odds_row = odds_by_match_id.get(mid)
            if not (np.isnan(lam_market[0]) or np.isnan(lam_market[1])):
                mkt_grid = market_grid_from_lambdas(lam_market[0], lam_market[1])
                mkt_modal = modal_score(mkt_grid)
                mkt_rec = optimizer.recommend_tip(mkt_grid)
                row_out["market_modal_points"] = optimizer.score_tip(mkt_modal, result)
                row_out["market_ev_points"] = optimizer.score_tip(mkt_rec["tip"], result)
            else:
                row_out["market_modal_points"] = None
                row_out["market_ev_points"] = None

            if odds_row is not None:
                c_grid = closing_odds_grid(odds_row)
                if c_grid is not None:
                    c_rec = optimizer.recommend_tip(c_grid)
                    row_out["closing_ev_points"] = optimizer.score_tip(c_rec["tip"], result)
                else:
                    row_out["closing_ev_points"] = None
            else:
                row_out["closing_ev_points"] = None

            forecast_row = forecast_by_match_id.get(mid)
            f_grid = forecast_grid(forecast_row) if forecast_row is not None else None
            if f_grid is not None:
                f_rec = optimizer.recommend_tip(f_grid)
                row_out["forecast_ev_points"] = optimizer.score_tip(f_rec["tip"], result)
            else:
                row_out["forecast_ev_points"] = None

            all_rows.append(row_out)

        season_df = pd.DataFrame([r for r in all_rows if r["season"] == season])
        season_results[season] = _summarise_season(season_df)
        season_results[season]["tuned_params"] = best_params

    results_df = pd.DataFrame(all_rows)
    return results_df, season_results


def _summarise_season(season_df):
    def _safe_sum(col):
        return float(season_df[col].dropna().sum())

    n = len(season_df)
    return {
        "n_matches": n,
        "model_points": _safe_sum("model_points"),
        "always21_points": _safe_sum("always21_points"),
        "market_modal_points": _safe_sum("market_modal_points"),
        "market_ev_points": _safe_sum("market_ev_points"),
        "closing_ev_points": _safe_sum("closing_ev_points"),
        "forecast_ev_points": _safe_sum("forecast_ev_points"),
        "rps_mean": float(season_df["rps"].mean()),
        "exact_hit_rate": float(season_df["exact_hit"].mean()),
        "gd_hit_rate": float(season_df["gd_hit"].mean()),
        "tendency_hit_rate": float(season_df["tendency_hit"].mean()),
    }


# ---------------------------------------------------------------------------
# Data prep helpers
# ---------------------------------------------------------------------------

def _join_odds_to_matches(matches_df, odds_df):
    """
    Join odds to matches on (harmonised home team, harmonised away team,
    date +/- 1 day). Returns dict match_id -> odds row (as a plain dict).
    Logs join coverage; hard-fails if a completed season has < 95%
    coverage (mirrors Acceptance A's join requirement).
    """
    from src import crosswalk

    odds_df = odds_df.copy()
    odds_df["Date"] = pd.to_datetime(odds_df["Date"])

    known_fd_names = set(odds_df["HomeTeam"]).union(odds_df["AwayTeam"])
    matches_df = matches_df.copy()
    matches_df["home_fd"] = matches_df["home_team"].map(
        lambda n: crosswalk.to_fd_name(n, known_fd_names=known_fd_names)
    )
    matches_df["away_fd"] = matches_df["away_team"].map(
        lambda n: crosswalk.to_fd_name(n, known_fd_names=known_fd_names)
    )

    odds_by_key = {}
    for _, r in odds_df.iterrows():
        key = (r["HomeTeam"], r["AwayTeam"], r["Date"].normalize())
        odds_by_key[key] = r.to_dict()

    result = {}
    matched, total = 0, 0
    coverage_by_season = {}
    for season in sorted(matches_df["season"].unique()):
        s_matches = matches_df[matches_df["season"] == season]
        s_matched = 0
        for _, m in s_matches.iterrows():
            total += 1
            found = None
            target_date = pd.Timestamp(m["datetime"]).normalize()
            for delta in (0, 1, -1):
                key = (m["home_fd"], m["away_fd"], target_date + pd.Timedelta(days=delta))
                if key in odds_by_key:
                    found = odds_by_key[key]
                    break
            if found is not None:
                result[m["match_id"]] = found
                matched += 1
                s_matched += 1
        coverage_by_season[season] = s_matched / len(s_matches) if len(s_matches) else 0.0

    for season, cov in coverage_by_season.items():
        _log("odds join coverage season {0}: {1:.1%}".format(season, cov))
        if cov < 0.95 and season in odds_df.get("season", pd.Series(dtype=int)).unique().tolist():
            raise RuntimeError(
                "Season {0} has only {1:.1%} odds join coverage (< 95% "
                "required for a completed season with odds data).".format(season, cov)
            )

    _log("overall odds join coverage: {0}/{1} = {2:.1%}".format(
        matched, total, matched / total if total else 0.0
    ))
    return result


def write_state(results_df, season_results, last_season):
    os.makedirs(config.STATE_DIR, exist_ok=True)

    final_params = season_results[last_season]["tuned_params"]
    with open(config.TUNED_PARAMS_PATH, "w") as f:
        json.dump({
            "halflife": final_params["halflife"],
            "use_negbin": final_params["use_negbin"],
            "weights": list(final_params["weights"]),
            "as_of_season": last_season,
        }, f, indent=2)

    summary_rows = []
    for season, summ in sorted(season_results.items()):
        row = {"season": season}
        row.update({k: v for k, v in summ.items() if k != "tuned_params"})
        summary_rows.append(row)
    pd.DataFrame(summary_rows).to_csv(
        os.path.join(config.STATE_DIR, "backtest_summary.csv"), index=False
    )
    results_df.to_parquet(os.path.join(config.STATE_DIR, "backtest_matches.parquet"), index=False)


if __name__ == "__main__":
    results_df, season_results = run_backtest()
    last_season = max(season_results.keys())
    write_state(results_df, season_results, last_season)

    print("\n=== Backtest summary ===")
    for season, summ in sorted(season_results.items()):
        print(season, {k: v for k, v in summ.items() if k != "tuned_params"})
