# Kicktipp Model — Status Report for Review

Repo: `kicktipp-model` (local, not yet pushed to GitHub). All numbers
below are from real backtest runs against real historical Bundesliga
data (Understat xG/shots + football-data.co.uk odds, 2014–2023 seed +
2024/2025 freshly scraped), not synthetic/simulated.

## Build status

All phases (A: data ingestion, B: model, C: backtest, D: live pipeline)
are code-complete, unit-tested (60/60 tests passing), and have been
dry-run end-to-end against live data sources. Not yet pushed to GitHub
or deployed. See "Remaining to deploy" below.

## Headline backtest result (7 seasons, 2017–2023, rolling-origin,
strictly out-of-sample)

Kicktipp 4/3/2 scoring. All tuning nested (a season's own results never
influence its own parameters).

| Benchmark | Total points (7 seasons) |
|---|---|
| **Model** | **2824** |
| Market-EV (optimizer run on de-margined bookmaker odds alone) | 2812 |
| Market modal (most likely scoreline from bookmaker odds) | 2778 |
| Always tip "2-1" | 2465 |

Model beats market-EV in 5 of 7 seasons and on the total. Beats
always-2-1 in every season.

Per-season model points: 2017=407, 2018=404, 2019=405, 2020=394,
2021=392, 2022=403, 2023=419 (306 matches/season, max 1224
points/season).

## Statistical significance of the model-vs-market edge

Block-bootstrap (resampled by matchday, not individual match, 2000
draws, 697 matchdays):

- Observed edge (model − market-EV): **+12 points** over 2142 matches.
- **90% CI: [−30, +54]**. Includes zero.
- 66.6% of bootstrap draws are positive.

**Interpretation: the edge over the market is not statistically
distinguishable from zero at this sample size.** The model is confidently
better than naive guessing and than the pre-fix model; it is *not yet
proven* to beat the market, only directionally competitive with it.

## Secondary diagnostics (sanity checks, all in expected ranges)

- 1X2 RPS: 0.185–0.205 (target ≈0.20–0.21, flagged outside 0.18–0.23 — in range)
- Exact-score hit rate: 7.2–10.5% (target 10–13% — slightly below target most seasons)
- GD hit rate: 17.3–23.2%
- Tendency hit rate: 50.0–53.6%
- Odds join coverage: 100% in all 7 (12 including 2024/2025) seasons
- Market-inversion residual (model vs. de-margined market 1X2 probs): MSE 0.00026–0.00057, small

## What changed to get here (fix round, from a prior failing state)

A first backtest attempt (old tuning method) **lost to market-EV in
every single season** (2762 vs 2812 total). Root-caused to: the
hyperparameter search (blend weights, DC half-life, Poisson-vs-NegBin,
draw handling) was tuned on a single 306-match prior-season holdout,
re-chosen from scratch every year — pure overfitting to season-to-season
noise, confirmed multiple ways (top-10 candidate weight vectors per
season spanned the entire simplex within a 12–31 point band; naive fixed
weights and pure-market-alone both outscored the "tuned" model
out-of-sample).

Fixes applied:
1. **Pooled leave-one-season-out tuning** — search now maximizes points
   over *all* available prior seasons pooled, not one holdout season.
2. **Market-anchored weight constraint** — blend weight search
   constrained to `w_market ≥ 0.5` (market is the single sharpest
   signal; xG/DC enter as corrections, not replacements).
3. **Draw-tip EV penalty** — a drawn tip is only recommended if its EV
   beats the best non-draw tip's EV by a tuned margin (0–0.08); draw
   tips carry no partial-credit floor the way tendency tips do, so they
   need a bigger EV lead to justify the added risk. (Root cause: 11 of
   the 15 worst single-match losses were the model tipping a draw where
   the market correctly read a decisive result.)
4. **Promoted-team prior wired in** — a regression from a promoted
   team's final 2.Bundesliga-season stats to their expected first-season
   npxG was written per the original spec but never actually connected
   to the live pipeline; now it is, seeding newly-promoted teams instead
   of leaving them on a generic fallback.

Result: total points 2762 → 2824 (+62, now beats every other benchmark
tested including old-tuning, fixed-weights, and pure-market).

## Known limitations / open risk

1. **Small, statistically fragile edge over the market** (see CI above).
   Should not be marketed as "beats the bookmakers" — more accurately
   "competitive with the market, clearly ahead of naive baselines."
2. **9-season extension in progress** (2017–2025, now that 2024/2025
   data is scraped) — not yet complete; current numbers are 7 seasons.
3. **One live data-source scraper had silently broken** (Understat
   restructured their site to client-side rendering) and was found +
   fixed during this work — now confirmed working against live data via
   their JSON API endpoints directly (`/getLeagueData/`,
   `/getMatchData/`), no headless browser needed.
4. **Elversberg** (one of three teams entering Bundesliga this season,
   per club standings) has zero historical Understat data — cannot
   pre-verify their exact name spelling matches between data sources.
   Designed to hard-fail loudly (not silently mismap) if it doesn't;
   will only be known once real data includes them.
5. Two more real integration bugs were found and fixed only by actually
   dry-running the live-prediction code path against real current data
   (a UTF-8 BOM breaking a CSV column lookup; a non-2xx HTTP response
   being silently parsed as if it were valid data). This suggests the
   live path had not been exercised end-to-end before this session —
   worth one supervised live run before fully trusting the automation.

## Remaining to deploy

1. Finish the 9-season backtest extension (running).
2. **Decision needed**: ship current model quality as-is, or invest in
   further improvement before going live, given the CI caveat above.
3. Push repo to GitHub (private), add 3 secrets (Gmail address, Gmail
   app password, recipient list).
4. Manually trigger the one-time bootstrap workflow, then the weekly
   workflow once, to confirm both run cleanly on GitHub's infrastructure
   (not just locally).
5. Observe one real automated weekly run end-to-end once the 2026/27
   season's fixtures are published (season had not started as of last
   check; kickoff expected imminently).
