"""
Team-name harmonisation: Understat names -> football-data.co.uk names.

Understat is treated as the canonical source; football-data names are
mapped onto it. Identical names map to themselves (both directions).

Hard-fails (raises) on any name from either source that isn't resolvable --
never fuzzy-matches silently. This is deliberate per the build spec: a
missed team-name mapping silently corrupts every downstream join, and a
loud crash is far cheaper than a wrong prediction.
"""

# Understat name (key) -> football-data.co.uk name (value), for clubs
# whose spelling actually DIFFERS between the two sources.
# Extend this as new promoted teams or renames appear.
UNDERSTAT_TO_FD = {
    "Borussia M.Gladbach": "M'gladbach",
    "FC Cologne": "FC Koln",
    "Fortuna Duesseldorf": "Fortuna Dusseldorf",
    "Arminia Bielefeld": "Bielefeld",
    "Eintracht Frankfurt": "Ein Frankfurt",
    "Hertha Berlin": "Hertha",
    "RasenBallsport Leipzig": "RB Leipzig",
    "VfB Stuttgart": "Stuttgart",
    "Bayer Leverkusen": "Leverkusen",
    "Borussia Dortmund": "Dortmund",
    "Hamburger SV": "Hamburg",
    "Hannover 96": "Hannover",
    "FC Augsburg": "Augsburg",
    "Mainz 05": "Mainz",
    "SC Freiburg": "Freiburg",
    "VfL Bochum": "Bochum",
    "VfL Wolfsburg": "Wolfsburg",
    "SV Darmstadt 98": "Darmstadt",
    "SC Paderborn 07": "Paderborn",
    "Greuther Fuerth": "Greuther Furth",
    "FC Heidenheim": "Heidenheim",
    "St. Pauli": "St Pauli",
    "Nuernberg": "Nurnberg",
}

# Understat names whose football-data spelling is IDENTICAL. Listed
# explicitly so to_fd_name() can validate an identity mapping without a
# football-data odds file present -- previously the only proof that (say)
# "Elversberg" was a real FD name came from the current-season odds
# HomeTeam/AwayTeam columns, so a late or failed D1.csv download turned a
# routine identity match into a hard UnresolvedTeamNameError and blocked
# results scoring for an already-completed matchday (observed 2026-08-31,
# football-data D1.csv HTTP 300, crash on "Elversberg"). Some entries
# (Augsburg, Bochum, Darmstadt, Freiburg, Paderborn, Wolfsburg) are also
# the VALUE of a UNDERSTAT_TO_FD rename -- Understat has used both the
# long ("FC Augsburg") and short ("Augsburg") form across seasons. Keep
# this current with the top two divisions; a genuine rename belongs in
# UNDERSTAT_TO_FD instead.
IDENTITY_FD_NAMES = {
    "Augsburg", "Bayern Munich", "Bochum", "Darmstadt", "Elversberg",
    "Freiburg", "Hoffenheim", "Holstein Kiel", "Ingolstadt", "Paderborn",
    "Schalke 04", "Union Berlin", "Werder Bremen", "Wolfsburg",
}


class UnresolvedTeamNameError(Exception):
    """Raised when a team name from either source cannot be harmonised."""
    pass


def _all_known_fd_names():
    """FD-side names that are valid targets: every rename value plus every
    club whose name is identical in both sources. Independent of any odds
    file -- this is the crosswalk's own idea of a valid football-data
    name."""
    return set(UNDERSTAT_TO_FD.values()) | set(IDENTITY_FD_NAMES)


def to_fd_name(understat_name, known_fd_names=None):
    """
    Harmonise an Understat team name to its football-data.co.uk equivalent.

    If `understat_name` is a key in UNDERSTAT_TO_FD, return the mapped
    value. Otherwise, assume identity mapping (name is the same in both
    sources) -- but only if that name is plausible, i.e. we don't try to
    fuzzy match.

    An identity mapping is accepted when the name is in IDENTITY_FD_NAMES
    (the crosswalk's own roster, always available) OR in the optional
    caller-supplied `known_fd_names` (e.g. the odds file's team column).
    It is rejected -- UnresolvedTeamNameError -- only when it is in
    neither. Passing `known_fd_names` widens what is accepted; it never
    narrows it below IDENTITY_FD_NAMES.
    """
    if understat_name in UNDERSTAT_TO_FD:
        return UNDERSTAT_TO_FD[understat_name]
    # Identity mapping candidate.
    if understat_name in IDENTITY_FD_NAMES:
        return understat_name
    if known_fd_names is not None and understat_name not in known_fd_names:
        raise UnresolvedTeamNameError(
            "Understat team name '{0}' has no crosswalk entry and does not "
            "match any known football-data.co.uk team name. Add it to "
            "UNDERSTAT_TO_FD or IDENTITY_FD_NAMES in src/crosswalk.py.".format(
                understat_name
            )
        )
    return understat_name


def validate_fd_name(fd_name, understat_names):
    """
    Hard-fail if `fd_name` (from football-data.co.uk) cannot be resolved
    back to any known Understat name -- i.e. it is neither a mapped target
    nor an identity match against the given Understat name universe.
    """
    mapped_targets = _all_known_fd_names()
    if fd_name in mapped_targets:
        return True
    if fd_name in understat_names:
        return True
    raise UnresolvedTeamNameError(
        "football-data.co.uk team name '{0}' has no crosswalk entry and "
        "does not match any known Understat team name. Add the appropriate "
        "pair to UNDERSTAT_TO_FD in src/crosswalk.py.".format(fd_name)
    )


def harmonise_series(series, known_fd_names=None):
    """Vectorised helper: harmonise a pandas Series of Understat team names."""
    return series.map(lambda n: to_fd_name(n, known_fd_names=known_fd_names))
