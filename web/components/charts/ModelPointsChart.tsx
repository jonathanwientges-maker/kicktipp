import type { ModelPerfRow } from "@/lib/data";
import { fmtInt } from "@/lib/format";

const W = 640;
const H = 240;
const PAD = { l: 34, r: 12, t: 12, b: 24 };

export function ModelPointsChart({ rows }: { rows: ModelPerfRow[] }) {
  if (!rows.length) return <p className="muted">Noch keine abgeschlossenen Spieltage.</p>;
  const maxY = Math.max(...rows.map((r) => Math.max(r.cum_points, r.cum_always21_points))) * 1.05;
  const xs = (i: number) => PAD.l + (i / Math.max(1, rows.length - 1)) * (W - PAD.l - PAD.r);
  const ys = (v: number) => H - PAD.b - (v / maxY) * (H - PAD.t - PAD.b);
  const line = (key: "cum_points" | "cum_always21_points") =>
    rows.map((r, i) => `${i === 0 ? "M" : "L"} ${xs(i)} ${ys(r[key])}`).join(" ");

  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet" style={{ width: "100%", height: "auto" }} role="img">
      <title>Kumulierte Modell-Punkte gegen die 2:1-Basis</title>
      <line x1={PAD.l} y1={H - PAD.b} x2={W - PAD.r} y2={H - PAD.b} stroke="var(--border)" />
      {[0, maxY / 2, maxY].map((v, i) => (
        <text key={i} x={PAD.l - 6} y={ys(v) + 3} fontSize={9} textAnchor="end" fill="var(--muted)">
          {fmtInt(v)}
        </text>
      ))}
      <path d={line("cum_points")} fill="none" stroke="var(--accent)" strokeWidth={2} />
      <path d={line("cum_always21_points")} fill="none" stroke="var(--muted)" strokeWidth={2} strokeDasharray="4 3" />
      <text x={W - PAD.r} y={PAD.t + 8} fontSize={10} textAnchor="end" fill="var(--accent)">
        Modell
      </text>
      <text x={W - PAD.r} y={PAD.t + 21} fontSize={10} textAnchor="end" fill="var(--muted)">
        immer 2:1
      </text>
    </svg>
  );
}
