"use client";
// A card whose header toggles an in-place detail panel. The summary and the
// detail are server-rendered and passed in as props, so this adds only the
// open/closed state. The panel animates with the same 0fr -> 1fr grid trick
// as the DataTable cards; while closed it is visibility:hidden, which also
// takes its links out of the tab order.
import { useId, useState } from "react";

export function ExpandCard({
  summary,
  children,
  accent,
}: {
  summary: React.ReactNode;
  children: React.ReactNode;
  accent: string;
}) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const toggle = () => setOpen((o) => !o);
  return (
    <div className="surface fx-card" data-open={open} style={{ borderLeft: `3px solid ${accent}` }}>
      <div
        className="fx-head"
        role="button"
        tabIndex={0}
        aria-expanded={open}
        aria-controls={id}
        onClick={toggle}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            toggle();
          }
        }}
      >
        <div className="fx-summary">{summary}</div>
        <span className="fx-foot" aria-hidden="true">
          <span>{open ? "Weniger" : "Spielanalyse"}</span>
          <span className="dt-chev-icon" data-open={open}>
            ›
          </span>
        </span>
      </div>
      <div id={id} className="dt-card-wrap fx-body" data-open={open}>
        <div className="dt-card-clip">{children}</div>
      </div>
    </div>
  );
}
