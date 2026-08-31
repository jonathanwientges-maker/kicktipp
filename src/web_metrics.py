"""
Derived metrics for the public website (BUILD BLUEPRINT Phase 2).

Pure functions: no I/O, no network. Every function here is unit-tested in
tests/test_web_metrics.py. Python 3.9 compatible (no match, no X | Y).

The project's definition of xPunkte for EVERY season is match_xpoints()
below -- exact Poisson-binomial convolution over individual shot
probabilities. Understat's own home_xPTS/away_xPTS columns exist only in
the seeded seasons and are NEVER read (that would split the metric
inconsistently between seeded and live partitions). The Methodik page
states this.
"""
import numpy as np
import pandas as pd

# situations that count as a "set piece" (vs open play vs penalty) for
# the set-piece split (§3.4).
SET_PIECE_SITUATIONS = {"FromCorner", "SetPiece", "DirectFreekick"}

_GOAL_RESULTS = {"Goal", "OwnGoal"}


# ---------------------------------------------------------------------------
# 2.1 shot -> goal distribution
# ---------------------------------------------------------------------------
def shot_goal_distribution(xg_values, max_goals=10):
    """
    Exact Poisson-binomial distribution of the number of goals from a set
    of shots with per-shot scoring probabilities `xg_values`, by
    convolution.

    Start with dist = [1.0]; for each probability p (clipped to
    [0, 0.999]) convolve with [1-p, p]. Truncate to max_goals+1 entries
    and renormalise at the end. Returns a 1-D array of length max_goals+1
    summing to 1.
    """
    dist = np.array([1.0])
    for p in np.asarray(list(xg_values), dtype=float):
        p = float(np.clip(p, 0.0, 0.999))
        dist = np.convolve(dist, np.array([1.0 - p, p]))
        if len(dist) > max_goals + 1:
            dist = dist[: max_goals + 1]
    out = np.zeros(max_goals + 1)
    out[: len(dist)] = dist
    total = out.sum()
    if total > 0:
        out = out / total
    return out


# ---------------------------------------------------------------------------
# 2.2 match xPoints
# ---------------------------------------------------------------------------
def match_xpoints(home_xg_values, away_xg_values):
    """
    Expected Kicktipp-agnostic league points (3 for a win, 1 for a draw)
    for home and away, from the two sides' shot-probability lists.

    dh, da = shot_goal_distribution(...) for each side.
    J = outer(dh, da). P_home = tril(J, -1).sum(); P_away = triu(J, 1).sum();
    P_draw = trace(J). Returns (3*P_home + P_draw, 3*P_away + P_draw).
    """
    dh = shot_goal_distribution(home_xg_values)
    da = shot_goal_distribution(away_xg_values)
    J = np.outer(dh, da)
    p_home = np.tril(J, -1).sum()
    p_away = np.triu(J, 1).sum()
    p_draw = np.trace(J)
    return (3.0 * p_home + p_draw, 3.0 * p_away + p_draw)


# ---------------------------------------------------------------------------
# 2.3 reconstruct shot context
# ---------------------------------------------------------------------------
def reconstruct_shot_context(match_shots_df):
    """
    Add score_home_before_shot, score_away_before_shot, cumulative_xG_home,
    cumulative_xG_away, game_state, score_diff_shooter to a single match's
    shots -- derived uniformly for every season so the schema does not
    depend on whether the partition was seeded or live-scraped.

    Sort by minute, then shot_id. Walk forward maintaining the running
    score and running cumulative (np)xG per side; for each shot record the
    state BEFORE it. game_state is from the shooter's perspective:
    "level" / "winning" / "losing". A shot with result in {"Goal",
    "OwnGoal"} increments the score AFTER being recorded; an own goal
    credits the opposing side.
    """
    if len(match_shots_df) == 0:
        cols = list(match_shots_df.columns) + [
            "score_home_before_shot", "score_away_before_shot",
            "cumulative_xG_home", "cumulative_xG_away",
            "score_diff_shooter", "game_state",
        ]
        return pd.DataFrame(columns=cols)

    df = match_shots_df.sort_values(["minute", "shot_id"]).reset_index(drop=True)
    npxg = df["npxG"] if "npxG" in df.columns else df["xG"]

    score_h = score_a = 0
    cum_h = cum_a = 0.0
    rows = []
    for i in range(len(df)):
        side = df.at[i, "home_away"]
        result = df.at[i, "result"]
        shot_npxg = float(npxg.iloc[i])

        if side == "h":
            diff_shooter = score_h - score_a
        else:
            diff_shooter = score_a - score_h
        if diff_shooter > 0:
            gs = "winning"
        elif diff_shooter < 0:
            gs = "losing"
        else:
            gs = "level"

        rows.append({
            "score_home_before_shot": score_h,
            "score_away_before_shot": score_a,
            "cumulative_xG_home": cum_h,
            "cumulative_xG_away": cum_a,
            "score_diff_shooter": diff_shooter,
            "game_state": gs,
        })

        if side == "h":
            cum_h += shot_npxg
        else:
            cum_a += shot_npxg

        if result == "Goal":
            if side == "h":
                score_h += 1
            else:
                score_a += 1
        elif result == "OwnGoal":
            # own goal credits the opposing side
            if side == "h":
                score_a += 1
            else:
                score_h += 1

    ctx = pd.DataFrame(rows)
    for c in ctx.columns:
        df[c] = ctx[c].values
    return df


# ---------------------------------------------------------------------------
# 2.4 game-state xG
# ---------------------------------------------------------------------------
def game_state_xg(match_shots_df):
    """
    Sum npxG per (team_side, game_state) using reconstruct_shot_context's
    output. Returns the six values keyed xg_while_level_h,
    xg_while_winning_h, xg_while_losing_h and the three away equivalents.
    """
    ctx = reconstruct_shot_context(match_shots_df)
    npxg_col = "npxG" if "npxG" in ctx.columns else "xG"
    out = {}
    for side in ("h", "a"):
        for state in ("level", "winning", "losing"):
            mask = (ctx["home_away"] == side) & (ctx["game_state"] == state)
            key = "xg_while_{0}_{1}".format(state, side)
            out[key] = float(ctx.loc[mask, npxg_col].sum()) if len(ctx) else 0.0
    return out


# ---------------------------------------------------------------------------
# 2.5 matchday number  (single source of truth, shared with lambda_table)
# ---------------------------------------------------------------------------
def matchday_number(matches_df):
    """
    1-indexed matchday within each season, by dense rank of distinct
    kickoff dates. src/lambda_table.py imports this so the two never
    diverge.

    NOTE: because a Bundesliga round is played across ~3 dates, this
    counts ~99 per season, not 1-34 -- it is a match-DATE index, not the
    football Spieltag. It is leakage-insensitive and only used for
    reporting/diagnostics. For the true 1-34 round shown on the website,
    use round_number().
    """
    out = matches_df.copy()
    out["_kickoff_date"] = pd.to_datetime(out["datetime"]).dt.date
    md = (
        out.groupby("season")["_kickoff_date"]
        .rank(method="dense")
        .astype(int)
    )
    return md


def round_number(matches_df, teams_per_round=9):
    """
    The true 1-indexed Bundesliga Spieltag (1..34) for each match, for
    DISPLAY on the website. Within each season, matches are ordered by
    kickoff and grouped in blocks of `teams_per_round` (9 matches = one
    round for an 18-team league); the block index + 1 is the round.

    This is exact for a completed season and for any season whose rounds
    have been played in order. A postponed fixture can momentarily shift
    a couple of matches into the neighbouring round until it is played;
    that self-corrects and never affects the internal matchday_number or
    any stored schema.

    Returns a pd.Series aligned to matches_df's index.
    """
    out = matches_df.copy()
    out["_dt"] = pd.to_datetime(out["datetime"])
    rounds = pd.Series(index=matches_df.index, dtype="int64")
    for season, grp in out.groupby("season"):
        ordered = grp.sort_values(["_dt", "match_id"])
        r = (pd.RangeIndex(len(ordered)) // teams_per_round) + 1
        rounds.loc[ordered.index] = r.astype("int64").values
    return rounds


# ---------------------------------------------------------------------------
# 2.6 kickoff display
# ---------------------------------------------------------------------------
def kickoff_display(match_row, odds_row):
    """
    (date_str 'YYYY-MM-DD', time_str 'HH:MM' or None) for a fixture.

    Date comes from Understat's `datetime`. Time comes from the odds
    parquet's `Time` column (UK local) converted Europe/London ->
    Europe/Berlin. Understat times are inconsistent between seeded and
    live partitions and are never displayed. Where `Time` is absent
    (D1 seasons 2014-2018) the time is None and the site shows the date
    only.
    """
    dt = pd.to_datetime(match_row["datetime"])
    date_str = dt.strftime("%Y-%m-%d")

    time_val = None
    if odds_row is not None:
        try:
            time_val = odds_row.get("Time") if hasattr(odds_row, "get") else odds_row["Time"]
        except (KeyError, TypeError):
            time_val = None
    if time_val is None or (isinstance(time_val, float) and np.isnan(time_val)) or time_val == "":
        return date_str, None

    try:
        hh, mm = str(time_val).strip().split(":")[:2]
        naive = pd.Timestamp(
            year=dt.year, month=dt.month, day=dt.day, hour=int(hh), minute=int(mm)
        )
        london = naive.tz_localize("Europe/London")
        berlin = london.tz_convert("Europe/Berlin")
        return date_str, berlin.strftime("%H:%M")
    except (ValueError, TypeError):
        return date_str, None


def kickoff_time_mismatch_minutes(match_row, odds_row):
    """
    Absolute difference in minutes between the Understat timestamp and the
    converted odds time, for the "log a one-line warning per season where
    they differ by more than 90 minutes" rule (§2.6). Returns None when
    there is no odds time to compare.
    """
    date_str, hhmm = kickoff_display(match_row, odds_row)
    if hhmm is None:
        return None
    dt = pd.to_datetime(match_row["datetime"])
    conv_minutes = int(hhmm[:2]) * 60 + int(hhmm[3:])
    us_minutes = dt.hour * 60 + dt.minute
    return abs(us_minutes - conv_minutes)


# ---------------------------------------------------------------------------
# helpers for the table builders
# ---------------------------------------------------------------------------
def _shot_xg_lists_by_match_side(shots_df):
    """{match_id: {"h": [xg,...], "a": [xg,...]}} using npxG where present
    plus penalty xG (so xPoints reflects total chance quality including
    penalties -- npxG zeroes penalties, but a penalty is still a scoring
    opportunity for the xPoints convolution). We use raw xG here."""
    out = {}
    if len(shots_df) == 0:
        return out
    xg = shots_df["xG"].values
    for mid, side, x in zip(shots_df["match_id"].values,
                            shots_df["home_away"].values, xg):
        out.setdefault(mid, {"h": [], "a": []})[side].append(float(x))
    return out


def _result_points(hg, ag):
    if hg > ag:
        return 3, 0
    if hg < ag:
        return 0, 3
    return 1, 1


# ---------------------------------------------------------------------------
# 2.7 season table
# ---------------------------------------------------------------------------
def season_table(matches_df, shots_df, upto_matchday=None):
    """
    One row per team with played/won/drawn/lost, goals_for/against,
    goal_diff, points, xg_for/against, xg_diff, xpoints and
    luck = points - xpoints. Sorted by points desc, goal_diff desc,
    goals_for desc.
    """
    m = matches_df.copy()
    if len(m) and upto_matchday is not None:
        md = matchday_number(m)
        m = m[md.values <= upto_matchday]

    xg_lists = _shot_xg_lists_by_match_side(shots_df)
    agg = {}

    def _row(team):
        return agg.setdefault(team, {
            "team": team, "played": 0, "won": 0, "drawn": 0, "lost": 0,
            "goals_for": 0, "goals_against": 0, "points": 0,
            "xg_for": 0.0, "xg_against": 0.0, "xpoints": 0.0,
        })

    for _, r in m.iterrows():
        h, a = r["home_team"], r["away_team"]
        hg, ag = int(r["home_goals"]), int(r["away_goals"])
        rh, ra = _row(h), _row(a)
        rh["played"] += 1
        ra["played"] += 1
        rh["goals_for"] += hg
        rh["goals_against"] += ag
        ra["goals_for"] += ag
        ra["goals_against"] += hg
        ph, pa = _result_points(hg, ag)
        rh["points"] += ph
        ra["points"] += pa
        if ph == 3:
            rh["won"] += 1
            ra["lost"] += 1
        elif pa == 3:
            ra["won"] += 1
            rh["lost"] += 1
        else:
            rh["drawn"] += 1
            ra["drawn"] += 1

        mid = r["match_id"]
        sides = xg_lists.get(mid, {"h": [], "a": []})
        hx, ax = sum(sides["h"]), sum(sides["a"])
        rh["xg_for"] += hx
        rh["xg_against"] += ax
        ra["xg_for"] += ax
        ra["xg_against"] += hx
        xph, xpa = match_xpoints(sides["h"], sides["a"])
        rh["xpoints"] += xph
        ra["xpoints"] += xpa

    df = pd.DataFrame(list(agg.values()))
    if len(df) == 0:
        return pd.DataFrame(columns=[
            "team", "played", "won", "drawn", "lost", "goals_for",
            "goals_against", "goal_diff", "points", "xg_for", "xg_against",
            "xg_diff", "xpoints", "luck",
        ])
    df["goal_diff"] = df["goals_for"] - df["goals_against"]
    df["xg_diff"] = df["xg_for"] - df["xg_against"]
    df["luck"] = df["points"] - df["xpoints"]
    df = df.sort_values(
        ["points", "goal_diff", "goals_for"], ascending=[False, False, False]
    ).reset_index(drop=True)
    return df[[
        "team", "played", "won", "drawn", "lost", "goals_for", "goals_against",
        "goal_diff", "points", "xg_for", "xg_against", "xg_diff", "xpoints", "luck",
    ]]


# ---------------------------------------------------------------------------
# 2.8 predicted table
# ---------------------------------------------------------------------------
def predicted_table(matches_df, model_tips_df):
    """
    Same core columns as season_table, but each recorded model tip is
    treated as the result. Only matches with a tip are included. Also
    returns points_actual per team (from the real result) so the site can
    show the difference.

    model_tips_df: columns match_id, tip_home, tip_away (ints).
    """
    tips = {
        int(r["match_id"]): (int(r["tip_home"]), int(r["tip_away"]))
        for _, r in model_tips_df.iterrows()
    }
    agg = {}

    def _row(team):
        return agg.setdefault(team, {
            "team": team, "played": 0, "won": 0, "drawn": 0, "lost": 0,
            "goals_for": 0, "goals_against": 0, "points": 0, "points_actual": 0,
        })

    for _, r in matches_df.iterrows():
        mid = int(r["match_id"])
        if mid not in tips:
            continue
        th, ta = tips[mid]
        h, a = r["home_team"], r["away_team"]
        rh, ra = _row(h), _row(a)
        rh["played"] += 1
        ra["played"] += 1
        rh["goals_for"] += th
        rh["goals_against"] += ta
        ra["goals_for"] += ta
        ra["goals_against"] += th
        ph, pa = _result_points(th, ta)
        rh["points"] += ph
        ra["points"] += pa
        if ph == 3:
            rh["won"] += 1
            ra["lost"] += 1
        elif pa == 3:
            ra["won"] += 1
            rh["lost"] += 1
        else:
            rh["drawn"] += 1
            ra["drawn"] += 1
        aph, apa = _result_points(int(r["home_goals"]), int(r["away_goals"]))
        rh["points_actual"] += aph
        ra["points_actual"] += apa

    df = pd.DataFrame(list(agg.values()))
    if len(df) == 0:
        return pd.DataFrame(columns=[
            "team", "played", "won", "drawn", "lost", "goals_for",
            "goals_against", "goal_diff", "points", "points_actual",
        ])
    df["goal_diff"] = df["goals_for"] - df["goals_against"]
    df = df.sort_values(
        ["points", "goal_diff", "goals_for"], ascending=[False, False, False]
    ).reset_index(drop=True)
    return df[[
        "team", "played", "won", "drawn", "lost", "goals_for", "goals_against",
        "goal_diff", "points", "points_actual",
    ]]


# ---------------------------------------------------------------------------
# 2.9 season simulation  (Dixon-Coles only -- safe to publish)
# ---------------------------------------------------------------------------
def simulate_season(remaining_fixtures, dc_fit, n_runs=10000, seed=20260830,
                    standings_so_far=None):
    """
    Monte-Carlo the rest of a Bundesliga season.

    remaining_fixtures: iterable of (home_team, away_team).
    dc_fit: a fitted Dixon-Coles model -- lambdas come ONLY from
      dixon_coles.dc_lambdas(dc_fit, home, away). Market lambdas are never
      used, so the simulation carries no odds information and is safe to
      publish.
    standings_so_far: optional {team: {"points": int, "goal_diff": int,
      "goals_for": int}} start state; defaults to all-zero for every team
      that appears in remaining_fixtures.

    Returns one row per team: p_pos_1..p_pos_18, p_title, p_cl, p_el,
    p_conf, p_relegation_playoff, p_relegation, mean_points.
    """
    from src import dixon_coles as dc

    rng = np.random.default_rng(seed)
    fixtures = [(h, a) for h, a in remaining_fixtures]
    teams = sorted({t for fx in fixtures for t in fx}
                   | set((standings_so_far or {}).keys()))
    idx = {t: i for i, t in enumerate(teams)}
    n = len(teams)

    base_pts = np.zeros(n)
    base_gd = np.zeros(n)
    base_gf = np.zeros(n)
    if standings_so_far:
        for t, s in standings_so_far.items():
            base_pts[idx[t]] = s.get("points", 0)
            base_gd[idx[t]] = s.get("goal_diff", 0)
            base_gf[idx[t]] = s.get("goals_for", 0)

    lam = np.array([dc.dc_lambdas(dc_fit, h, a) for h, a in fixtures])  # (F, 2)
    home_i = np.array([idx[h] for h, _ in fixtures])
    away_i = np.array([idx[a] for _, a in fixtures])

    pos_counts = np.zeros((n, n))  # [team, finishing_position_0indexed]
    points_sum = np.zeros(n)

    for _ in range(n_runs):
        gh = rng.poisson(lam[:, 0])
        ga = rng.poisson(lam[:, 1])
        pts = base_pts.copy()
        gd = base_gd.copy()
        gf = base_gf.copy()

        home_win = gh > ga
        away_win = ga > gh
        draw = gh == ga
        np.add.at(pts, home_i, np.where(home_win, 3, np.where(draw, 1, 0)))
        np.add.at(pts, away_i, np.where(away_win, 3, np.where(draw, 1, 0)))
        np.add.at(gd, home_i, gh - ga)
        np.add.at(gd, away_i, ga - gh)
        np.add.at(gf, home_i, gh)
        np.add.at(gf, away_i, ga)

        # rank: points, then goal_diff, then goals_for (all desc). Random
        # tiebreak last so ties don't systematically favour one team.
        order = np.lexsort((rng.random(n), -gf, -gd, -pts))
        for finish_pos, team_i in enumerate(order):
            pos_counts[team_i, finish_pos] += 1
        points_sum += pts

    rows = []
    for t in teams:
        i = idx[t]
        p = pos_counts[i] / n_runs
        row = {"team": t}
        for pos in range(1, n + 1):
            row["p_pos_{0}".format(pos)] = float(p[pos - 1])
        row["p_title"] = float(p[0])
        row["p_cl"] = float(p[0:4].sum())
        row["p_el"] = float(p[4]) if n > 4 else 0.0
        row["p_conf"] = float(p[5]) if n > 5 else 0.0
        row["p_relegation_playoff"] = float(p[15]) if n > 15 else 0.0
        row["p_relegation"] = float(p[16:18].sum()) if n > 16 else 0.0
        row["mean_points"] = float(points_sum[i] / n_runs)
        rows.append(row)
    return pd.DataFrame(rows).sort_values("mean_points", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# 2.10 records & streaks
# ---------------------------------------------------------------------------
def _match_level_frame(matches_df, shots_df):
    xg_lists = _shot_xg_lists_by_match_side(shots_df)
    rows = []
    for _, r in matches_df.sort_values("datetime").iterrows():
        mid = r["match_id"]
        sides = xg_lists.get(mid, {"h": [], "a": []})
        hx, ax = sum(sides["h"]), sum(sides["a"])
        xph, xpa = match_xpoints(sides["h"], sides["a"])
        ph, pa = _result_points(int(r["home_goals"]), int(r["away_goals"]))
        rows.append({
            "match_id": mid, "datetime": r["datetime"],
            "home_team": r["home_team"], "away_team": r["away_team"],
            "home_goals": int(r["home_goals"]), "away_goals": int(r["away_goals"]),
            "home_xg": hx, "away_xg": ax, "combined_xg": hx + ax,
            "xg_diff": hx - ax,
            "home_points": ph, "away_points": pa,
            "home_xpoints": xph, "away_xpoints": xpa,
            "home_luck_swing": ph - xph, "away_luck_swing": pa - xpa,
        })
    return pd.DataFrame(rows)


def _current_streak(matches_df, kind):
    """kind: 'unbeaten' or 'winless'. Returns (team, length) for the team
    with the longest CURRENT run of that kind, considering each team's
    matches in chronological order from the end."""
    best_team, best_len = None, 0
    # sorted so ties break deterministically (set iteration order is not
    # stable across runs -> noisy re-exports otherwise)
    teams = sorted(set(matches_df["home_team"]) | set(matches_df["away_team"]))
    for team in teams:
        tm = matches_df[
            (matches_df["home_team"] == team) | (matches_df["away_team"] == team)
        ].sort_values("datetime")
        run = 0
        for _, r in tm[::-1].iterrows():
            is_home = r["home_team"] == team
            gf = r["home_goals"] if is_home else r["away_goals"]
            ga = r["away_goals"] if is_home else r["home_goals"]
            won = gf > ga
            lost = gf < ga
            if kind == "unbeaten":
                if lost:
                    break
            else:  # winless
                if won:
                    break
            run += 1
        if run > best_len:
            best_team, best_len = team, run
    return best_team, best_len


def records_and_streaks(matches_df, shots_df):
    """
    Longest current unbeaten run, longest current winless run, biggest xG
    win, most one-sided match (highest xG ratio), highest-xG match by
    combined xG, highest-xG shot that did not score, biggest single-match
    luck swing.
    """
    out = {}
    ub_team, ub_len = _current_streak(matches_df, "unbeaten")
    wl_team, wl_len = _current_streak(matches_df, "winless")
    out["longest_unbeaten"] = {"team": ub_team, "length": ub_len}
    out["longest_winless"] = {"team": wl_team, "length": wl_len}

    mf = _match_level_frame(matches_df, shots_df)
    if len(mf) == 0:
        out["biggest_xg_win"] = None
        out["most_one_sided"] = None
        out["highest_combined_xg"] = None
        out["highest_xg_no_goal"] = None
        out["biggest_luck_swing"] = None
        return out

    mf["abs_xg_diff"] = mf["xg_diff"].abs()
    row = mf.loc[mf["abs_xg_diff"].idxmax()]
    out["biggest_xg_win"] = {
        "match_id": int(row["match_id"]), "home_team": row["home_team"],
        "away_team": row["away_team"], "home_xg": float(row["home_xg"]),
        "away_xg": float(row["away_xg"]), "xg_diff": float(row["xg_diff"]),
    }

    mf["xg_ratio"] = mf.apply(
        lambda r: (max(r["home_xg"], r["away_xg"]) / min(r["home_xg"], r["away_xg"]))
        if min(r["home_xg"], r["away_xg"]) > 0.05 else np.nan, axis=1
    )
    if mf["xg_ratio"].notna().any():
        row = mf.loc[mf["xg_ratio"].idxmax()]
        out["most_one_sided"] = {
            "match_id": int(row["match_id"]), "home_team": row["home_team"],
            "away_team": row["away_team"], "home_xg": float(row["home_xg"]),
            "away_xg": float(row["away_xg"]), "xg_ratio": float(row["xg_ratio"]),
        }
    else:
        out["most_one_sided"] = None

    row = mf.loc[mf["combined_xg"].idxmax()]
    out["highest_combined_xg"] = {
        "match_id": int(row["match_id"]), "home_team": row["home_team"],
        "away_team": row["away_team"], "combined_xg": float(row["combined_xg"]),
    }

    no_goal = shots_df[~shots_df["result"].isin(_GOAL_RESULTS)]
    if len(no_goal) > 0:
        srow = no_goal.loc[no_goal["xG"].idxmax()]
        out["highest_xg_no_goal"] = {
            "match_id": int(srow["match_id"]),
            "player": srow.get("player"),
            "xg": float(srow["xG"]),
            "minute": int(srow["minute"]),
            "result": srow["result"],
        }
    else:
        out["highest_xg_no_goal"] = None

    mf["max_luck_swing"] = mf[["home_luck_swing", "away_luck_swing"]].abs().max(axis=1)
    row = mf.loc[mf["max_luck_swing"].idxmax()]
    out["biggest_luck_swing"] = {
        "match_id": int(row["match_id"]), "home_team": row["home_team"],
        "away_team": row["away_team"],
        "home_luck_swing": float(row["home_luck_swing"]),
        "away_luck_swing": float(row["away_luck_swing"]),
    }
    return out


# ---------------------------------------------------------------------------
# 2.11 head to head
# ---------------------------------------------------------------------------
def head_to_head(matches_df, team_a, team_b):
    """
    All meetings between team_a and team_b across the loaded seasons:
    results list, aggregate record, aggregate xG, and the most recent
    five with dates.
    """
    m = matches_df[
        ((matches_df["home_team"] == team_a) & (matches_df["away_team"] == team_b))
        | ((matches_df["home_team"] == team_b) & (matches_df["away_team"] == team_a))
    ].sort_values("datetime")

    meetings = []
    a_wins = b_wins = draws = 0
    a_goals = b_goals = 0
    for _, r in m.iterrows():
        hg, ag = int(r["home_goals"]), int(r["away_goals"])
        if r["home_team"] == team_a:
            ag_a, ag_b = hg, ag
        else:
            ag_a, ag_b = ag, hg
        a_goals += ag_a
        b_goals += ag_b
        if ag_a > ag_b:
            a_wins += 1
        elif ag_b > ag_a:
            b_wins += 1
        else:
            draws += 1
        meetings.append({
            "match_id": int(r["match_id"]),
            "date": pd.to_datetime(r["datetime"]).strftime("%Y-%m-%d"),
            "season": int(r["season"]),
            "home_team": r["home_team"], "away_team": r["away_team"],
            "home_goals": hg, "away_goals": ag,
        })

    return {
        "team_a": team_a, "team_b": team_b,
        "meetings": meetings,
        "record": {"a_wins": a_wins, "b_wins": b_wins, "draws": draws,
                   "played": len(meetings)},
        "aggregate_goals": {"a": a_goals, "b": b_goals},
        "recent": meetings[-5:],
    }


# ---------------------------------------------------------------------------
# 2.12 player aggregates
# ---------------------------------------------------------------------------
def player_aggregates(shots_df, rosters_df, season):
    """
    Per player for one season, joining shots and rosters on
    (match_id, player_id): minutes, appearances, starts, goals, npxg, xa,
    shots, npxg_per_90, xa_per_90, npxg_per_shot, npxg_overperformance
    (goals - npxg). Players with < 450 minutes are flagged low_minutes
    (not dropped).
    """
    ros = rosters_df[rosters_df["season"] == season].copy() if len(rosters_df) else rosters_df.copy()
    sh = shots_df[shots_df["season"] == season].copy() if len(shots_df) else shots_df.copy()

    if len(ros) == 0:
        return pd.DataFrame(columns=[
            "player_id", "player", "minutes", "appearances", "starts", "goals",
            "npxg", "xa", "shots", "npxg_per_90", "xa_per_90", "npxg_per_shot",
            "npxg_overperformance", "low_minutes",
        ])

    ros = ros[ros["player_id"] >= 0]
    grp = ros.groupby("player_id")
    base = grp.agg(
        player=("player", "last"),
        minutes=("minutes", "sum"),
        appearances=("match_id", "nunique"),
        starts=("is_starter", "sum"),
        xa=("xA", "sum"),
    ).reset_index()

    # shot-derived: npxg, goals, shot count from the shots table (more
    # precise than the rosters' rounded per-match aggregates).
    if len(sh) > 0:
        sh = sh[sh["player_id"] >= 0] if "player_id" in sh.columns else sh.iloc[0:0]
    if len(sh) > 0:
        npxg_col = sh["npxG"] if "npxG" in sh.columns else sh["xG"]
        sh = sh.assign(_npxg=npxg_col,
                       _goal=sh["result"].isin(_GOAL_RESULTS).astype(int))
        sgrp = sh.groupby("player_id").agg(
            npxg=("_npxg", "sum"),
            goals=("_goal", "sum"),
            shots=("shot_id", "count"),
        ).reset_index()
    else:
        sgrp = pd.DataFrame(columns=["player_id", "npxg", "goals", "shots"])

    df = base.merge(sgrp, on="player_id", how="left")
    for c in ("npxg", "goals", "shots", "xa"):
        df[c] = df[c].fillna(0.0)
    df["starts"] = df["starts"].astype(int)
    df["npxg_per_90"] = np.where(df["minutes"] > 0, df["npxg"] / df["minutes"] * 90.0, 0.0)
    df["xa_per_90"] = np.where(df["minutes"] > 0, df["xa"] / df["minutes"] * 90.0, 0.0)
    df["npxg_per_shot"] = np.where(df["shots"] > 0, df["npxg"] / df["shots"], 0.0)
    df["npxg_overperformance"] = df["goals"] - df["npxg"]
    df["low_minutes"] = df["minutes"] < 450
    return df.sort_values("npxg", ascending=False).reset_index(drop=True)[[
        "player_id", "player", "minutes", "appearances", "starts", "goals",
        "npxg", "xa", "shots", "npxg_per_90", "xa_per_90", "npxg_per_shot",
        "npxg_overperformance", "low_minutes",
    ]]
