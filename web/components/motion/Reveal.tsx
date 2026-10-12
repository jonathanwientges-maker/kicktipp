"use client";
import { useEffect, useState } from "react";
import { useInView } from "@/hooks/useInView";

/**
 * Enter animation (opacity 0->1, translateY 8px->0) that fires once on
 * scroll-in. `index` staggers by 30ms, capped at 12.
 *
 * Content is only hidden ("armed") by JS, and only when it starts below the
 * fold: server HTML, no-JS, and above-the-fold content are always visible.
 * Reduced motion never arms.
 */
export function Reveal({
  children,
  index = 0,
  as: Tag = "div",
  className = "",
  style,
}: {
  children: React.ReactNode;
  index?: number;
  as?: any;
  className?: string;
  style?: React.CSSProperties;
}) {
  const [ref, inView] = useInView<HTMLElement>();
  const [armed, setArmed] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el || inView) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    if (el.getBoundingClientRect().top >= window.innerHeight * 0.9) setArmed(true);
  }, [ref, inView]);

  const delay = Math.min(index, 12) * 30;
  const cls = armed ? `enter ${inView ? "in" : ""}` : "";
  return (
    <Tag
      ref={ref as any}
      className={`${cls} ${className}`.trim()}
      style={{ transitionDelay: inView ? `${delay}ms` : "0ms", ...style }}
    >
      {children}
    </Tag>
  );
}
