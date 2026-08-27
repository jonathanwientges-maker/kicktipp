"""
Acceptance A hard rule: no closing-odds columns (PSCH, AvgCH, PC>2.5,
AHCh, ...) may ever appear in any feature dataframe used for modelling.

This scans:
  1. The regex itself against known closing/AH column name examples
     (positive control) and known allowed pre-match column names
     (negative control).
  2. Every ingested odds parquet actually on disk (data/odds/season=*/
     D1.parquet) -- the real enforcement, run against whatever the
     pipeline has produced.
"""
import glob
import os
import re

import pandas as pd

import config

CLOSING_EXAMPLES = [
    "PSCH", "PSCD", "PSCA", "AvgCH", "AvgCD", "AvgCA", "MaxCH",
    "B365CH", "B365C>2.5", "B365C<2.5", "AvgC>2.5", "MaxC<2.5",
    "BbAH", "BbAHh", "BbMxAHH", "BbAvAHH", "BbMxAHA", "BbAvAHA",
    "B365AHH", "B365AHA", "MaxAHH", "MaxAHA", "AvgAHH", "AvgAHA",
]

ALLOWED_EXAMPLES = [
    "PSH", "PSD", "PSA", "AvgH", "AvgD", "AvgA", "B365H", "B365D", "B365A",
    "P>2.5", "P<2.5", "Avg>2.5", "Avg<2.5", "B365>2.5", "B365<2.5",
    "HS", "AS", "HST", "AST", "Date", "Time", "HomeTeam", "AwayTeam",
    "FTHG", "FTAG", "FTR",
]


def test_regex_flags_all_known_closing_and_ah_columns():
    for col in CLOSING_EXAMPLES:
        assert re.search(config.CLOSING_ODDS_REGEX, col), (
            "Closing/AH column '{0}' was NOT flagged by CLOSING_ODDS_REGEX".format(col)
        )


def test_regex_does_not_flag_allowed_columns():
    for col in ALLOWED_EXAMPLES:
        assert not re.search(config.CLOSING_ODDS_REGEX, col), (
            "Allowed pre-match column '{0}' was incorrectly flagged as closing/AH".format(col)
        )


def test_no_closing_odds_columns_in_ingested_odds_parquets():
    pattern = os.path.join(config.ODDS_DIR, "season=*", "*.parquet")
    paths = glob.glob(pattern)
    if not paths:
        import pytest
        pytest.skip("No ingested odds parquets on disk yet -- run ingestion first.")
    for path in paths:
        df = pd.read_parquet(path)
        offending = [c for c in df.columns if re.search(config.CLOSING_ODDS_REGEX, c)]
        assert not offending, "Closing/AH odds columns found in {0}: {1}".format(path, offending)


def test_select_feature_columns_excludes_closing_and_ah():
    from src import scrape_footballdata
    raw = pd.DataFrame({c: [1.5] for c in CLOSING_EXAMPLES + ALLOWED_EXAMPLES})
    kept = scrape_footballdata.select_feature_columns(raw)
    offending = [c for c in kept.columns if re.search(config.CLOSING_ODDS_REGEX, c)]
    assert not offending
