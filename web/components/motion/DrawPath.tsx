"use client";
import { useEffect, useRef, useState } from "react";

/**
 * An SVG <path> that draws itself in when it scrolls into view: its own
 * length becomes the dasharray, and the dashoffset transitions from that
 * length to 0 over --dur-slow. Reduced motion => rendered whole.
 * Must be rendered inside an <svg> that is itself inside a ref'd wrapper
 * marked in-view (the chart passes `inView` down).
 */
export function DrawPath({
  d,
  inView,
  ...rest
}: { d: string; inView: boolean } & React.SVGProps<SVGPathElement>) {
  const ref = useRef<SVGPathElement | null>(null);
  const [len, setLen] = useState(0);

  useEffect(() => {
    if (ref.current) {
      try {
        setLen(ref.current.getTotalLength());
      } catch {
        setLen(0);
      }
    }
  }, [d]);

  const reduce =
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const drawn = inView || reduce || len === 0;

  return (
    <path
      ref={ref}
      d={d}
      className="chart-draw"
      style={
        len
          ? {
              strokeDasharray: len,
              strokeDashoffset: drawn ? 0 : len,
            }
          : undefined
      }
      {...rest}
    />
  );
}
