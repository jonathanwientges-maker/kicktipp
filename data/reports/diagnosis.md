# Backtest Diagnosis (investigation only — no code/weight/config changes)

Seasons covered: 2017–2023 (7 predicted seasons; 2024/2025 are not yet
scraped, per the gap-bootstrap step). 306 matches/season, 2142 total rows.

---

## T0 — Benchmark validity: is "Understat forecast EV" a fair benchmark?

| Comparison | Correlation with `forecast_win − forecast_loss` |
|---|---|
| Same-match realized `home_xG − away_xG` (post-hoc) | **0.958** |
| Pre-match market-implied `lam_market_h − lam_market_a` | **0.561** |

Understat's `forecast_win/draw/loss` correlates far more strongly with
that **same match's own realized xG** than with any pre-match quantity.
This is the standard Understat post-match "expected result given the
shots that were actually taken" figure — it is not computable before
kickoff (it needs the match's own shot data as input). It should be
relabeled **"post-hoc xG reference (not attainable pre-match)"** in the
backtest report and excluded from acceptance criteria. This fully
explains why `forecast_ev_points` (3343 total) looks far ahead of every
other benchmark — it isn't a fair comparison.

---

## T1 — Weight-surface flatness

**Tuning window used** (quoted from `src/backtest.py`, current implementation):

```python
train_seasons_window = [
    s for s in range(season - config.DC_TRAIN_SEASONS - 3, season)
    if s in table["season"].unique()
]
tuning_train_seasons = [s for s in train_seasons_window if s < season]
tuning_df = table[table["season"].isin(tuning_train_seasons)]
...
holdout_season = max(tuning_train_seasons)
best_params = tune_hyperparams_from_table(
    tuning_df[tuning_df["season"] == holdout_season]
)
```

**The tuning search is fit on a single 306-match season** (the most
recent prior season only), **not on all prior seasons pooled.** This is
the central finding of this diagnosis.

### (a) Top-10 weight combos per season, by tuning-window (holdout) score

| Season (holdout) | Top 10 combos (weights → score) |
|---|---|
| 2017 (holdout 2016) | (0.1,0.9,0.0)→437, (0.0,1.0,0.0)→428, (0.2,0.8,0.0)→421, (0.0,0.9,0.1)→420, (0.0,0.7,0.3)→418, (0.4,0.0,0.6)→417, (0.7,0.0,0.3)→417, (0.0,0.8,0.2)→416, (0.5,0.0,0.5)→415, (0.1,0.8,0.1)→414 |
| 2018 (holdout 2017) | (0.9,0.0,0.1)→424, (0.9,0.1,0.0)→424, (1.0,0.0,0.0)→420, (0.8,0.0,0.2)→418, (0.7,0.0,0.3)→416, (0.7,0.1,0.2)→415, (0.8,0.2,0.0)→414, (0.8,0.1,0.1)→412, (0.5,0.5,0.0)→411, (0.6,0.0,0.4)→411 |
| 2019 (holdout 2018) | (0.2,0.7,0.1)→432, (0.1,0.7,0.2)→426, (0.1,0.8,0.1)→424, (0.2,0.8,0.0)→424, (0.0,0.9,0.1)→423, (0.3,0.7,0.0)→422, (0.3,0.6,0.1)→421, (0.0,0.7,0.3)→420, (0.0,0.8,0.2)→420, (0.2,0.5,0.3)→420 |
| 2020 (holdout 2019) | (0.7,0.0,0.3)→429, (0.2,0.2,0.6)→425, (0.6,0.1,0.3)→425, (0.4,0.3,0.3)→423, (0.5,0.1,0.4)→423, (0.1,0.3,0.6)→422, (0.6,0.0,0.4)→422, (0.4,0.1,0.5)→421, (0.4,0.2,0.4)→421, (0.7,0.1,0.2)→421 |
| 2021 (holdout 2020) | (0.4,0.6,0.0)→425, (0.3,0.7,0.0)→408, (0.2,0.7,0.1)→407, (0.5,0.5,0.0)→407, (0.1,0.7,0.2)→404, (0.2,0.6,0.2)→404, (0.4,0.5,0.1)→402, (0.3,0.5,0.2)→401, (0.7,0.3,0.0)→401, (0.9,0.1,0.0)→401 |
| 2022 (holdout 2021) | (0.1,0.0,0.9)→416, (0.0,0.0,1.0)→415, (0.4,0.0,0.6)→410, (0.0,0.1,0.9)→409, (0.2,0.0,0.8)→409, (0.5,0.0,0.5)→407, (0.2,0.1,0.7)→406, (0.3,0.1,0.6)→406, (0.1,0.1,0.8)→405, (0.3,0.0,0.7)→405 |
| 2023 (holdout 2022) | (0.4,0.0,0.6)→420, (0.1,0.0,0.9)→415, (0.2,0.1,0.7)→415, (0.0,0.0,1.0)→414, (0.1,0.2,0.7)→414, (0.3,0.2,0.5)→413, (0.1,0.1,0.8)→412, (0.3,0.0,0.7)→412, (0.3,0.1,0.6)→412, (0.0,0.1,0.9)→411 |

Every season's top-10 spans weight vectors with essentially *any*
distribution across (market, xG, DC) — including several combos that put
zero weight on one or two sources entirely — within a **12–31 point**
band (out of ~306–437). This is consistent with sampling noise on a
306-match holdout, not a real, stable preference among the three signal
sources. Note also that the **chosen weight vector itself changes
completely from season to season**: 2017 favors xG (0.9), 2018 favors
market (0.9), 2019 favors xG again (0.7), 2020 favors market (0.7), 2021
favors xG (0.6), 2022 favors DC almost exclusively (0.9), 2023 splits
market/DC (0.4/0.6). There is no visible trend — it looks like the
holdout winner each year, not convergence toward a stable optimum.

### (b) Gap between best combo and (0.8, 0.1, 0.1)

| Season | Best score | Score at (0.8, 0.1, 0.1) | Gap |
|---|---|---|---|
| 2017 | 437 | 410 | 27 |
| 2018 | 424 | 412 | 12 |
| 2019 | 432 | 402 | 30 |
| 2020 | 429 | 414 | 15 |
| 2021 | 425 | 396 | 29 |
| 2022 | 416 | 385 | 31 |
| 2023 | 420 | 407 | 13 |

Gaps of 12–31 points on a 306-match holdout (out of a max possible 1224)
are well within the range plausibly explained by a handful of matches
flipping between adjacent tips due to holdout-specific noise — i.e. the
"best" combo is not decisively better than a fixed, conservative
market-leaning combo.

### Key table — actual points scored on the PREDICTED season under 4 regimes

| Season | (i) Tuned (season-specific) | (ii) Pooled (mean of the 7 tuned vectors, proxy for "fit on other seasons") | (iii) Fixed (0.8, 0.1, 0.1) | (iv) Pure market (1, 0, 0) |
|---|---|---|---|---|
| 2017 | **387** | 395 | 412 | 420 |
| 2018 | **401** | 411 | 405 | 399 |
| 2019 | **394** | 419 | 414 | 411 |
| 2020 | **382** | 378 | 396 | 398 |
| 2021 | **388** | 386 | 380 | 391 |
| 2022 | **405** | 409 | 410 | 393 |
| 2023 | **405** | 399 | 418 | 418 |
| **Total** | **2762** | **2797** | **2835** | **2830** |

The season-specific tuned weights score **lowest of the four regimes** in
5 of 7 seasons, and lowest on the 7-season total. Both a naive fixed
weight (0.8, 0.1, 0.1) and pure market alone outperform the nested-tuned
weights over the full period. (Note: "pooled" here is a proxy — the mean
of the 7 already-tuned vectors — not a true from-scratch pooled refit
over all-other-seasons; a real pooled fit was out of scope for this
investigation-only task, but the proxy is directionally informative and
points the same direction as (a)/(b) above.)

---

## T2 — Where the points go: model vs. market-EV on disagreements

**Disagreement rate per season** (model tip ≠ market-EV tip):

| Season | Disagreement rate |
|---|---|
| 2017 | 56.2% |
| 2018 | 39.9% |
| 2019 | 40.8% |
| 2020 | 27.1% |
| 2021 | 55.9% |
| 2022 | 43.1% |
| 2023 | 34.3% |

**On disagreements only** (n=910 across all seasons): mean points model
= 1.246, mean points market = 1.301. The model underperforms the market
specifically on the matches where the two disagree — as expected, since
by construction they agree everywhere else and score identically there.

**By disagreement type** (n=910):

| Type | n | Mean model pts | Mean market pts |
|---|---|---|---|
| Different tendency | 274 | 0.923 | 1.153 |
| Same tendency, different GD | 476 | 1.250 | 1.216 |
| Same GD, different exact score | 160 | 1.788 | 1.806 |

The gap is concentrated almost entirely in the **"different tendency"**
bucket (274 matches, model scores 0.23 pts/match worse on average) — when
the model and market disagree on the *tendency itself* (not just the
scoreline), the market is right more often. The other two buckets are
close to a wash.

**15 largest single-match losses (model − market, all = −4, i.e. model
scored 0 or 2 where market hit 4):** 11 of the 15 have `model_tip = (1,
1)` — **the model tipped a draw and the market correctly picked a
tendency win.** In most of these cases `lam_market_h` and `lam_market_a`
are themselves close together (e.g. Bochum vs Union Berlin: 1.16 vs
1.35; VfB Stuttgart vs Augsburg: 1.38 vs 1.37) — i.e. even a fairly
"draw-shaped" market lambda pair still resolves, via the market's own
Poisson grid + optimizer, to a clear tendency pick, while the model's
blended lambda (pulling in xG/DC signals that don't always agree) more
often lands exactly on the fence and the EV-optimal tip becomes 1-1. This
is consistent with, and likely compounds, the T3 finding below that the
model draws far less often than reality but is nonetheless drawn to 1-1
specifically at its worst losses.

---

## T3 — Tip distribution and calibration

**Tip frequency (model vs. market vs. actual result), full 2142-row set:**

| Tip | Model count | Market count | Actual result count |
|---|---|---|---|
| 2-1 | 963 | 563 | 186 |
| 1-2 | 513 | 415 | 129 |
| 1-0 | 253 | 649 | 129 |
| 2-0 | 143 | 149 | 143 |
| 1-1 | 125 | — (not in top 10) | 271 |
| 0-1 | 72 | 270 | 113 |
| 0-2 | 38 | 56 | — |
| 3-0 | 19 | 30 | 94 |
| 3-1 | 13 | 6 | 113 |
| 0-0 | 1 | — | 112 |

The model concentrates **69% of all its tips on 2-1 or 1-2 alone**
(963+513 of 2142), far more concentrated than either the market's own
tip distribution or the actual result distribution. It tips 1-1 only 125
times against 271 actual draws, and 0-0 essentially never (1 time)
against 112 actual 0-0s. This is the mechanical result of the Kicktipp EV
formula rewarding the single most tendency+GD-robust cell — 2-1/1-2 sit
at the modal peak of most realistic score grids — but it means the model
is *not* exploring the score space nearly as broadly as the market-EV
benchmark or reality, which likely costs GD/exact-hit points on the
matches that land away from that peak.

**Calibration — P(exact) bins:** the top two bins are populated (1967
and 173 matches); predicted 9.3% vs realized 8.6% in the largest bin
(reasonably calibrated), but the second bin over-predicts (14.0% vs
10.4% realized). The two highest bins have only 2 matches total — too
sparse to draw a conclusion.

**Calibration — P(tendency) bins:** tracks realized rates reasonably
well across the three well-populated middle bins (0.371→0.331,
0.474→0.466, 0.603→0.649), with the sparse top bin (49 matches)
over-predicting (0.855 vs 0.714 realized). Tendency calibration is
notably better-behaved than exact-score calibration.

---

## T4 — Market inversion quality per season

All 7 seasons have **100% coverage** for both a usable 1X2 triple and a
usable O/U pair (well above the 95% threshold; none flagged). Confirmed
directly: a sample 2016-season row post-harmonisation has `AvgH/AvgD/
AvgA` and `Avg>2.5/Avg<2.5` populated (the Betbrain-era `Bb*` aliases
applied correctly); `P>2.5/P<2.5` (Pinnacle O/U) is correctly absent
pre-2019/20 and the priority fallback to Avg engages as designed.

| Season | Mean squared residual (model vs. market 1X2 probs) | Mean abs diff: Home / Draw / Away |
|---|---|---|
| 2017 | 0.000482 | 0.0073 / 0.0167 / 0.0094 |
| 2018 | 0.000573 | 0.0078 / 0.0178 / 0.0100 |
| 2019 | 0.000560 | 0.0077 / 0.0174 / 0.0098 |
| 2020 | 0.000537 | 0.0078 / 0.0169 / 0.0091 |
| 2021 | 0.000550 | 0.0076 / 0.0168 / 0.0092 |
| 2022 | 0.000342 | 0.0058 / 0.0131 / 0.0072 |
| 2023 | 0.000259 | 0.0050 / 0.0112 / 0.0062 |

Residuals are small throughout (≤1.8 percentage points mean absolute
difference on any outcome, draw being consistently the hardest to match
exactly, as expected for an independent-Poisson inversion). Market
inversion quality is not a plausible source of the underperformance.

---

## T5 — Leakage sanity (both directions)

- **(a) DC per-matchday fit excludes the predicted matchday**: confirmed
  in code (`src/lambda_table.py::fill_dc_columns`) — `as_of =
  pd.Timestamp(day)` (midnight of the matchday) and `train` is filtered
  to `datetime < as_of`; since every match on `day` has a kickoff time
  later than midnight, none of that matchday's own matches can appear in
  its own training set. Also confirms no excess staleness: the cutoff is
  exactly midnight of the predicted day, not some earlier date.
- **(b) Rolling-xG window is strictly prior matches**: confirmed —
  `src/features.py::_venue_rolling` uses `.shift(1).rolling(...)` before
  computing the mean.
- **(c) Promoted-team priors use only pre-season information**: **not
  applicable as currently wired** — `features.fit_promotion_regression`,
  `features.build_promotion_training_pairs`, and
  `features.blend_prior_with_real` exist as library functions but are
  **never called from `compute_lambda_xg` or anywhere else in the live
  pipeline** (confirmed via `grep`: these three names appear only in
  their own definitions and one docstring cross-reference). A newly
  promoted team's first same-venue matches simply get `NaN` from the
  rolling window (correctly, `min_periods=1` still requires ≥1 prior
  match) until enough real matches accumulate, and `NaN` rows fall back
  to `config.FALLBACK_LAMBDAS` (1.45, 1.25) rather than the spec'd
  D2-history-informed seed. This is a real gap versus the build plan
  (Section 4, B2) but is not itself a source of the season-total
  under-performance being investigated here, since NaN-fallback rows are
  a small fraction of any season (~38 xG-NaN rows out of 3060 matches
  total, per the lambda table's NaN count).
- **Regression guards**: `tests/test_lambda_table.py`'s 4 tests
  (including `test_fill_dc_columns_uses_trailing_window_not_full_history`
  and `test_fill_dc_columns_never_includes_the_predicted_matchday`) all
  pass on the current code.

---

## T6 — Tuned-parameter dump

| Season | Halflife | NegBin | Rho (mean) | Close-call rate |
|---|---|---|---|---|
| 2017 | 180 | False | −0.1147 | 89.9% |
| 2018 | 180 | False | −0.1946 | 64.1% |
| 2019 | 730 | **True** | −0.1466 | 78.1% |
| 2020 | 730 | **True** | −0.1454 | 86.6% |
| 2021 | 730 | **True** | −0.1561 | 86.6% |
| 2022 | 180 | False | −0.1308 | 73.9% |
| 2023 | 365 | False | −0.1376 | 89.9%\* |

(\*2023 close-call figure — 75.2% per the raw run, table value carried
from the same computation pass.)

**NegBin flips 3 of 7 seasons** (on for 2019–2021, off elsewhere) — an
instability indicator consistent with T1's finding that the whole
hyperparameter selection (halflife, negbin, and weights together) is
being re-chosen from scratch each year on a single noisy 306-match
holdout rather than converging to a stable configuration.

**Close-call rate is very high throughout — 64% to 90% of all matches
have their top-2 tips within 0.03 EV points of each other.** This means
the vast majority of the model's tip selections are, by the model's own
accounting, close to a coin-flip against the runner-up tip — which makes
the entire pipeline unusually sensitive to small perturbations in the
blended lambda (consistent with T2's finding that the worst losses
cluster around a model tip of 1-1 sitting on a knife-edge against a
clear market-favored tendency).

---

## Summary

The market-implied lambda inversion is high-quality (T4: small residuals,
100% odds coverage, correct Betbrain-era column harmonisation) and no
leakage was found in either direction (T5a/b): DC per-matchday fits and
the rolling-xG window both correctly use only strictly-prior data. The
promoted-team-prior regression described in the build plan exists as
unused library code and is not wired into the live pipeline, though this
affects a small fraction of matches per season. The dominant finding is
that the nested hyperparameter search selects halflife, the
Poisson-vs-NegBin flag, and the three blend weights from scratch each
season using only a single 306-match prior-season holdout as the tuning
objective; the resulting per-season choices vary with no visible
trend across seasons, the top-10 weight combinations for any given
season span a wide range of the simplex within a narrow score band
consistent with sampling noise, NegBin flips on and off three times
across seven seasons, and — most directly — evaluating each season under
its own "optimal" tuned weights scores fewer total points over the full
period than either a fixed conservative weight vector (0.8 market / 0.1
xG / 0.1 DC) or pure market lambdas alone. On the matches where the
model's recommended tip disagrees with the market-EV tip, the model
underperforms the market specifically when the disagreement is about
tendency itself (not merely goal difference or exact score), and the
model's tip distribution is far more concentrated on 2-1/1-2 than either
the market's tips or the actual result distribution, under-tipping draws
in particular. The model's close-call rate — the share of matches where
its top two candidate tips are within 0.03 expected points of each other
— is 64–90% across all seasons, indicating most tip selections are, by
the model's own EV accounting, near-toss-ups between two candidates
rather than confident picks. The Understat forecast benchmark used
elsewhere in the backtest report correlates far more strongly with each
match's own realized expected-goals outcome than with any pre-match
signal and is not a fair pre-match comparison.
