// Data-source outage banner. Rendered by app/layout.tsx when the exported
// manifest says Understat is down (manifest.data_status.understat.ok ===
// false, written by src/export_web.py from data/state/source_status.json).
// The next run that reaches Understat flips the flag, the site rebuilds and
// the banner disappears -- nothing to remove by hand.
//
// Copy lives in the constants below so it can be changed without touching
// the markup.

const COPY = {
  tag: "Datenausfall",
  headline: "Totalschaden am Datenball.",
  body: (since: string, lastData: string) =>
    `Unser xG-Lieferant Understat ist seit ${since} offline. Offenbar hat es den Server erwischt, was genau passiert ist, ist noch unklar. Bis er wieder läuft, zeigen xG, Schüsse und Tabellen den Stand vom ${lastData}.`,
  footnote:
    "Diagnose: Ball geplatzt. Prognose: Comeback, sobald wieder frische Daten fließen. Die Seite aktualisiert sich dann automatisch.",
};

// ---- pixel art -------------------------------------------------------------
// A 16x16 football, cracked along a zig-zag and split into two halves that
// drift apart, with smoke rising out of the crack. Generated from a circle
// mask instead of a hand-typed bitmap so the shape is always symmetric.

const N = 16;
const C = 7.5;
const R = 7.6;
// x-position of the crack per row (zig-zag down the middle)
const CRACK = [8, 8, 7, 7, 8, 9, 8, 7, 7, 8, 9, 9, 8, 7, 8, 8];
// centres of the black patches -- kept off the crack so the split reads
// as a gap, not as one dark blob
const PATCHES: [number, number][] = [
  [3.4, 4.6], [12.0, 4.4], [3.6, 11.4], [12.2, 11.6], [7.6, 15.6], [7.4, -0.6],
];

type Px = { x: number; y: number; fill: string };

function ballPixels(): { left: Px[]; right: Px[] } {
  const left: Px[] = [];
  const right: Px[] = [];
  for (let y = 0; y < N; y++) {
    for (let x = 0; x < N; x++) {
      const d = Math.hypot(x - C, y - C);
      if (d > R) continue;
      const cx = CRACK[y];
      if (x === cx) continue; // the crack itself is empty
      let fill: string;
      if (d > R - 1.05) fill = "#6b7280"; // outline
      else if (PATCHES.some(([px, py]) => Math.hypot(x - px, y - py) < 1.9)) fill = "#1b1e24";
      else if (x + y > 19) fill = "#c4cad3"; // shade, lower right
      else if (x + y < 8) fill = "#ffffff"; // highlight, upper left
      else fill = "#e8ebef";
      (x < cx ? left : right).push({ x, y, fill });
    }
  }
  return { left, right };
}

const BALL = ballPixels();

const SMOKE: { x: number; y: number; d: number; s: number }[] = [
  { x: 7, y: -1, d: 0, s: 1 },
  { x: 8, y: -3, d: 0.6, s: 1 },
  { x: 6, y: -4, d: 1.2, s: 1 },
  { x: 9, y: -5, d: 1.8, s: 1 },
  { x: 7, y: -6, d: 2.4, s: 1 },
];
const SPARKS: { x: number; y: number; d: number }[] = [
  { x: 4, y: -2, d: 0.2 },
  { x: 11, y: -1, d: 0.9 },
  { x: 0, y: 4, d: 1.5 },
  { x: 16, y: 6, d: 0.5 },
];

function BrokenBall() {
  return (
    <svg
      className="ob-art"
      viewBox="-3 -8 22 25"
      shapeRendering="crispEdges"
      role="img"
      aria-label="Pixel-Fußball, in zwei Hälften geplatzt, mit Rauch"
    >
      {SMOKE.map((p, i) => (
        <rect
          key={`s${i}`}
          className="ob-smoke"
          style={{ animationDelay: `${p.d}s` }}
          x={p.x}
          y={p.y}
          width={p.s}
          height={p.s}
          fill="#7d8492"
        />
      ))}
      <g className="ob-half ob-left">
        {BALL.left.map((p) => (
          <rect key={`l${p.x}-${p.y}`} x={p.x} y={p.y} width={1} height={1} fill={p.fill} />
        ))}
      </g>
      <g className="ob-half ob-right">
        {BALL.right.map((p) => (
          <rect key={`r${p.x}-${p.y}`} x={p.x} y={p.y} width={1} height={1} fill={p.fill} />
        ))}
      </g>
      {SPARKS.map((p, i) => (
        <rect
          key={`k${i}`}
          className="ob-spark"
          style={{ animationDelay: `${p.d}s` }}
          x={p.x}
          y={p.y}
          width={1}
          height={1}
          fill="var(--warning)"
        />
      ))}
      {/* ground shadow */}
      <rect x={1} y={16.2} width={14} height={0.8} fill="rgba(0,0,0,0.45)" />
    </svg>
  );
}

// ---- banner ----------------------------------------------------------------

function fmtDay(iso: string | null | undefined): string {
  if (!iso) return "einigen Tagen";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "einigen Tagen";
  return d.toLocaleDateString("de-DE", { day: "numeric", month: "long", timeZone: "Europe/Berlin" });
}

export function OutageBanner({
  downSince,
  lastDataDate,
}: {
  downSince: string | null | undefined;
  lastDataDate: string | null | undefined;
}) {
  const since = downSince ? `dem ${fmtDay(downSince)}` : "einigen Tagen";
  const lastData = lastDataDate ? fmtDay(lastDataDate) : "letzten Abruf";
  return (
    <aside className="ob container-page" role="status" aria-live="polite">
      <div className="ob-tape" aria-hidden="true" />
      <div className="ob-inner">
        <BrokenBall />
        <div className="ob-text">
          <span className="ob-tag">{COPY.tag}</span>
          <p className="ob-headline">{COPY.headline}</p>
          <p className="ob-body">{COPY.body(since, lastData)}</p>
          <p className="ob-foot">{COPY.footnote}</p>
        </div>
      </div>
    </aside>
  );
}
