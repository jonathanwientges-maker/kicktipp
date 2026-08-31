"use client";
import type { ModelPerfRow } from "@/lib/data";
import { fmtInt } from "@/lib/format";
import { useInView } from "@/hooks/useInView";
import { DrawPath } from "@/components/motion/DrawPath";

const W = 640;
const H = 240;
const PAD = { l: 34, r: 12, t: 12, b: 24 };

export function ModelPointsChart({ rows }: { rows: ModelPerfRow[] }) {
  const [ref, inView] = useInView<HTMLDivElement>();
  if (!rows.length) return <p className="muted">Noch keine abgeschlossenen Spieltage.</p>;
  const maxY = Math.max(...rows.map((r) => Math.max(r.cum_points, r.cum_always21_points))) * 1.05;
  const xs = (i: number) => PAD.l + (i / Math.max(1, rows.length - 1)) * (W - PAD.l - PAD.r);
  const ys = (v: number) => H - PAD.b - (v / maxY) * (H - PAD.t - PAD.b);
  const line = (key: "cum_points" | "cum_always21_points") =>
    rows.map((r, i) => `${i === 0 ? "M" : "L"} ${xs(i)} ${ys(r[key])}`).join(" ");

  return (
    <div ref={ref}>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet" style={{ width: "100%", height: "auto" }} role="img">
        <title>Kumulierte Modell-Punkte gegen die 2:1-Basis</title>
        {[0, maxY / 2, maxY].map((v, i) => (
          <line key={i} className="chart-grid" x1={PAD.l} y1={ys(v)} x2={W - PAD.r} y2={ys(v)} />
        ))}
        {[0, maxY / 2, maxY].map((v, i) => (
          <text key={i} x={PAD.l - 6} y={ys(v) + 3} className="chart-axis-label" textAnchor="end">
            {fmtInt(v)}
          </text>
        ))}
        <DrawPath d={line("cum_points")} inView={inView} fill="none" stroke="var(--accent)" strokeWidth={2.5} strokeLinecap="round" />
        <DrawPath
          d={line("cum_always21_points")}
          inView={inView}
          fill="none"
          stroke="var(--text-dim)"
          strokeWidth={2}
          strokeDasharray="4 4"
          strokeLinecap="round"
        />
        <text x={W - PAD.r} y={PAD.t + 8} fontSize={10} textAnchor="end" fill="var(--accent)">
          Modell
        </text>
        <text x={W - PAD.r} y={PAD.t + 21} fontSize={10} textAnchor="end" fill="var(--text-dim)">
          immer 2:1
        </text>
      </svg>
    </div>
  );
}
