"""
Kicktipp auto-submission (optional weekly step).

Logs into kicktipp.de with a plain requests.Session (no browser) and
enters the model's tips into the community bet form. Deliberately narrow:
it places the exact-score tip the model already computed, for still-open
matches of the current matchday.

Each weekly run is a full recompute, and by default its tips SUPERSEDE
the previous run's: an existing value in the form -- a prior auto-entry
or a manual edit, indistinguishable to us -- is overwritten. Set
config.KICKTIPP_FILL_BLANKS_ONLY = True to go back to touching only blank
rows.

Safety model
------------
* OFF unless KICKTIPP_LIVE=1 is in the environment. Without it, the whole
  flow runs (login, parse, decide) and returns a summary of what it WOULD
  submit, but sends no POST. `dry_run=True` (predict.py --no-email) forces
  the same.
* A match that has already kicked off is never touched. With
  config.KICKTIPP_MIN_LEAD_HOURS > 0, nothing inside that pre-kickoff
  window is touched either; 0 (the default) disables that window.
* A row already holding exactly the model tip is left alone (no-op).
* config.KICKTIPP_FILL_BLANKS_ONLY (default False): when True, any row
  that already holds a value is left as-is.
* Team names are matched Kicktipp-display -> football-data via
  config.KICKTIPP_TEAM_ALIASES. An unmapped name is a HARD FAILURE
  (KicktippSubmitError), never a silent skip -- a score entered against
  the wrong fixture is worse than no score.
* Caller (predict.py) invokes this AFTER the report email is sent and
  wraps it in try/except: a submission failure must never cost the report.

Form contract
-------------
Reverse-engineered from the long-standing kicktipp-betbot projects and
stable for years:
  * login:  POST {BASE}/info/profil/loginaction
              kennung=<email>&passwort=<pw>&_charset_=UTF-8
              &showLoginAdditionalOptions=
            success = a 'login' cookie is set on the session.
  * form :  GET  {BASE}/{community}/tippabgabe?&spieltagIndex=<md>
            one <form> containing a row per match. Each row has two text
            inputs named
              spieltippForms[<gameId>].heimTipp
              spieltippForms[<gameId>].gastTipp
            plus hidden inputs (submit button name, csrf-ish tokens) that
            must be echoed back verbatim.
  * submit: POST to the form's `action` with every field: blanks we fill,
            existing values preserved, hidden fields echoed.

If Kicktipp changes the markup this module raises a clear
KicktippSubmitError rather than silently posting garbage.
"""
import os
import re
import time

import requests
from bs4 import BeautifulSoup

import config


MAX_ATTEMPTS = 3
RETRY_DELAY_S = 5
TIMEOUT_S = 30

_FIELD_RE = re.compile(r"spieltippForms\[(?P<gid>[^\]]+)\]\.(?P<side>heimTipp|gastTipp)")


class KicktippSubmitError(Exception):
    """A hard failure once submission was actually attempted (bad login,
    changed markup, unmapped team). Surfaced as a report warning."""


class KicktippNotConfigured(Exception):
    """Credentials absent -- auto-submit is simply not set up yet. Not an
    error; the caller logs it quietly and moves on."""


# --------------------------------------------------------------------------
# HTTP helpers
# --------------------------------------------------------------------------
def _new_session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        )
    })
    return s


def _login(session, user, password):
    url = "{0}/info/profil/loginaction".format(config.KICKTIPP_BASE)
    payload = {
        "kennung": user,
        "passwort": password,
        "_charset_": "UTF-8",
        "showLoginAdditionalOptions": "",
    }
    last_err = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            resp = session.post(url, data=payload, timeout=TIMEOUT_S,
                                allow_redirects=True)
            resp.raise_for_status()
            if session.cookies.get("login"):
                return
            last_err = RuntimeError(
                "login POST returned {0} but no 'login' cookie was set "
                "(bad credentials, or social-login-only account).".format(
                    resp.status_code
                )
            )
        except Exception as exc:  # noqa: BLE001 - deliberate broad retry
            last_err = exc
        if attempt < MAX_ATTEMPTS:
            time.sleep(RETRY_DELAY_S)
    raise KicktippSubmitError(
        "Kicktipp login failed after {0} attempts: {1}".format(MAX_ATTEMPTS, last_err)
    )


def _fetch_form_page(session, matchday_index):
    url = "{0}/{1}/tippabgabe".format(config.KICKTIPP_BASE, config.KICKTIPP_COMMUNITY)
    params = {"spieltagIndex": matchday_index} if matchday_index is not None else {}
    last_err = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            resp = session.get(url, params=params, timeout=TIMEOUT_S)
            resp.raise_for_status()
            if resp.status_code != 200:
                raise RuntimeError("unexpected HTTP {0}".format(resp.status_code))
            return resp.text
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            if attempt < MAX_ATTEMPTS:
                time.sleep(RETRY_DELAY_S)
    raise KicktippSubmitError(
        "Could not load Kicktipp bet form ({0}): {1}".format(url, last_err)
    )


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------
# Boilerplate that varies between Kicktipp / football-data renderings of
# the same club: legal-form prefixes, founding-year numbers, "Borussia".
# Stripping these before matching turns "1899 Hoffenheim" -> "hoffenheim",
# "1. FC Koln" -> "koln", "VfB Stuttgart" -> "stuttgart", etc. -- so the
# alias map only needs one canonical spelling per club, not every skin's
# variant. Still deterministic; still hard-fails if the core token is
# genuinely unknown.
_CLUB_NOISE_RE = re.compile(
    r"\b(?:1\.?\s*)?(?:FC|FSV|VfL|VfB|TSG|SV|SC|SpVgg|Borussia|Bor\.?|Eintracht|"
    r"1899|1846|1900|1907|18\d{2}|19\d{2}|0[4-9]|[4-9]\d)\b",
    re.IGNORECASE,
)


def _normalize_team_token(name):
    s = re.sub(r"\s*\([HA]\)\s*$", "", name or "").strip()
    s = _CLUB_NOISE_RE.sub(" ", s)
    s = re.sub(r"[.\-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


# Precomputed normalized index of the alias map, built once on import.
_NORMALIZED_ALIASES = {}
for _k, _v in config.KICKTIPP_TEAM_ALIASES.items():
    _NORMALIZED_ALIASES.setdefault(_normalize_team_token(_k), _v)


def _resolve_team(display_name):
    """Kicktipp display name -> football-data name. Hard-fail if unmapped.

    Tries, in order: exact match, match after stripping a trailing
    "(H)"/"(A)", then a normalized-token match that ignores legal-form
    prefixes and founding-year numbers (see _CLUB_NOISE_RE). The last step
    lets a club be listed once in config.KICKTIPP_TEAM_ALIASES regardless
    of which spelling variant Kicktipp happens to render.
    """
    name = (display_name or "").strip()
    if name in config.KICKTIPP_TEAM_ALIASES:
        return config.KICKTIPP_TEAM_ALIASES[name]

    stripped = re.sub(r"\s*\([HA]\)\s*$", "", name).strip()
    if stripped in config.KICKTIPP_TEAM_ALIASES:
        return config.KICKTIPP_TEAM_ALIASES[stripped]

    token = _normalize_team_token(name)
    if token and token in _NORMALIZED_ALIASES:
        return _NORMALIZED_ALIASES[token]

    raise KicktippSubmitError(
        "Kicktipp team name {0!r} (normalized {1!r}) is not in "
        "config.KICKTIPP_TEAM_ALIASES -- add the mapping (see crosswalk.py "
        "philosophy: never guess).".format(name, token)
    )


def parse_bet_form(html):
    """
    Return (form_meta, rows).

    form_meta = {"action": str, "hidden": {name: value, ...}}
    rows = [
      {
        "game_id": str,
        "home_fd": str, "away_fd": str,           # resolved football-data names
        "home_display": str, "away_display": str,
        "heim_field": str, "gast_field": str,     # exact input names to POST
        "heim_value": str, "gast_value": str,     # current values ("" if blank)
      }, ...
    ]

    Raises KicktippSubmitError if the expected structure is absent.
    """
    soup = BeautifulSoup(html, "html.parser")

    form = None
    for f in soup.find_all("form"):
        if f.find("input", attrs={"name": _FIELD_RE}):
            form = f
            break
    if form is None:
        raise KicktippSubmitError(
            "No bet form found on the Kicktipp page (no "
            "spieltippForms[...].heimTipp inputs) -- markup may have changed, "
            "or the matchday is not open for tipping."
        )

    action = form.get("action") or ""
    if action.startswith("/"):
        action = "{0}{1}".format(config.KICKTIPP_BASE, action)
    elif not action.startswith("http"):
        action = "{0}/{1}/{2}".format(
            config.KICKTIPP_BASE, config.KICKTIPP_COMMUNITY, action
        ).replace("//", "/").replace("https:/", "https://")

    hidden = {}
    for inp in form.find_all("input", attrs={"type": "hidden"}):
        nm = inp.get("name")
        if nm:
            hidden[nm] = inp.get("value", "")

    # Collect the per-game inputs, then pair heim+gast by game_id.
    by_game = {}
    for inp in form.find_all("input", attrs={"name": _FIELD_RE}):
        m = _FIELD_RE.match(inp.get("name", ""))
        if not m:
            continue
        gid = m.group("gid")
        by_game.setdefault(gid, {})[m.group("side")] = {
            "field": inp.get("name"),
            "value": (inp.get("value") or "").strip(),
        }

    rows = []
    for row_el in form.find_all("tr"):
        inp = row_el.find("input", attrs={"name": _FIELD_RE})
        if inp is None:
            continue
        m = _FIELD_RE.match(inp.get("name", ""))
        gid = m.group("gid")
        pair = by_game.get(gid, {})
        if "heimTipp" not in pair or "gastTipp" not in pair:
            raise KicktippSubmitError(
                "Game {0} is missing one of heimTipp/gastTipp -- unexpected "
                "form structure.".format(gid)
            )

        # Team names: Kicktipp renders them in cells of the same row,
        # commonly class 'nowrap' with the home team before the score
        # inputs and the away team after. Fall back to the first two
        # non-empty text cells that are not the score inputs.
        names = _row_team_names(row_el)
        if len(names) < 2:
            raise KicktippSubmitError(
                "Could not read both team names for game {0} from its row.".format(gid)
            )
        home_display, away_display = names[0], names[1]

        rows.append({
            "game_id": gid,
            "home_display": home_display,
            "away_display": away_display,
            "home_fd": _resolve_team(home_display),
            "away_fd": _resolve_team(away_display),
            "heim_field": pair["heimTipp"]["field"],
            "gast_field": pair["gastTipp"]["field"],
            "heim_value": pair["heimTipp"]["value"],
            "gast_value": pair["gastTipp"]["value"],
        })

    if not rows:
        raise KicktippSubmitError("Bet form parsed but yielded zero match rows.")

    return {"action": action, "hidden": hidden}, rows


def _row_team_names(row_el):
    """Best-effort: ordered list of team-name strings in a form row."""
    names = []
    for cell in row_el.find_all(["td", "th"]):
        if cell.find("input") is not None:
            continue
        text = cell.get_text(" ", strip=True)
        if not text:
            continue
        # skip pure numbers / odds / kickoff times
        if re.fullmatch(r"[\d.:,\s/\-]+", text):
            continue
        names.append(text)
    return names


# --------------------------------------------------------------------------
# Decision + submission
# --------------------------------------------------------------------------
def _index_model_tips(match_contexts):
    """(home_fd, away_fd) -> (tip_h, tip_a, kickoff_ts) from predict output."""
    out = {}
    for m in match_contexts:
        out[(m["home_team"], m["away_team"])] = (
            int(m["tip_h"]), int(m["tip_a"]), m.get("kickoff_ts"),
        )
    return out


def _decide(rows, model_tips, now):
    """
    Split rows into actions. Returns dict of lists (see submit_tips summary).
    `now` is a tz-naive pandas Timestamp in Europe/Berlin local time.

    With config.KICKTIPP_FILL_BLANKS_ONLY == False (the default) every
    still-open match with a model tip is (re)written -- an existing value,
    whether a prior auto-entry or a manual edit, is overwritten. The one
    thing skipped is a row whose value already equals the model tip
    (nothing to change) and, when KICKTIPP_MIN_LEAD_HOURS > 0, a match
    inside that pre-kickoff window. A match that has already kicked off is
    always skipped regardless of the lead setting.
    """
    import pandas as pd  # local: keep module importable without pandas at parse time

    min_lead = pd.Timedelta(hours=config.KICKTIPP_MIN_LEAD_HOURS)
    to_place, skipped_existing = [], []
    skipped_unchanged, skipped_kickoff, unmatched = [], [], []

    for row in rows:
        key = (row["home_fd"], row["away_fd"])
        if key not in model_tips:
            unmatched.append("{0} vs {1} (no model tip)".format(*key))
            continue
        tip_h, tip_a, kickoff_ts = model_tips[key]
        cur_h, cur_a = row["heim_value"], row["gast_value"]
        had_value = bool(cur_h or cur_a)

        if config.KICKTIPP_FILL_BLANKS_ONLY and had_value:
            skipped_existing.append(
                "{0} vs {1} (already {2}:{3})".format(
                    key[0], key[1], cur_h or "-", cur_a or "-"
                )
            )
            continue

        # No-op: the form already holds exactly this tip.
        if cur_h == str(tip_h) and cur_a == str(tip_a):
            skipped_unchanged.append(
                "{0} vs {1} (already {2}:{3})".format(key[0], key[1], tip_h, tip_a)
            )
            continue

        if kickoff_ts is not None:
            kt = pd.Timestamp(kickoff_ts)
            # Always skip a match that has genuinely started; additionally
            # skip anything inside the lead window when one is configured.
            if kt <= now or (min_lead > pd.Timedelta(0) and kt - now < min_lead):
                skipped_kickoff.append(
                    "{0} vs {1} (kickoff {2})".format(key[0], key[1], kt)
                )
                continue

        to_place.append({
            "row": row, "tip_h": tip_h, "tip_a": tip_a,
            "overwrite": had_value,
            "prev": "{0}:{1}".format(cur_h or "-", cur_a or "-") if had_value else None,
        })

    return {
        "to_place": to_place,
        "skipped_existing": skipped_existing,
        "skipped_unchanged": skipped_unchanged,
        "skipped_kickoff": skipped_kickoff,
        "unmatched": unmatched,
    }


def _build_post_body(form_meta, rows, to_place):
    """
    Full form body: every field Kicktipp expects back. `to_place` rows get
    the model tip (overwriting whatever was there); every other row is
    echoed back with its current value untouched.
    """
    body = dict(form_meta["hidden"])
    place_ids = {p["row"]["game_id"]: p for p in to_place}
    for row in rows:
        p = place_ids.get(row["game_id"])
        if p is not None:
            body[row["heim_field"]] = str(p["tip_h"])
            body[row["gast_field"]] = str(p["tip_a"])
        else:
            body[row["heim_field"]] = row["heim_value"]
            body[row["gast_field"]] = row["gast_value"]
    return body


def _submit(session, action, body):
    last_err = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            resp = session.post(action, data=body, timeout=TIMEOUT_S,
                                allow_redirects=True)
            resp.raise_for_status()
            return resp.status_code
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            if attempt < MAX_ATTEMPTS:
                time.sleep(RETRY_DELAY_S)
    raise KicktippSubmitError(
        "Kicktipp submit POST failed after {0} attempts: {1}".format(
            MAX_ATTEMPTS, last_err
        )
    )


# --------------------------------------------------------------------------
# Public entrypoint
# --------------------------------------------------------------------------
def submit_tips(match_contexts, matchday_index, dry_run=False, live=None):
    """
    Enter the model's tips into the Kicktipp bet form.

    match_contexts : list of predict.build_match_context dicts. Each needs
                     home_team, away_team, tip_h, tip_a, and ideally
                     kickoff_ts (DST-corrected, from predict.kickoff_timestamps).
    matchday_index : Kicktipp spieltagIndex; None lets Kicktipp pick the
                     currently-open matchday.
    dry_run        : if True, never POST (predict.py --no-email path).
    live           : override config.KICKTIPP_LIVE. If the effective value
                     is False, behaves like dry_run but still logs in and
                     parses so the summary is real.

    Returns a summary dict:
      {
        "live": bool, "submitted": bool, "http_status": int|None,
        "placed": [str, ...],            # "Home vs Away -> h:a" (fresh fills)
        "overwritten": [str, ...],       # "Home vs Away: 1:1 -> 2:1"
        "skipped_existing": [str, ...],  # only when FILL_BLANKS_ONLY
        "skipped_unchanged": [str, ...], # form already held this exact tip
        "skipped_kickoff": [str, ...],
        "unmatched": [str, ...],
      }

    Raises KicktippSubmitError on any hard failure (login, missing form,
    unmapped team name).
    """
    import pandas as pd

    effective_live = config.KICKTIPP_LIVE if live is None else bool(live)
    will_submit = effective_live and not dry_run

    user = os.environ.get("KICKTIPP_USER")
    password = os.environ.get("KICKTIPP_PASSWORD")
    if not user or not password:
        raise KicktippNotConfigured(
            "KICKTIPP_USER / KICKTIPP_PASSWORD not set -- auto-submit skipped."
        )
    if config.KICKTIPP_COMMUNITY in ("", "CHANGEME"):
        raise KicktippNotConfigured(
            "config.KICKTIPP_COMMUNITY is not configured -- auto-submit skipped."
        )

    if not match_contexts:
        return {
            "live": effective_live, "submitted": False, "http_status": None,
            "placed": [], "overwritten": [], "skipped_existing": [],
            "skipped_unchanged": [], "skipped_kickoff": [],
            "unmatched": [], "note": "no fixtures to submit",
        }

    session = _new_session()
    _login(session, user, password)

    html = _fetch_form_page(session, matchday_index)
    form_meta, rows = parse_bet_form(html)

    model_tips = _index_model_tips(match_contexts)
    now = pd.Timestamp.now(tz="Europe/Berlin").tz_localize(None)
    decision = _decide(rows, model_tips, now)

    placed_labels = [
        "{0} vs {1} -> {2}:{3}".format(
            p["row"]["home_fd"], p["row"]["away_fd"], p["tip_h"], p["tip_a"]
        )
        for p in decision["to_place"] if not p["overwrite"]
    ]
    overwritten_labels = [
        "{0} vs {1}: {2} -> {3}:{4}".format(
            p["row"]["home_fd"], p["row"]["away_fd"], p["prev"], p["tip_h"], p["tip_a"]
        )
        for p in decision["to_place"] if p["overwrite"]
    ]

    http_status = None
    submitted = False
    if decision["to_place"] and will_submit:
        body = _build_post_body(form_meta, rows, decision["to_place"])
        http_status = _submit(session, form_meta["action"], body)
        submitted = True

    return {
        "live": effective_live,
        "submitted": submitted,
        "http_status": http_status,
        "placed": placed_labels,
        "overwritten": overwritten_labels,
        "skipped_existing": decision["skipped_existing"],
        "skipped_unchanged": decision["skipped_unchanged"],
        "skipped_kickoff": decision["skipped_kickoff"],
        "unmatched": decision["unmatched"],
    }


def summary_lines(summary):
    """Human-readable lines for the log and the email report."""
    if summary.get("note") == "no fixtures to submit":
        return ["Kicktipp: no fixtures to submit."]
    mode = (
        "LIVE, submitted" if summary["submitted"]
        else ("LIVE, nothing to place" if summary["live"] else "DRY-RUN (KICKTIPP_LIVE not set)")
    )
    lines = ["Kicktipp auto-submit [{0}]:".format(mode)]
    submitted = summary["submitted"]
    if summary["placed"]:
        lines.append("  {0}: {1}".format(
            "Placed" if submitted else "Would place", "; ".join(summary["placed"])
        ))
    if summary.get("overwritten"):
        lines.append("  {0}: {1}".format(
            "Overwrote" if submitted else "Would overwrite",
            "; ".join(summary["overwritten"]),
        ))
    if not summary["placed"] and not summary.get("overwritten"):
        lines.append("  Nothing to place.")
    for label, key in (
        ("Skipped (already the model tip)", "skipped_unchanged"),
        ("Skipped (fill-blanks-only, value present)", "skipped_existing"),
        ("Skipped (kicked off / too close)", "skipped_kickoff"),
        ("Unmatched (no model tip)", "unmatched"),
    ):
        if summary.get(key):
            lines.append("  {0}: {1}".format(label, "; ".join(summary[key])))
    if summary["http_status"] is not None:
        lines.append("  HTTP {0}".format(summary["http_status"]))
    return lines
