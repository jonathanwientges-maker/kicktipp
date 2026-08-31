"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV: { href: string; label: string }[] = [
  { href: "/", label: "Start" },
  { href: "/tabelle", label: "Tabelle" },
  { href: "/team", label: "Teams" },
  { href: "/spieler", label: "Spieler" },
  { href: "/modell", label: "Modell" },
  { href: "/simulation", label: "Simulation" },
  { href: "/rekorde", label: "Rekorde" },
  { href: "/methodik", label: "Methodik" },
];

// Bottom tab bar on mobile: 5 items max.
const TABS = NAV.filter((n) =>
  ["/", "/tabelle", "/team", "/modell", "/simulation"].includes(n.href),
);

function isActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(href + "/");
}

export function NavBar() {
  const pathname = usePathname() || "/";
  return (
    <>
      <header className="topbar">
        <div
          className="container-page"
          style={{ display: "flex", alignItems: "center", gap: "1.5rem", height: 56 }}
        >
          <Link href="/" className="wordmark">
            BUNDESLIGA <span className="hub">HUB</span>
          </Link>
          <nav
            className="topbar-nav"
            style={{ display: "flex", gap: "1.1rem", alignItems: "center", overflowX: "auto" }}
          >
            {NAV.map((n) => (
              <Link
                key={n.href}
                href={n.href}
                className="nav-link"
                data-active={isActive(pathname, n.href)}
              >
                {n.label}
              </Link>
            ))}
          </nav>
        </div>
      </header>

      <nav className="tabbar" aria-label="Hauptnavigation">
        {TABS.map((n) => (
          <Link key={n.href} href={n.href} data-active={isActive(pathname, n.href)}>
            {n.label}
          </Link>
        ))}
      </nav>
    </>
  );
}
