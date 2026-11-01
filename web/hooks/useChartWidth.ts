"use client";
import { useLayoutEffect, useRef, useState } from "react";

/**
 * Measures the container so a chart can draw at real pixel size. Text and
 * dots then stay at their intended size on a phone instead of shrinking with
 * a fixed viewBox. Starts at `initial` so server and first client render match.
 */
export function useChartWidth<T extends HTMLElement>(initial = 640): [React.RefObject<T | null>, number] {
  const ref = useRef<T>(null);
  const [w, setW] = useState(initial);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const measure = () => setW(Math.max(280, Math.round(el.getBoundingClientRect().width)));
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, w];
}
