"use client";
// Two-line rolling xG for/against with a shaded band between.
import { fmtNum } from "@/lib/format";
import { useInView } from "@/hooks/useInView";
import { DrawPath } from "@/components/motion/DrawPath";

const W = 620;
const H = 220;
const PAD = { l: 30, r: 12, t: 12, b: 22 };

export function RollingDual({
  forVals,
  againstVals,
  title = "Rollender xG-Schnitt (8 Spiele)",
  teamColor = "var(--accent)",
}: {
  forVals: number[];
  againstVals: number[];
  title?: string;
  teamColor?: string;
}) {
  const [ref, inView] = useInView<HTMLDivElement>();
  const n = Math.max(forVals.length, againstVals.length);
  if (n === 0) return <p className="muted" style={{ fontSize: "var(--fs-small)" }}>Noch keine Spiele in dieser Ansicht.</p>;
  if (n < 2) {
    return (
      <div style={{ display: "flex", gap: "1.75rem", flexWrap: "wrap", alignItems: "baseline" }}>
        <div>
          <div className="label" style={{ marginBottom: "0.3rem" }}>xG erzielt</div>
          <span className="display-m num">{fmtNum(forVals[0] ?? 0, 2)}</span>
        </div>
        <div>
          <div className="label" style={{ marginBottom: "0.3rem" }}>xG zugelassen</div>
          <span className="display-m num">{fmtNum(againstVals[0] ?? 0, 2)}</span>
        </div>
        <span className="muted" style={{ fontSize: "var(--fs-small)" }}>
          Bisher 1 Spiel — der Verlauf wird ab dem 2. Spieltag angezeigt.
        </span>
      </div>
    );
  }
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
    <div ref={ref}>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet" style={{ width: "100%", height: "auto" }} role="img">
        <title>{title}</title>
        {[0, maxV / 2, maxV].map((v, i) => (
          <line key={i} className="chart-grid" x1={PAD.l} y1={ys(v)} x2={W - PAD.r} y2={ys(v)} />
        ))}
        {[0, maxV / 2, maxV].map((v, i) => (
          <text key={i} x={PAD.l - 5} y={ys(v) + 3} className="chart-axis-label" textAnchor="end">
            {fmtNum(v, 1)}
          </text>
        ))}
        {band && <path d={band} fill={teamColor} fillOpacity={0.1} />}
        <DrawPath d={line(forVals)} inView={inView} fill="none" stroke={teamColor} strokeWidth={2.5} strokeLinecap="round" />
        <DrawPath
          d={line(againstVals)}
          inView={inView}
          fill="none"
          stroke="var(--negative)"
          strokeWidth={2.5}
          strokeLinecap="round"
        />
        <text x={W - PAD.r} y={PAD.t + 8} fontSize={10} textAnchor="end" fill={teamColor}>
          xG erzielt
        </text>
        <text x={W - PAD.r} y={PAD.t + 21} fontSize={10} textAnchor="end" fill="var(--negative)">
          xG zugelassen
        </text>
      </svg>
    </div>
  );
}
