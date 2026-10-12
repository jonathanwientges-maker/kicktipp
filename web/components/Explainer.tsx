"use client";
import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";

/**
 * An inline "?" affordance that toggles a short glossary note. Purely
 * presentational; the note text is passed in. Keyboard-operable, and it
 * carries proper aria wiring.
 */
export function Explainer({ label, children }: { label: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const rootRef = useRef<HTMLSpanElement>(null);
  const popRef = useRef<HTMLSpanElement>(null);
  const [shift, setShift] = useState(0);

  // keep the note inside the viewport, and grow it out of the "?" button
  useLayoutEffect(() => {
    if (!open) return;
    const pop = popRef.current;
    const root = rootRef.current;
    if (!pop || !root) return;
    const margin = 8;
    const r = pop.getBoundingClientRect();
    const vw = document.documentElement.clientWidth;
    let dx = 0;
    if (r.right > vw - margin) dx = vw - margin - r.right;
    if (r.left + dx < margin) dx = margin - r.left;
    setShift(dx);
    const btn = root.querySelector("button");
    if (btn) {
      const b = btn.getBoundingClientRect();
      pop.style.setProperty("--ox", `${b.left + b.width / 2 - (r.left + dx)}px`);
    }
  }, [open]);

  // dismiss on outside press and Escape
  useEffect(() => {
    if (!open) return;
    const onDown = (e: PointerEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onDown);
      document.removeEventListener("keydown", onKey);
      setShift(0);
    };
  }, [open]);

  return (
    <span ref={rootRef} style={{ display: "inline-flex", alignItems: "center", gap: label ? "0.4rem" : 0, position: "relative" }}>
      {label ? <span>{label}</span> : null}
      <button
        type="button"
        aria-expanded={open}
        aria-controls={id}
        aria-label={`Erklärung: ${label}`}
        onClick={() => setOpen((v) => !v)}
        className="explainer-btn"
        style={{
          width: 16,
          height: 16,
          borderRadius: "var(--r-full)",
          border: "1px solid var(--border-strong)",
          background: open ? "var(--accent)" : "transparent",
          color: open ? "var(--accent-on)" : "var(--text-dim)",
          fontFamily: "var(--font-display)",
          fontSize: "0.62rem",
          fontWeight: 700,
          lineHeight: 1,
          cursor: "pointer",
          padding: 0,
          flex: "0 0 auto",
          position: "relative",
        }}
      >
        ?
      </button>
      {open && (
        <span
          id={id}
          ref={popRef}
          role="note"
          className="explainer-pop"
          style={{
            position: "absolute",
            top: "calc(100% + 8px)",
            left: shift,
            zIndex: 30,
            width: "min(320px, 78vw)",
            padding: "0.75rem 0.85rem",
            background: "var(--surface-raised)",
            border: "1px solid var(--border-strong)",
            borderRadius: "var(--r-md)",
            boxShadow: "var(--shadow-pop)",
            fontFamily: "var(--font-body)",
            fontSize: "var(--fs-small)",
            fontWeight: 400,
            lineHeight: 1.55,
            color: "var(--text-muted)",
            textTransform: "none",
            letterSpacing: "normal",
          }}
        >
          {children}
        </span>
      )}
    </span>
  );
}
