// Central number/date formatting. de-DE throughout. Never call toFixed
// directly in a component -- go through here (BUILD BLUEPRINT §5.2).

const MINUS = "−"; // U+2212 MINUS SIGN, not a hyphen

export function fmtNum(n: number | null | undefined, dp = 2): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "–";
  return n.toLocaleString("de-DE", {
    minimumFractionDigits: dp,
    maximumFractionDigits: dp,
  });
}

export function fmtInt(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "–";
  return Math.round(n).toLocaleString("de-DE");
}

export function fmtSigned(n: number | null | undefined, dp = 2): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "–";
  const body = Math.abs(n).toLocaleString("de-DE", {
    minimumFractionDigits: dp,
    maximumFractionDigits: dp,
  });
  if (n > 0) return `+${body}`;
  if (n < 0) return `${MINUS}${body}`;
  return body;
}

export function fmtSignedInt(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "–";
  const body = Math.abs(Math.round(n)).toLocaleString("de-DE");
  if (n > 0) return `+${body}`;
  if (n < 0) return `${MINUS}${body}`;
  return body;
}

// iso: "YYYY-MM-DD" -> "DD.MM.YYYY"
export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "–";
  const parts = iso.split("-");
  if (parts.length !== 3) return iso;
  return `${parts[2]}.${parts[1]}.${parts[0]}`;
}

// hhmm: "HH:MM" -> "HH:MM Uhr"
export function fmtTime(hhmm: string | null | undefined): string | null {
  if (!hhmm) return null;
  return `${hhmm} Uhr`;
}

// Team name -> URL slug. Pure; safe to import from client components.
export function slugify(team: string): string {
  return team
    .toLowerCase()
    .replace(/[^a-z0-9\s\-_'.]/g, "")
    .replace(/[\s\-_'.]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

// Glücksfaktor text colour: lime-positive vs rose-negative, at full token.
export function luckColor(luck: number): string {
  if (luck > 0.05) return "var(--positive)";
  if (luck < -0.05) return "var(--negative)";
  return "var(--text-muted)";
}

// Glücksfaktor pill background: --positive / --negative at an opacity of
// min(|luck| / 8, 1) * 0.22.
export function luckPillBg(luck: number): string {
  const a = Math.min(Math.abs(luck) / 8, 1) * 0.22;
  const base = luck >= 0 ? "74, 222, 128" : "251, 113, 133"; // --positive / --negative rgb
  return `rgba(${base}, ${a.toFixed(3)})`;
}
