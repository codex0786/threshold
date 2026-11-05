"use client";
import { type CSSProperties, type ReactNode, useEffect, useRef, useState } from "react";

// Runs once when the element first scrolls into view. Without observer support, it runs straight away.
function useInView<T extends HTMLElement>(onEnter: (el: T) => void) {
  const ref = useRef<T>(null);
  const callback = useRef(onEnter);
  callback.current = onEnter;
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (!("IntersectionObserver" in window)) { callback.current(el); return; }
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) { callback.current(el); observer.disconnect(); }
    }, { threshold: 0.12, rootMargin: "0px 0px -6% 0px" });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);
  return ref;
}

export function Reveal({ children, delay = 0, className = "" }: { children: ReactNode; delay?: number; className?: string }) {
  const ref = useInView<HTMLDivElement>((el) => el.classList.add("is-in"));
  return <div ref={ref} data-reveal className={className} style={{ "--delay": `${delay}ms` } as CSSProperties}>{children}</div>;
}

// The server renders the real value, so the figure is correct with no JavaScript, in print and if the animation never runs.
export function CountUp({ value, duration = 1400 }: { value: number; duration?: number }) {
  const [shown, setShown] = useState(value);
  const ref = useInView<HTMLSpanElement>(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const start = performance.now();
    const step = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      setShown(t === 1 ? value : Math.round(value * (1 - (1 - t) ** 3)));
      if (t < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  });
  return <span ref={ref} className="tnum">{shown.toLocaleString("en-IN")}</span>;
}
