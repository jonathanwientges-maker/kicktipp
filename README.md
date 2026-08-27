# kicktipp-model

Automated Bundesliga exact-score prediction system, optimized for expected
points under the **Kicktipp 4/3/2 scoring rule** (4 = exact score, 3 = correct
goal difference, 2 = correct tendency, 0 = wrong).

## How it works

Three independent estimates of each match's expected goals (λ_home, λ_away)
are blended into one score grid, which an EV-maximizing optimizer turns into
a single recommended tip per match:

1. **Market-implied** (`src/market.py`) — de-margined 1X2 + O/U odds
   (Shin's method), inverted to λ via least squares.
2. **Rolling xG** (`src/features.py`) — same-venue rolling mean of
   non-penalty xG for/against, with a promoted-team prior for newly-promoted
   clubs.
3. **Dixon-Coles** (`src/dixon_coles.py`) — time-weighted MLE attack/defence
   ratings with the classic low-score τ correction, refit per matchday on a
   trailing window of history.

The blend weights, DC half-life, and Poisson-vs-negative-binomial choice are
all tuned via nested (out-of-sample) grid search in the historical backtest
— see `src/backtest.py` and `src/lambda_table.py`.

## Repository layout

```
config.py                  All tunable constants
src/
  scrape_understat.py      Understat xG/shots scraper
  scrape_footballdata.py   football-data.co.uk odds/fixtures downloader
  crosswalk.py             Team-name harmonisation (hard-fails on unknown names)
  storage.py                Season-partitioned parquet I/O
  ingest_seed.py            One-time seed-data ingestion (2014-2023)
  bootstrap_gap.py          One-time gap scrape (2024-2025 + all D2)
  features.py                Rolling-xG lambdas + promoted-team prior
  market.py                   Shin's method + lambda inversion
  dixon_coles.py               DC ratings, tau correction
  blend.py                      Lambda ensemble + final score grid
  optimizer.py                   Kicktipp EV tip selection
  lambda_table.py                 Precomputed lambda table (perf-critical, see below)
  backtest.py                      Rolling-origin historical evaluation
  predict.py                        Weekly prediction entrypoint
  report.py + templates/report.html.j2   Self-contained HTML report
  notify.py                                Gmail SMTP delivery
  results_refresh.py                        Post-matchday scoring
.github/workflows/
  bootstrap.yml    workflow_dispatch only -- run once
  weekly.yml       Fri/Tue cron -- predictions + report + email
  results_refresh.yml   Mon cron -- score last matchday, update tracker
data/
  seed/            Pre-supplied historical data (committed)
  understat/, odds/   Season-partitioned scraped data (committed)
  state/            Tuned params, lambda table cache, drift hashes
  reports/           Rendered HTML archive
```

## Performance design: the lambda table

`src/lambda_table.py` precomputes every match's three raw λ pairs (market /
xG / DC-per-halflife) exactly once into `data/state/lambda_table.parquet`,
keyed by a hash of the config values that affect it. Every value is
out-of-sample by construction:

- **λ_market** is a pure function of that match's pre-match odds row —
  computed once, ever.
- **λ_xG** comes from the rolling window, which is already strictly
  before-the-match by construction (`shift(1)`).
- **λ_DC** uses sequential, warm-started per-matchday Dixon-Coles fits (each
  matchday initialized from the previous matchday's solution, and trained
  only on the trailing `DC_TRAIN_SEASONS` seasons — never unbounded
  history), checkpointed to disk after each half-life so a crash mid-build
  resumes instead of restarting.

`src/backtest.py`'s nested hyperparameter search then runs as pure
vectorized array access over this table — no scipy calls, no DC fits, no
per-match dict lookups inside the 396-combo weight-search loop. An earlier
version recomputed the market-lambda inversion (a `scipy.optimize.minimize`
call) redundantly inside that loop; the fix cut a multi-hour backtest to
minutes.

## Running things locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python -m src.ingest_seed        # one-time: load data/seed/ into the layout
python -m src.bootstrap_gap      # one-time: scrape 2024/2025 + all D2
python -u -m src.lambda_table    # build/refresh the cached lambda table
python -u -m src.backtest        # run the historical backtest, writes
                                  # data/state/tuned_params.json
python -m src.predict --no-email # dry-run a weekly prediction locally
pytest tests/ -q                 # 38 unit tests
```

## Hard rules (enforced, not just documented)

- **No closing-odds columns** in any feature, anywhere — enforced by
  `tests/test_no_closing_odds.py` scanning both a regex-based allow/deny
  list and every ingested odds parquet on disk.
- **No silent fallbacks** — an unresolved team name, a failed scrape, or a
  detected Understat data-drift all raise/abort loudly rather than
  defaulting quietly.
- **Every probability grid sums to 1** within `1e-9` (asserted in
  `blend.build_final_grid`).
- **All backtest tuning is nested/out-of-sample** — a predicted season's own
  results never influence its own hyperparameters.
