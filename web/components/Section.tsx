import type { ReactNode } from "react";

export function Section({
  title,
  children,
  sub,
  info,
}: {
  title: string;
  sub?: string;
  /** optional glossary node rendered as a "?" affordance next to the title */
  info?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section style={{ marginBottom: "2.5rem" }}>
      <h2 style={{ margin: "0 0 0.15rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
        {title}
        {info}
      </h2>
      {sub ? (
        <p className="muted" style={{ margin: "0 0 0.85rem", fontSize: "var(--fs-small)" }}>
          {sub}
        </p>
      ) : (
        <div style={{ height: "0.75rem" }} />
      )}
      {children}
    </section>
  );
}
