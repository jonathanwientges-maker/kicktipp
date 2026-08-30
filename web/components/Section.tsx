export function Section({
  title,
  children,
  sub,
}: {
  title: string;
  sub?: string;
  children: React.ReactNode;
}) {
  return (
    <section style={{ marginBottom: "2.25rem" }}>
      <h2 style={{ fontSize: "1.15rem", margin: "0 0 0.15rem" }}>{title}</h2>
      {sub && <p className="muted" style={{ margin: "0 0 0.75rem", fontSize: "0.9rem" }}>{sub}</p>}
      {!sub && <div style={{ height: "0.6rem" }} />}
      {children}
    </section>
  );
}
