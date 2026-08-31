"""
Season-partitioned parquet storage for Understat and odds data.

Layout (per config.py):
    data/understat/season=YYYY/matches.parquet
    data/understat/season=YYYY/shots.parquet
    data/odds/season=YYYY/D1.parquet
    data/odds/season=YYYY/D2.parquet

All reads/writes go through this module so the partition layout is defined
in exactly one place.
"""
import glob
import os

import pandas as pd

import config


def season_dir(base_dir, season):
    return os.path.join(base_dir, "season={0}".format(season))


def write_parquet(df, base_dir, season, name):
    """Write `df` to base_dir/season={season}/{name}.parquet, creating dirs."""
    d = season_dir(base_dir, season)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "{0}.parquet".format(name))
    df.to_parquet(path, index=False)
    return path


def read_parquet(base_dir, season, name):
    path = os.path.join(season_dir(base_dir, season), "{0}.parquet".format(name))
    if not os.path.exists(path):
        return None
    return pd.read_parquet(path)


def available_seasons(base_dir):
    """List season ints present under base_dir as season=YYYY partitions."""
    pattern = os.path.join(base_dir, "season=*")
    seasons = []
    for p in glob.glob(pattern):
        base = os.path.basename(p)
        try:
            seasons.append(int(base.split("=", 1)[1]))
        except (IndexError, ValueError):
            continue
    return sorted(seasons)


def read_all_seasons(base_dir, name, seasons=None):
    """Concatenate a given parquet `name` across all (or given) seasons."""
    if seasons is None:
        seasons = available_seasons(base_dir)
    frames = []
    for s in seasons:
        df = read_parquet(base_dir, s, name)
        if df is not None and len(df) > 0:
            frames.append(df)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def understat_matches(season):
    return read_parquet(config.UNDERSTAT_DIR, season, "matches")


def understat_shots(season):
    return read_parquet(config.UNDERSTAT_DIR, season, "shots")


def write_understat_matches(df, season):
    return write_parquet(df, config.UNDERSTAT_DIR, season, "matches")


def write_understat_shots(df, season):
    return write_parquet(df, config.UNDERSTAT_DIR, season, "shots")


def understat_rosters(season):
    return read_parquet(config.UNDERSTAT_DIR, season, "rosters")


def write_understat_rosters(df, season):
    return write_parquet(df, config.UNDERSTAT_DIR, season, "rosters")


def understat_team_stats(season):
    return read_parquet(config.UNDERSTAT_DIR, season, "team_stats")


def write_understat_team_stats(df, season):
    return write_parquet(df, config.UNDERSTAT_DIR, season, "team_stats")


def understat_fixtures(season):
    return read_parquet(config.UNDERSTAT_DIR, season, "fixtures")


def write_understat_fixtures(df, season):
    return write_parquet(df, config.UNDERSTAT_DIR, season, "fixtures")


def odds_d1(season):
    return read_parquet(config.ODDS_DIR, season, "D1")


def odds_d2(season):
    return read_parquet(config.ODDS_DIR, season, "D2")


def write_odds_d1(df, season):
    return write_parquet(df, config.ODDS_DIR, season, "D1")


def write_odds_d2(df, season):
    return write_parquet(df, config.ODDS_DIR, season, "D2")


def all_understat_matches(seasons=None):
    return read_all_seasons(config.UNDERSTAT_DIR, "matches", seasons=seasons)


def all_understat_shots(seasons=None):
    return read_all_seasons(config.UNDERSTAT_DIR, "shots", seasons=seasons)


def all_understat_rosters(seasons=None):
    return read_all_seasons(config.UNDERSTAT_DIR, "rosters", seasons=seasons)


def all_understat_team_stats(seasons=None):
    return read_all_seasons(config.UNDERSTAT_DIR, "team_stats", seasons=seasons)


def all_understat_fixtures(seasons=None):
    return read_all_seasons(config.UNDERSTAT_DIR, "fixtures", seasons=seasons)


def all_odds_d1(seasons=None):
    return read_all_seasons(config.ODDS_DIR, "D1", seasons=seasons)


def all_odds_d2(seasons=None):
    return read_all_seasons(config.ODDS_DIR, "D2", seasons=seasons)
