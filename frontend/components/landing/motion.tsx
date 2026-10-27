"use client";

import { CheckCircle2, Sparkles } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";

const reduced = () => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/** Fades its children in when they scroll into view (once). */
export function Reveal({ children, delay = 0, className = "" }: { children: ReactNode; delay?: number; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(([e]) => {
      if (e.isIntersecting) { setShown(true); io.disconnect(); }
    }, { threshold: 0.15 });
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return (
    <div ref={ref} className={`tt-reveal ${shown ? "is-in" : ""} ${className}`} style={{ transitionDelay: `${delay}ms` }}>
      {children}
    </div>
  );
}

/** Counts up to `to` when it scrolls into view. */
export function CountUp({ to }: { to: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  const [n, setN] = useState(0);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (reduced()) { setN(to); return; }
    const io = new IntersectionObserver(([e]) => {
      if (!e.isIntersecting) return;
      io.disconnect();
      const start = performance.now();
      const tick = (t: number) => {
        const p = Math.min(1, (t - start) / 1300);
        setN(Math.round(to * (1 - Math.pow(1 - p, 3))));
        if (p < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    }, { threshold: 0.4 });
    io.observe(el);
    return () => io.disconnect();
  }, [to]);
  return <span ref={ref}>{n.toLocaleString("en-IN")}</span>;
}

const ASK = "Dr. Kaur is away tomorrow. Cover her classes.";
const STEPS = ["Found her 4 classes", "Ranked free teachers of the same subject", "Checked every change for clashes"];

/** A looping, scripted preview of the assistant: ask → it works → a plan card → applied. */
export function ChatDemo() {
  const [typed, setTyped] = useState(0);
  const [step, setStep] = useState(0); // 0 typing · 1-3 steps · 4 card · 5 applied
  useEffect(() => {
    if (reduced()) { setTyped(ASK.length); setStep(4); return; }
    let alive = true;
    const timers: ReturnType<typeof setTimeout>[] = [];
    const at = (ms: number, f: () => void) => timers.push(setTimeout(() => alive && f(), ms));
    const run = () => {
      setTyped(0); setStep(0);
      for (let i = 1; i <= ASK.length; i++) at(400 + i * 38, () => setTyped(i));
      const done = 400 + ASK.length * 38;
      [1, 2, 3, 4, 5].forEach((s, i) => at(done + 500 + i * 900, () => setStep(s)));
      at(done + 500 + 4 * 900 + 2600, run);
    };
    run();
    return () => { alive = false; timers.forEach(clearTimeout); };
  }, []);

  return (
    <div className="rounded-2xl border border-border bg-surface p-4 text-sm shadow-xl">
      <div className="mb-3 flex items-center gap-2 text-xs text-muted">
        <Sparkles size={14} className="text-accent-text" aria-hidden /> Assistant
      </div>
      <div className="ml-auto w-fit max-w-[88%] rounded-2xl rounded-br-sm bg-accent px-3 py-2 text-white dark:text-bg">
        {ASK.slice(0, typed)}
        {typed < ASK.length && <span className="tt-caret ml-px inline-block h-4 w-px translate-y-0.5 bg-current" />}
      </div>
      <ul className="mt-3 min-h-[4.5rem] space-y-1.5 text-xs text-muted">
        {STEPS.map((s, i) => step > i && (
          <li key={s} className="tt-fade-up flex items-center gap-1.5">
            <CheckCircle2 size={13} className="text-ok" aria-hidden /> {s}
          </li>
        ))}
      </ul>
      <div className={`mt-2 rounded-xl border p-3 transition-all duration-500 ${step >= 4 ? "border-accent/35 bg-accent-soft/50 opacity-100" : "border-transparent opacity-0"}`}>
        <p className="text-xs font-semibold text-accent-text">Cover plan for tomorrow</p>
        <p className="mt-1 text-xs">3 substitutes · 1 cancelled · 0 clashes</p>
        <div className="mt-2.5 flex items-center gap-2">
          {step >= 5 ? (
            <span className="tt-pop inline-flex items-center gap-1.5 rounded-md bg-ok-soft px-2.5 py-1 text-xs font-medium text-ok">
              <CheckCircle2 size={13} aria-hidden /> Applied · students notified
            </span>
          ) : (
            <span className="relative inline-flex">
              <span className="tt-ping absolute inset-0 rounded-md bg-accent" aria-hidden />
              <span className="relative rounded-md bg-accent px-2.5 py-1 text-xs font-medium text-white dark:text-bg">Apply</span>
            </span>
          )}
          <span className="text-[11px] text-muted">Nothing changes until you click.</span>
        </div>
      </div>
    </div>
  );
}
