"use client";
import { useEffect, useRef, useState } from "react";
import { useInView } from "@/hooks/useInView";
import { fmtNum, fmtInt, fmtSigned } from "@/lib/format";

type Fmt = "num" | "int" | "signed";

function format(v: number, fmt: Fmt, dp: number): string {
  if (fmt === "int") return fmtInt(v);
  if (fmt === "signed") return fmtSigned(v, dp);
  return fmtNum(v, dp);
}

function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

/**
 * Counts from 0 to `value` on first view, over --dur-mid with --ease-out.
 * Renders the final value immediately when reduced motion is set.
 */
export function CountUp({
  value,
  fmt = "num",
  dp = 2,
  className,
}: {
  value: number;
  fmt?: Fmt;
  dp?: number;
  className?: string;
}) {
  const [ref, inView] = useInView<HTMLSpanElement>();
  const [display, setDisplay] = useState(() =>
    prefersReducedMotion() ? value : 0,
  );
  const started = useRef(false);

  useEffect(() => {
    if (!inView || started.current) return;
    started.current = true;
    if (prefersReducedMotion() || typeof requestAnimationFrame === "undefined") {
      setDisplay(value);
      return;
    }
    const DUR = 350;
    const ease = (t: number) => 1 - Math.pow(1 - t, 3); // ~ cubic-bezier(.16,1,.30,1)
    const t0 = performance.now();
    let raf = 0;
    const tick = (now: number) => {
      const p = Math.min(1, (now - t0) / DUR);
      setDisplay(value * ease(p));
      if (p < 1) raf = requestAnimationFrame(tick);
      else setDisplay(value);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [inView, value]);

  return (
    <span ref={ref} className={className}>
      {format(display, fmt, dp)}
    </span>
  );
}
