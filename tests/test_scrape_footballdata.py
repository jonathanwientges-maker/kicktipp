"""
Tests for src/scrape_footballdata.py, focused on the BOM regression
found while dry-running predict.py against the live fixtures.csv:
football-data.co.uk serves that file with a UTF-8 BOM prefix, which
requests' auto-decoded .text leaves baked into the string as three
literal mojibake characters rather than stripping it -- silently
turning the 'Div' column into '﻿Div' and breaking any df["Div"]
lookup with a confusing KeyError.
"""
from unittest.mock import MagicMock, patch

import pytest

from src import scrape_footballdata as sfd


def _mock_response(raw_bytes, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.raise_for_status.return_value = None
    resp.content = raw_bytes
    return resp


@patch("src.scrape_footballdata.requests.get")
def test_download_fixtures_csv_strips_utf8_bom(mock_get):
    """Regression test: a UTF-8-BOM-prefixed fixtures.csv must still
    resolve df["Div"] correctly instead of raising KeyError."""
    csv_bytes = (
        "﻿Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG\n"
        "D1,25/08/26,18:30,Bayern Munich,Wolfsburg,,\n"
        "E0,25/08/26,15:00,Arsenal,Chelsea,,\n"
    ).encode("utf-8-sig")
    mock_get.return_value = _mock_response(csv_bytes)

    df = sfd.download_fixtures_csv()
    assert list(df.columns)[:2] == ["Div", "Date"]  # no leftover BOM in the column name
    assert len(df) == 1  # filtered to Div == 'D1' only
    assert df.iloc[0]["HomeTeam"] == "Bayern Munich"


@patch("src.scrape_footballdata.requests.get")
def test_read_csv_bytes_is_a_noop_without_a_bom(mock_get):
    """A file with no BOM at all must parse identically (utf-8-sig is a
    no-op when there's nothing to strip)."""
    csv_bytes = "Div,Date,HomeTeam,AwayTeam\nD1,25/08/26,Bayern Munich,Wolfsburg\n".encode("utf-8")
    df = sfd._read_csv_bytes(csv_bytes)
    assert list(df.columns) == ["Div", "Date", "HomeTeam", "AwayTeam"]


@patch("src.scrape_footballdata.requests.get")
def test_non_200_status_raises_clear_error_not_csv_parse_error(mock_get):
    """Regression test: football-data.co.uk returns a 300 Multiple
    Choices HTML 'did you mean...?' page (not a 4xx/5xx, so
    raise_for_status() doesn't catch it) when a season's file hasn't
    been published yet -- observed live for 2026/27's D1.csv while
    D2.csv for the same season already existed. Silently handing that
    HTML to pandas produced a confusing 'Error tokenizing data'
    exception; this must instead raise a clear, actionable error."""
    html_error_page = (
        b"<html><head><title>300 Multiple Choices</title></head>"
        b"<body>Available documents: ...</body></html>"
    )
    mock_get.return_value = _mock_response(html_error_page, status=300)

    with pytest.raises(RuntimeError, match="Unexpected HTTP 300"):
        sfd.download_division_csv(2026, "D1")


@patch("src.scrape_footballdata.requests.get")
def test_download_division_csv_strips_bom_too(mock_get):
    """The BOM fix must apply to season CSVs (D1/D2), not just
    fixtures.csv -- confirmed present on live D1 season files too, just
    never triggered a KeyError there because no code selects df["Div"]
    on them."""
    csv_bytes = (
        "﻿Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR\n"
        "D1,22/08/14,Bayern Munich,Wolfsburg,2,1,H\n"
    ).encode("utf-8-sig")
    mock_get.return_value = _mock_response(csv_bytes)

    df = sfd.download_division_csv(2014, "D1")
    assert list(df.columns)[:1] == ["Div"]
    assert df.iloc[0]["HomeTeam"] == "Bayern Munich"
