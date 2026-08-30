// Two-line rolling xG for/against with a shaded band between
// (BUILD BLUEPRINT §7.4).
import { fmtNum } from "@/lib/format";

const W = 620;
const H = 220;
const PAD = { l: 30, r: 12, t: 12, b: 22 };

export function RollingDual({
  forVals,
  againstVals,
  title = "Rollender xG-Schnitt (8 Spiele)",
}: {
  forVals: number[];
  againstVals: number[];
  title?: string;
}) {
  const n = Math.max(forVals.length, againstVals.length);
  if (n === 0) return <p className="muted">Keine Daten.</p>;
  const maxV = Math.max(0.5, ...forVals, ...againstVals) * 1.1;
  const xs = (i: number) => PAD.l + (i / Math.max(1, n - 1)) * (W - PAD.l - PAD.r);
  const ys = (v: number) => H - PAD.b - (v / maxV) * (H - PAD.t - PAD.b);

  const line = (vals: number[]) => vals.map((v, i) => `${i === 0 ? "M" : "L"} ${xs(i)} ${ys(v)}`).join(" ");
  const band =
    forVals.length === againstVals.length && forVals.length > 0
      ? `${forVals.map((v, i) => `${i === 0 ? "M" : "L"} ${xs(i)} ${ys(v)}`).join(" ")} ` +
        `${againstVals
          .map((v, i) => `L ${xs(againstVals.length - 1 - i)} ${ys(againstVals[againstVals.length - 1 - i])}`)
          .join(" ")} Z`
      : "";

  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet" style={{ width: "100%", height: "auto" }} role="img">
      <title>{title}</title>
      <line x1={PAD.l} y1={H - PAD.b} x2={W - PAD.r} y2={H - PAD.b} stroke="var(--border)" />
      {[0, maxV / 2, maxV].map((v, i) => (
        <text key={i} x={PAD.l - 5} y={ys(v) + 3} fontSize={9} textAnchor="end" fill="var(--muted)">
          {fmtNum(v, 1)}
        </text>
      ))}
      {band && <path d={band} fill="var(--accent)" fillOpacity={0.12} />}
      <path d={line(forVals)} fill="none" stroke="var(--accent)" strokeWidth={2} />
      <path d={line(againstVals)} fill="none" stroke="var(--negative)" strokeWidth={2} />
      <text x={W - PAD.r} y={PAD.t + 8} fontSize={10} textAnchor="end" fill="var(--accent)">
        xG erzielt
      </text>
      <text x={W - PAD.r} y={PAD.t + 21} fontSize={10} textAnchor="end" fill="var(--negative)">
        xG zugelassen
      </text>
    </svg>
  );
}
