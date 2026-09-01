"""
D1: weekly prediction entrypoint (`python -m src.predict`).

1. Refresh current-season Understat + D1.csv; run drift check; update parquets.
2. Download fixtures.csv; filter D1; harmonise names; detect brand-new
   teams -> build promoted prior from D2 history.
3. Rebuild ratings/rolling state from full history (deterministic, fast).
4. For every fixture with kickoff in the next 8 days: compute the three
   lambda pairs, blend with tuned weights, build grid, optimize tip.
5. Render report (report.py), email it (notify.py), commit data + report.
6. Season-tracker: handled by results_refresh (separate entrypoint) after
   results arrive.

CLI flags:
    --no-email   dry-run mode: build + save the report, skip sending mail.
"""
import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

import config
from src import (
    blend,
    crosswalk,
    dixon_coles as dc,
    features,
    kicktipp_submit,
    market,
    notify,
    optimizer,
    promoted_prior,
    report,
    scrape_footballdata,
    scrape_understat,
    storage,
)

FIXTURE_WINDOW_DAYS = 8

# football-data.co.uk's fixtures.csv Time column for Bundesliga (D1) is
# published in UK local time (GMT/BST), NOT German local time -- it is
# consistently ONE HOUR BEHIND the real CET/CEST kickoff. Both zones
# observe DST on the same dates, so the gap is a flat +1h year-round, not
# a seasonal quirk. Confirmed on the 2026/27 opener: CSV said 19:30 for
# Bayern Munich vs Stuttgart, actual kickoff 20:30 CEST. The rest of this
# module treats fixture timestamps as German local (that is the frame the
# report shows and the frame `now` is computed in), so the correction is
# applied once, here, as the CSV is parsed.
FD_FIXTURES_TZ_OFFSET = timedelta(hours=1)


def _log(msg):
    print("[predict] {0}".format(msg))


def load_tuned_params():
    if not os.path.exists(config.TUNED_PARAMS_PATH):
        raise RuntimeError(
            "No tuned_params.json found at {0} -- run the backtest "
            "(src/backtest.py) at least once before predict.py.".format(
                config.TUNED_PARAMS_PATH
            )
        )
    with open(config.TUNED_PARAMS_PATH) as f:
        return json.load(f)


def refresh_current_season_data(season, warnings):
    """Step 1: scrape current-season Understat + D1.csv, run drift check."""
    existing = storage.understat_matches(season)
    existing_ids = set(existing["match_id"]) if existing is not None else set()

    try:
        matches_df, shots_df, rosters_df, team_stats_df, fixtures_df = (
            scrape_understat.scrape_season_enriched(
                config.LEAGUE, season, existing_match_ids=existing_ids,
                warnings=warnings,
            )
        )
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "Understat scrape for season {0} failed: {1}. Aborting run "
            "(no silent fallback).".format(season, exc)
        )

    # Not-yet-played fixtures (teams + kickoff only) -- always overwrite
    # with the freshest pull; shrinks to empty as the season completes.
    storage.write_understat_fixtures(fixtures_df, season)

    if len(matches_df) > 0:
        # scrape_season_enriched only computes the derived per-match npxG /
        # shot counts for matches it actually re-fetched. For an already-
        # complete season nothing is re-fetched, so carry those columns
        # over from the existing partition instead of writing NaN.
        if existing is not None and len(existing) > 0:
            carry_cols = [c for c in ("home_npxG", "away_npxG", "home_shots",
                                      "away_shots")
                          if c in existing.columns]
            if carry_cols:
                prior = existing[["match_id"] + carry_cols].set_index("match_id")
                for c in carry_cols:
                    filled = matches_df["match_id"].map(prior[c])
                    if c in matches_df.columns:
                        matches_df[c] = matches_df[c].where(
                            matches_df[c].notna(), filled
                        )
                    else:
                        matches_df[c] = filled
        storage.write_understat_matches(matches_df, season)
        if existing is not None and len(existing) > 0:
            prior_shots = storage.understat_shots(season)
            if prior_shots is not None and len(prior_shots) > 0:
                shots_df = pd.concat([prior_shots, shots_df], ignore_index=True)
            prior_rosters = storage.understat_rosters(season)
            if prior_rosters is not None and len(prior_rosters) > 0:
                rosters_df = pd.concat([prior_rosters, rosters_df], ignore_index=True)
        storage.write_understat_shots(shots_df, season)
        if len(rosters_df) > 0:
            rosters_df = rosters_df.drop_duplicates(
                subset=["match_id", "player_id", "team_side"], keep="last"
            )
        storage.write_understat_rosters(rosters_df, season)
        # team_stats is a whole-season snapshot from getLeagueData -- always
        # overwrite with the freshest pull (empty frame with correct schema
        # when Understat doesn't expose the per-team block).
        storage.write_understat_team_stats(team_stats_df, season)
        _log("Refreshed season {0}: {1} matches, {2} shot rows, {3} roster rows, "
             "{4} team-stat rows.".format(
                 season, len(matches_df), len(shots_df), len(rosters_df),
                 len(team_stats_df)
             ))

    drift_ok = run_drift_check(warnings)
    if not drift_ok:
        warnings.append(
            "DATA_DRIFT: Understat historical reference data has changed "
            "since the last check -- see drift_hashes.json."
        )

    try:
        d1_df = scrape_footballdata.download_division_csv(season, "D1")
        d1_df = scrape_footballdata.parse_date_column(d1_df, date_col="Date")
        keep = scrape_footballdata.select_feature_columns(d1_df)
        storage.write_odds_d1(keep, season)
        _log("Refreshed current-season D1.csv: {0} rows.".format(len(keep)))
    except Exception as exc:  # noqa: BLE001
        warnings.append(
            "Could not refresh current-season odds (D1.csv): {0}. "
            "Predictions for matches needing fresh odds may be degraded.".format(exc)
        )


def run_drift_check(warnings):
    """Re-scrape the 50 fixed historical match summaries and compare
    SHA256 hashes of (home_xG, away_xG) against drift_hashes.json."""
    if not os.path.exists(config.DRIFT_HASHES_PATH):
        warnings.append("No drift_hashes.json found -- skipping drift check.")
        return True

    with open(config.DRIFT_HASHES_PATH) as f:
        reference = json.load(f)

    try:
        dates_data = scrape_understat.fetch_league_season(config.LEAGUE, reference["season"])
    except Exception as exc:  # noqa: BLE001
        warnings.append("Drift check could not fetch reference season: {0}".format(exc))
        return True

    current_by_id = {int(m["id"]): m for m in dates_data if m.get("isResult")}
    mismatches = []
    for mid_str, expected_hash in reference["hashes"].items():
        mid = int(mid_str)
        m = current_by_id.get(mid)
        if m is None:
            mismatches.append((mid, "missing"))
            continue
        pair_str = "{0:.6f},{1:.6f}".format(float(m["xG"]["h"]), float(m["xG"]["a"]))
        actual_hash = hashlib.sha256(pair_str.encode("utf-8")).hexdigest()
        if actual_hash != expected_hash:
            mismatches.append((mid, "hash mismatch"))

    if mismatches:
        _log("WARNING: DATA DRIFT detected in {0} reference matches: {1}".format(
            len(mismatches), mismatches
        ))
        return False
    _log("Drift check OK: all {0} reference matches match.".format(len(reference["hashes"])))
    return True


def load_fixtures(warnings):
    """Step 2: download fixtures.csv, filter D1, harmonise names, detect
    brand-new teams."""
    try:
        fixtures_df = scrape_footballdata.download_fixtures_csv()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("Could not download fixtures.csv: {0}".format(exc))

    fixtures_df = scrape_footballdata.parse_date_column(fixtures_df, date_col="Date")
    return fixtures_df


def build_full_history():
    matches = storage.all_understat_matches()
    shots = storage.all_understat_shots()
    odds = storage.all_odds_d1()
    return matches, shots, odds


def detect_new_teams(fixtures_df, known_understat_names, warnings):
    """A team in fixtures.csv not resolvable via the crosswalk (and not
    already known) needs a promoted-team prior built from D2 history --
    flagged loudly rather than silently defaulted."""
    fd_names_seen = set(fixtures_df["HomeTeam"]).union(fixtures_df["AwayTeam"])
    known_fd_targets = set(crosswalk.UNDERSTAT_TO_FD.values()).union(known_understat_names)
    new_teams = [n for n in fd_names_seen if n not in known_fd_targets]
    if new_teams:
        warnings.append(
            "New team(s) detected with no crosswalk/history entry: {0}. "
            "Add crosswalk mapping in src/crosswalk.py; promoted-team "
            "prior will use fallback lambdas until D2 history is mapped.".format(new_teams)
        )
    return new_teams


def rebuild_state(matches, shots):
    """Step 3: rebuild rolling xG + DC ratings from full history."""
    # Fix round F4: seed promoted teams' rolling window with a
    # D2-informed prior. Live prediction uses the "no held-out future"
    # fit (promoted_team_seeds_for_live) -- there's no future to leak
    # from when predicting the actual upcoming matchday.
    promoted_seeds = promoted_prior.promoted_team_seeds_for_live(matches)
    xg_enriched = features.compute_lambda_xg(matches, shots, promoted_seeds=promoted_seeds)
    xg_lookup = {
        r["match_id"]: (r["lambda_xg_h"], r["lambda_xg_a"])
        for _, r in xg_enriched.iterrows()
    }

    tuned = load_tuned_params()
    as_of = pd.Timestamp.now(tz="UTC").tz_localize(None)
    dc_fit = dc.fit_dixon_coles(matches, as_of, halflife=tuned["halflife"])

    return xg_lookup, dc_fit, tuned, xg_enriched


def team_rolling_lambda_for_fixture(home_fd, away_fd, xg_enriched, known_fd_names):
    """
    For an upcoming fixture (not yet in matches_df), approximate the
    rolling-xG lambda using each team's most recent same-venue rolling
    values from history (last computed value carries forward as the
    estimate for the next same-venue match).
    """
    home_hist = xg_enriched[xg_enriched["home_team"].map(
        lambda n: crosswalk.to_fd_name(n, known_fd_names=known_fd_names)
    ) == home_fd].sort_values("datetime")
    away_hist = xg_enriched[xg_enriched["away_team"].map(
        lambda n: crosswalk.to_fd_name(n, known_fd_names=known_fd_names)
    ) == away_fd].sort_values("datetime")

    if len(home_hist) == 0 or len(away_hist) == 0:
        return config.FALLBACK_LAMBDAS

    home_attack = home_hist.iloc[-1]["home_attack_roll"]
    away_conceded = away_hist.iloc[-1]["away_conceded_roll_asvenue"]
    away_attack = away_hist.iloc[-1]["away_attack_roll"]
    home_conceded = home_hist.iloc[-1]["home_conceded_roll_asvenue"]
    penalty_addback = home_hist.iloc[-1].get("penalty_addback", 0.0)

    lam_h = (
        config.LAMBDA_BLEND * home_attack
        + (1 - config.LAMBDA_BLEND) * away_conceded
        + penalty_addback
    )
    lam_a = (
        config.LAMBDA_BLEND * away_attack
        + (1 - config.LAMBDA_BLEND) * home_conceded
        + penalty_addback
    )
    if pd.isna(lam_h) or pd.isna(lam_a):
        return config.FALLBACK_LAMBDAS
    return float(lam_h), float(lam_a)


def kickoff_timestamps(fixtures_df, date_col="Date", time_col="Time"):
    """
    Combine fixtures.csv's separate Date and Time columns into a single
    kickoff timestamp, in GERMAN LOCAL TIME (Europe/Berlin), returned
    tz-naive in that same local frame.

    Why this exists: fixtures.csv splits kickoff into `Date` (dd/mm/yyyy)
    and `Time` (HH:MM local). parse_date_column() only parses the date
    part, so a fixture's timestamp lands at 00:00 of its matchday. If
    that is compared against "now" to find upcoming matches, EVERY
    same-day fixture is dropped the moment the clock passes midnight --
    the Friday-evening game is invisible to a Friday-afternoon run, which
    is exactly the match the Friday cron exists to cover. Observed live:
    a run at 20:04 local excluded a 19:30 kickoff still 30 minutes away,
    because it compared against that day's midnight.

    A missing/unparseable Time is treated as 23:59 on the matchday --
    deliberately the END of the day, so an unknown kickoff time keeps the
    fixture in the upcoming window all day rather than silently dropping
    it (a tip published slightly late is recoverable; a tip never
    published is not).

    The parsed Time is shifted by FD_FIXTURES_TZ_OFFSET (+1h): the source
    publishes D1 kickoff times in UK local time, one hour behind the real
    German local kickoff (see that constant's definition). The 23:59
    missing-Time fallback is NOT shifted -- it is an end-of-day sentinel,
    not a real clock reading.
    """
    dates = pd.to_datetime(fixtures_df[date_col])
    times = fixtures_df[time_col] if time_col in fixtures_df.columns else None

    kickoffs = []
    for i, date_val in enumerate(dates):
        if pd.isna(date_val):
            kickoffs.append(pd.NaT)
            continue
        raw_time = times.iloc[i] if times is not None else None
        parsed = pd.to_datetime(str(raw_time), format="%H:%M", errors="coerce") \
            if raw_time is not None and not pd.isna(raw_time) else pd.NaT
        if pd.isna(parsed):
            kickoffs.append(pd.Timestamp(date_val).normalize() + pd.Timedelta(hours=23, minutes=59))
        else:
            kickoffs.append(
                pd.Timestamp(date_val).normalize()
                + pd.Timedelta(hours=int(parsed.hour), minutes=int(parsed.minute))
                + FD_FIXTURES_TZ_OFFSET
            )
    return pd.Series(kickoffs, index=fixtures_df.index)


def understat_fixture_fallback(now, window_end, known_fd_names, warnings):
    """
    Backup fixture source for when fixtures.csv carries no usable D1 row
    for the upcoming window (football-data.co.uk drops the Bundesliga
    block entirely during international breaks and early in a season).

    Reads the Understat fixture partition written every run by
    refresh_current_season_data(), keeps matches whose kickoff falls in
    [now, window_end], and returns them shaped like the `upcoming` frame
    the rest of predict_fixtures() consumes: columns HomeTeam / AwayTeam
    (football-data names, via the crosswalk), kickoff_ts, and a Time
    string (German local HH:MM, so the report shows the real kickoff and
    not just the date). No odds columns -- market lambdas degrade to NaN
    and blend.py renormalises onto xG + DC, which is already handled.

    Understat `datetime` is stored tz-naive UTC (confirmed against
    completed matchdays: a 20:30 CEST kickoff is stored as 18:30). The
    rest of this module works in German local time, so it is converted
    here -- and unlike fixtures.csv there is no UK-vs-German +1h offset to
    undo, Understat times are already correct once shifted to Berlin.
    """
    empty = pd.DataFrame(columns=["HomeTeam", "AwayTeam", "kickoff_ts", "Time"])
    fx = storage.understat_fixtures(config.CURRENT_SEASON)
    if fx is None or len(fx) == 0:
        return empty

    fx = fx.copy()
    kickoff_local = (
        fx["datetime"].dt.tz_localize("UTC").dt.tz_convert("Europe/Berlin").dt.tz_localize(None)
    )
    fx["kickoff_ts"] = kickoff_local
    fx["Time"] = kickoff_local.dt.strftime("%H:%M")
    fx = fx[(fx["kickoff_ts"] >= now) & (fx["kickoff_ts"] <= window_end)].copy()
    if len(fx) == 0:
        return empty

    try:
        fx["HomeTeam"] = fx["home_team"].map(
            lambda n: crosswalk.to_fd_name(n, known_fd_names=known_fd_names)
        )
        fx["AwayTeam"] = fx["away_team"].map(
            lambda n: crosswalk.to_fd_name(n, known_fd_names=known_fd_names)
        )
    except crosswalk.UnresolvedTeamNameError as exc:
        warnings.append(
            "Understat fixture fallback: unresolved team name ({0}). "
            "Add it to UNDERSTAT_TO_FD in src/crosswalk.py.".format(exc)
        )
        return empty

    return fx[["HomeTeam", "AwayTeam", "kickoff_ts", "Time"]].sort_values("kickoff_ts")


def _predict_one_fixture(fx, known_fd_names, xg_enriched, dc_fit, tuned):
    """Blend the three lambda sources for a single upcoming fixture and
    build its report context. `fx` is a row with HomeTeam / AwayTeam /
    kickoff_ts, optionally a Time and odds columns (absent for the
    Understat fallback -> market lambdas come back NaN, handled by
    blend.py)."""
    home_fd, away_fd = fx["HomeTeam"], fx["AwayTeam"]

    lam_market = market.compute_market_lambdas(fx)

    lam_xg = team_rolling_lambda_for_fixture(home_fd, away_fd, xg_enriched, known_fd_names)

    home_understat = _fd_to_understat(home_fd)
    away_understat = _fd_to_understat(away_fd)
    lam_dc = dc.dc_lambdas(dc_fit, home_understat, away_understat)

    weights = tuple(tuned["weights"])
    lam_h, lam_a = blend.blend_log_lambda(lam_market, lam_xg, lam_dc, weights)

    dispersion = (0.05, 0.05) if tuned.get("use_negbin") else None
    grid = blend.build_final_grid(
        lam_h, lam_a, dc_fit["rho"], use_negbin=tuned.get("use_negbin", False),
        dispersion=dispersion,
    )
    rec = optimizer.recommend_tip(grid, draw_margin=tuned.get("draw_margin", config.DRAW_MARGIN))

    mkt_probs = None
    odds_1x2 = market.pick_1x2_odds(fx)
    if odds_1x2 is not None:
        mkt_probs = tuple(market.shin_probabilities(odds_1x2))

    kickoff_cet = _to_cet_string(fx["kickoff_ts"], fx.get("Time"))
    fixture_row = {"home_team": home_fd, "away_team": away_fd, "kickoff_cet": kickoff_cet}

    ctx = report.build_match_context(fixture_row, rec, lam_market, lam_xg, lam_dc, mkt_probs)
    # DST-corrected kickoff timestamp (pd.Timestamp, Europe/Berlin,
    # tz-naive) -- kicktipp_submit uses it for the "too close to
    # kickoff" guard; not shown in the report.
    ctx["kickoff_ts"] = fx["kickoff_ts"]
    ctx["heatmap_div"] = report.heatmap_html(
        grid, div_id="grid-{0}-{1}".format(home_fd, away_fd).replace(" ", "_")
    )
    return ctx


def fixture_source_warning(meta, n_contexts):
    """The report's fixture-source line. Returns "" when the CSV supplied
    fixtures normally (nothing to warn about), otherwise one of three
    strings so a reader can tell apart:
      - Understat fallback used (tips built, but with no market odds);
      - fixtures.csv has NO D1 block at all and Understat had nothing
        either (upstream data-source failure, not a real break);
      - fixtures.csv has a D1 block but none in the window (matchday
        break -- expected, benign).
    """
    n = FIXTURE_WINDOW_DAYS
    if meta["used_understat_fallback"]:
        return (
            "fixtures.csv had no Bundesliga (D1) fixture in the next {0} days "
            "({1} D1 row(s) present at all) -- fell back to the Understat "
            "schedule for {2} fixture(s). These tips have NO market odds "
            "input (blend is xG + Dixon-Coles only); re-check after the "
            "Friday run once football-data republishes the D1 block.".format(
                n, meta["d1_rows_in_csv"], n_contexts
            )
        )
    if n_contexts == 0:
        if meta["d1_rows_in_csv"] == 0:
            return (
                "fixtures.csv contains NO Bundesliga (D1) rows at all, and "
                "the Understat schedule had no fixture in the next {0} days "
                "either. Likely an upstream fixtures.csv data-source issue "
                "rather than a genuine matchday break -- verify manually.".format(n)
            )
        return (
            "No Bundesliga fixtures in the next {0} days -- matchday break. "
            "({1} D1 row(s) in fixtures.csv, none inside the window.)".format(
                n, meta["d1_rows_in_csv"]
            )
        )
    return ""


def predict_fixtures(fixtures_df, matches, xg_lookup, xg_enriched, dc_fit, tuned, warnings):
    # Compare like with like: fixtures.csv kickoff times are German local
    # (CET/CEST), so "now" must be German local too -- a UTC "now" would
    # be 1-2h off and drop fixtures that are still upcoming (or keep ones
    # already played).
    now = pd.Timestamp.now(tz="Europe/Berlin").tz_localize(None)
    window_end = now + timedelta(days=FIXTURE_WINDOW_DAYS)

    fixtures_df = fixtures_df.copy()
    # A fixtures.csv with no D1 rows still keeps its columns; but be
    # defensive -- a truly columnless empty frame must not crash
    # kickoff_timestamps(), it just means "no CSV fixtures, try Understat".
    has_csv_rows = len(fixtures_df) > 0 and "Date" in fixtures_df.columns
    if has_csv_rows:
        fixtures_df["kickoff_ts"] = kickoff_timestamps(fixtures_df)
        upcoming = fixtures_df[
            (fixtures_df["kickoff_ts"] >= now) & (fixtures_df["kickoff_ts"] <= window_end)
        ].copy()
    else:
        upcoming = pd.DataFrame(columns=["HomeTeam", "AwayTeam", "kickoff_ts"])

    # The set of football-data-side names we can resolve a fixture
    # against: every name seen in fixtures.csv itself, plus every
    # historical Understat team name mapped through the crosswalk (or
    # taken as-is for teams never needing a rename).
    known_fd_names = set()
    if "HomeTeam" in fixtures_df.columns:
        known_fd_names = set(fixtures_df["HomeTeam"]).union(fixtures_df["AwayTeam"])
    known_fd_names |= set(
        crosswalk.UNDERSTAT_TO_FD.get(n, n) for n in matches["home_team"].unique()
    )

    # Fixture-source bookkeeping so main() can tell "genuine matchday
    # break" from "upstream fixtures.csv is missing the Bundesliga block".
    # `d1_rows_in_csv` counts D1 rows in fixtures.csv at all (it is
    # already D1-filtered upstream in download_fixtures_csv).
    meta = {
        "d1_rows_in_csv": int(len(fixtures_df)),
        "csv_upcoming": int(len(upcoming)),
        "source": "fixtures.csv",
        "used_understat_fallback": False,
    }

    if len(upcoming) == 0:
        fallback = understat_fixture_fallback(now, window_end, known_fd_names, warnings)
        if len(fallback) > 0:
            _log(
                "fixtures.csv had no D1 fixture in the {0}-day window "
                "({1} D1 row(s) total); using Understat schedule fallback "
                "({2} fixture(s)).".format(
                    FIXTURE_WINDOW_DAYS, meta["d1_rows_in_csv"], len(fallback)
                )
            )
            upcoming = fallback
            meta["source"] = "understat"
            meta["used_understat_fallback"] = True

    match_contexts = []
    for _, fx in upcoming.iterrows():
        match_contexts.append(
            _predict_one_fixture(fx, known_fd_names, xg_enriched, dc_fit, tuned)
        )

    return match_contexts, meta


def _fd_to_understat(fd_name):
    """Reverse lookup: given a football-data name, find the corresponding
    Understat name (or assume identity if never mapped)."""
    reverse = {v: k for k, v in crosswalk.UNDERSTAT_TO_FD.items()}
    return reverse.get(fd_name, fd_name)


def _to_cet_string(kickoff_ts, time_val):
    """Human-facing kickoff label, German local time.

    `kickoff_ts` is the already-corrected timestamp from
    kickoff_timestamps() (source Time + FD_FIXTURES_TZ_OFFSET). The raw
    `time_val` is only consulted to tell "real kickoff time known" from
    "missing Time -> 23:59 end-of-day sentinel"; its clock value is not
    displayed, so the +1h correction is never shown uncorrected.
    """
    ts = pd.Timestamp(kickoff_ts)
    date_str = ts.strftime("%a %d %b")
    if time_val is not None and not pd.isna(time_val):
        return "{0} {1}".format(date_str, ts.strftime("%H:%M"))
    return date_str


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-email", action="store_true",
                         help="Dry-run: build and save the report, skip sending mail.")
    args = parser.parse_args()

    warnings = []
    season = config.CURRENT_SEASON

    _log("Step 1: refreshing current-season data...")
    refresh_current_season_data(season, warnings)

    _log("Step 2: loading fixtures...")
    fixtures_df = load_fixtures(warnings)

    matches, shots, odds = build_full_history()
    detect_new_teams(fixtures_df, set(matches["home_team"]), warnings)

    _log("Step 3: rebuilding ratings/rolling state...")
    xg_lookup, dc_fit, tuned, xg_enriched = rebuild_state(matches, shots)

    _log("Step 4: predicting fixtures in the next {0} days...".format(FIXTURE_WINDOW_DAYS))
    match_contexts, fixture_meta = predict_fixtures(
        fixtures_df, matches, xg_lookup, xg_enriched, dc_fit, tuned, warnings
    )

    fixture_warning = fixture_source_warning(fixture_meta, len(match_contexts))
    if fixture_warning:
        warnings.append(fixture_warning)

    season_points_path = config.SEASON_POINTS_PATH
    if os.path.exists(season_points_path):
        season_points_df = pd.read_csv(season_points_path)
    else:
        season_points_df = pd.DataFrame(columns=["model_points", "always21_points", "market_ev_points"])

    season_tracker_div = report.season_tracker_html(season_points_df, div_id="season-tracker")
    season_stats = {
        "matchdays": len(season_points_df),
        "points_per_matchday": (
            season_points_df["model_points"].mean() if len(season_points_df) else 0.0
        ),
        "exact_hits": int(season_points_df.get("exact_hit", pd.Series(dtype=int)).sum()),
        "gd_hits": int(season_points_df.get("gd_hit", pd.Series(dtype=int)).sum()),
    }

    latest_understat_date = matches["datetime"].max()
    odds_file_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    matchday_number = _infer_matchday_number(fixtures_df)

    # Step 5a: Kicktipp auto-submission. Fully guarded -- any failure is
    # logged and folded into the report, never raised: the report/email
    # is the source of truth and must survive a Kicktipp outage or markup
    # change. Actually places tips only when KICKTIPP_LIVE=1 is in the
    # env AND this is not a --no-email dry run; otherwise it logs in,
    # parses, and reports what it WOULD place.
    kicktipp_lines = []
    try:
        kt_summary = kicktipp_submit.submit_tips(
            match_contexts, matchday_index=None, dry_run=args.no_email
        )
        kicktipp_lines = kicktipp_submit.summary_lines(kt_summary)
        for line in kicktipp_lines:
            _log(line)
    except kicktipp_submit.KicktippNotConfigured as exc:
        _log("Kicktipp auto-submit not configured: {0}".format(exc))
    except kicktipp_submit.KicktippSubmitError as exc:
        msg = "Kicktipp auto-submit failed (report unaffected): {0}".format(exc)
        _log(msg)
        kicktipp_lines = [msg]
        warnings.append(msg)

    context = {
        "matchday_number": matchday_number,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "latest_understat_date": (
            latest_understat_date.strftime("%Y-%m-%d") if pd.notna(latest_understat_date) else "n/a"
        ),
        "odds_file_date": odds_file_date,
        "warnings": warnings,
        "matches": match_contexts,
        "season_tracker_div": season_tracker_div,
        "season_stats": season_stats,
        "tuned_params": tuned,
        "kicktipp_lines": kicktipp_lines,
    }

    out_path = os.path.join(
        config.REPORTS_DIR, "matchday_{0:02d}_report.html".format(matchday_number)
    )
    html = report.render_report(context, out_path)
    _log("Report written to {0}".format(out_path))

    try:
        notify.send_report_email(
            matchday_number, len(match_contexts), html, dry_run=args.no_email
        )
    except notify.EmailSendError as exc:
        _log("ERROR sending email: {0}".format(exc))
        _log("Report was still saved to {0} -- not lost.".format(out_path))
        sys.exit(1)

    if any("DATA_DRIFT" in w for w in warnings):
        _log("Completing with DATA_DRIFT warning(s) present -- see report banner.")


def _infer_matchday_number(fixtures_df):
    """Best-effort matchday inference: count distinct D1 gameweeks played
    so far this season from the odds history + 1. Falls back to 1."""
    try:
        current = storage.odds_d1(config.CURRENT_SEASON)
        if current is not None and len(current) > 0:
            return int(len(current) / 9) + 1  # 9 matches per Bundesliga matchday
    except Exception:  # noqa: BLE001
        pass
    return 1


if __name__ == "__main__":
    main()
