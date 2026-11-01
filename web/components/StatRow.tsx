"use client";
// One home-vs-away comparison row with a short label, a one-line hint and a
// "?" that opens its explanation INLINE under the row. The shared Explainer
// popover cannot be used here: it is absolutely positioned and the fixture
// card clips its overflow, so it would never show.
import { useId, useState } from "react";

export function StatRow({
  label,
  hint,
  explain,
  homeText,
  awayText,
  homePct,
  awayPct,
  homeColor,
  awayColor,
  homeBigger,
}: {
  label: string;
  hint?: string;
  explain?: React.ReactNode;
  homeText: string;
  awayText: string;
  homePct: number;
  awayPct: number;
  homeColor: string;
  awayColor: string;
  homeBigger: boolean;
}) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <div className="cmp-row">
      <div className="cmp-vals">
        <span className="cmp-val home" data-bigger={homeBigger}>
          {homeText}
        </span>
        <span className="fx-stat-label">
          {label}
          {explain && (
            <button
              type="button"
              className="fx-q"
              data-open={open}
              aria-expanded={open}
              aria-controls={id}
              aria-label={`Erklärung: ${label}`}
              onClick={() => setOpen((v) => !v)}
            >
              ?
            </button>
          )}
        </span>
        <span className="cmp-val away" data-bigger={!homeBigger}>
          {awayText}
        </span>
      </div>
      {hint && <div className="fx-hint">{hint}</div>}
      <div className="cmp-bar" aria-hidden="true">
        <span className="cmp-bar-half home">
          <span className="cmp-bar-fill" style={{ width: `${homePct}%`, background: homeColor }} />
        </span>
        <span className="cmp-bar-half away">
          <span className="cmp-bar-fill" style={{ width: `${awayPct}%`, background: awayColor }} />
        </span>
      </div>
      {open && explain && (
        <div id={id} role="note" className="fx-note">
          {explain}
        </div>
      )}
    </div>
  );
}
