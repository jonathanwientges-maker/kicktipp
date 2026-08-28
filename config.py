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

# Bump this whenever the LOGIC of feature computation changes in a way
# that isn't captured by any config VALUE above -- e.g. F4 (fix round,
# data/reports/diagnosis.md) wired the promoted-team prior into
# features.compute_lambda_xg / src/promoted_prior.py, which changes the
# lambda table's contents for the exact same config values as before.
# src/lambda_table.py's cache-invalidation hash includes this constant
# precisely so a code-only change like that can't silently serve a stale
# cached table (which is what happened the first time -- the cache was
# rebuilt from a stale run right after F4 landed, caught only because
# the discrepancy was checked for manually).
FEATURE_LOGIC_VERSION = 2

# ---------------------------------------------------------------------------
# Dixon-Coles
# ---------------------------------------------------------------------------
DC_HALFLIFE_GRID = [180, 365, 730]   # days; tuned in backtest, nested/out-of-sample
DC_TRAIN_SEASONS = 4                  # seasons of trailing history per DC fit

# ---------------------------------------------------------------------------
# Blend / ensemble
# ---------------------------------------------------------------------------
BLEND_STEP = 0.1              # simplex grid step for (w_market, w_xG, w_DC) search

# Fix round F2 (backtest diagnosis, data/reports/diagnosis.md T1): the
# weight search is constrained to w_market >= MIN_MARKET_WEIGHT. The
# market is the sharpest single source of the three (small inversion
# residuals, T4; and every unconstrained-search alternative -- pooled,
# fixed, pure-market -- beat the per-season-tuned weights out of sample,
# T1's key table); xG and DC are meant to enter as corrections on top of
# the market signal, not as replacements for it.
MIN_MARKET_WEIGHT = 0.5

# Fix round F3 (diagnosis T2/T6): a drawn tip (h == a) is only
# recommended if its EV exceeds the best non-draw tip's EV by at least
# DRAW_MARGIN. Draw tips carry no 2-point tendency floor (a wrong draw
# tip on a decisive result scores 0, whereas a wrong-GD tendency tip
# still often scores 2), so their EV estimate carries asymmetric
# downside risk under lambda error -- the diagnosis found 11 of the 15
# worst single-match losses were exactly this failure mode (model tips
# 1-1, market correctly reads a tendency winner). Tuned jointly with the
# blend weights over DRAW_MARGIN_GRID in the backtest.
DRAW_MARGIN = 0.0             # default/fallback; overwritten by tuning
DRAW_MARGIN_GRID = [0.00, 0.02, 0.04, 0.06, 0.08]

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

# ---------------------------------------------------------------------------
# Kicktipp auto-submission (src/kicktipp_submit.py)
#
# The weekly run can log into kicktipp.de and enter the model's tips into
# the bet form automatically. Credentials come from the environment
# (KICKTIPP_USER / KICKTIPP_PASSWORD), like the Gmail ones -- never
# committed. Submission is OFF unless KICKTIPP_LIVE=1 is set in the
# environment: without it the module runs a full dry-run (login, parse,
# decide) and reports what it WOULD place, but sends no POST. This is the
# master safety switch -- set the KICKTIPP_LIVE secret only once the
# dry-run output has been checked against manual entry.
# ---------------------------------------------------------------------------
KICKTIPP_BASE = "https://www.kicktipp.de"
KICKTIPP_COMMUNITY = "buli-challenge"   # community short-name in the URL path
KICKTIPP_LIVE = os.environ.get("KICKTIPP_LIVE", "").strip() == "1"

# Never place (or overwrite) a tip within this many hours of kickoff --
# a late model run should not fight a manual entry made near the deadline.
# Uses the DST-corrected kickoff timestamp from predict.kickoff_timestamps.
KICKTIPP_MIN_LEAD_HOURS = 2

# Fill-blanks-only: a match whose Kicktipp form already holds a value
# (any manual or prior entry) is left untouched. Set False to let the
# model overwrite its own earlier auto-entries (still never within
# KICKTIPP_MIN_LEAD_HOURS, still not implemented as a hard overwrite of
# manual edits -- see kicktipp_submit.py).
KICKTIPP_FILL_BLANKS_ONLY = True

# Kicktipp shows German short team names in the bet form; the model
# works in football-data.co.uk names. This maps the Kicktipp display
# name (as seen in the form's row cells) -> football-data name. Mirrors
# crosswalk.py's philosophy: an unmapped name is a HARD FAILURE, never a
# silent skip -- entering a score against the wrong fixture is worse
# than entering nothing. Extend as Kicktipp's rendering or the league
# roster changes.
KICKTIPP_TEAM_ALIASES = {
    "Bayern": "Bayern Munich",
    "FC Bayern": "Bayern Munich",
    "Bayern München": "Bayern Munich",
    "Dortmund": "Dortmund",
    "BVB": "Dortmund",
    "Leverkusen": "Leverkusen",
    "Bayer Leverkusen": "Leverkusen",
    "Leipzig": "RB Leipzig",
    "RB Leipzig": "RB Leipzig",
    "Stuttgart": "Stuttgart",
    "VfB Stuttgart": "Stuttgart",
    "Frankfurt": "Ein Frankfurt",
    "Eintracht Frankfurt": "Ein Frankfurt",
    "Freiburg": "Freiburg",
    "SC Freiburg": "Freiburg",
    "Hoffenheim": "Hoffenheim",
    "TSG Hoffenheim": "Hoffenheim",
    "Mainz": "Mainz",
    "Mainz 05": "Mainz",
    "1. FSV Mainz 05": "Mainz",
    "Wolfsburg": "Wolfsburg",
    "VfL Wolfsburg": "Wolfsburg",
    "M'gladbach": "M'gladbach",
    "Gladbach": "M'gladbach",
    "Bor. Mönchengladbach": "M'gladbach",
    "Mönchengladbach": "M'gladbach",
    "Werder": "Werder Bremen",
    "Werder Bremen": "Werder Bremen",
    "Bremen": "Werder Bremen",
    "Union": "Union Berlin",
    "Union Berlin": "Union Berlin",
    "1. FC Union Berlin": "Union Berlin",
    "Augsburg": "Augsburg",
    "FC Augsburg": "Augsburg",
    "Köln": "FC Koln",
    "1. FC Köln": "FC Koln",
    "Koln": "FC Koln",
    "Heidenheim": "Heidenheim",
    "1. FC Heidenheim": "Heidenheim",
    "1. FC Heidenheim 1846": "Heidenheim",
    "St. Pauli": "St Pauli",
    "FC St. Pauli": "St Pauli",
    "Hamburg": "Hamburg",
    "Hamburger SV": "Hamburg",
    "HSV": "Hamburg",
    "Paderborn": "Paderborn",
    "SC Paderborn": "Paderborn",
    "SC Paderborn 07": "Paderborn",
    "Elversberg": "Elversberg",
    "SV Elversberg": "Elversberg",
    "SV 07 Elversberg": "Elversberg",
}

# EV close-call flag threshold (Section 4, B5)
CLOSE_CALL_EV_MARGIN = 0.03
