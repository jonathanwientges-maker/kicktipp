"""
One-time ingestion of the pre-supplied seed data (build plan Section 9,
the AMENDMENT) into the project's season-partitioned parquet layout.

Inputs (data/seed/):
    matches.parquet   - 18,085 rows, all leagues, Understat naming
    shots.parquet     - 454,557 rows, shot-level
    odds_cache/D1_2014.csv ... D1_2023.csv - raw football-data.co.uk

Outputs:
    data/understat/season=YYYY/matches.parquet   (season = 2014..2023)
    data/understat/season=YYYY/shots.parquet
    data/odds/season=YYYY/D1.parquet
    data/state/drift_hashes.json   (built from seed data, point 4)

Steps, exactly per the amendment:
  1. Filter matches/shots to league == 'Bundesliga'.
  2. Derive match-level npxG by summing shot npxG per (match_id, home_away).
     shots.home_away plays the role the base plan calls h_a.
  3. Harmonise odds columns (BbAvH -> AvgH etc.), assert >=95% 1X2 + O/U
     coverage per season, report per-season coverage.
  4. Build drift_hashes.json from the seed data itself (first 50
     Bundesliga match_ids of season 2016), before any new scraping.
  5. Pass xG_while_level_h/a and forecast_win/draw/loss through unchanged
     (do not re-derive game-state xG or Understat forecasts).
"""
import hashlib
import json
import os

import pandas as pd

import config
from src import crosswalk, scrape_footballdata, storage

DRIFT_N_MATCHES = 50
DRIFT_SEASON = 2016
MIN_ODDS_COVERAGE = 0.95


def _log(msg):
    print("[ingest_seed] {0}".format(msg))


def load_seed_matches():
    df = pd.read_parquet(config.SEED_MATCHES_PATH)
    df = df[df["league"] == config.LEAGUE].copy()
    return df


def load_seed_shots():
    df = pd.read_parquet(config.SEED_SHOTS_PATH)
    df = df[df["league"] == config.LEAGUE].copy()
    return df


def derive_match_npxg(matches_df, shots_df):
    """
    Derive home_npxG/away_npxG/home_shots/away_shots by summing shots.npxG
    per (match_id, home_away), and merge onto matches_df. npxG excludes
    penalties (shots_df['is_penalty'] already encodes this precisely).
    """
    shots_df = shots_df.copy()
    shots_df["npxG"] = shots_df["xG"].where(~shots_df["is_penalty"], 0.0)

    agg = (
        shots_df.groupby(["match_id", "home_away"])
        .agg(npxG=("npxG", "sum"), shots=("shot_id", "count"))
        .reset_index()
    )
    home = agg[agg["home_away"] == "h"].rename(
        columns={"npxG": "home_npxG", "shots": "home_shots"}
    )[["match_id", "home_npxG", "home_shots"]]
    away = agg[agg["home_away"] == "a"].rename(
        columns={"npxG": "away_npxG", "shots": "away_shots"}
    )[["match_id", "away_npxG", "away_shots"]]

    # Derived npxG/shots supersede any pre-existing columns of the same
    # name in the seed data (Understat's own totals) -- drop them first so
    # the merge doesn't produce _x/_y suffixed duplicates.
    out = matches_df.drop(
        columns=["home_npxG", "away_npxG", "home_shots", "away_shots"],
        errors="ignore",
    )
    out = out.merge(home, on="match_id", how="left")
    out = out.merge(away, on="match_id", how="left")

    # A match_id can be entirely absent from one side of the groupby if
    # that side genuinely recorded zero shots (a real Understat data gap,
    # not a join failure) -- the left merge then leaves NaN where the
    # true value is 0. Distinguish "true zero" (match_id present in
    # shots_df at all) from "no shots data whatsoever for this match"
    # (match_id missing from shots_df entirely, i.e. a real gap that
    # should NOT be silently zero-filled).
    matches_with_any_shots = set(shots_df["match_id"].unique())
    for side, npxg_col, shots_col in (
        ("h", "home_npxG", "home_shots"),
        ("a", "away_npxG", "away_shots"),
    ):
        present_ids = set(agg.loc[agg["home_away"] == side, "match_id"])
        # match_ids with shots data on the OTHER side but zero on this one:
        zero_fill_ids = matches_with_any_shots - present_ids
        mask = out["match_id"].isin(zero_fill_ids)
        n_zero = int(mask.sum())
        if n_zero > 0:
            zero_matches = out.loc[mask, ["match_id", "home_team", "away_team"]]
            _log(
                "WARNING: {0} match(es) have zero recorded shots on the "
                "'{1}' side (Understat data gap, not a join failure) -- "
                "npxG/shots set to 0 for: {2}".format(
                    n_zero, side,
                    ", ".join(
                        "{0} ({1} vs {2})".format(r.match_id, r.home_team, r.away_team)
                        for r in zero_matches.itertuples()
                    ),
                )
            )
        out.loc[mask, npxg_col] = out.loc[mask, npxg_col].fillna(0.0)
        out.loc[mask, shots_col] = out.loc[mask, shots_col].fillna(0)

    # Any match_id still NaN after that (i.e. missing from shots_df on
    # BOTH sides -- no shot data at all) is a genuine gap; leave as NaN so
    # it surfaces downstream rather than being silently treated as 0.
    still_null = out[out["home_npxG"].isna() | out["away_npxG"].isna()]
    if len(still_null) > 0:
        _log(
            "WARNING: {0} match(es) have NO shot data at all (neither side) "
            "and remain NaN for npxG -- these will need fallback handling "
            "downstream: match_ids {1}".format(
                len(still_null), still_null["match_id"].tolist()
            )
        )

    return out


def build_matches_schema(matches_df):
    """
    Select/rename into the project's canonical matches schema, passing
    through xG_while_level_h/a and forecast_win/draw/loss unchanged
    (amendment point 5).
    """
    cols = {
        "match_id": "match_id",
        "season": "season",
        "datetime": "datetime",
        "home_team": "home_team",
        "away_team": "away_team",
        "home_goals": "home_goals",
        "away_goals": "away_goals",
        "home_xG": "home_xG",
        "away_xG": "away_xG",
        "home_npxG": "home_npxG",
        "away_npxG": "away_npxG",
        "home_shots": "home_shots",
        "away_shots": "away_shots",
    }
    passthrough = [
        "xG_while_level_h", "xG_while_level_a",
        "xG_while_winning_h", "xG_while_winning_a",
        "xG_while_losing_h", "xG_while_losing_a",
        "forecast_win", "forecast_draw", "forecast_loss",
        "home_xPTS", "away_xPTS",
        "home_shot_on_target", "away_shot_on_target",
        "home_deep", "away_deep", "home_PPDA", "away_PPDA",
    ]
    out_cols = list(cols.values()) + [c for c in passthrough if c in matches_df.columns]
    renamed = matches_df.rename(columns=cols)
    return renamed[out_cols].copy()


def harmonise_team_names(matches_df):
    """Harmonise Understat home/away team names against a per-season known
    football-data team-name universe once odds are loaded (validated at
    join time in join.py). Here we just ensure crosswalk keys resolve."""
    understat_names = set(matches_df["home_team"]).union(matches_df["away_team"])
    unresolved = [n for n in understat_names if n not in crosswalk.UNDERSTAT_TO_FD]
    # Names not in the crosswalk dict are assumed identity-mapped; that's
    # fine here, actual hard-fail validation happens against FD names in
    # the join step (src/crosswalk.validate_fd_name).
    _log(
        "{0} distinct Understat team names, {1} via explicit crosswalk, "
        "{2} assumed identity.".format(
            len(understat_names),
            len(understat_names) - len(unresolved),
            len(unresolved),
        )
    )
    return matches_df


def ingest_odds():
    """
    Load and harmonise all seed odds CSVs, assert coverage, write
    season-partitioned parquets. Returns per-season coverage report dict.
    """
    seed_odds = scrape_footballdata.load_all_seed_odds()
    coverage_report = {}
    for season, df in sorted(seed_odds.items()):
        df = scrape_footballdata.parse_date_column(df, date_col="Date")
        n = len(df)

        has_1x2 = df[config.COLS_1X2].notna().any(axis=1) if any(
            c in df.columns for c in config.COLS_1X2
        ) else pd.Series([False] * n)
        has_ou = df[[c for c in config.COLS_OU if c in df.columns]].notna().any(axis=1) if any(
            c in df.columns for c in config.COLS_OU
        ) else pd.Series([False] * n)

        both = (has_1x2 & has_ou).sum()
        coverage = both / n if n else 0.0
        coverage_report[season] = {
            "n_matches": n,
            "coverage_1x2_and_ou": coverage,
            "coverage_1x2_only": has_1x2.mean() if n else 0.0,
            "coverage_ou_only": has_ou.mean() if n else 0.0,
        }
        _log(
            "season {0}: n={1}, 1X2&OU coverage={2:.1%} (1X2 only={3:.1%}, "
            "O/U only={4:.1%})".format(
                season, n, coverage,
                coverage_report[season]["coverage_1x2_only"],
                coverage_report[season]["coverage_ou_only"],
            )
        )
        if coverage < MIN_ODDS_COVERAGE:
            raise RuntimeError(
                "Season {0} has only {1:.1%} matches with both usable 1X2 "
                "and O/U odds (< {2:.0%} required). Check odds column "
                "harmonisation in scrape_footballdata.py.".format(
                    season, coverage, MIN_ODDS_COVERAGE
                )
            )

        keep = scrape_footballdata.select_feature_columns(df)
        storage.write_odds_d1(keep, season)

    return coverage_report


def build_drift_hashes(matches_df):
    """
    Amendment point 4: build drift_hashes.json from the seed data itself
    (first 50 Bundesliga match_ids of season 2016, ordered by kickoff
    datetime), before any new scraping.
    """
    season_df = matches_df[matches_df["season"] == DRIFT_SEASON].sort_values("datetime")
    subset = season_df.head(DRIFT_N_MATCHES)
    if len(subset) < DRIFT_N_MATCHES:
        raise RuntimeError(
            "Expected >= {0} matches in season {1} for drift hashing, "
            "found {2}.".format(DRIFT_N_MATCHES, DRIFT_SEASON, len(subset))
        )

    hashes = {}
    for _, row in subset.iterrows():
        pair_str = "{0:.6f},{1:.6f}".format(row["home_xG"], row["away_xG"])
        h = hashlib.sha256(pair_str.encode("utf-8")).hexdigest()
        hashes[str(int(row["match_id"]))] = h

    payload = {
        "season": DRIFT_SEASON,
        "n_matches": DRIFT_N_MATCHES,
        "match_ids": [int(x) for x in subset["match_id"].tolist()],
        "hashes": hashes,
    }
    os.makedirs(config.STATE_DIR, exist_ok=True)
    with open(config.DRIFT_HASHES_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    _log("Wrote drift hashes for {0} matches from season {1} to {2}".format(
        DRIFT_N_MATCHES, DRIFT_SEASON, config.DRIFT_HASHES_PATH
    ))
    return payload


def run():
    _log("Loading seed matches + shots...")
    matches_df = load_seed_matches()
    shots_df = load_seed_shots()
    _log("Seed matches (Bundesliga): {0} rows".format(len(matches_df)))
    _log("Seed shots (Bundesliga): {0} rows".format(len(shots_df)))

    matches_df = derive_match_npxg(matches_df, shots_df)
    matches_df = build_matches_schema(matches_df)
    matches_df = harmonise_team_names(matches_df)

    seasons = sorted(matches_df["season"].unique())
    _log("Seasons present: {0}".format(seasons))

    for season in seasons:
        season_matches = matches_df[matches_df["season"] == season].reset_index(drop=True)
        season_shots = shots_df[shots_df["match_id"].isin(season_matches["match_id"])]
        n = len(season_matches)
        if not (250 <= n <= 400):
            raise RuntimeError(
                "Season {0} has {1} matches; expected between 250 and 400 "
                "(306 typical).".format(season, n)
            )
        storage.write_understat_matches(season_matches, season)
        storage.write_understat_shots(season_shots, season)
        _log("season={0}: {1} matches, {2} shots written".format(
            season, n, len(season_shots)
        ))

    _log("Ingesting seed odds (D1 2014-2023)...")
    coverage_report = ingest_odds()

    _log("Building drift hashes from seed data...")
    build_drift_hashes(matches_df)

    _log("Seed ingestion complete.")
    return {
        "seasons": seasons,
        "odds_coverage": coverage_report,
    }


if __name__ == "__main__":
    run()
