"""
Tests for src/kicktipp_submit.py -- form parsing, the fill-blanks /
kickoff / team-alias decision logic, and the guarantee that nothing is
POSTed unless submission is explicitly live.

No network: the bet form is a hand-written HTML fixture matching the
long-standing Kicktipp structure (spieltippForms[<id>].heimTipp /
gastTipp inputs, hidden token fields, one <tr> per match).
"""
import pandas as pd
import pytest

import config
from src import kicktipp_submit as ks


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------
def _form_html(rows, hidden=None):
    """rows: list of (game_id, home_display, away_display, heim_val, gast_val)."""
    hidden = hidden or {"_csrf": "tok123", "submitbutton": "Tippen"}
    hidden_html = "".join(
        '<input type="hidden" name="{0}" value="{1}">'.format(k, v)
        for k, v in hidden.items()
    )
    tr_html = ""
    for gid, home, away, hv, gv in rows:
        tr_html += (
            "<tr>"
            '<td class="nowrap">{home}</td>'
            '<td><input type="text" name="spieltippForms[{gid}].heimTipp" value="{hv}"></td>'
            '<td>:</td>'
            '<td><input type="text" name="spieltippForms[{gid}].gastTipp" value="{gv}"></td>'
            '<td class="nowrap">{away}</td>'
            "</tr>"
        ).format(home=home, away=away, gid=gid, hv=hv, gv=gv)
    return (
        "<html><body>"
        '<form action="/buli-challenge/tippabgabe" method="post">'
        "{hidden}"
        "<table><tbody>{trs}</tbody></table>"
        '<input type="submit" name="submitbutton" value="Tippen">'
        "</form></body></html>"
    ).format(hidden=hidden_html, trs=tr_html)


def _ctx(home, away, h, a, kickoff):
    return {
        "home_team": home, "away_team": away,
        "tip_h": h, "tip_a": a,
        "kickoff_ts": pd.Timestamp(kickoff) if kickoff else None,
    }


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------
def test_parse_extracts_rows_fields_and_hidden():
    html = _form_html([
        ("111", "Bayern", "Stuttgart", "", ""),
        ("222", "Dortmund", "Hamburg", "2", "1"),
    ])
    meta, rows = ks.parse_bet_form(html)

    assert meta["action"].endswith("/buli-challenge/tippabgabe")
    assert meta["hidden"]["_csrf"] == "tok123"

    assert [r["game_id"] for r in rows] == ["111", "222"]
    assert rows[0]["home_fd"] == "Bayern Munich"
    assert rows[0]["away_fd"] == "Stuttgart"
    assert rows[0]["heim_field"] == "spieltippForms[111].heimTipp"
    assert rows[0]["gast_field"] == "spieltippForms[111].gastTipp"
    assert rows[0]["heim_value"] == "" and rows[0]["gast_value"] == ""
    assert rows[1]["heim_value"] == "2" and rows[1]["gast_value"] == "1"


def test_parse_raises_when_no_bet_form_present():
    with pytest.raises(ks.KicktippSubmitError):
        ks.parse_bet_form("<html><body><form><input name='other'></form></body></html>")


def test_unmapped_team_name_is_a_hard_failure():
    html = _form_html([("1", "Bayern", "Wattenscheid 09", "", "")])
    with pytest.raises(ks.KicktippSubmitError) as ei:
        ks.parse_bet_form(html)
    assert "KICKTIPP_TEAM_ALIASES" in str(ei.value)


def test_every_current_bundesliga_alias_resolves_without_raising():
    # 2026/27 fixtures.csv D1 team names -> must all be reachable.
    names = [
        "Bayern", "Stuttgart", "Elversberg", "Leverkusen", "Köln", "Hoffenheim",
        "Mainz", "Paderborn", "RB Leipzig", "Gladbach", "Union", "Frankfurt",
        "Dortmund", "Hamburg", "Freiburg", "Werder", "Augsburg", "St. Pauli",
        "Heidenheim",
    ]
    for n in names:
        assert ks._resolve_team(n)  # no raise


def test_full_kicktipp_style_names_resolve_via_normalization():
    """The variants Kicktipp actually renders -- founding years, legal
    forms, 'Borussia' -- must resolve without needing an exact entry."""
    cases = {
        "1899 Hoffenheim": "Hoffenheim",
        "TSG 1899 Hoffenheim": "Hoffenheim",
        "1. FC Köln": "FC Koln",
        "1. FSV Mainz 05": "Mainz",
        "VfB Stuttgart": "Stuttgart",
        "VfL Wolfsburg": "Wolfsburg",
        "Borussia Dortmund": "Dortmund",
        "Bor. Mönchengladbach": "M'gladbach",
        "1. FC Union Berlin": "Union Berlin",
        "1. FC Heidenheim 1846": "Heidenheim",
        "SV 07 Elversberg": "Elversberg",
        "Hamburger SV": "Hamburg",
        "SC Freiburg": "Freiburg",
        "FC Augsburg": "Augsburg",
        "SV Werder Bremen": "Werder Bremen",
    }
    for kt_name, expected in cases.items():
        assert ks._resolve_team(kt_name) == expected, kt_name


def test_second_bundesliga_names_now_resolve():
    cases = {
        "FC Schalke 04": "Schalke 04",
        "Hertha BSC": "Hertha",
        "1. FC Nürnberg": "Nurnberg",
        "Fortuna Düsseldorf": "Fortuna Dusseldorf",
        "Karlsruher SC": "Karlsruhe",
        "1. FC Kaiserslautern": "Kaiserslautern",
        "SpVgg Greuther Fürth": "Greuther Furth",
        "Holstein Kiel": "Holstein Kiel",
    }
    for kt_name, expected in cases.items():
        assert ks._resolve_team(kt_name) == expected, kt_name


def test_normalization_still_hard_fails_on_a_genuinely_unknown_club():
    with pytest.raises(ks.KicktippSubmitError) as ei:
        ks._resolve_team("SV Neverheard 1900")
    assert "not in" in str(ei.value)


def test_schalke_fixture_resolves_and_is_placed_when_model_has_a_tip():
    """Augsburg vs Schalke 04 is a real 2026/27 Bundesliga fixture the
    model tips -- it must resolve and be placed, not hard-fail."""
    html = _form_html([("1", "Augsburg", "FC Schalke 04", "", "")])
    rows = _rows_from(html)
    assert rows[0]["home_fd"] == "Augsburg"
    assert rows[0]["away_fd"] == "Schalke 04"

    model = {("Augsburg", "Schalke 04"): (1, 2, pd.Timestamp("2099-01-01 15:30"))}
    d = ks._decide(rows, model, pd.Timestamp("2098-01-01 12:00"))
    assert [p["row"]["game_id"] for p in d["to_place"]] == ["1"]


def test_form_row_with_no_model_tip_is_skipped_not_fatal():
    """A form row for a fixture outside the model's D1 fixture window must
    land in 'unmatched' and be skipped -- never placed, never a crash."""
    html = _form_html([
        ("1", "Hertha BSC", "1. FC Nürnberg", "", ""),
        ("2", "Bayern", "Stuttgart", "", ""),
    ])
    rows = _rows_from(html)
    model = {("Bayern Munich", "Stuttgart"): (3, 1, pd.Timestamp("2099-01-01 15:30"))}
    d = ks._decide(rows, model, pd.Timestamp("2098-01-01 12:00"))

    assert [p["row"]["game_id"] for p in d["to_place"]] == ["2"]
    assert d["unmatched"] and "Hertha vs Nurnberg" in d["unmatched"][0]


# --------------------------------------------------------------------------
# Decision logic
# --------------------------------------------------------------------------
def _rows_from(html):
    _, rows = ks.parse_bet_form(html)
    return rows


def test_fill_blanks_only_skips_rows_that_already_have_a_value():
    html = _form_html([
        ("1", "Bayern", "Stuttgart", "", ""),      # blank -> place
        ("2", "Dortmund", "Hamburg", "2", "1"),    # filled -> skip
    ])
    rows = _rows_from(html)
    model = {
        ("Bayern Munich", "Stuttgart"): (3, 1, pd.Timestamp("2099-01-01 15:30")),
        ("Dortmund", "Hamburg"): (2, 0, pd.Timestamp("2099-01-01 15:30")),
    }
    now = pd.Timestamp("2098-12-31 12:00")
    d = ks._decide(rows, model, now)

    assert [p["row"]["game_id"] for p in d["to_place"]] == ["1"]
    assert d["skipped_existing"] and "Dortmund" in d["skipped_existing"][0]


def test_kickoff_guard_skips_matches_within_min_lead_hours():
    html = _form_html([("1", "Bayern", "Stuttgart", "", "")])
    rows = _rows_from(html)
    now = pd.Timestamp("2026-08-28 19:00")
    model = {("Bayern Munich", "Stuttgart"): (3, 1, pd.Timestamp("2026-08-28 20:30"))}
    # 1.5h to kickoff, min lead is 2h -> skip
    d = ks._decide(rows, model, now)
    assert not d["to_place"]
    assert d["skipped_kickoff"]


def test_kickoff_guard_allows_matches_outside_min_lead_hours():
    html = _form_html([("1", "Bayern", "Stuttgart", "", "")])
    rows = _rows_from(html)
    now = pd.Timestamp("2026-08-28 16:00")
    model = {("Bayern Munich", "Stuttgart"): (3, 1, pd.Timestamp("2026-08-28 20:30"))}
    d = ks._decide(rows, model, now)
    assert [p["row"]["game_id"] for p in d["to_place"]] == ["1"]


def test_row_without_a_model_tip_is_reported_unmatched():
    html = _form_html([("1", "Bayern", "Stuttgart", "", "")])
    rows = _rows_from(html)
    d = ks._decide(rows, {}, pd.Timestamp("2026-08-01 12:00"))
    assert not d["to_place"]
    assert d["unmatched"] and "Bayern Munich vs Stuttgart" in d["unmatched"][0]


# --------------------------------------------------------------------------
# POST body
# --------------------------------------------------------------------------
def test_post_body_fills_blanks_and_preserves_everything_else():
    html = _form_html([
        ("1", "Bayern", "Stuttgart", "", ""),
        ("2", "Dortmund", "Hamburg", "2", "1"),
    ])
    meta, rows = ks.parse_bet_form(html)
    to_place = [{"row": rows[0], "tip_h": 3, "tip_a": 1}]
    body = ks._build_post_body(meta, rows, to_place)

    assert body["spieltippForms[1].heimTipp"] == "3"
    assert body["spieltippForms[1].gastTipp"] == "1"
    # untouched row keeps its existing values
    assert body["spieltippForms[2].heimTipp"] == "2"
    assert body["spieltippForms[2].gastTipp"] == "1"
    # hidden fields echoed
    assert body["_csrf"] == "tok123"


# --------------------------------------------------------------------------
# submit_tips end-to-end (mocked HTTP) -- the no-POST-unless-live guarantee
# --------------------------------------------------------------------------
class _FakeResp:
    def __init__(self, text="", status=200):
        self.text = text
        self.status_code = status

    def raise_for_status(self):
        pass


class _FakeSession:
    def __init__(self, form_html):
        self._form_html = form_html
        self.cookies = {"login": "yes"}
        self.headers = {}
        self.posts = []

    def get(self, url, params=None, timeout=None):
        return _FakeResp(self._form_html)

    def post(self, url, data=None, timeout=None, allow_redirects=True):
        self.posts.append((url, data))
        return _FakeResp("ok", 200)


@pytest.fixture
def _live_creds(monkeypatch):
    monkeypatch.setenv("KICKTIPP_USER", "me@example.com")
    monkeypatch.setenv("KICKTIPP_PASSWORD", "pw")


def _patch_session(monkeypatch, fake):
    monkeypatch.setattr(ks, "_new_session", lambda: fake)
    # _login just checks the 'login' cookie, which the fake already has;
    # but it also POSTs -- let it, the fake records & ignores.


def test_not_live_does_full_dry_run_but_never_posts_a_bet(monkeypatch, _live_creds):
    fake = _FakeSession(_form_html([("1", "Bayern", "Stuttgart", "", "")]))
    _patch_session(monkeypatch, fake)

    ctx = [_ctx("Bayern Munich", "Stuttgart", 3, 1, "2099-01-01 15:30")]
    summary = ks.submit_tips(ctx, matchday_index=None, dry_run=False, live=False)

    assert summary["live"] is False
    assert summary["submitted"] is False
    assert summary["placed"] == ["Bayern Munich vs Stuttgart -> 3:1"]
    # only the login POST may have happened -- never a POST to the form action
    form_posts = [p for p in fake.posts if "tippabgabe" in p[0]]
    assert form_posts == []


def test_dry_run_flag_forces_no_post_even_when_live(monkeypatch, _live_creds):
    fake = _FakeSession(_form_html([("1", "Bayern", "Stuttgart", "", "")]))
    _patch_session(monkeypatch, fake)

    ctx = [_ctx("Bayern Munich", "Stuttgart", 3, 1, "2099-01-01 15:30")]
    summary = ks.submit_tips(ctx, matchday_index=None, dry_run=True, live=True)

    assert summary["submitted"] is False
    assert [p for p in fake.posts if "tippabgabe" in p[0]] == []


def test_live_and_not_dry_run_posts_exactly_once(monkeypatch, _live_creds):
    fake = _FakeSession(_form_html([("1", "Bayern", "Stuttgart", "", "")]))
    _patch_session(monkeypatch, fake)

    ctx = [_ctx("Bayern Munich", "Stuttgart", 3, 1, "2099-01-01 15:30")]
    summary = ks.submit_tips(ctx, matchday_index=None, dry_run=False, live=True)

    assert summary["submitted"] is True
    form_posts = [p for p in fake.posts if "tippabgabe" in p[0]]
    assert len(form_posts) == 1
    _, body = form_posts[0]
    assert body["spieltippForms[1].heimTipp"] == "3"
    assert body["spieltippForms[1].gastTipp"] == "1"


def test_missing_credentials_raise_not_configured_not_error(monkeypatch):
    monkeypatch.delenv("KICKTIPP_USER", raising=False)
    monkeypatch.delenv("KICKTIPP_PASSWORD", raising=False)
    with pytest.raises(ks.KicktippNotConfigured):
        ks.submit_tips([_ctx("Bayern Munich", "Stuttgart", 1, 0, None)],
                       matchday_index=None)


def test_no_fixtures_returns_clean_summary(monkeypatch, _live_creds):
    summary = ks.submit_tips([], matchday_index=None, live=True)
    assert summary["placed"] == []
    assert summary.get("note") == "no fixtures to submit"
