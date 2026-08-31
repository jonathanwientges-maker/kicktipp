"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

// Every route, in the order the sheet lists them (BRIEF §6).
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

function isActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(href + "/");
}

export function NavBar() {
  const pathname = usePathname() || "/";
  const [open, setOpen] = useState(false);
  const burgerRef = useRef<HTMLButtonElement>(null);
  const sheetRef = useRef<HTMLDivElement>(null);

  const close = useCallback(() => {
    setOpen(false);
    burgerRef.current?.focus();
  }, []);

  // close on route change
  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  // body scroll lock + Escape + focus trap while open
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const sheet = sheetRef.current;
    const focusables = () =>
      Array.from(
        sheet?.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])',
        ) ?? [],
      );
    focusables()[0]?.focus();

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        close();
        return;
      }
      if (e.key !== "Tab") return;
      const els = focusables();
      if (!els.length) return;
      const first = els[0];
      const last = els[els.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = prev;
      document.removeEventListener("keydown", onKey);
    };
  }, [open, close]);

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
          <button
            ref={burgerRef}
            type="button"
            className="nav-burger"
            aria-label="Menü öffnen"
            aria-expanded={open}
            aria-controls="nav-sheet"
            onClick={() => setOpen(true)}
          >
            <span className="nav-burger-lines" aria-hidden="true" />
          </button>
        </div>
      </header>

      <div
        className="nav-backdrop"
        data-open={open}
        onClick={close}
        aria-hidden="true"
      />
      <div
        id="nav-sheet"
        ref={sheetRef}
        className="nav-sheet"
        data-open={open}
        role="dialog"
        aria-modal="true"
        aria-label="Navigation"
      >
        <div className="nav-sheet-head">
          <button
            type="button"
            className="nav-sheet-close"
            aria-label="Menü schließen"
            onClick={close}
          >
            ✕
          </button>
        </div>
        <nav aria-label="Hauptnavigation">
          {NAV.map((n) => (
            <Link
              key={n.href}
              href={n.href}
              className="nav-sheet-link"
              data-active={isActive(pathname, n.href)}
              onClick={() => setOpen(false)}
            >
              {n.label}
            </Link>
          ))}
        </nav>
      </div>
    </>
  );
}
