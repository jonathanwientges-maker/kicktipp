"""
Bootstrap gap scrape (Section 9 amendment, point 1). Runs ONCE via the
bootstrap.yml workflow, after src.ingest_seed has populated seasons
2014-2023 from the seed files.

Scrapes exactly the gap:
    - Understat seasons 2024, 2025 (config.GAP_SEASONS) -- ~612 matches +
      their shot pages.
    - football-data D1_2024.csv, D1_2025.csv.
    - football-data D2_*.csv for ALL seasons 2014-2025 (config.D2_SEASONS)
      -- never seeded, needed for the promoted-team prior regression (B2).

Aborts (non-zero exit) on any persistent scrape failure -- no silent
partial bootstrap.
"""
import config
from src import scrape_footballdata, scrape_understat, storage


def _log(msg):
    print("[bootstrap_gap] {0}".format(msg))


def scrape_understat_gap_seasons():
    for season in config.GAP_SEASONS:
        _log("Scraping Understat season {0}...".format(season))
        existing = storage.understat_matches(season)
        existing_ids = set(existing["match_id"]) if existing is not None else set()

        matches_df, shots_df = scrape_understat.scrape_season(
            config.LEAGUE, season, existing_match_ids=existing_ids
        )
        if len(matches_df) == 0:
            _log("WARNING: season {0} returned 0 matches (season may not "
                 "have started yet) -- skipping write.".format(season))
            continue

        if existing is not None and len(existing) > 0:
            prior_shots = storage.understat_shots(season)
            if prior_shots is not None and len(prior_shots) > 0:
                import pandas as pd
                shots_df = pd.concat([prior_shots, shots_df], ignore_index=True)

            # scrape_understat.scrape_season() always re-fetches the full
            # match list (goals/xG/forecast refresh correctly every run),
            # but only fetches home_npxG/away_npxG/home_shots/away_shots
            # for match_ids NOT already in existing_ids -- for match_ids
            # that already existed, those 4 columns come back NaN from the
            # merge (nothing was re-fetched for them, by design, to avoid
            # redundant network calls). Left as-is, re-running this
            # function on a repo that already has a prior *complete*
            # scrape committed would silently OVERWRITE good npxG/shots
            # data with NaN for every previously-scraped match -- this is
            # exactly what happened on a real GitHub Actions run (a
            # checkpoint commit made mid-run meant a later re-invocation
            # in the same job saw "everything already exists" and wiped
            # 611 matches' npxG to NaN, corrupting the promoted-team-prior
            # regression, which needs real npxG to fit). Backfill those 4
            # columns from `existing` for any match_id that was already
            # present, so only genuinely-new matches get NaN (to be
            # filled by the next incremental run, same as the live weekly
            # pipeline's normal operation).
            npxg_cols = ["home_npxG", "away_npxG", "home_shots", "away_shots"]
            existing_lookup = existing.set_index("match_id")[npxg_cols]
            matches_df = matches_df.set_index("match_id")
            for col in npxg_cols:
                already_had_data = matches_df.index.isin(existing_lookup.index) & matches_df[col].isna()
                matches_df.loc[already_had_data, col] = existing_lookup.loc[
                    matches_df.index[already_had_data], col
                ].values
            matches_df = matches_df.reset_index()

        storage.write_understat_matches(matches_df, season)
        storage.write_understat_shots(shots_df, season)
        _log("season {0}: {1} matches, {2} shots written.".format(
            season, len(matches_df), len(shots_df)
        ))


def scrape_d1_gap_seasons():
    for season in config.GAP_SEASONS:
        _log("Downloading D1 odds for season {0}...".format(season))
        try:
            df = scrape_footballdata.download_division_csv(season, "D1")
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "Failed to download D1_{0}.csv: {1}. Aborting bootstrap "
                "(no silent partial data).".format(season, exc)
            )
        df = scrape_footballdata.parse_date_column(df, date_col="Date")
        keep = scrape_footballdata.select_feature_columns(df)
        storage.write_odds_d1(keep, season)
        _log("season {0}: {1} D1 odds rows written.".format(season, len(keep)))


def scrape_d2_all_seasons():
    for season in config.D2_SEASONS:
        _log("Downloading D2 odds/results for season {0}...".format(season))
        try:
            df = scrape_footballdata.download_division_csv(season, "D2")
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "Failed to download D2_{0}.csv: {1}. Aborting bootstrap "
                "(no silent partial data).".format(season, exc)
            )
        df = scrape_footballdata.parse_date_column(df, date_col="Date")
        keep = scrape_footballdata.select_feature_columns(df)
        storage.write_odds_d2(keep, season)
        _log("season {0}: {1} D2 rows written.".format(season, len(keep)))


def run():
    _log("Starting gap bootstrap scrape...")
    scrape_understat_gap_seasons()
    scrape_d1_gap_seasons()
    scrape_d2_all_seasons()
    _log("Gap bootstrap scrape complete.")


if __name__ == "__main__":
    run()
