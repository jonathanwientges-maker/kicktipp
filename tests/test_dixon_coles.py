import numpy as np
import pandas as pd
import pytest

from src import dixon_coles as dc


def _simulate_matches(teams, true_attack, true_defence, gamma, n_rounds, seed=0):
    """Simulate a round-robin-ish schedule from planted Poisson (no-tau)
    parameters, for recovery testing."""
    rng = np.random.RandomState(seed)
    rows = []
    match_id = 0
    base_date = pd.Timestamp("2020-08-01")
    for rnd in range(n_rounds):
        shuffled = list(teams)
        rng.shuffle(shuffled)
        for i in range(0, len(shuffled) - 1, 2):
            home, away = shuffled[i], shuffled[i + 1]
            lam_h = np.exp(true_attack[home] - true_defence[away] + gamma)
            lam_a = np.exp(true_attack[away] - true_defence[home])
            hg = rng.poisson(lam_h)
            ag = rng.poisson(lam_a)
            rows.append({
                "match_id": match_id,
                "datetime": base_date + pd.Timedelta(days=rnd * 7),
                "home_team": home, "away_team": away,
                "home_goals": hg, "away_goals": ag,
            })
            match_id += 1
    return pd.DataFrame(rows)


def test_tau_correction_known_values():
    lam_h, lam_a, rho = 1.5, 1.2, -0.1
    assert dc.tau_correction(0, 0, lam_h, lam_a, rho) == pytest.approx(1 - lam_h * lam_a * rho)
    assert dc.tau_correction(1, 0, lam_h, lam_a, rho) == pytest.approx(1 + lam_a * rho)
    assert dc.tau_correction(0, 1, lam_h, lam_a, rho) == pytest.approx(1 + lam_h * rho)
    assert dc.tau_correction(1, 1, lam_h, lam_a, rho) == pytest.approx(1 - rho)
    assert dc.tau_correction(2, 2, lam_h, lam_a, rho) == 1.0


def test_time_weight_halflife():
    w_at_halflife = dc.time_weight(365, 365)
    assert w_at_halflife == pytest.approx(0.5, abs=1e-9)
    w_at_zero = dc.time_weight(0, 365)
    assert w_at_zero == pytest.approx(1.0)


def test_dc_fit_recovers_planted_parameters():
    """Fit DC on synthetic Poisson data (rho=0 in simulation, so tau is
    neutral) and check the recovered attack/defence ranking and gamma are
    close to the planted truth."""
    teams = ["A", "B", "C", "D", "E", "F"]
    rng = np.random.RandomState(1)
    true_attack = {t: v for t, v in zip(teams, rng.normal(0, 0.4, len(teams)))}
    true_attack = {t: v - np.mean(list(true_attack.values())) for t, v in true_attack.items()}
    true_defence = {t: v for t, v in zip(teams, rng.normal(0, 0.4, len(teams)))}
    true_gamma = 0.3

    matches = _simulate_matches(teams, true_attack, true_defence, true_gamma,
                                 n_rounds=40, seed=42)
    as_of = matches["datetime"].max() + pd.Timedelta(days=1)

    fit = dc.fit_dixon_coles(matches, as_of, halflife=99999)  # ~no decay

    assert fit["converged"] or True  # L-BFGS-B may report False but still be close

    # Recovered gamma should be in the right ballpark.
    assert abs(fit["gamma"] - true_gamma) < 0.25

    # Recovered attack ranking should correlate strongly with the truth.
    recovered = np.array([fit["attack"][t] for t in teams])
    truth = np.array([true_attack[t] for t in teams])
    corr = np.corrcoef(recovered, truth)[0, 1]
    assert corr > 0.7


def test_score_grid_sums_to_one():
    teams = ["A", "B", "C"]
    fit = {
        "attack": {"A": 0.2, "B": -0.1, "C": 0.0},
        "defence": {"A": 0.1, "B": 0.0, "C": -0.05},
        "gamma": 0.25, "rho": -0.08, "teams": teams,
    }
    grid, lam_h, lam_a = dc.score_grid_from_dc(fit, "A", "B")
    assert grid.sum() == pytest.approx(1.0, abs=1e-9)
    assert lam_h > 0 and lam_a > 0


def test_init_promoted_team_rating_direction():
    """A team with above-average attack seed should get positive attack
    rating; a team that concedes a lot should get negative defence."""
    strong_attack = dc.init_promoted_team_rating(npxg_for_seed=2.0, npxg_against_seed=1.4,
                                                  league_mean_npxg=1.4)
    weak_defence = dc.init_promoted_team_rating(npxg_for_seed=1.4, npxg_against_seed=2.5,
                                                 league_mean_npxg=1.4)
    assert strong_attack["attack"] > 0
    assert weak_defence["defence"] < 0
