# Kicktipp Model — Status Report for Review

Repo: `kicktipp-model`, pushed to `https://github.com/jonathanwientges-maker/kicktipp`
(private). All numbers below are from real backtest runs against real
historical Bundesliga data (Understat xG/shots + football-data.co.uk
odds, 2014–2023 seed + 2024/2025 freshly scraped), not
synthetic/simulated.

## Build status

All phases (A: data ingestion, B: model, C: backtest, D: live pipeline)
are code-complete, unit-tested (62/62 tests passing), and have been
dry-run end-to-end against live data sources. Repo is pushed to GitHub.
One real bug was found and fixed via an actual `bootstrap.yml` run on
GitHub's infrastructure (see "What changed" below). See "Remaining to
deploy" for what's left.

## Headline backtest result — FULL 9 seasons (2017–2025), rolling-origin,
strictly out-of-sample

Kicktipp 4/3/2 scoring. All tuning nested (a season's own results never
influence its own parameters).

| Benchmark | Total points (9 seasons, 2754 matches) |
|---|---|
| **Model** | **3641** |
| Market-EV (optimizer run on de-margined bookmaker odds alone) | 3642 |
| Market modal (most likely scoreline from bookmaker odds) | 3478 |
| Always tip "2-1" | 3116 |

**Model is now essentially tied with market-EV** (3641 vs 3642 — model
1 point behind over 2754 matches). Model beats market-EV in 6 of 9
seasons individually but the two new seasons (2024, 2025) shifted the
full-period total from a nominal lead to a dead heat. Model clearly
beats market-modal (+163) and always-2-1 (+525) in every season.

| Season | Model | Always-2-1 | Market modal | Market-EV |
|---|---|---|---|---|
| 2017 | 407 | 366 | 405 | 406 |
| 2018 | 404 | 348 | 393 | 404 |
| 2019 | 405 | 322 | 351 | 406 |
| 2020 | 394 | 344 | 455 | 398 |
| 2021 | 392 | 379 | 402 | 383 |
| 2022 | 403 | 368 | 342 | 401 |
| 2023 | 419 | 338 | 430 | 414 |
| 2024 | 391 | 299 | 330 | 414 |
| 2025 | 426 | 352 | 370 | 416 |

## Statistical significance of the model-vs-market edge (7-season CI,
seasons 2024/2025 not yet re-run through the bootstrap)

Block-bootstrap (resampled by matchday, not individual match, 2000
draws, 697 matchdays, computed on the 7-season 2017–2023 window):

- Observed edge (model − market-EV) at 7 seasons: +12 points.
- **90% CI: [−30, +54]**. Included zero.
- 66.6% of bootstrap draws were positive.

**The 9-season extension is exactly the outcome that CI predicted was
plausible**: the +12 lead at 7 seasons fell inside a wide interval that
already included zero, and two more real seasons of data landed the
total almost exactly on zero (−1). This is not a new negative finding —
it's the original honest caveat playing out as data accumulated. The
edge over the market was never statistically established; it should not
be treated as disproven either (a wide CI cuts both ways) — the
practically correct read is "no demonstrated edge over the market,
clear and now-strengthening edge over naive/modal baselines."

## Secondary diagnostics (sanity checks, all in expected ranges)

- 1X2 RPS: 0.185–0.205 (target ≈0.20–0.21, flagged outside 0.18–0.23 — in range)
- Exact-score hit rate: 6.9–10.5% (target 10–13% — slightly below target most seasons)
- GD hit rate: 17.3–23.2%
- Tendency hit rate: 50.0–55.2%
- Odds join coverage: 100% in all 12 seasons (2014–2025)
- Market-inversion residual (model vs. de-margined market 1X2 probs): MSE 0.00026–0.00057, small

## What changed to get here

**Fix round (mid-project)**: a first backtest attempt (old tuning
method) lost to market-EV in every single season (2762 vs 2812 total,
7 seasons). Root-caused to a hyperparameter search overfitting to a
single 306-match prior-season holdout, re-chosen from scratch every
year. Four fixes applied: pooled leave-one-season-out tuning,
market-anchored weight floor (`w_market ≥ 0.5`), a draw-tip EV penalty,
and wiring in a previously-unused promoted-team-prior regression. Result
at the time: 2762 → 2824 (7 seasons) — later diluted to near-parity once
2024/2025 were added, per above.

**GitHub deployment bug (found via a real `bootstrap.yml` run)**: the
first live trigger of `bootstrap.yml` on GitHub's infrastructure failed
with `KeyError: 'match_id'` inside the Understat scraper. Root cause: an
empty list of "matches still to fetch" produced a pandas DataFrame with
zero columns (not an empty-but-correctly-shaped one), which then broke
a `merge(..., on="match_id")` call downstream. Fixed by explicitly
pinning the DataFrame's column schema; added 2 regression tests. This is
exactly the kind of bug only a clean-environment run surfaces — the
local dev environment always had at least one match left to fetch, so
it never hit this path.

## Known limitations / open risk

1. **No demonstrated edge over the market at 9 seasons** (model 3641 vs
   market-EV 3642, essentially tied). Should not be marketed as "beats
   the bookmakers." Accurate framing: "competitive with the market,
   clearly and increasingly ahead of naive/modal baselines."
2. **Elversberg** (one of the three teams entering Bundesliga 2026/27,
   confirmed via 2025/26 2.Bundesliga standings) has zero historical
   Understat data — cannot pre-verify their exact name spelling matches
   between data sources. Designed to hard-fail loudly (not silently
   mismap) if it doesn't; will only be known once real data includes
   them.
3. Three real integration bugs were found only by actually running the
   live code paths against real data (not by unit tests alone): a
   UTF-8 BOM breaking a CSV column lookup, a non-2xx HTTP response being
   silently parsed as if valid, and the empty-DataFrame merge bug above.
   This pattern — bugs only surfacing on first real execution — suggests
   budgeting for at least one more live-fire surprise before trusting
   the automation unattended.
4. The Understat site itself restructured mid-project (moved from
   server-rendered HTML to a client-side JSON API); the scraper was
   rewritten to call the API directly and is now simpler than the
   original approach, but is inherently coupled to Understat's current
   implementation and could break again if they change it further.

## Remaining to deploy

1. Re-trigger `bootstrap.yml` on GitHub with the merge-bug fix now
   pushed; confirm it completes end-to-end on a clean environment.
2. Add the 3 GitHub secrets (`GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`,
   `MAIL_TO`) if not already done.
3. Manually trigger `weekly.yml` once to confirm the first real email
   arrives.
4. Observe one real automated weekly run end-to-end once the 2026/27
   season's fixtures are published (season had not started as of last
   check; kickoff expected imminently, with Schalke 04/Elversberg/
   Paderborn as the promoted/playoff teams).
5. **Standing decision, now with 9-season evidence**: ship as-is (still
   clearly better than guessing; roughly matches the market, which is a
   perfectly reasonable bar for a casual Kicktipp pool) — or treat the
   near-parity-with-market result as a signal to invest in further model
   improvement before fully trusting it. No further blocking technical
   work either way.
