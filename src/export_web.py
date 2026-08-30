"""
JSON export for the public website (BUILD BLUEPRINT Phase 3).

Entrypoint: python -m src.export_web
Writes minified UTF-8 JSON into web/public/data/.

HARD RULES (enforced by tests/test_export_web.py):
  - Nothing forward-looking is ever published: no lambdas, no
    probabilities, no model tips or odds for UNPLAYED matches. The only
    forward-looking artefact is season/{s}/simulation.json, derived from
    Dixon-Coles ratings only (never market odds).
  - No data/reports/*.html content reaches web output.
  - Every float rounded to 3 decimals; NaN -> null.

Python 3.9 compatible.
"""
import json
import math
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

import config
from src import storage, web_metrics

WEB_DATA_DIR = os.path.join(config.ROOT_DIR, "web", "public", "data")

_SET_PIECE = web_metrics.SET_PIECE_SITUATIONS
_GOAL_RESULTS = {"Goal", "OwnGoal"}


def _log(msg):
    print("[export_web] {0}".format(msg))


# ---------------------------------------------------------------------------
# JSON writing
# ---------------------------------------------------------------------------
def _clean(obj):
    """Recursively round floats to 3 dp and replace NaN/inf with None."""
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        f = float(obj)
        if math.isnan(f) or math.isinf(f):
            return None
        return round(f, 3)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (np.ndarray,)):
        return [_clean(v) for v in obj.tolist()]
    if isinstance(obj, pd.Timestamp):
        return obj.strftime("%Y-%m-%d")
    return obj


def _write(rel_path, payload):
    path = os.path.join(WEB_DATA_DIR, rel_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(_clean(payload), f, separators=(",", ":"), ensure_ascii=False)
    return path


def _slug(team):
    out = []
    for ch in team.lower():
        if ch.isalnum():
            out.append(ch)
        elif ch in (" ", "-", "_", "'", "."):
            out.append("-")
    s = "".join(out)
    while "--" in s:
        s = s.replace("--", "-")
    return s.strip("-")


# ---------------------------------------------------------------------------
# data load
# ---------------------------------------------------------------------------
class Bundle(object):
    def __init__(self):
        self.matches = storage.all_understat_matches()
        self.shots = storage.all_understat_shots()
        self.rosters = storage.all_understat_rosters()
        self.team_stats = storage.all_understat_team_stats()
        self.odds_d1 = storage.all_odds_d1()
        if len(self.matches):
            self.matches = self.matches.sort_values("datetime").reset_index(drop=True)
            self.matches["matchday"] = web_metrics.matchday_number(self.matches).values
        self.seasons = sorted(self.matches["season"].unique().tolist()) if len(self.matches) else []
        # "current season" = latest season that actually has played matches.
        self.current_season = self.seasons[-1] if self.seasons else config.CURRENT_SEASON
        self.team_stats_available = len(self.team_stats) > 0
        self._odds_by_match = None
        self._backtest = None

    @property
    def odds_by_match(self):
        if self._odds_by_match is None:
            if len(self.odds_d1) and len(self.matches):
                from src.backtest import _join_odds_to_matches
                try:
                    self._odds_by_match = _join_odds_to_matches(self.matches, self.odds_d1)
                except Exception as exc:  # noqa: BLE001
                    _log("odds join failed ({0}); kickoff times degrade to date-only".format(exc))
                    self._odds_by_match = {}
            else:
                self._odds_by_match = {}
        return self._odds_by_match

    @property
    def backtest(self):
        if self._backtest is None:
            p = os.path.join(config.STATE_DIR, "backtest_matches.parquet")
            self._backtest = pd.read_parquet(p) if os.path.exists(p) else pd.DataFrame()
        return self._backtest

    def season_matches(self, season):
        return self.matches[self.matches["season"] == season]

    def season_shots(self, season):
        return self.shots[self.shots["season"] == season] if len(self.shots) else self.shots


# ---------------------------------------------------------------------------
# per-match derived numbers (shared by matches.json and match/{id}.json)
# ---------------------------------------------------------------------------
def _match_shot_lists(shots_m):
    h = shots_m[shots_m["home_away"] == "h"]
    a = shots_m[shots_m["home_away"] == "a"]
    return h, a


def _big_chances(shots_side):
    return int((shots_side["xG"] > 0.3).sum())


def _match_core(b, m):
    mid = int(m["match_id"])
    shots_m = b.shots[b.shots["match_id"] == mid] if len(b.shots) else b.shots.iloc[0:0]
    h, a = _match_shot_lists(shots_m)
    hx = float(h["xG"].sum())
    ax = float(a["xG"].sum())
    npxg_col_h = h["npxG"] if "npxG" in h.columns else h["xG"]
    npxg_col_a = a["npxG"] if "npxG" in a.columns else a["xG"]
    hnp = float(npxg_col_h.sum())
    anp = float(npxg_col_a.sum())
    xph, xpa = web_metrics.match_xpoints(list(h["xG"]), list(a["xG"]))
    date_str, time_str = web_metrics.kickoff_display(m, b.odds_by_match.get(mid))
    return {
        "match_id": mid,
        "matchday": int(m["matchday"]),
        "date": date_str,
        "time": time_str,
        "home": m["home_team"],
        "away": m["away_team"],
        "home_goals": int(m["home_goals"]),
        "away_goals": int(m["away_goals"]),
        "home_xg": hx,
        "away_xg": ax,
        "home_npxg": hnp,
        "away_npxg": anp,
        "home_xpoints": xph,
        "away_xpoints": xpa,
        "home_shots": int(len(h)),
        "away_shots": int(len(a)),
        "home_big_chances": _big_chances(h),
        "away_big_chances": _big_chances(a),
    }


# ---------------------------------------------------------------------------
# 3.7 auto-verdict
# ---------------------------------------------------------------------------
def _fmt_de(x):
    return ("%.2f" % x).replace(".", ",")


def _verdict(core):
    hx, ax = core["home_xg"], core["away_xg"]
    xg_diff = hx - ax
    combined = hx + ax
    hg, ag = core["home_goals"], core["away_goals"]
    tore = "{0}:{1}".format(hg, ag)
    if hx >= ax:
        xg_winner, xg_loser = core["home"], core["away"]
        xg_win_goals, xg_lose_goals = hg, ag
        winner_hi, winner_lo = _fmt_de(hx), _fmt_de(ax)
    else:
        xg_winner, xg_loser = core["away"], core["home"]
        xg_win_goals, xg_lose_goals = ag, hg
        winner_hi, winner_lo = _fmt_de(ax), _fmt_de(hx)
    xg_winner_won = xg_win_goals > xg_lose_goals

    if abs(xg_diff) >= 1.5 and not xg_winner_won:
        return ("{0} gewann das xG-Duell mit {1}:{2}, stand am Ende aber mit "
                "leeren Händen da.").format(xg_winner, winner_hi, winner_lo)
    if abs(xg_diff) >= 1.5 and xg_winner_won:
        return "{0} war klar überlegen und gewann verdient mit {1}.".format(
            xg_winner if hx >= ax else core["away"], tore)
    if combined >= 4.0:
        n = core["home_big_chances"] + core["away_big_chances"]
        return "Ein offenes Spiel mit {0} Großchancen auf beiden Seiten.".format(n)
    if combined <= 1.5:
        return "Ein zerfahrenes Spiel mit wenigen echten Torchancen."
    return "Ein ausgeglichenes Spiel — xG {0}:{1}, Endstand {2}.".format(
        _fmt_de(hx), _fmt_de(ax), tore)


# ---------------------------------------------------------------------------
# model tips per match (ONLY for played matches -- from the backtest log
# and season_points.csv, never re-derived here for unplayed fixtures)
# ---------------------------------------------------------------------------
def _model_tips_frame(b):
    """One row per played match that has a recorded model tip:
    match_id, tip_home, tip_away, model_points, result_home, result_away."""
    frames = []
    bt = b.backtest
    if len(bt):
        rows = []
        for _, r in bt.iterrows():
            tip = r["model_tip"]
            th, ta = int(tip[0]), int(tip[1])
            rows.append({
                "match_id": int(r["match_id"]), "tip_home": th, "tip_away": ta,
                "model_points": int(r["model_points"]),
                "result_home": int(r["home_goals"]), "result_away": int(r["away_goals"]),
            })
        frames.append(pd.DataFrame(rows))
    sp = config.SEASON_POINTS_PATH
    if os.path.exists(sp):
        spdf = pd.read_csv(sp)
        rows = []
        for _, r in spdf.iterrows():
            try:
                th, ta = str(r["model_tip"]).split("-")
            except (ValueError, AttributeError):
                continue
            rows.append({
                "match_id": int(r["match_id"]), "tip_home": int(th), "tip_away": int(ta),
                "model_points": int(r["model_points"]),
                "result_home": np.nan, "result_away": np.nan,
            })
        if rows:
            frames.append(pd.DataFrame(rows))
    if not frames:
        return pd.DataFrame(columns=[
            "match_id", "tip_home", "tip_away", "model_points",
            "result_home", "result_away",
        ])
    return pd.concat(frames, ignore_index=True).drop_duplicates(
        subset=["match_id"], keep="first"
    )


# ---------------------------------------------------------------------------
# exporters
# ---------------------------------------------------------------------------
def export_manifest(b, warnings):
    latest_md = 0
    if len(b.season_matches(b.current_season)):
        latest_md = int(b.season_matches(b.current_season)["matchday"].max())
    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "current_season": int(b.current_season),
        "latest_matchday": latest_md,
        "seasons": [int(s) for s in b.seasons],
        "team_stats_available": bool(b.team_stats_available),
        "warnings": list(warnings),
    }
    _write("manifest.json", payload)


def export_season_table(b, season):
    sm = b.season_matches(season)
    ss = b.season_shots(season)
    table = web_metrics.season_table(sm, ss)
    rows = table.to_dict("records")

    # position-over-time history: per matchday, each team's position
    history = []
    if len(sm):
        max_md = int(sm["matchday"].max())
        for md in range(1, max_md + 1):
            t = web_metrics.season_table(sm, ss, upto_matchday=md)
            for pos, rec in enumerate(t.to_dict("records"), start=1):
                history.append({"matchday": md, "team": rec["team"], "position": pos})
    _write("season/{0}/table.json".format(season),
           {"season": int(season), "table": rows, "history": history})


def export_season_matches(b, season):
    sm = b.season_matches(season)
    entries = [_match_core(b, m) for _, m in sm.iterrows()]
    _write("season/{0}/matches.json".format(season),
           {"season": int(season), "matches": entries})


def _xg_race(shots_m):
    """Cumulative xG per side per minute as step points."""
    ctx = web_metrics.reconstruct_shot_context(shots_m)
    pts_h = [{"minute": 0, "xg": 0.0}]
    pts_a = [{"minute": 0, "xg": 0.0}]
    npxg_col = "npxG" if "npxG" in ctx.columns else "xG"
    cum_h = cum_a = 0.0
    for _, s in ctx.iterrows():
        if s["home_away"] == "h":
            cum_h += float(s[npxg_col])
            pts_h.append({"minute": int(s["minute"]), "xg": cum_h})
        else:
            cum_a += float(s[npxg_col])
            pts_a.append({"minute": int(s["minute"]), "xg": cum_a})
    return {"home": pts_h, "away": pts_a}


def _set_piece_split(shots_side):
    npxg_col = "npxG" if "npxG" in shots_side.columns else "xG"
    open_play = float(shots_side.loc[shots_side["situation"] == "OpenPlay", npxg_col].sum())
    set_piece = float(shots_side.loc[shots_side["situation"].isin(_SET_PIECE), npxg_col].sum())
    penalty = float(shots_side.loc[shots_side["situation"] == "Penalty", "xG"].sum())
    return {"open_play": open_play, "set_piece": set_piece, "penalty": penalty}


def _players_for_match(b, mid):
    if not len(b.rosters):
        return []
    r = b.rosters[b.rosters["match_id"] == mid]
    out = []
    for _, p in r.iterrows():
        out.append({
            "player_id": int(p["player_id"]), "player": p["player"],
            "team_side": p["team_side"], "position": p.get("position"),
            "minutes": int(p["minutes"]), "is_starter": bool(p["is_starter"]),
            "goals": int(p["goals"]), "shots": int(p["shots"]),
            "xg": float(p["xG"]), "xa": float(p["xA"]),
            "key_passes": int(p["key_passes"]), "assists": int(p["assists"]),
            "yellow_card": int(p["yellow_card"]), "red_card": int(p["red_card"]),
        })
    return out


def _team_stat_for_match(b, m):
    """(ppda_home, deep_home, ppda_away, deep_away) or Nones."""
    if not b.team_stats_available:
        return None, None, None, None
    date = pd.to_datetime(m["datetime"]).strftime("%Y-%m-%d")
    ts = b.team_stats
    def _lookup(team, ha):
        row = ts[(ts["team"] == team) & (ts["match_date"].astype(str).str[:10] == date)]
        if len(row) == 0:
            return None, None
        r0 = row.iloc[0]
        return (float(r0["ppda"]) if pd.notna(r0["ppda"]) else None,
                float(r0["deep"]) if pd.notna(r0["deep"]) else None)
    ph, dh = _lookup(m["home_team"], "h")
    pa, da = _lookup(m["away_team"], "a")
    return ph, dh, pa, da


def export_match(b, m, tips_by_id):
    mid = int(m["match_id"])
    core = _match_core(b, m)
    shots_m = b.shots[b.shots["match_id"] == mid] if len(b.shots) else b.shots.iloc[0:0]

    shot_rows = []
    for _, s in shots_m.iterrows():
        npxg = float(s["npxG"]) if "npxG" in s and pd.notna(s["npxG"]) else float(s["xG"])
        shot_rows.append({
            "minute": int(s["minute"]),
            "x": float(s["X"]), "y": float(s["Y"]),
            "xg": float(s["xG"]), "npxg": npxg,
            "result": s["result"], "situation": s["situation"],
            "shot_type": s.get("shotType"),
            "player": s.get("player"),
            "team_side": s["home_away"],
            "is_penalty": bool(s["is_penalty"]),
        })

    h, a = _match_shot_lists(shots_m)
    payload = dict(core)
    payload["shots"] = shot_rows
    payload["xg_race"] = _xg_race(shots_m)
    payload["game_state_xg"] = web_metrics.game_state_xg(shots_m)
    payload["set_piece_split"] = {
        "home": _set_piece_split(h), "away": _set_piece_split(a),
    }
    payload["players"] = _players_for_match(b, mid)
    payload["verdict"] = _verdict(core)

    ph, dh, pa, da = _team_stat_for_match(b, m)
    if ph is not None or pa is not None:
        payload["ppda"] = {"home": ph, "away": pa}
    if dh is not None or da is not None:
        payload["deep"] = {"home": dh, "away": da}

    tip = tips_by_id.get(mid)
    if tip is not None:
        payload["model"] = {
            "tip": [tip["tip_home"], tip["tip_away"]],
            "points": tip["model_points"],
            "result": [core["home_goals"], core["away_goals"]],
        }
    else:
        payload["model"] = None

    _write("match/{0}.json".format(mid), payload)


def export_predicted_table(b, season):
    sm = b.season_matches(season)
    tips = _model_tips_frame(b)
    tips = tips[tips["match_id"].isin(set(sm["match_id"]))]
    pt = web_metrics.predicted_table(sm, tips)
    _write("season/{0}/predicted_table.json".format(season),
           {"season": int(season), "table": pt.to_dict("records")})


def export_model_performance(b, season):
    """Per matchday + cumulative: exact/GD/tendency/miss counts, points,
    and the always-2-1 baseline. Read from backtest_matches.parquet and
    season_points.csv -- NEVER the current unplayed matchday."""
    bt = b.backtest
    rows = []
    if len(bt):
        s = bt[bt["season"] == season].copy()
        if len(s):
            s = s.merge(
                b.matches[["match_id", "matchday"]], on="match_id", how="left"
            ).sort_values("matchday")
            per_md = []
            cum = {"points": 0, "always21": 0, "exact": 0, "gd": 0, "tend": 0,
                   "miss": 0, "n": 0}
            for md, g in s.groupby("matchday"):
                exact = int(g["exact_hit"].sum())
                gd = int(((g["gd_hit"] == 1) & (g["exact_hit"] == 0)).sum())
                tend = int(((g["tendency_hit"] == 1) & (g["gd_hit"] == 0)).sum())
                miss = int(len(g) - exact - gd - tend)
                pts = int(g["model_points"].sum())
                a21 = int(g["always21_points"].sum())
                cum["points"] += pts
                cum["always21"] += a21
                cum["exact"] += exact
                cum["gd"] += gd
                cum["tend"] += tend
                cum["miss"] += miss
                cum["n"] += len(g)
                per_md.append({
                    "matchday": int(md),
                    "exact": exact, "gd": gd, "tendency": tend, "miss": miss,
                    "points": pts, "always21_points": a21,
                    "cum_points": cum["points"], "cum_always21_points": cum["always21"],
                    "cum_exact": cum["exact"], "cum_gd": cum["gd"],
                    "cum_tendency": cum["tend"], "cum_miss": cum["miss"],
                })
            rows = per_md
    _write("season/{0}/model_performance.json".format(season),
           {"season": int(season), "by_matchday": rows})


def export_simulation(b, season):
    """season/{s}/simulation.json -- Dixon-Coles ratings only. Only
    produced for a season with unplayed fixtures remaining AND a usable
    DC fit. Otherwise an explicit {available: false}."""
    payload = {"season": int(season), "available": False}
    try:
        from src import dixon_coles as dc, predict as predict_mod
        sm = b.season_matches(season)
        # remaining fixtures come from the league 'dates' list -- but the
        # scraped matches.parquet only holds PLAYED matches. Without a
        # fixture source for unplayed games we cannot simulate; emit
        # available:false rather than inventing fixtures.
        if len(sm) == 0 or len(sm) >= 306:
            _write("season/{0}/simulation.json".format(season), payload)
            return
        tuned = predict_mod.load_tuned_params()
        history = b.matches[b.matches["datetime"] < sm["datetime"].max()]
        if len(history) < 200:
            _write("season/{0}/simulation.json".format(season), payload)
            return
        dc_fit = dc.fit_dixon_coles(
            history, pd.Timestamp(sm["datetime"].max()), halflife=tuned["halflife"]
        )
        played_pairs = set(zip(sm["home_team"], sm["away_team"]))
        teams = sorted(set(sm["home_team"]) | set(sm["away_team"]))
        remaining = [(h, a) for h in teams for a in teams
                     if h != a and (h, a) not in played_pairs]
        st = web_metrics.season_table(sm, b.season_shots(season))
        standings = {
            r["team"]: {"points": r["points"], "goal_diff": r["goal_diff"],
                        "goals_for": r["goals_for"]}
            for r in st.to_dict("records")
        }
        sim = web_metrics.simulate_season(
            remaining, dc_fit, n_runs=10000, standings_so_far=standings
        )
        payload = {"season": int(season), "available": True,
                   "teams": sim.to_dict("records"), "n_runs": 10000}
    except Exception as exc:  # noqa: BLE001
        _log("simulation for {0} skipped: {1}".format(season, exc))
    _write("season/{0}/simulation.json".format(season), payload)


def export_records(b, season):
    sm = b.season_matches(season)
    ss = b.season_shots(season)
    _write("season/{0}/records.json".format(season),
           {"season": int(season), "records": web_metrics.records_and_streaks(sm, ss)})


def export_h2h(b, season):
    sm = b.season_matches(season)
    teams = sorted(set(sm["home_team"]) | set(sm["away_team"]))
    for i in range(len(teams)):
        for j in range(i + 1, len(teams)):
            a, bteam = teams[i], teams[j]
            h2h = web_metrics.head_to_head(b.matches, a, bteam)
            _write("h2h/{0}__{1}.json".format(_slug(a), _slug(bteam)), h2h)


def export_players(b, season):
    idx = web_metrics.player_aggregates(b.shots, b.rosters, season)
    _write("player/{0}/index.json".format(season),
           {"season": int(season), "players": idx.to_dict("records")})
    if not len(b.rosters):
        return
    ss = b.season_shots(season)
    for _, prow in idx.iterrows():
        pid = int(prow["player_id"])
        psh = ss[ss.get("player_id", pd.Series(dtype=int)) == pid] if "player_id" in ss.columns else ss.iloc[0:0]
        per_match = []
        cum = 0.0
        goals_cum = 0
        series = []
        for mid, g in psh.groupby("match_id"):
            npxg = float(g["npxG"].sum() if "npxG" in g.columns else g["xG"].sum())
            goals = int(g["result"].isin(_GOAL_RESULTS).sum())
            cum += npxg
            goals_cum += goals
            per_match.append({"match_id": int(mid), "npxg": npxg, "goals": goals,
                              "shots": int(len(g))})
            series.append({"match_id": int(mid), "cum_npxg": cum, "cum_goals": goals_cum})
        shot_map = [{"x": float(s["X"]), "y": float(s["Y"]), "xg": float(s["xG"]),
                     "result": s["result"], "match_id": int(s["match_id"])}
                    for _, s in psh.iterrows()]
        best = sorted(per_match, key=lambda r: r["npxg"], reverse=True)[:5]
        _write("player/{0}/{1}.json".format(season, pid), {
            "season": int(season), "player_id": pid, "player": prow["player"],
            "aggregates": {k: prow[k] for k in prow.index},
            "per_match": per_match, "shot_map": shot_map,
            "cumulative": series, "best_matches": best,
        })


def export_leaders(b, season):
    st = web_metrics.season_table(b.season_matches(season), b.season_shots(season))
    team_over = st.sort_values("luck", ascending=False).head(5).to_dict("records")
    team_under = st.sort_values("luck", ascending=True).head(5).to_dict("records")
    pl = web_metrics.player_aggregates(b.shots, b.rosters, season)
    pl_ok = pl[~pl["low_minutes"]] if len(pl) else pl
    player_over = pl_ok.sort_values("npxg_overperformance", ascending=False).head(10).to_dict("records") if len(pl_ok) else []
    player_under = pl_ok.sort_values("npxg_overperformance", ascending=True).head(10).to_dict("records") if len(pl_ok) else []
    _write("season/{0}/leaders.json".format(season), {
        "season": int(season),
        "teams": {"overperformers": team_over, "underperformers": team_under},
        "players": {"overperformers": player_over, "underperformers": player_under},
    })


def export_team_pages(b, season):
    sm = b.season_matches(season).sort_values("matchday")
    ss = b.season_shots(season)
    teams = sorted(set(sm["home_team"]) | set(sm["away_team"]))
    xg_lists = web_metrics._shot_xg_lists_by_match_side(ss)
    for team in teams:
        tmatches = sm[(sm["home_team"] == team) | (sm["away_team"] == team)]
        results = []
        luck_by_md = []
        gs_totals = {"level": 0.0, "winning": 0.0, "losing": 0.0}
        roll_for = {"home": [], "away": []}
        roll_against = {"home": [], "away": []}
        for _, r in tmatches.iterrows():
            is_home = r["home_team"] == team
            mid = r["match_id"]
            sides = xg_lists.get(mid, {"h": [], "a": []})
            xf = sum(sides["h"]) if is_home else sum(sides["a"])
            xa = sum(sides["a"]) if is_home else sum(sides["h"])
            gf = int(r["home_goals"]) if is_home else int(r["away_goals"])
            ga = int(r["away_goals"]) if is_home else int(r["home_goals"])
            venue = "home" if is_home else "away"
            roll_for[venue].append(xf)
            roll_against[venue].append(xa)
            xph, xpa = web_metrics.match_xpoints(sides["h"], sides["a"])
            xp = xph if is_home else xpa
            pts = 3 if gf > ga else (1 if gf == ga else 0)
            results.append({
                "match_id": int(mid), "matchday": int(r["matchday"]),
                "opponent": r["away_team"] if is_home else r["home_team"],
                "venue": venue, "goals_for": gf, "goals_against": ga,
                "xg_for": xf, "xg_against": xa, "points": pts, "xpoints": xp,
            })
            luck_by_md.append({"matchday": int(r["matchday"]), "luck": pts - xp})
            shots_m = ss[ss["match_id"] == mid] if len(ss) else ss.iloc[0:0]
            gsx = web_metrics.game_state_xg(shots_m)
            side = "h" if is_home else "a"
            gs_totals["level"] += gsx["xg_while_level_{0}".format(side)]
            gs_totals["winning"] += gsx["xg_while_winning_{0}".format(side)]
            gs_totals["losing"] += gsx["xg_while_losing_{0}".format(side)]

        def _rolling(vals, n=8):
            out = []
            for i in range(len(vals)):
                w = vals[max(0, i - n + 1): i + 1]
                out.append(sum(w) / len(w))
            return out

        payload = {
            "season": int(season), "team": team, "slug": _slug(team),
            "results": results,
            "luck_by_matchday": luck_by_md,
            "game_state_xg_totals": gs_totals,
            "rolling_xg": {
                "home": {"for": _rolling(roll_for["home"]),
                         "against": _rolling(roll_against["home"])},
                "away": {"for": _rolling(roll_for["away"]),
                         "against": _rolling(roll_against["away"])},
            },
            "upcoming": [],  # opponent + date only; no fixture source for unplayed games
        }
        if b.team_stats_available:
            ts = b.team_stats[b.team_stats["team"] == team]
            payload["ppda_trend"] = [
                {"date": str(x)[:10], "ppda": float(p) if pd.notna(p) else None}
                for x, p in zip(ts["match_date"], ts["ppda"])
            ]
            payload["deep_trend"] = [
                {"date": str(x)[:10], "deep": float(d) if pd.notna(d) else None}
                for x, d in zip(ts["match_date"], ts["deep"])
            ]
        _write("team/{0}/{1}.json".format(season, _slug(team)), payload)


def export_stat_of_the_week(b):
    """§3.8: candidates from the completed matchday, pick the largest
    |z-score| vs the season-to-date distribution."""
    season = b.current_season
    sm = b.season_matches(season)
    if len(sm) == 0:
        _write("stat_of_the_week.json", {"matchday": 0, "headline": "", "value": None,
                                        "context": "", "link": ""})
        return
    latest_md = int(sm["matchday"].max())
    ss = b.season_shots(season)
    mf = web_metrics._match_level_frame(sm, ss)
    mf = mf.merge(sm[["match_id", "matchday"]], on="match_id", how="left")
    season_to_date = mf[mf["matchday"] <= latest_md]
    week = mf[mf["matchday"] == latest_md]
    if len(week) == 0 or len(season_to_date) < 3:
        _write("stat_of_the_week.json", {"matchday": latest_md, "headline": "",
                                        "value": None, "context": "", "link": ""})
        return

    def _z(series, val):
        sd = series.std(ddof=0)
        return 0.0 if sd == 0 else (val - series.mean()) / sd

    cands = []
    # highest combined xG
    row = week.loc[week["combined_xg"].idxmax()]
    cands.append((abs(_z(season_to_date["combined_xg"], row["combined_xg"])),
                  "Höchster Gesamt-xG des Spieltags",
                  round(float(row["combined_xg"]), 2),
                  "{0} – {1}: xG {2}".format(row["home_team"], row["away_team"],
                                                  _fmt_de(row["combined_xg"])),
                  "/spiel/{0}".format(int(row["match_id"]))))
    # biggest xG upset: largest |xg_diff| where the xG winner did NOT win
    week2 = week.assign(abs_xg_diff=week["xg_diff"].abs())
    upset = week2[
        ((week2["xg_diff"] > 0) & (week2["home_goals"] <= week2["away_goals"]))
        | ((week2["xg_diff"] < 0) & (week2["away_goals"] <= week2["home_goals"]))
    ]
    if len(upset):
        row = upset.loc[upset["abs_xg_diff"].idxmax()]
        cands.append((abs(_z(season_to_date["xg_diff"].abs(), row["abs_xg_diff"])),
                      "Größte xG-Überraschung",
                      round(float(row["abs_xg_diff"]), 2),
                      "{0} – {1}: xG-Vorteil {2}, Punkte trotzdem verschenkt".format(
                          row["home_team"], row["away_team"], _fmt_de(row["abs_xg_diff"])),
                      "/spiel/{0}".format(int(row["match_id"]))))
    # highest single-shot xG without a goal
    week_shots = ss[ss["match_id"].isin(set(week["match_id"]))]
    ng = week_shots[~week_shots["result"].isin(_GOAL_RESULTS)]
    all_ng = ss[~ss["result"].isin(_GOAL_RESULTS)]
    if len(ng) and len(all_ng) >= 3:
        srow = ng.loc[ng["xG"].idxmax()]
        cands.append((abs(_z(all_ng["xG"], srow["xG"])),
                      "Größte vergebene Einzelchance",
                      round(float(srow["xG"]), 2),
                      "{0}: xG {1}, kein Tor".format(srow.get("player"), _fmt_de(srow["xG"])),
                      "/spiel/{0}".format(int(srow["match_id"]))))
    # largest luck swing
    week3 = week.assign(mls=week[["home_luck_swing", "away_luck_swing"]].abs().max(axis=1))
    all_ls = pd.concat([season_to_date["home_luck_swing"].abs(),
                        season_to_date["away_luck_swing"].abs()])
    row = week3.loc[week3["mls"].idxmax()]
    cands.append((abs(_z(all_ls, row["mls"])),
                  "Größter Glücksfaktor-Ausschlag",
                  round(float(row["mls"]), 2),
                  "{0} – {1}".format(row["home_team"], row["away_team"]),
                  "/spiel/{0}".format(int(row["match_id"]))))

    cands.sort(key=lambda c: c[0], reverse=True)
    _, headline, value, ctx, link = cands[0]
    _write("stat_of_the_week.json", {
        "matchday": latest_md, "headline": headline, "value": value,
        "context": ctx, "link": link,
    })


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def run():
    b = Bundle()
    warnings = []
    if not b.team_stats_available:
        warnings.append("team_stats unavailable -- PPDA and deep-completion "
                        "panels are hidden site-wide")
    if not len(b.rosters):
        warnings.append("rosters unavailable -- player pages are empty until "
                        "backfill_rosters has run")

    _log("seasons: {0}; current: {1}".format(b.seasons, b.current_season))
    os.makedirs(WEB_DATA_DIR, exist_ok=True)

    tips = _model_tips_frame(b)
    tips_by_id = {int(r["match_id"]): r for _, r in tips.iterrows()}

    for season in b.seasons:
        _log("exporting season {0}...".format(season))
        export_season_table(b, season)
        export_season_matches(b, season)
        export_predicted_table(b, season)
        export_model_performance(b, season)
        export_records(b, season)
        export_players(b, season)
        export_leaders(b, season)
        export_team_pages(b, season)
        for _, m in b.season_matches(season).iterrows():
            export_match(b, m, tips_by_id)

    # current-season-only artefacts
    export_h2h(b, b.current_season)
    export_simulation(b, b.current_season)
    export_stat_of_the_week(b)
    export_manifest(b, warnings)
    _log("done -> {0}".format(WEB_DATA_DIR))


if __name__ == "__main__":
    run()
