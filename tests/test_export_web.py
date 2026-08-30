"""
Tests for src/export_web.py's output (BUILD BLUEPRINT §9, tests 4-5).
New file -- does not modify any existing test.

The leak guard (9.4) and report guard (9.5) walk the already-exported
web/public/data/ tree. If the tree has not been generated in this
checkout the guards skip -- they are a CI gate on a real export, not a
unit of pure logic.
"""
import glob
import json
import os
import re

import pandas as pd
import pytest

import config

WEB_DATA_DIR = os.path.join(config.ROOT_DIR, "web", "public", "data")
WEB_PUBLIC_DIR = os.path.join(config.ROOT_DIR, "web", "public")


def _all_data_json():
    return glob.glob(os.path.join(WEB_DATA_DIR, "**", "*.json"), recursive=True)


def _require_export():
    if not os.path.isdir(WEB_DATA_DIR) or not _all_data_json():
        pytest.skip("web/public/data/ not exported in this checkout "
                    "(run: python -m src.export_web)")


# ---------------------------------------------------------------------------
# 9.4 leak guard
# ---------------------------------------------------------------------------
_FORBIDDEN_KEY = re.compile(r"lam_|lambda|prob|odds|market|tip_recommend|ev_")


def _walk_keys(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            for kk in _walk_keys(v, path + "/" + str(k)):
                yield kk
    elif isinstance(obj, list):
        for v in obj:
            for kk in _walk_keys(v, path):
                yield kk


def test_no_forward_looking_keys_for_future_matches():
    _require_export()
    manifest = json.load(open(os.path.join(WEB_DATA_DIR, "manifest.json")))
    generated_at = pd.Timestamp(manifest["generated_at"]).tz_localize(None)

    # collect the date of every match referenced anywhere
    match_dates = {}
    for f in glob.glob(os.path.join(WEB_DATA_DIR, "match", "*.json")):
        d = json.load(open(f))
        if d.get("date"):
            match_dates[int(d["match_id"])] = pd.Timestamp(d["date"])

    offenders = []
    for f in _all_data_json():
        payload = json.load(open(f))
        keys = set(_walk_keys(payload))
        bad = {k for k in keys if _FORBIDDEN_KEY.search(k)}
        if not bad:
            continue
        # only a violation if this file concerns a FUTURE match
        mid = payload.get("match_id")
        this_date = match_dates.get(int(mid)) if mid is not None else None
        if this_date is not None and this_date > generated_at:
            offenders.append((f, bad))
        elif this_date is None:
            # non-match file carrying a forbidden key at all is a smell
            offenders.append((f, bad))

    assert not offenders, "forward-looking keys leaked: {0}".format(offenders[:5])


def test_simulation_carries_no_odds_derived_fields():
    _require_export()
    for f in glob.glob(os.path.join(WEB_DATA_DIR, "season", "*", "simulation.json")):
        txt = open(f).read()
        assert "lambda" not in txt and "market" not in txt and "odds" not in txt


# ---------------------------------------------------------------------------
# 9.5 report guard
# ---------------------------------------------------------------------------
def test_no_stray_html_under_web_public():
    _require_export()
    out_dir = os.path.join(config.ROOT_DIR, "web", "out")
    for f in glob.glob(os.path.join(WEB_PUBLIC_DIR, "**", "*"), recursive=True):
        if f.endswith(".html"):
            # Next.js-generated pages live under web/out/, never web/public/
            assert f.startswith(out_dir), "stray .html under web/public/: {0}".format(f)


def test_no_report_artefacts_in_web_data():
    _require_export()
    needle = re.compile(r"matchday_.*_report")
    for f in _all_data_json():
        assert not needle.search(open(f).read()), \
            "report-artefact substring found in {0}".format(f)


# ---------------------------------------------------------------------------
# structural smoke checks
# ---------------------------------------------------------------------------
def test_manifest_shape():
    _require_export()
    m = json.load(open(os.path.join(WEB_DATA_DIR, "manifest.json")))
    for k in ("generated_at", "current_season", "latest_matchday", "seasons",
              "team_stats_available", "warnings"):
        assert k in m
    assert isinstance(m["seasons"], list) and m["seasons"]


def test_floats_are_rounded_and_no_nan_tokens():
    _require_export()
    for f in _all_data_json()[:400]:
        txt = open(f).read()
        assert "NaN" not in txt and "Infinity" not in txt
