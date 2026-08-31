"use client";
import { useInView } from "@/hooks/useInView";

/**
 * Wraps children in an enter animation (opacity 0->1, translateY 8px->0)
 * that fires once on scroll-in. `index` staggers by 30ms, capped at 12.
 * The reduced-motion guard in globals.css collapses the transition.
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
  const delay = Math.min(index, 12) * 30;
  return (
    <Tag
      ref={ref as any}
      className={`enter ${inView ? "in" : ""} ${className}`.trim()}
      style={{ transitionDelay: inView ? `${delay}ms` : "0ms", ...style }}
    >
      {children}
    </Tag>
  );
}
