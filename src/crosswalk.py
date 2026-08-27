"""
Team-name harmonisation: Understat names -> football-data.co.uk names.

Understat is treated as the canonical source; football-data names are
mapped onto it. Identical names map to themselves (both directions).

Hard-fails (raises) on any name from either source that isn't resolvable --
never fuzzy-matches silently. This is deliberate per the build spec: a
missed team-name mapping silently corrupts every downstream join, and a
loud crash is far cheaper than a wrong prediction.
"""

# Understat name (key) -> football-data.co.uk name (value).
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


class UnresolvedTeamNameError(Exception):
    """Raised when a team name from either source cannot be harmonised."""
    pass


def _all_known_fd_names():
    """FD-side names that are valid targets: mapped values plus any
    Understat name that is presumed identical in both sources (self-map)."""
    return set(UNDERSTAT_TO_FD.values())


def to_fd_name(understat_name, known_fd_names=None):
    """
    Harmonise an Understat team name to its football-data.co.uk equivalent.

    If `understat_name` is a key in UNDERSTAT_TO_FD, return the mapped
    value. Otherwise, assume identity mapping (name is the same in both
    sources) -- but only if that name is plausible, i.e. we don't try to
    fuzzy match. Callers that need strict validation against a known set
    of FD names should pass `known_fd_names`.
    """
    if understat_name in UNDERSTAT_TO_FD:
        return UNDERSTAT_TO_FD[understat_name]
    # Identity mapping candidate.
    if known_fd_names is not None and understat_name not in known_fd_names:
        raise UnresolvedTeamNameError(
            "Understat team name '{0}' has no crosswalk entry and does not "
            "match any known football-data.co.uk team name. Add it to "
            "UNDERSTAT_TO_FD in src/crosswalk.py.".format(understat_name)
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
