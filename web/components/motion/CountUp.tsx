"use client";
import { useEffect } from "react";
import { useInView } from "@/hooks/useInView";
import { fmtNum, fmtInt, fmtSigned } from "@/lib/format";

type Fmt = "num" | "int" | "signed";

function format(v: number, fmt: Fmt, dp: number): string {
  if (fmt === "int") return fmtInt(v);
  if (fmt === "signed") return fmtSigned(v, dp);
  return fmtNum(v, dp);
}

/**
 * Always renders the real value (server HTML, no-JS, reduced motion, and
 * anything already on screen). Only a number that starts below the fold is
 * reset to 0 and counted up when it scrolls into view. The count writes to
 * the DOM directly, so React does not re-render every frame.
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
  const final = format(value, fmt, dp);

  useEffect(() => {
    const el = ref.current;
    if (!el || inView) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    if (el.getBoundingClientRect().top >= window.innerHeight * 0.9) {
      el.textContent = format(0, fmt, dp);
    }
  }, [ref, inView, fmt, dp]);

  useEffect(() => {
    const el = ref.current;
    if (!inView || !el || el.textContent === final) return;
    const DUR = 350;
    const ease = (t: number) => 1 - Math.pow(1 - t, 3);
    const t0 = performance.now();
    let raf = 0;
    const tick = (now: number) => {
      const p = Math.min(1, (now - t0) / DUR);
      el.textContent = p < 1 ? format(value * ease(p), fmt, dp) : final;
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf);
      el.textContent = final;
    };
  }, [inView, value, fmt, dp, final, ref]);

  return (
    <span ref={ref} className={className}>
      {final}
    </span>
  );
}
