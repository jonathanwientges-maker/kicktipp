"""
Fix round F4 (data/reports/diagnosis.md T5c): tests for the promoted-team
prior wiring into features.compute_lambda_xg.

These are data-driven integration tests against the real ingested
history (data/understat/, data/odds/season=*/D2.parquet) rather than
synthetic fixtures, because the whole point of F4 is that it depends on
real D2 stats resolving through the real crosswalk for real promotion
events -- a synthetic case would not exercise the actual regression
fit/predict path meaningfully. Skips gracefully if the D2 data isn't
present (e.g. a fresh checkout before running the D2 download step).
"""
import math

import pytest

import config
from src import features, promoted_prior, storage


def _has_d2_data():
    for season in range(2014, 2024):
        if storage.odds_d2(season) is None:
            return False
    return True


requires_d2 = pytest.mark.skipif(
    not _has_d2_data(), reason="D2 odds data not present -- run the D2 download step first."
)


@requires_d2
def test_detect_promotions_finds_known_events():
    matches = storage.all_understat_matches()
    promotions = promoted_prior.detect_promotions(matches)
    teams = {p["team"] for p in promotions}
    # A few promotion events known to be in the 2014-2023 seed data.
    for expected in ("Union Berlin", "Arminia Bielefeld", "Bochum", "FC Heidenheim"):
        assert expected in teams


@requires_d2
def test_build_regression_and_seeds_produces_seeds_for_shots_complete_promotions():
    matches = storage.all_understat_matches()
    seeds = promoted_prior.build_regression_and_seeds(matches)
    # These promotions have D2 seasons with shots data (2017/18 onward);
    # they must get a real seed, not be silently dropped.
    for team in ("Union Berlin", "Arminia Bielefeld", "Bochum", "FC Heidenheim"):
        assert team in seeds
        assert seeds[team]["npxg_for_seed"] > 0
        assert seeds[team]["npxg_against_seed"] > 0


@requires_d2
def test_build_regression_and_seeds_excludes_shots_incomplete_promotions():
    """Ingolstadt/Darmstadt (D2 2014) and RB Leipzig (D2 2015) predate
    football-data.co.uk's D2 shot-count columns -- they must NOT be
    silently given a fabricated shots-based seed."""
    matches = storage.all_understat_matches()
    seeds = promoted_prior.build_regression_and_seeds(matches)
    for team in ("Ingolstadt", "Darmstadt", "RasenBallsport Leipzig"):
        assert team not in seeds


@requires_d2
def test_promoted_team_first_matchday_lambda_is_not_raw_fallback():
    """The required F4 regression test: a newly promoted team's first
    same-venue matchday lambda must NOT equal config.FALLBACK_LAMBDAS
    when D2 history (with shots) is available for that team -- it should
    be a genuine D2-informed value instead."""
    matches = storage.all_understat_matches()
    shots = storage.all_understat_shots()
    seeds = promoted_prior.build_regression_and_seeds(matches)

    enriched = features.compute_lambda_xg(matches, shots, promoted_seeds=seeds)

    # Union Berlin's first-ever Bundesliga home match (2019 promotion).
    ub_home = enriched[enriched["home_team"] == "Union Berlin"].sort_values("datetime")
    assert len(ub_home) > 0
    first_match = ub_home.iloc[0]

    assert not math.isnan(first_match["lambda_xg_h"]), (
        "First promoted-team matchday lambda is NaN -- the prior seed was not applied."
    )
    assert first_match["lambda_xg_h"] != pytest.approx(config.FALLBACK_LAMBDAS[0], abs=1e-9), (
        "First promoted-team matchday lambda equals the raw fallback -- "
        "the D2-informed seed was not used."
    )


@requires_d2
def test_without_promoted_seeds_first_matchday_is_nan_baseline():
    """Sanity check on the OLD behavior (promoted_seeds=None, the
    default): confirms the prior test's contrast is meaningful -- i.e.
    without the fix, the first matchday genuinely was NaN (which the
    caller would then fallback-substitute), not already some other
    non-fallback value by coincidence."""
    matches = storage.all_understat_matches()
    shots = storage.all_understat_shots()
    enriched = features.compute_lambda_xg(matches, shots, promoted_seeds=None)

    ub_home = enriched[enriched["home_team"] == "Union Berlin"].sort_values("datetime")
    first_match = ub_home.iloc[0]
    assert math.isnan(first_match["lambda_xg_h"])


@requires_d2
def test_leakage_safe_seeds_dont_use_future_promotions():
    """promoted_team_seeds_leakage_safe must give a promotion's seed that
    is identical to what build_regression_and_seeds gives when trained
    only on strictly-earlier promotions -- i.e. a later promotion's
    first-Bundesliga npxG outcome must never influence an earlier
    promotion's seed.

    Given the actual 2014-2023 promotion history, there are only 5
    candidate training promotions before bl_season 2021 (Darmstadt/
    Ingolstadt 2015, RB Leipzig 2016, Fortuna Dusseldorf/Nurnberg 2018),
    of which only 2 have complete (shots-included) D2 data -- below the
    >= 4 minimum the regression requires for identifiability. So neither
    Union Berlin (2019) nor Arminia Bielefeld (2020) can get a
    leakage-safe seed at all with the data currently available; they
    correctly fall through to config.FALLBACK_LAMBDAS rather than being
    given a seed trained partly on future information. Bochum/Greuther
    Fuerth (2021) are the first promotions with enough strictly-prior
    complete training data (Fortuna Dusseldorf, Nurnberg, Union Berlin,
    Arminia Bielefeld = 4 events, all with usable D2 shots data)."""
    matches = storage.all_understat_matches()

    leakage_safe_seeds = promoted_prior.promoted_team_seeds_leakage_safe(matches)

    # Bochum/Greuther Fuerth (bl_season 2021) are the first promotions
    # with enough strictly-prior data to be leakage-safe-seedable.
    assert "Bochum" in leakage_safe_seeds
    assert "Greuther Fuerth" in leakage_safe_seeds
    direct_seeds_as_of_2021 = promoted_prior.build_regression_and_seeds(
        matches, as_of_season=2021
    )
    assert leakage_safe_seeds["Bochum"]["npxg_for_seed"] == pytest.approx(
        direct_seeds_as_of_2021["Bochum"]["npxg_for_seed"], abs=1e-9
    )

    # Union Berlin (2019) and Arminia Bielefeld (2020) must NOT receive a
    # leakage-safe seed -- there is not enough strictly-prior complete
    # training data for them without reaching into the future.
    assert "Union Berlin" not in leakage_safe_seeds
    assert "Arminia Bielefeld" not in leakage_safe_seeds

    # But the live-path fit (no held-out future, uses all history) DOES
    # give Union Berlin a seed -- confirming the difference is real and
    # not just both functions failing identically.
    live_seeds = promoted_prior.promoted_team_seeds_for_live(matches)
    assert "Union Berlin" in live_seeds


@requires_d2
def test_promoted_prior_decay_reaches_pure_real_data_after_window():
    """After a promoted team has played >= XG_WINDOW_N same-venue
    matches, its rolling npxG should be computed purely from real data
    (prior weight decayed to zero) -- i.e. compute_lambda_xg with vs.
    without promoted_seeds should converge for that team's later
    matches, per blend_prior_with_real's documented decay contract."""
    matches = storage.all_understat_matches()
    shots = storage.all_understat_shots()
    seeds = promoted_prior.build_regression_and_seeds(matches)

    without = features.compute_lambda_xg(matches, shots, promoted_seeds=None)
    with_seed = features.compute_lambda_xg(matches, shots, promoted_seeds=seeds)

    ub_home_ids = with_seed[with_seed["home_team"] == "Union Berlin"].sort_values(
        "datetime"
    )["match_id"].tolist()
    if len(ub_home_ids) <= config.XG_WINDOW_N:
        pytest.skip("Not enough Union Berlin home matches in the data to test full decay.")

    late_match_id = ub_home_ids[config.XG_WINDOW_N]  # first match fully past the window
    late_with = with_seed[with_seed["match_id"] == late_match_id]["lambda_xg_h"].iloc[0]
    late_without = without[without["match_id"] == late_match_id]["lambda_xg_h"].iloc[0]

    assert late_with == pytest.approx(late_without, abs=1e-6)
