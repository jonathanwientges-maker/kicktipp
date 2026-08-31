// Club colours keyed by the football-data.co.uk team name (the naming used
// throughout web/public/data/**). Used ONLY for: a 3px left bar on a table
// row's team cell, per-team chart line/area/dot colour, a match card's left
// border, and team-attributed bar fills in BarRow / StackedPositions.
// Never as a full-width background behind text.

export const TEAM_COLORS: Record<string, { color: string; on: string }> = {
  "Bayern Munich": { color: "#DC052D", on: "#FFFFFF" },
  "Dortmund": { color: "#FDE100", on: "#0D0E11" },
  "Leverkusen": { color: "#E32221", on: "#FFFFFF" },
  "RB Leipzig": { color: "#DD0741", on: "#FFFFFF" },
  "Stuttgart": { color: "#E32219", on: "#FFFFFF" },
  "Ein Frankfurt": { color: "#E1000F", on: "#FFFFFF" },
  "Freiburg": { color: "#E2001A", on: "#FFFFFF" },
  "Hoffenheim": { color: "#1C63B7", on: "#FFFFFF" },
  "Mainz": { color: "#C3141E", on: "#FFFFFF" },
  "Wolfsburg": { color: "#65B32E", on: "#0D0E11" },
  "M'gladbach": { color: "#00953F", on: "#FFFFFF" },
  "Werder Bremen": { color: "#1D9053", on: "#FFFFFF" },
  "Union Berlin": { color: "#EB1923", on: "#FFFFFF" },
  "Augsburg": { color: "#BA3733", on: "#FFFFFF" },
  "FC Koln": { color: "#ED1C24", on: "#FFFFFF" },
  "Heidenheim": { color: "#E30613", on: "#FFFFFF" },
  "St Pauli": { color: "#8C5A3C", on: "#FFFFFF" },
  "Hamburg": { color: "#0A3A82", on: "#FFFFFF" },
  "Schalke 04": { color: "#004D9D", on: "#FFFFFF" },
  "Elversberg": { color: "#D40028", on: "#FFFFFF" },
  "Hertha": { color: "#005CA9", on: "#FFFFFF" },
  "Bochum": { color: "#00519E", on: "#FFFFFF" },
  "Darmstadt": { color: "#0B4EA2", on: "#FFFFFF" },
  "Holstein Kiel": { color: "#0056A3", on: "#FFFFFF" },
  "Nurnberg": { color: "#AD1732", on: "#FFFFFF" },
  "Fortuna Dusseldorf": { color: "#DA291C", on: "#FFFFFF" },
  "Greuther Furth": { color: "#007A3D", on: "#FFFFFF" },
  "Hannover": { color: "#00963F", on: "#FFFFFF" },
  "Paderborn": { color: "#005CA9", on: "#FFFFFF" },
  "Bielefeld": { color: "#004E9E", on: "#FFFFFF" },
  "Karlsruhe": { color: "#009EE0", on: "#0D0E11" },
  "Kaiserslautern": { color: "#E2001A", on: "#FFFFFF" },
  "Magdeburg": { color: "#004B9B", on: "#FFFFFF" },
  "Braunschweig": { color: "#FFCC00", on: "#0D0E11" },
  "Munster": { color: "#004C9E", on: "#FFFFFF" },
  "Regensburg": { color: "#DF002A", on: "#FFFFFF" },
  "Ulm": { color: "#E2001A", on: "#FFFFFF" },
  "Dynamo Dresden": { color: "#FFE500", on: "#0D0E11" },
};

const FALLBACK = { color: "#6B7280", on: "#F2F4F7" };

// The exported JSON carries Understat team names, not football-data names.
// This maps the Understat spelling onto the TEAM_COLORS key so teamColor()
// resolves either. Mirrors src/crosswalk.py's UNDERSTAT_TO_FD (colours only).
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

// Display names: the exported JSON uses Understat's English/ASCII
// spellings ("Bayern Munich", "FC Cologne", …). This map is applied by
// teamName() everywhere a club is shown in the UI. Slugs, colour keys
// and the underlying data are untouched.
const DISPLAY_NAME: Record<string, string> = {
  "Bayern Munich": "Bayern München",
  "FC Cologne": "1. FC Köln",
  "Freiburg": "SC Freiburg",
  "RasenBallsport Leipzig": "RB Leipzig",
  "Borussia M.Gladbach": "Bor. Mönchengladbach",
  "Borussia Dortmund": "Borussia Dortmund",
  "Bayer Leverkusen": "Bayer Leverkusen",
  "Eintracht Frankfurt": "Eintracht Frankfurt",
  "VfB Stuttgart": "VfB Stuttgart",
  "Hamburger SV": "Hamburger SV",
  "Werder Bremen": "Werder Bremen",
  "Union Berlin": "1. FC Union Berlin",
  "Mainz 05": "1. FSV Mainz 05",
  "Hertha Berlin": "Hertha BSC",
  "Hannover 96": "Hannover 96",
  "Fortuna Duesseldorf": "Fortuna Düsseldorf",
  "Greuther Fuerth": "SpVgg Greuther Fürth",
  "Nuernberg": "1. FC Nürnberg",
  "FC Heidenheim": "1. FC Heidenheim",
  "Arminia Bielefeld": "Arminia Bielefeld",
  "St. Pauli": "FC St. Pauli",
  "Schalke 04": "FC Schalke 04",
  "Bochum": "VfL Bochum",
  "Wolfsburg": "VfL Wolfsburg",
  "Augsburg": "FC Augsburg",
  "Hoffenheim": "TSG Hoffenheim",
  "Darmstadt": "SV Darmstadt 98",
  "Paderborn": "SC Paderborn 07",
  "Holstein Kiel": "Holstein Kiel",
  "Elversberg": "SV Elversberg",
  "Ingolstadt": "FC Ingolstadt 04",
};

export function teamName<T extends string | null | undefined>(raw: T): T extends string ? string : T {
  if (raw == null) return raw as never;
  return (DISPLAY_NAME[raw] ?? raw) as never;
}

// Longest-first list so "Bayern Munich" is replaced before a shorter
// substring could match. Used to rewrite the exporter's free-text
// verdict, which carries Understat spellings we can't change upstream.
const _NAME_PAIRS = Object.entries(DISPLAY_NAME).sort((a, b) => b[0].length - a[0].length);

export function withTeamNames(text: string): string {
  let out = text;
  for (const [raw, nice] of _NAME_PAIRS) {
    if (raw === nice) continue;
    out = out.split(raw).join(nice);
  }
  return out;
}

export function teamColor(name: string): { color: string; on: string } {
  if (TEAM_COLORS[name]) return TEAM_COLORS[name];
  const key = UNDERSTAT_TO_KEY[name];
  if (key && TEAM_COLORS[key]) return TEAM_COLORS[key];
  return FALLBACK;
}
