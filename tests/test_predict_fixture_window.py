"""
Regression tests for predict.py's upcoming-fixture window.

The bug these guard against was found live on the first real matchday of
the 2026/27 season: a weekly run at 20:04 local time did NOT include the
19:30 Bayern Munich vs Stuttgart fixture that was still 30 minutes from
kickoff. Cause: fixtures.csv splits kickoff into separate `Date`
(dd/mm/yyyy) and `Time` (HH:MM) columns, and only `Date` was parsed --
so every fixture's timestamp was 00:00 of its matchday. Comparing that
against "now" silently dropped EVERY same-day fixture once the clock
passed midnight, meaning the Friday-evening game was invisible to any
Friday run -- exactly the match the Friday cron exists to cover.

A second, compounding bug: "now" was computed in UTC while kickoff times
are German local (CET/CEST), a 1-2 hour skew on top of the date problem.
"""
import pandas as pd
import pytest

from src import predict


def _fixtures(rows):
    """rows: list of (home, away, date_str 'YYYY-MM-DD', time_str or None)."""
    return pd.DataFrame([
        {
            "HomeTeam": h, "AwayTeam": a,
            "Date": pd.Timestamp(d), "Time": t,
        }
        for h, a, d, t in rows
    ])


def test_kickoff_timestamp_combines_date_and_time():
    """The core fix: a 19:30 fixture must resolve to 19:30 on its
    matchday, not to 00:00 (which reads as ~20 hours in the past)."""
    df = _fixtures([("Bayern Munich", "Stuttgart", "2026-08-28", "19:30")])
    ts = predict.kickoff_timestamps(df)
    assert ts.iloc[0] == pd.Timestamp("2026-08-28 19:30:00")


def test_evening_fixture_is_upcoming_during_the_afternoon_of_its_own_matchday():
    """The exact live failure: at 16:30 on matchday, a 19:30 kickoff the
    same evening must still count as upcoming. Under the old
    date-only parsing it resolved to 00:00 that day and was dropped."""
    df = _fixtures([("Bayern Munich", "Stuttgart", "2026-08-28", "19:30")])
    kickoff = predict.kickoff_timestamps(df).iloc[0]

    afternoon_of_matchday = pd.Timestamp("2026-08-28 16:30:00")
    assert kickoff >= afternoon_of_matchday, (
        "Same-day evening fixture was excluded from the upcoming window -- "
        "the real bug this test guards against."
    )


def test_fixture_already_kicked_off_is_not_upcoming():
    """The flip side must still hold: once kickoff has genuinely passed,
    the fixture drops out. A fix that made everything 'upcoming' would
    be just as wrong."""
    df = _fixtures([("Bayern Munich", "Stuttgart", "2026-08-28", "19:30")])
    kickoff = predict.kickoff_timestamps(df).iloc[0]

    after_kickoff = pd.Timestamp("2026-08-28 20:05:00")
    assert not (kickoff >= after_kickoff)


def test_missing_time_falls_back_to_end_of_matchday_not_start():
    """An unparseable/missing Time must keep the fixture alive for the
    whole matchday (23:59), not drop it at 00:00. Publishing a tip
    slightly late is recoverable; never publishing one is not."""
    df = _fixtures([("Some Team", "Other Team", "2026-08-29", None)])
    ts = predict.kickoff_timestamps(df)
    assert ts.iloc[0] == pd.Timestamp("2026-08-29 23:59:00")

    midday_of_matchday = pd.Timestamp("2026-08-29 12:00:00")
    assert ts.iloc[0] >= midday_of_matchday


def test_handles_a_full_matchday_mix():
    """End-to-end shape check across a realistic matchday spread."""
    df = _fixtures([
        ("Bayern Munich", "Stuttgart", "2026-08-28", "19:30"),
        ("Elversberg", "Leverkusen", "2026-08-29", "14:30"),
        ("Dortmund", "Hamburg", "2026-08-29", "17:30"),
        ("Augsburg", "Schalke 04", "2026-08-30", "16:30"),
    ])
    ts = predict.kickoff_timestamps(df)
    assert list(ts) == [
        pd.Timestamp("2026-08-28 19:30:00"),
        pd.Timestamp("2026-08-29 14:30:00"),
        pd.Timestamp("2026-08-29 17:30:00"),
        pd.Timestamp("2026-08-30 16:30:00"),
    ]
