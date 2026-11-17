"""
What was ACTUALLY entered on Kicktipp, as opposed to what the model would
have tipped.

results_refresh re-derives each completed match's model tip from data
strictly before kickoff and scores it. That says nothing about whether the
tip reached Kicktipp: during the Nov 2026 Understat outage every weekly run
aborted before submitting, so matchday 9 was scored in season_points.csv
although no tip was ever entered. This module keeps the two apart:

  * append()   -- predict.py logs every match the Kicktipp step saw, per
                  run, to data/state/kicktipp_log.csv (status + committed).
  * annotate() -- results_refresh adds two columns to season_points.csv:
        tip_submitted  1 = a live run had the tip standing in the Kicktipp
                       form before kickoff, 0 = it never got there.
        submitted_tip  the last tip committed before kickoff ("" if unknown
                       -- see below). May differ from model_tip, which is
                       re-derived after the fact.

Matches that kicked off before config.KICKTIPP_LOG_START predate this log.
They are taken as submitted (tip_submitted = 1, submitted_tip = ""): the
weekly runs before the outage all succeeded, and the only matchday known to
be missed (9, 6-8 Nov 2026) lies after the cutoff, so it is marked 0 by the
missing log entries.
"""
import os

import pandas as pd

import config
from src import crosswalk

LOG_PATH = os.path.join(config.STATE_DIR, "kicktipp_log.csv")
LOG_COLUMNS = ["run_at_utc", "home_fd", "away_fd", "kickoff_local", "tip",
               "status", "live", "committed"]


def _load(path=None):
    path = path or LOG_PATH
    if not os.path.exists(path):
        return pd.DataFrame(columns=LOG_COLUMNS)
    return pd.read_csv(path)


def append(summary, match_contexts, run_at_utc=None, path=None):
    """Append one row per entry of a submit_tips() summary."""
    path = path or LOG_PATH
    entries = summary.get("entries") or []
    if not entries:
        return 0
    run_at = pd.Timestamp(run_at_utc) if run_at_utc is not None else pd.Timestamp.now(tz="UTC")
    if run_at.tzinfo is not None:
        run_at = run_at.tz_convert("UTC").tz_localize(None)
    kickoff = {(m["home_team"], m["away_team"]): m.get("kickoff_ts") for m in match_contexts}
    rows = [{
        "run_at_utc": run_at.strftime("%Y-%m-%d %H:%M:%S"),
        "home_fd": e["home_fd"], "away_fd": e["away_fd"],
        "kickoff_local": (
            pd.Timestamp(kickoff[(e["home_fd"], e["away_fd"])]).strftime("%Y-%m-%d %H:%M")
            if kickoff.get((e["home_fd"], e["away_fd"])) is not None else ""
        ),
        "tip": e["tip"], "status": e["status"],
        "live": int(bool(summary.get("live"))), "committed": int(bool(e["committed"])),
    } for e in entries]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    new = pd.DataFrame(rows, columns=LOG_COLUMNS)
    new.to_csv(path, mode="a", header=not os.path.exists(path), index=False)
    return len(rows)


def annotate(season_points, path=None, log_start=None):
    """Return season_points with tip_submitted / submitted_tip (re)computed
    for every row from the log. Idempotent -- safe to run every refresh.

    season_points `datetime` is Understat kickoff, tz-naive UTC; the log's
    run_at_utc is tz-naive UTC too, so "committed before kickoff" compares
    like with like."""
    df = season_points.copy()
    if len(df) == 0:
        df["tip_submitted"] = pd.Series(dtype="int64")
        df["submitted_tip"] = pd.Series(dtype="object")
        return df

    log_start = pd.Timestamp(log_start or config.KICKTIPP_LOG_START)
    log = _load(path)
    if len(log):
        log = log[log["committed"].astype(int) == 1].copy()
        log["run_at_utc"] = pd.to_datetime(log["run_at_utc"])

    flags, tips = [], []
    for _, r in df.iterrows():
        kickoff = pd.Timestamp(r["datetime"])
        if kickoff < log_start:
            flags.append(1)
            tips.append("")
            continue
        home_fd = crosswalk.UNDERSTAT_TO_FD.get(r["home_team"], r["home_team"])
        away_fd = crosswalk.UNDERSTAT_TO_FD.get(r["away_team"], r["away_team"])
        hit = log[(log["home_fd"] == home_fd) & (log["away_fd"] == away_fd)
                  & (log["run_at_utc"] < kickoff)] if len(log) else log
        if len(hit):
            flags.append(1)
            tips.append(str(hit.sort_values("run_at_utc").iloc[-1]["tip"]))
        else:
            flags.append(0)
            tips.append("")
    df["tip_submitted"] = flags
    df["submitted_tip"] = tips
    return df
