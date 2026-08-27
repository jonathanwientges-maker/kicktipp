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


def _fetch_csv_bytes(url):
    """
    Returns the response body as RAW BYTES (not requests' auto-decoded
    .text). fixtures.csv is served with a UTF-8 BOM (b'\\xef\\xbb\\xbf')
    prefixed to the content; requests' .text decodes those bytes but
    does NOT strip the BOM, leaving it as three literal mojibake
    characters ('\\ufeff' rendered as "ï»¿") baked into the returned
    string. Re-encoding that already-decoded string can't recover the
    original BOM byte sequence, so downstream BOM-aware decoding
    (encoding="utf-8-sig") only works if it operates on these original
    bytes, not on .text. Callers must decode via _read_csv_bytes, not a
    plain .decode("utf-8").
    """
    last_err = None
    for attempt in range(_RETRIES):
        try:
            resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
            resp.raise_for_status()
            # raise_for_status() only raises on 4xx/5xx -- football-data.co.uk
            # returns a 300 Multiple Choices HTML "did you mean...?" page
            # (not a CSV, and not a 4xx/5xx) when a season's file doesn't
            # exist yet at the expected path (observed for a just-started
            # season whose D1.csv hadn't been published yet, while D2.csv
            # for the same season already existed). Silently handing that
            # HTML to pd.read_csv produces a confusing "Error tokenizing
            # data" exception instead of a clear "this file isn't
            # available" one -- require a plain 200 explicitly.
            if resp.status_code != 200:
                raise RuntimeError(
                    "Unexpected HTTP {0} for {1} (expected 200) -- the file may "
                    "not be published yet.".format(resp.status_code, url)
                )
            return resp.content
        except Exception as exc:  # noqa: BLE001 - deliberate broad retry
            last_err = exc
            if attempt < _RETRIES - 1:
                time.sleep(_BACKOFF_BASE ** attempt)
    raise RuntimeError(
        "Failed to fetch {0} after {1} retries: {2}".format(url, _RETRIES, last_err)
    )


def _read_csv_bytes(raw_bytes):
    """
    Parse CSV raw bytes from football-data.co.uk. fixtures.csv (and
    possibly other files) is served with a UTF-8 BOM prefix -- pandas
    leaves that BOM attached to the first column's name if not told
    about it (producing a literal '\\ufeffDiv' column instead of 'Div',
    which silently breaks any df["Div"] lookup with a KeyError that
    doesn't obviously point at the real cause). utf-8-sig strips a
    leading BOM if present and is a no-op otherwise, so this is always
    safe to use -- but it MUST be given the original bytes (see
    _fetch_csv_bytes's docstring for why passing an already-.text-decoded
    string doesn't work).
    """
    return pd.read_csv(io.BytesIO(raw_bytes), encoding="utf-8-sig")


def download_division_csv(season, division):
    """
    Download the raw CSV for a given season/division (e.g. 'D1', 'D2') from
    football-data.co.uk and return it as a DataFrame with harmonised odds
    column names. Raises on persistent failure (no silent skip).
    """
    yy = _season_to_yy_pair(season)
    url = "{0}/mmz4281/{1}/{2}.csv".format(config.FD_BASE, yy, division)
    raw_bytes = _fetch_csv_bytes(url)
    df = _read_csv_bytes(raw_bytes)
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
    raw_bytes = _fetch_csv_bytes(url)
    df = _read_csv_bytes(raw_bytes)
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
    df = pd.read_csv(path, encoding="utf-8-sig")
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
