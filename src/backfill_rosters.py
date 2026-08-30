"""
Backfill enriched shots (§1.1: player_id, player_assisted, lastAction) and
rosters (§1.2) for one or more already-scraped Understat seasons.

`workflow_dispatch`-only via .github/workflows/backfill_rosters.yml. For
each requested season it re-scrapes every match page (respecting
config.UNDERSTAT_DELAY_S), rewrites that season's shots.parquet with the
enriched columns and writes rosters.parquet alongside it.

Idempotent: a season whose shots already carry player_id/player_assisted/
lastAction AND that already has a rosters.parquet is SKIPPED unless
--force is passed.

Seasons 2014-2023 already carry the three enriched shot columns from the
seed but have no rosters -- they are in scope for a manual run of this
script (pass --seasons "2014,2015,..."), not run automatically.

Python 3.9 compatible.
"""
import argparse
import sys

import pandas as pd

import config
from src import scrape_understat, storage

_ENRICHED_SHOT_COLS = {"player_id", "player_assisted", "lastAction"}


def _log(msg):
    print("[backfill_rosters] {0}".format(msg))


def _season_already_done(season):
    shots = storage.understat_shots(season)
    rosters = storage.understat_rosters(season)
    if shots is None or rosters is None or len(rosters) == 0:
        return False
    return _ENRICHED_SHOT_COLS.issubset(set(shots.columns))


def backfill_season(season, force=False):
    if not force and _season_already_done(season):
        _log("season {0} already enriched + has rosters -- skipping "
             "(pass --force to re-scrape).".format(season))
        return

    matches = storage.understat_matches(season)
    if matches is None or len(matches) == 0:
        _log("season {0}: no matches.parquet -- nothing to backfill.".format(season))
        return

    match_ids = list(matches["match_id"])
    _log("season {0}: re-scraping {1} match pages...".format(season, len(match_ids)))

    warnings = []
    npxg_df, shots_df, rosters_df = scrape_understat.build_match_npxg_shots_rosters(
        match_ids, season, warnings
    )
    for w in warnings:
        _log("WARNING: {0}".format(w))

    # Refresh the derived per-match npxG/shot counts on matches.parquet too,
    # so it stays consistent with the freshly re-scraped shots.
    matches = matches.drop(
        columns=[c for c in ("home_npxG", "away_npxG", "home_shots", "away_shots")
                 if c in matches.columns]
    ).merge(npxg_df, on="match_id", how="left")

    storage.write_understat_matches(matches, season)
    storage.write_understat_shots(shots_df, season)
    storage.write_understat_rosters(rosters_df, season)
    _log("season {0}: wrote {1} shot rows, {2} roster rows.".format(
        season, len(shots_df), len(rosters_df)
    ))


def parse_seasons(raw):
    out = []
    for tok in raw.split(","):
        tok = tok.strip()
        if not tok:
            continue
        out.append(int(tok))
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seasons", default="2024,2025",
                        help="comma-separated Understat season years")
    parser.add_argument("--force", action="store_true",
                        help="re-scrape even if the season already looks complete")
    args = parser.parse_args(argv)

    seasons = parse_seasons(args.seasons)
    if not seasons:
        _log("no seasons parsed from {0!r} -- nothing to do.".format(args.seasons))
        return 1

    for season in seasons:
        backfill_season(season, force=args.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
