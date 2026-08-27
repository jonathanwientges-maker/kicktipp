import numpy as np

from src import market


def test_shin_probabilities_sum_to_one():
    odds = (2.0, 3.5, 4.0)
    p = market.shin_probabilities(odds)
    assert abs(sum(p) - 1.0) < 1e-6


def test_shin_reduces_booksum():
    """De-margined probabilities should be strictly less than the raw
    (overround-inflated) implied probabilities for a book with overround."""
    odds = (2.0, 3.5, 4.0)
    pis = np.array([1.0 / o for o in odds])
    booksum = pis.sum()
    assert booksum > 1.0  # sanity: these odds do carry overround

    p = market.shin_probabilities(odds)
    # Shin probabilities should sum to 1, strictly below the raw booksum
    # of implied (vig-inflated) probabilities.
    assert abs(sum(p) - 1.0) < 1e-6
    assert sum(pis) > sum(p) - 1e-9


def test_shin_matches_proportional_when_no_overround():
    """A fair book (booksum == 1) should have Shin's z solve near 0 and
    match proportional normalisation."""
    # Fair odds: probabilities 0.5, 0.3, 0.2 -> odds 2.0, 3.3333, 5.0
    true_p = np.array([0.5, 0.3, 0.2])
    odds = tuple(1.0 / true_p)
    p = market.shin_probabilities(odds)
    assert np.allclose(p, true_p, atol=1e-3)


def test_ou_probabilities_sum_to_one():
    p = market.ou_probabilities((1.9, 1.95))
    assert abs(sum(p) - 1.0) < 1e-9


def test_inversion_recovers_known_lambdas():
    """Round-trip: generate synthetic 'market' probabilities from known
    lambdas, invert, and recover lambdas within 0.02."""
    true_lam_h, true_lam_a = 1.8, 1.1
    p_home, p_draw, p_away = market.model_1x2_probs(true_lam_h, true_lam_a)
    p_over = market.model_over_2_5(true_lam_h, true_lam_a)

    lam_h, lam_a = market.invert_lambdas((p_home, p_draw, p_away), p_over)
    assert abs(lam_h - true_lam_h) < 0.02
    assert abs(lam_a - true_lam_a) < 0.02


def test_inversion_without_ou_uses_soft_penalty():
    true_lam_h, true_lam_a = 1.5, 1.3
    p_home, p_draw, p_away = market.model_1x2_probs(true_lam_h, true_lam_a)
    lam_h, lam_a = market.invert_lambdas((p_home, p_draw, p_away), None)
    # Without O/U info, recovery is less precise but should still be in
    # a sane range and preserve the 1X2 shape reasonably.
    assert 0.5 < lam_h < 4.0
    assert 0.5 < lam_a < 4.0


def test_invert_lambdas_missing_1x2_returns_nan():
    lam_h, lam_a = market.invert_lambdas(None, None)
    assert np.isnan(lam_h)
    assert np.isnan(lam_a)


def test_pick_1x2_odds_priority():
    row = {"PSH": 1.5, "PSD": 4.0, "PSA": 6.0, "AvgH": 1.6, "AvgD": 3.9, "AvgA": 5.5}
    picked = market.pick_1x2_odds(row)
    assert picked == (1.5, 4.0, 6.0)


def test_pick_1x2_odds_falls_back_when_pinnacle_missing():
    row = {"PSH": float("nan"), "PSD": float("nan"), "PSA": float("nan"),
           "AvgH": 1.6, "AvgD": 3.9, "AvgA": 5.5}
    picked = market.pick_1x2_odds(row)
    assert picked == (1.6, 3.9, 5.5)


def test_pick_ou_odds_priority():
    row = {"P>2.5": 1.9, "P<2.5": 1.95, "Avg>2.5": 1.85, "Avg<2.5": 2.0}
    picked = market.pick_ou_odds(row)
    assert picked == (1.9, 1.95)
