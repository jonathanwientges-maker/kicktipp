"use client";
import { useId, useState } from "react";

/**
 * An inline "?" affordance that toggles a short glossary note. Purely
 * presentational; the note text is passed in. Keyboard-operable, and it
 * carries proper aria wiring.
 */
export function Explainer({ label, children }: { label: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: label ? "0.4rem" : 0, position: "relative" }}>
      {label ? <span>{label}</span> : null}
      <button
        type="button"
        aria-expanded={open}
        aria-controls={id}
        aria-label={`Erklärung: ${label}`}
        onClick={() => setOpen((v) => !v)}
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
        }}
      >
        ?
      </button>
      {open && (
        <span
          id={id}
          role="note"
          style={{
            position: "absolute",
            top: "calc(100% + 8px)",
            left: 0,
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
