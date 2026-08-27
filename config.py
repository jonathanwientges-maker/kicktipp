"""
Central configuration for the Bundesliga Kicktipp prediction pipeline.

All constants used across the codebase live here. Do not hardcode any of
these values elsewhere -- import from this module instead.

Python 3.9 compatible (no match statements, no X | Y unions).
"""
import os

# ---------------------------------------------------------------------------
# League / season scope
# ---------------------------------------------------------------------------
LEAGUE = "Bundesliga"
FIRST_SEASON = 2014          # 2014/15 -- first season with data (seed + scrape)
BACKTEST_FIRST = 2017        # first PREDICTED season in the backtest (2014-16 = warmup)
CURRENT_SEASON = 2026        # 2026/27 -- first LIVE season

# Seed data (Section 9 amendment) covers seasons 2014/15..2023/24 already.
# Bootstrap only needs to scrape the gap: SEED_LAST_SEASON+1 .. CURRENT_SEASON.
SEED_LAST_SEASON = 2023
GAP_SEASONS = [2024, 2025]   # Understat + D1 seasons to scrape at bootstrap
D2_SEASONS = list(range(FIRST_SEASON, CURRENT_SEASON))  # D2 never seeded

# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------
XG_WINDOW_N = 8               # same-venue rolling window (matches)
LAMBDA_BLEND = 0.5            # own attack vs opponent-conceded weight
GRID_MAX_GOALS = 10           # score grid 0..10 (inclusive)

# ---------------------------------------------------------------------------
# Dixon-Coles
# ---------------------------------------------------------------------------
DC_HALFLIFE_GRID = [180, 365, 730]   # days; tuned in backtest, nested/out-of-sample
DC_TRAIN_SEASONS = 4                  # seasons of trailing history per DC fit

# ---------------------------------------------------------------------------
# Blend / ensemble
# ---------------------------------------------------------------------------
BLEND_STEP = 0.1              # simplex grid step for (w_market, w_xG, w_DC) search

# ---------------------------------------------------------------------------
# Fallbacks
# ---------------------------------------------------------------------------
TOTAL_GOALS_PRIOR = 3.10             # fallback total goals when O/U odds missing
FALLBACK_LAMBDAS = (1.45, 1.25)      # absolute last-resort (home, away) lambdas

# ---------------------------------------------------------------------------
# Scraping
# ---------------------------------------------------------------------------
UNDERSTAT_DELAY_S = 2.0       # minimum seconds between Understat requests
UNDERSTAT_BASE = "https://understat.com"
FD_BASE = "https://www.football-data.co.uk"

# ---------------------------------------------------------------------------
# Odds columns -- PRE-MATCH ONLY.
#
# Columns containing 'C' variants (PSCH, AvgCH, PC>2.5, AHCh, ...) are
# CLOSING odds and are BANNED from all feature construction. This is
# enforced by a unit test (tests/test_no_closing_odds.py) that scans every
# feature dataframe's columns against a regex.
# ---------------------------------------------------------------------------
COLS_1X2 = ["PSH", "PSD", "PSA", "AvgH", "AvgD", "AvgA", "B365H", "B365D", "B365A"]
COLS_OU = ["P>2.5", "P<2.5", "Avg>2.5", "Avg<2.5", "B365>2.5", "B365<2.5"]
COLS_SHOTS = ["HS", "AS", "HST", "AST"]

# Regex fragment matching any closing-odds column name. Used by the
# enforcement test. Matches: PSCH/PSCD/PSCA, AvgCH/AvgCD/AvgCA, MaxCH...,
# B365CH..., P>2.5C / PC>2.5-style variants, and all AH (Asian handicap)
# columns including AHCh.
CLOSING_ODDS_REGEX = r"(^[A-Za-z0-9]*C[HDA]$)|(^[A-Za-z0-9]*C[<>]2\.5$)|(AH)"

# Legacy football-data.co.uk column renames applied when modern names are
# absent (older seasons used the Betbrain-style Bb* prefix).
LEGACY_ODDS_RENAME = {
    "BbAvH": "AvgH",
    "BbAvD": "AvgD",
    "BbAvA": "AvgA",
    "BbMxH": "MaxH",
    "BbMxD": "MaxD",
    "BbMxA": "MaxA",
    "BbAv>2.5": "Avg>2.5",
    "BbAv<2.5": "Avg<2.5",
    "BbMx>2.5": "Max>2.5",
    "BbMx<2.5": "Max<2.5",
}

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT_DIR, "data")
SEED_DIR = os.path.join(DATA_DIR, "seed")
SEED_MATCHES_PATH = os.path.join(SEED_DIR, "matches.parquet")
SEED_SHOTS_PATH = os.path.join(SEED_DIR, "shots.parquet")
SEED_ODDS_DIR = os.path.join(SEED_DIR, "odds_cache")
UNDERSTAT_DIR = os.path.join(DATA_DIR, "understat")
ODDS_DIR = os.path.join(DATA_DIR, "odds")
STATE_DIR = os.path.join(DATA_DIR, "state")
REPORTS_DIR = os.path.join(DATA_DIR, "reports")

DRIFT_HASHES_PATH = os.path.join(STATE_DIR, "drift_hashes.json")
TUNED_PARAMS_PATH = os.path.join(STATE_DIR, "tuned_params.json")
SEASON_POINTS_PATH = os.path.join(STATE_DIR, "season_points.csv")

# ---------------------------------------------------------------------------
# Kicktipp scoring rule (4/3/2)
# ---------------------------------------------------------------------------
POINTS_EXACT = 4
POINTS_GOALDIFF = 3
POINTS_TENDENCY = 2
POINTS_WRONG = 0

# EV close-call flag threshold (Section 4, B5)
CLOSE_CALL_EV_MARGIN = 0.03
