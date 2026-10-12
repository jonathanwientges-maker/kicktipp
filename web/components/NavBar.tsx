"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

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

// Apple's momentum projection: where a flick at `v` px/s would come to rest.
const DECEL = 0.998;
const project = (v: number) => ((v / 1000) * DECEL) / (1 - DECEL);

export function NavBar() {
  const pathname = usePathname() || "/";
  const [open, setOpen] = useState(false);
  const burgerRef = useRef<HTMLButtonElement>(null);
  const sheetRef = useRef<HTMLDivElement>(null);
  const backdropRef = useRef<HTMLDivElement>(null);
  const navRef = useRef<HTMLElement>(null);
  const [ink, setInk] = useState<{ x: number; w: number } | null>(null);
  const [slide, setSlide] = useState(false);

  const close = useCallback(() => {
    setOpen(false);
    burgerRef.current?.focus();
  }, []);

  // sliding underline under the active top-bar link
  useLayoutEffect(() => {
    const nav = navRef.current;
    const el = nav?.querySelector<HTMLElement>('.nav-link[data-active="true"]');
    if (!nav || !el) {
      setInk(null);
      return;
    }
    setInk({ x: el.offsetLeft, w: el.offsetWidth });
    // enable the transition only after the first placement
    const id = requestAnimationFrame(() => setSlide(true));
    return () => cancelAnimationFrame(id);
  }, [pathname]);

  // drag the sheet away: 1:1 tracking, then momentum decides
  useEffect(() => {
    const sheet = sheetRef.current;
    const backdrop = backdropRef.current;
    if (!sheet || !backdrop || !open) return;
    let startX = 0;
    let startY = 0;
    let pid: number | null = null;
    let dragging = false;
    let samples: { x: number; t: number }[] = [];

    const apply = (dx: number) => {
      const w = sheet.offsetWidth;
      // pulling further open than rest resists (rubber band)
      const x = dx >= 0 ? dx : (dx * 0.55 * w) / (w + 0.55 * Math.abs(dx));
      sheet.style.transform = `translateX(${x}px)`;
      backdrop.style.opacity = String(Math.max(0, 1 - Math.max(0, dx) / w));
    };
    const reset = () => {
      sheet.style.transform = "";
      backdrop.style.opacity = "";
      delete sheet.dataset.dragging;
      delete backdrop.dataset.dragging;
    };
    const down = (e: PointerEvent) => {
      if (e.pointerType === "mouse") return;
      pid = e.pointerId;
      startX = e.clientX;
      startY = e.clientY;
      samples = [{ x: e.clientX, t: e.timeStamp }];
    };
    const move = (e: PointerEvent) => {
      if (e.pointerId !== pid) return;
      const dx = e.clientX - startX;
      if (!dragging) {
        const dy = e.clientY - startY;
        if (Math.abs(dx) < 10 || Math.abs(dx) < Math.abs(dy)) return;
        dragging = true;
        sheet.setPointerCapture(e.pointerId);
        sheet.dataset.dragging = "true";
        backdrop.dataset.dragging = "true";
      }
      samples.push({ x: e.clientX, t: e.timeStamp });
      if (samples.length > 6) samples.shift();
      apply(dx);
    };
    const up = (e: PointerEvent) => {
      if (e.pointerId !== pid) return;
      pid = null;
      if (!dragging) return;
      dragging = false;
      const dx = e.clientX - startX;
      const a = samples[0];
      const b = samples[samples.length - 1];
      const v = b.t > a.t ? ((b.x - a.x) / (b.t - a.t)) * 1000 : 0;
      const dismiss = dx + project(v) > sheet.offsetWidth / 2;
      // clearing inline styles lets the spring settle from the live position
      reset();
      if (dismiss) setOpen(false);
    };
    sheet.addEventListener("pointerdown", down);
    sheet.addEventListener("pointermove", move);
    sheet.addEventListener("pointerup", up);
    sheet.addEventListener("pointercancel", up);
    return () => {
      sheet.removeEventListener("pointerdown", down);
      sheet.removeEventListener("pointermove", move);
      sheet.removeEventListener("pointerup", up);
      sheet.removeEventListener("pointercancel", up);
      reset();
    };
  }, [open]);

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
            ref={navRef}
            data-slide={ink !== null}
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
            {ink && (
              <span
                className="nav-ink"
                aria-hidden="true"
                style={{
                  ["--x" as any]: `${ink.x}px`,
                  ["--w" as any]: `${ink.w}px`,
                  transitionDuration: slide ? undefined : "0s",
                }}
              />
            )}
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
        ref={backdropRef}
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
