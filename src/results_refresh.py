"""
D1 step 6 / results_refresh.yml entrypoint: after results arrive, score
the previously recommended tips and append to data/state/season_points.csv
(model vs. always-2-1 vs. market-EV, cumulative).

Refreshes current-season data first (so newly played matches are picked
up), then finds fixtures that now have a final result but were not yet
scored, computes what the model recommended for them (re-deriving the
same prediction the weekly run would have made, using data strictly
before that match), and appends one row per newly-completed match.
"""
import json
import os

import pandas as pd

import config
from src import (
    blend,
    dixon_coles as dc,
    features,
    market,
    optimizer,
    predict as predict_mod,
    scrape_footballdata,
    scrape_understat,
    storage,
)


def _log(msg):
    print("[results_refresh] {0}".format(msg))


def load_season_points():
    if os.path.exists(config.SEASON_POINTS_PATH):
        return pd.read_csv(config.SEASON_POINTS_PATH)
    return pd.DataFrame(columns=[
        "match_id", "season", "datetime", "home_team", "away_team",
        "model_tip", "model_points", "always21_points", "market_ev_points",
        "exact_hit", "gd_hit", "tendency_hit",
    ])


def refresh_and_score():
    warnings = []
    season = config.CURRENT_SEASON

    _log("Refreshing current-season data...")
    predict_mod.refresh_current_season_data(season, warnings)
    for w in warnings:
        _log("WARNING: {0}".format(w))

    matches, shots, odds = predict_mod.build_full_history()
    tuned = predict_mod.load_tuned_params()

    already_scored = load_season_points()
    scored_ids = set(already_scored["match_id"]) if len(already_scored) else set()

    season_matches = matches[matches["season"] == season].sort_values("datetime")
    newly_completed = season_matches[~season_matches["match_id"].isin(scored_ids)]

    if len(newly_completed) == 0:
        _log("No newly-completed matches to score.")
        return already_scored

    xg_enriched = features.compute_lambda_xg(matches, shots)
    xg_lookup = {
        r["match_id"]: (r["lambda_xg_h"], r["lambda_xg_a"])
        for _, r in xg_enriched.iterrows()
    }

    odds_by_id = _index_odds(odds)

    new_rows = []
    for _, m in newly_completed.iterrows():
        mid = m["match_id"]
        as_of = pd.Timestamp(m["datetime"])
        history_before = matches[matches["datetime"] < as_of]
        if len(history_before) < 50:
            continue  # not enough history to have made a real prediction

        dc_fit = dc.fit_dixon_coles(history_before, as_of, halflife=tuned["halflife"])

        lam_market = market.compute_market_lambdas(odds_by_id.get(mid, {}))
        lam_xg = xg_lookup.get(mid, config.FALLBACK_LAMBDAS)
        if pd.isna(lam_xg[0]) or pd.isna(lam_xg[1]):
            lam_xg = config.FALLBACK_LAMBDAS
        lam_dc = dc.dc_lambdas(dc_fit, m["home_team"], m["away_team"])

        lam_h, lam_a = blend.blend_log_lambda(
            lam_market, lam_xg, lam_dc, tuple(tuned["weights"])
        )
        dispersion = (0.05, 0.05) if tuned.get("use_negbin") else None
        grid = blend.build_final_grid(
            lam_h, lam_a, dc_fit["rho"], use_negbin=tuned.get("use_negbin", False),
            dispersion=dispersion,
        )
        rec = optimizer.recommend_tip(grid, draw_margin=tuned.get("draw_margin", config.DRAW_MARGIN))
        result = (int(m["home_goals"]), int(m["away_goals"]))
        model_points = optimizer.score_tip(rec["tip"], result)
        always21_points = optimizer.score_tip((2, 1), result)

        market_ev_points = None
        odds_row = odds_by_id.get(mid)
        if odds_row:
            mkt_lam_h, mkt_lam_a = market.compute_market_lambdas(odds_row)
            if not pd.isna(mkt_lam_h):
                from scipy.stats import poisson
                import numpy as np
                hg = np.arange(0, config.GRID_MAX_GOALS + 1)
                mkt_grid = np.outer(poisson.pmf(hg, mkt_lam_h), poisson.pmf(hg, mkt_lam_a))
                mkt_grid = mkt_grid / mkt_grid.sum()
                mkt_rec = optimizer.recommend_tip(mkt_grid)
                market_ev_points = optimizer.score_tip(mkt_rec["tip"], result)

        new_rows.append({
            "match_id": mid, "season": season, "datetime": m["datetime"],
            "home_team": m["home_team"], "away_team": m["away_team"],
            "model_tip": "{0}-{1}".format(*rec["tip"]), "model_points": model_points,
            "always21_points": always21_points, "market_ev_points": market_ev_points,
            "exact_hit": int(rec["tip"] == result),
            "gd_hit": int((rec["tip"][0] - rec["tip"][1]) == (result[0] - result[1])),
            "tendency_hit": int(
                optimizer.tendency(*rec["tip"]) == optimizer.tendency(*result)
            ),
        })

    if not new_rows:
        _log("No matches had sufficient history to score.")
        return already_scored

    updated = pd.concat([already_scored, pd.DataFrame(new_rows)], ignore_index=True)
    os.makedirs(config.STATE_DIR, exist_ok=True)
    updated.to_csv(config.SEASON_POINTS_PATH, index=False)
    _log("Scored {0} newly-completed match(es); season_points.csv now has {1} rows.".format(
        len(new_rows), len(updated)
    ))
    return updated


def _index_odds(odds_df):
    """Index odds rows by match via a simple (home,away,date) key, reusing
    the same tolerant matching as backtest._join_odds_to_matches but
    returning a flat dict for direct lookup convenience here."""
    from src.backtest import _join_odds_to_matches
    matches = storage.all_understat_matches(seasons=[config.CURRENT_SEASON])
    if len(matches) == 0:
        return {}
    return _join_odds_to_matches(matches, odds_df)


if __name__ == "__main__":
    refresh_and_score()
