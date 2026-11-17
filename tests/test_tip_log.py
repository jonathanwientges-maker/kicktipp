"""
Scored-but-never-entered tips (src/tip_log.py).

Live case it guards: during the Nov 2026 Understat outage the weekly runs
aborted before Kicktipp submission, so matchday 9 (6-8 Nov) got no tips,
yet results_refresh later scored the model's re-derived tips for it. Those
rows must be marked tip_submitted = 0 and shown as such.
"""
import pandas as pd
import pytest

from src import kicktipp_submit as ks
from src import report, tip_log
from tests.test_kicktipp_submit import _FakeSession, _ctx, _form_html, _patch_session


@pytest.fixture
def _live_creds(monkeypatch):
    monkeypatch.setenv("KICKTIPP_USER", "me@example.com")
    monkeypatch.setenv("KICKTIPP_PASSWORD", "pw")


# --------------------------------------------------------------------------
# submit_tips -> per-match entries
# --------------------------------------------------------------------------

def test_live_post_marks_entries_committed(monkeypatch, _live_creds):
    fake = _FakeSession(_form_html([
        ("1", "Bayern", "Stuttgart", "", ""),     # blank -> placed
        ("2", "Freiburg", "Mainz", "2", "1"),     # already the tip -> unchanged
    ]))
    _patch_session(monkeypatch, fake)
    ctx = [_ctx("Bayern Munich", "Stuttgart", 3, 1, "2099-01-01 15:30"),
           _ctx("Freiburg", "Mainz", 2, 1, "2099-01-01 15:30")]
    s = ks.submit_tips(ctx, matchday_index=None, live=True)

    by_key = {(e["home_fd"], e["away_fd"]): e for e in s["entries"]}
    assert by_key[("Bayern Munich", "Stuttgart")] == {
        "home_fd": "Bayern Munich", "away_fd": "Stuttgart", "tip": "3-1",
        "status": "placed", "committed": True}
    assert by_key[("Freiburg", "Mainz")]["status"] == "unchanged"
    assert by_key[("Freiburg", "Mainz")]["committed"] is True


def test_dry_run_never_commits(monkeypatch, _live_creds):
    fake = _FakeSession(_form_html([("1", "Bayern", "Stuttgart", "", "")]))
    _patch_session(monkeypatch, fake)
    ctx = [_ctx("Bayern Munich", "Stuttgart", 3, 1, "2099-01-01 15:30")]
    s = ks.submit_tips(ctx, matchday_index=None, live=False)
    assert [e["committed"] for e in s["entries"]] == [False]


def test_kicked_off_match_is_logged_but_not_committed(monkeypatch, _live_creds):
    fake = _FakeSession(_form_html([("1", "Bayern", "Stuttgart", "", "")]))
    _patch_session(monkeypatch, fake)
    ctx = [_ctx("Bayern Munich", "Stuttgart", 3, 1, "2000-01-01 15:30")]
    s = ks.submit_tips(ctx, matchday_index=None, live=True)
    assert s["entries"][0]["status"] == "kickoff"
    assert s["entries"][0]["committed"] is False


# --------------------------------------------------------------------------
# append + annotate
# --------------------------------------------------------------------------

def _season_points():
    # Understat names, tz-naive UTC kickoffs
    return pd.DataFrame([
        # matchday 8 -- before the log existed -> assumed submitted
        {"match_id": 1, "datetime": "2026-11-01 15:30:00",
         "home_team": "Eintracht Frankfurt", "away_team": "Hamburger SV",
         "model_tip": "2-1", "model_points": 2},
        # matchday 9 -- no run got through -> NOT submitted
        {"match_id": 2, "datetime": "2026-11-08 13:30:00",
         "home_team": "FC Cologne", "away_team": "Bayer Leverkusen",
         "model_tip": "1-2", "model_points": 4},
        # later match with a committed live entry before kickoff
        {"match_id": 3, "datetime": "2026-11-21 14:30:00",
         "home_team": "RasenBallsport Leipzig", "away_team": "Borussia M.Gladbach",
         "model_tip": "2-1", "model_points": 2},
        # later match whose only entry came AFTER kickoff -> not submitted
        {"match_id": 4, "datetime": "2026-11-21 14:30:00",
         "home_team": "Freiburg", "away_team": "Mainz 05",
         "model_tip": "1-1", "model_points": 0},
    ])


def _summary(entries, live=True):
    return {"live": live, "entries": entries}


def test_annotate_marks_only_tips_that_reached_kicktipp(tmp_path):
    log = str(tmp_path / "kicktipp_log.csv")
    tip_log.append(_summary([
        {"home_fd": "RB Leipzig", "away_fd": "M'gladbach", "tip": "2-0",
         "status": "placed", "committed": True},
    ]), [], run_at_utc="2026-11-20 16:31:00", path=log)
    # a later run re-entered a different tip, still before kickoff -> latest wins
    tip_log.append(_summary([
        {"home_fd": "RB Leipzig", "away_fd": "M'gladbach", "tip": "2-1",
         "status": "overwritten", "committed": True},
    ]), [], run_at_utc="2026-11-21 09:00:00", path=log)
    tip_log.append(_summary([
        {"home_fd": "Freiburg", "away_fd": "Mainz", "tip": "1-1",
         "status": "placed", "committed": True},
    ]), [], run_at_utc="2026-11-21 15:00:00", path=log)  # after 14:30 kickoff

    out = tip_log.annotate(_season_points(), path=log, log_start="2026-11-02")

    assert list(out["tip_submitted"]) == [1, 0, 1, 0]
    assert list(out["submitted_tip"]) == ["", "", "2-1", ""]


def test_dry_run_rows_in_log_do_not_count(tmp_path):
    log = str(tmp_path / "kicktipp_log.csv")
    tip_log.append(_summary([
        {"home_fd": "FC Koln", "away_fd": "Leverkusen", "tip": "1-2",
         "status": "placed", "committed": False},
    ], live=False), [], run_at_utc="2026-11-06 16:30:00", path=log)
    out = tip_log.annotate(_season_points(), path=log, log_start="2026-11-02")
    assert out.loc[out["match_id"] == 2, "tip_submitted"].item() == 0


def test_annotate_without_any_log_still_flags_post_cutoff_rows(tmp_path):
    out = tip_log.annotate(_season_points(), path=str(tmp_path / "none.csv"),
                           log_start="2026-11-02")
    assert list(out["tip_submitted"]) == [1, 0, 0, 0]


def test_append_without_entries_writes_nothing(tmp_path):
    log = tmp_path / "kicktipp_log.csv"
    assert tip_log.append({"live": True}, [], path=str(log)) == 0
    assert not log.exists()


# --------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------

def test_report_counts_points_not_earned():
    sp = _season_points()
    sp["tip_submitted"] = [1, 0, 1, 0]
    st = report.season_summary_stats(sp)
    assert st["not_entered"] == 2
    assert st["not_entered_points"] == 4
    assert st["entered_points_total"] == 4

    md = report.matchday_points(sp)
    assert md["entered_points"].sum() == 4
    assert md["model_points"].sum() == 8
