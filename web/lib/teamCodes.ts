// Three-letter club short codes, keyed by the football-data.co.uk team name
// (the same key space as web/lib/teamColors.ts's TEAM_COLORS). Used by
// <TeamChip variant="code"> everywhere table space is tight (<768px).
//
// The exported JSON carries Understat spellings, so teamCode() first maps
// those onto a football-data key via the same crosswalk teamColor() uses,
// then falls back to the first three letters uppercased.

export const TEAM_CODES: Record<string, string> = {
  "Bayern Munich": "FCB",   "Dortmund": "BVB",        "Leverkusen": "B04",
  "RB Leipzig": "RBL",      "Stuttgart": "VfB",       "Ein Frankfurt": "SGE",
  "Freiburg": "SCF",        "Hoffenheim": "TSG",      "Mainz": "M05",
  "Wolfsburg": "WOB",       "M'gladbach": "BMG",      "Werder Bremen": "SVW",
  "Union Berlin": "FCU",    "Augsburg": "FCA",        "FC Koln": "KOE",
  "Heidenheim": "FCH",      "St Pauli": "STP",        "Hamburg": "HSV",
  "Schalke 04": "S04",      "Elversberg": "SVE",      "Hertha": "BSC",
  "Bochum": "BOC",          "Darmstadt": "SVD",       "Holstein Kiel": "KSV",
  "Nurnberg": "FCN",        "Fortuna Dusseldorf": "F95", "Greuther Furth": "SGF",
  "Hannover": "H96",        "Paderborn": "SCP",       "Bielefeld": "DSC",
  "Karlsruhe": "KSC",       "Kaiserslautern": "FCK",  "Magdeburg": "FCM",
  "Braunschweig": "EBS",    "Munster": "MUE",         "Regensburg": "SSV",
  "Ulm": "SSU",             "Dynamo Dresden": "SGD",
};

// Mirrors UNDERSTAT_TO_KEY in web/lib/teamColors.ts so a code resolves for
// either spelling of a club name.
const UNDERSTAT_TO_KEY: Record<string, string> = {
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
  "FC Heidenheim": "Heidenheim",
  "St. Pauli": "St Pauli",
  "Nuernberg": "Nurnberg",
  "Greuther Fuerth": "Greuther Furth",
};

export function teamCode(name: string): string {
  if (TEAM_CODES[name]) return TEAM_CODES[name];
  const key = UNDERSTAT_TO_KEY[name];
  if (key && TEAM_CODES[key]) return TEAM_CODES[key];
  return name.replace(/[^A-Za-z0-9]/g, "").slice(0, 3).toUpperCase();
}
