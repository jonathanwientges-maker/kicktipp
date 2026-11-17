"""
Upstream data-source health, persisted in data/state/source_status.json.

Why this exists: Understat went fully offline in early November 2026 (every
URL served a "We will come back soon" page). Under the original rule
"a failed scrape aborts the run", that one outage stopped EVERYTHING --
no tips were placed on Kicktipp, no results were scored, the website froze
-- even though the tuned blend puts weight 0.0 on the xG source and the
odds (football-data.co.uk) were perfectly available.

The outage path is now an explicit, LOUD degraded mode instead of an abort:
predict.refresh_current_season_data() records the failure here, adds an
UNDERSTAT_OUTAGE warning to the report/email, and the run continues on
football-data odds + results. The website reads this state (via
export_web's manifest) to show an outage banner, and the first run that
reaches Understat again flips it back to ok -- the banner disappears and
the normal scrape backfills every missed match automatically.

State shape (one entry per source):
    {"understat": {"ok": false,
                    "down_since": "2026-11-02T09:00:00Z",
                    "last_success": "2026-10-30T16:31:10Z",
                    "last_checked": "2026-11-17T09:00:00Z",
                    "last_error": "..."}}
"""
import json
import os
from datetime import datetime, timezone

import config

SOURCE_STATUS_PATH = os.path.join(config.STATE_DIR, "source_status.json")


def _now_iso(now=None):
    now = now or datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%SZ")


def load(path=None):
    path = path or SOURCE_STATUS_PATH
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def _save(state, path=None):
    path = path or SOURCE_STATUS_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(state, f, indent=2, sort_keys=True)


def mark_down(source, error, now=None, path=None):
    """Record a failed fetch. `down_since` is kept from the FIRST failure
    of the current outage, so repeated failing runs don't reset it."""
    state = load(path)
    entry = dict(state.get(source, {}))
    stamp = _now_iso(now)
    if entry.get("ok", True) or not entry.get("down_since"):
        entry["down_since"] = stamp
    entry["ok"] = False
    entry["last_checked"] = stamp
    entry["last_error"] = str(error)[:500]
    state[source] = entry
    _save(state, path)
    return entry


def mark_ok(source, now=None, path=None):
    state = load(path)
    entry = dict(state.get(source, {}))
    stamp = _now_iso(now)
    entry.update({"ok": True, "down_since": None, "last_checked": stamp,
                  "last_success": stamp, "last_error": None})
    state[source] = entry
    _save(state, path)
    return entry


def is_ok(source, path=None):
    return bool(load(path).get(source, {}).get("ok", True))
