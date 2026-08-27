"""
football-data.co.uk downloader + odds column harmonisation.

Historical/current-season match+odds CSVs (D1 = Bundesliga, D2 = 2.
Bundesliga) and the forward fixtures.csv (upcoming matches + odds).

Per the AMENDMENT (build plan Section 9): seasons 2014-2023 D1 odds are
already available as seed CSVs (data/seed/odds_cache/D1_2014.csv ...
D1_2023.csv) and are NOT re-downloaded. This module downloads only:
  - D1_2024.csv, D1_2025.csv (the gap seasons)
  - D2_*.csv for ALL seasons 2014-2025 (never seeded)
  - fixtures.csv (forward fixtures, every run)
  - current-season D1 (re-downloaded fully every run once season is live)

Column harmonisation renames legacy Betbrain-prefixed columns (BbAvH,
BbMxH, BbAv>2.5, ...) to their modern equivalents (AvgH, MaxH, Avg>2.5,
...) so a single COLS_1X2 / COLS_OU lookup works across all seasons.
"""
import io
import os
import time

import pandas as pd
import requests

import config

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

_RETRIES = 3
_BACKOFF_BASE = 2.0


def _season_to_yy_pair(season):
    """2014 -> ('1415'), i.e. the two-digit start/end pair FD uses in URLs."""
    yy1 = season % 100
    yy2 = (season + 1) % 100
    return "{0:02d}{1:02d}".format(yy1, yy2)


def _fetch_csv_text(url):
    last_err = None
    for attempt in range(_RETRIES):
        try:
            resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
            resp.raise_for_status()
            return resp.text
        except Exception as exc:  # noqa: BLE001 - deliberate broad retry
            last_err = exc
            if attempt < _RETRIES - 1:
                time.sleep(_BACKOFF_BASE ** attempt)
    raise RuntimeError(
        "Failed to fetch {0} after {1} retries: {2}".format(url, _RETRIES, last_err)
    )


def download_division_csv(season, division):
    """
    Download the raw CSV for a given season/division (e.g. 'D1', 'D2') from
    football-data.co.uk and return it as a DataFrame with harmonised odds
    column names. Raises on persistent failure (no silent skip).
    """
    yy = _season_to_yy_pair(season)
    url = "{0}/mmz4281/{1}/{2}.csv".format(config.FD_BASE, yy, division)
    text = _fetch_csv_text(url)
    df = pd.read_csv(io.StringIO(text))
    df = harmonise_odds_columns(df)
    df["season"] = season
    df["division"] = division
    return df


def download_fixtures_csv():
    """
    Download the forward fixtures file (all divisions, all leagues) and
    filter to Bundesliga (Div == 'D1'). This is the source of upcoming
    fixtures AND their pre-match odds.
    """
    url = "{0}/fixtures.csv".format(config.FD_BASE)
    text = _fetch_csv_text(url)
    df = pd.read_csv(io.StringIO(text))
    df = df[df["Div"] == "D1"].copy()
    df = harmonise_odds_columns(df)
    return df


def harmonise_odds_columns(df):
    """
    Rename legacy Betbrain-prefixed odds columns to their modern
    equivalents, per config.LEGACY_ODDS_RENAME. Only renames columns that
    exist and does not overwrite a modern column that is already present.
    """
    rename_map = {}
    for old, new in config.LEGACY_ODDS_RENAME.items():
        if old in df.columns and new not in df.columns:
            rename_map[old] = new
    if rename_map:
        df = df.rename(columns=rename_map)
    return df


def parse_date_column(df, date_col="Date"):
    """
    football-data.co.uk dates are dd/mm/yy in older files and dd/mm/yyyy
    in newer ones. Parse both by string length, per-row.
    """
    def _parse_one(s):
        if pd.isna(s):
            return pd.NaT
        s = str(s).strip()
        fmt = "%d/%m/%Y" if len(s) == 10 else "%d/%m/%y"
        return pd.to_datetime(s, format=fmt)

    df = df.copy()
    df[date_col] = df[date_col].map(_parse_one)
    return df


def select_feature_columns(df):
    """
    Keep only the columns the pipeline is allowed to use: identity/result
    columns, shots, 1X2 odds, O/U odds. Explicitly excludes AH and closing
    odds even if present (defence in depth alongside the unit test).
    """
    keep = ["Date", "Time", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR"]
    keep += [c for c in config.COLS_SHOTS if c in df.columns]
    keep += [c for c in config.COLS_1X2 if c in df.columns]
    keep += [c for c in config.COLS_OU if c in df.columns]
    keep = [c for c in keep if c in df.columns]
    return df[keep].copy()


def load_seed_odds_csv(path):
    """Load one of the pre-supplied data/seed/odds_cache/D1_YYYY.csv files
    and apply the same harmonisation as freshly downloaded files."""
    df = pd.read_csv(path)
    df = harmonise_odds_columns(df)
    return df


def load_all_seed_odds():
    """Load every seed odds CSV (D1_2014..D1_2023) into one dict
    {season: DataFrame}, harmonised."""
    out = {}
    if not os.path.isdir(config.SEED_ODDS_DIR):
        return out
    for fname in sorted(os.listdir(config.SEED_ODDS_DIR)):
        if not fname.startswith("D1_") or not fname.endswith(".csv"):
            continue
        season = int(fname[len("D1_"):-len(".csv")])
        out[season] = load_seed_odds_csv(os.path.join(config.SEED_ODDS_DIR, fname))
    return out
