"""
Regression tests for predict.py's upcoming-fixture window.

Two bugs are guarded here, both found live on real 2026/27 matchdays.

1. DATE-ONLY PARSING. A weekly run at 20:04 local did NOT include the
   Bayern Munich vs Stuttgart fixture still 30 minutes from kickoff.
   Cause: fixtures.csv splits kickoff into separate `Date` (dd/mm/yyyy)
   and `Time` (HH:MM) columns, and only `Date` was parsed -- so every
   fixture's timestamp was 00:00 of its matchday. Comparing that against
   "now" silently dropped EVERY same-day fixture once the clock passed
   midnight, so the Friday-evening game was invisible to any Friday run.

2. WRONG SOURCE TIME ZONE. football-data.co.uk publishes D1 `Time`
   values in UK local time, a flat one hour BEHIND the real German local
   kickoff (both zones share DST dates, so the gap does not vary by
   season). The 2026/27 opener was listed as 19:30 for a 20:30 CEST
   kickoff. Uncorrected, any run between 19:30 and 20:30 treated the
   match as already played and published no tip. predict.py now adds
   FD_FIXTURES_TZ_OFFSET (+1h) to every parsed Time.
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


def test_kickoff_timestamp_combines_date_and_time_with_tz_correction():
    """The core fix: a fixture listed at 19:30 is really a 20:30 German
    local kickoff on its matchday (source Time is UK local, +1h behind),
    not 00:00 (which reads as ~20 hours in the past)."""
    df = _fixtures([("Bayern Munich", "Stuttgart", "2026-08-28", "19:30")])
    ts = predict.kickoff_timestamps(df)
    assert ts.iloc[0] == pd.Timestamp("2026-08-28 20:30:00")


def test_parsed_time_is_shifted_by_exactly_one_hour():
    """The offset is a flat +1h regardless of month (UK and German DST
    switch on the same dates), so it holds for a January midweek round
    just as for an August opener."""
    df = _fixtures([
        ("Bayern Munich", "Stuttgart", "2026-08-28", "19:30"),
        ("Dortmund", "Hamburg", "2027-01-20", "18:00"),
    ])
    ts = predict.kickoff_timestamps(df)
    assert list(ts) == [
        pd.Timestamp("2026-08-28 20:30:00"),
        pd.Timestamp("2027-01-20 19:00:00"),
    ]


def test_evening_fixture_is_upcoming_during_the_afternoon_of_its_own_matchday():
    """The exact live failure: at 16:30 on matchday, an evening kickoff
    the same day must still count as upcoming. Under the old date-only
    parsing it resolved to 00:00 that day and was dropped."""
    df = _fixtures([("Bayern Munich", "Stuttgart", "2026-08-28", "19:30")])
    kickoff = predict.kickoff_timestamps(df).iloc[0]

    afternoon_of_matchday = pd.Timestamp("2026-08-28 16:30:00")
    assert kickoff >= afternoon_of_matchday, (
        "Same-day evening fixture was excluded from the upcoming window -- "
        "the real bug this test guards against."
    )


def test_fixture_is_still_upcoming_at_the_listed_time_because_real_kickoff_is_an_hour_later():
    """A run at 19:45 -- past the listed 19:30, before the real 20:30 --
    must still see the fixture as upcoming. This is the second live bug:
    the +1h correction is what keeps it in the window."""
    df = _fixtures([("Bayern Munich", "Stuttgart", "2026-08-28", "19:30")])
    kickoff = predict.kickoff_timestamps(df).iloc[0]

    run_at = pd.Timestamp("2026-08-28 19:45:00")
    assert kickoff >= run_at


def test_fixture_already_kicked_off_is_not_upcoming():
    """The flip side must still hold: once the real (corrected) kickoff
    has genuinely passed, the fixture drops out. A fix that made
    everything 'upcoming' would be just as wrong."""
    df = _fixtures([("Bayern Munich", "Stuttgart", "2026-08-28", "19:30")])
    kickoff = predict.kickoff_timestamps(df).iloc[0]

    after_kickoff = pd.Timestamp("2026-08-28 21:05:00")
    assert not (kickoff >= after_kickoff)


def test_missing_time_falls_back_to_end_of_matchday_not_start():
    """An unparseable/missing Time must keep the fixture alive for the
    whole matchday (23:59), not drop it at 00:00. The +1h source-zone
    correction does NOT apply to this sentinel -- it is an end-of-day
    marker, not a real clock reading."""
    df = _fixtures([("Some Team", "Other Team", "2026-08-29", None)])
    ts = predict.kickoff_timestamps(df)
    assert ts.iloc[0] == pd.Timestamp("2026-08-29 23:59:00")

    midday_of_matchday = pd.Timestamp("2026-08-29 12:00:00")
    assert ts.iloc[0] >= midday_of_matchday


def test_handles_a_full_matchday_mix():
    """End-to-end shape check across a realistic matchday spread; every
    listed Time is shifted +1h to German local."""
    df = _fixtures([
        ("Bayern Munich", "Stuttgart", "2026-08-28", "19:30"),
        ("Elversberg", "Leverkusen", "2026-08-29", "14:30"),
        ("Dortmund", "Hamburg", "2026-08-29", "17:30"),
        ("Augsburg", "Schalke 04", "2026-08-30", "16:30"),
    ])
    ts = predict.kickoff_timestamps(df)
    assert list(ts) == [
        pd.Timestamp("2026-08-28 20:30:00"),
        pd.Timestamp("2026-08-29 15:30:00"),
        pd.Timestamp("2026-08-29 18:30:00"),
        pd.Timestamp("2026-08-30 17:30:00"),
    ]


def test_display_string_shows_corrected_german_local_time():
    """The human-facing label must show the corrected kickoff (20:30),
    never the raw source value (19:30)."""
    label = predict._to_cet_string(pd.Timestamp("2026-08-28 20:30:00"), "19:30")
    assert "20:30" in label
    assert "19:30" not in label


def test_display_string_omits_time_when_source_time_missing():
    label = predict._to_cet_string(pd.Timestamp("2026-08-29 23:59:00"), None)
    assert "23:59" not in label
    assert "Sat 29 Aug" in label
