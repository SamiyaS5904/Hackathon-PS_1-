"use client";

import {
  Bell, CalendarDays, CheckCircle2, ChevronDown, House, MousePointer2, ShieldCheck, Sparkles, Undo2, Users,
} from "lucide-react";
import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";

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
    <div className="rounded-2xl border border-border-strong/70 bg-surface p-4 text-sm shadow-[0_30px_80px_-20px_rgb(0_0_0/0.35)] sm:p-5">
      <div className="mb-4 flex items-center gap-2 border-b border-border pb-3 text-xs">
        <Sparkles size={14} className="text-accent-text" aria-hidden /> <span className="font-medium">Assistant</span>
        <span className="ml-auto inline-flex items-center gap-2 rounded-full bg-surface-2 px-2.5 py-1 text-muted">
          <span className="tt-wave flex h-3 items-center gap-[2px]" aria-hidden>
            {[0, 1, 2, 3].map((k) => <span key={k} className="h-3 w-[2px] rounded bg-accent-text" style={{ animationDelay: `${k * 120}ms` }} />)}
          </span>
          Talk mode
        </span>
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

const PERIODS = ["9:00", "10:00", "11:00", "12:00", "1:00"];
const WEEK = ["Mon", "Tue", "Wed", "Thu", "Fri"];
const CELLS: (string | null)[][] = [
  ["DBMS", "OS", "Maths", "DBMS", "CN"],
  ["OS", "Lab", "CN", "Maths", "OS"],
  ["Lunch", "Lab", "Lunch", "Lunch", "DBMS"],
  [null, "Lunch", "OS", "Lab", "Lunch"],
  ["Maths", null, null, "Lab", null],
];
const HUES: Record<string, number> = { DBMS: 228, OS: 160, CN: 32, Maths: 280, Lab: 200 };
const FROM = { r: 3, c: 0 };
const TO = { r: 4, c: 2 };
const SAFE = ["4-1", "4-2"];
const OKAY = ["4-4"];
const ROW_H = 46;
const HEAD_H = 24;
const at = (r: number, c: number): CSSProperties => ({
  top: HEAD_H + r * ROW_H,
  left: `calc(44px + ${c} * ((100% - 44px) / 5))`,
  width: "calc((100% - 44px) / 5 - 6px)",
  height: ROW_H - 6,
});

/** The product itself in the hero: a class is dragged to a safe (green) slot, checked, then undone. Loops. */
export function HeroApp() {
  const [phase, setPhase] = useState(0); // 0 idle · 1 pick · 2 moved · 3 toast · 4 undo
  useEffect(() => {
    if (reduced()) { setPhase(3); return; }
    const order = [[1, 1400], [2, 1300], [3, 1100], [4, 2600], [0, 1100]] as const;
    let i = 0;
    let timer: ReturnType<typeof setTimeout>;
    const next = () => {
      const [p, wait] = order[i % order.length];
      timer = setTimeout(() => { setPhase(p); i += 1; next(); }, wait);
    };
    next();
    return () => clearTimeout(timer);
  }, []);
  const moved = phase === 2 || phase === 3;
  const pos = moved ? TO : FROM;
  const picking = phase === 1 || phase === 2;

  return (
    <div className="overflow-hidden rounded-2xl border border-border-strong/70 bg-surface text-left shadow-[0_30px_80px_-20px_rgb(0_0_0/0.35)]">
      <div className="flex items-center gap-2 border-b border-border bg-surface-2/70 px-4 py-2.5">
        <span className="h-2.5 w-2.5 rounded-full bg-border-strong" /><span className="h-2.5 w-2.5 rounded-full bg-border-strong" /><span className="h-2.5 w-2.5 rounded-full bg-border-strong" />
        <span className="mx-auto rounded-md bg-surface px-3 py-0.5 font-mono text-[11px] text-muted">timetabl.ai/timetable</span>
        <span className="w-10" />
      </div>
      <div className="flex">
        <div className="hidden w-12 shrink-0 flex-col items-center gap-3 border-r border-border py-4 text-muted sm:flex">
          <span className="grid h-7 w-7 place-items-center rounded-md bg-accent text-[11px] font-bold text-white dark:text-bg">T</span>
          {[House, CalendarDays, Users, Bell].map((I, k) => (
            <span key={k} className={`grid h-7 w-7 place-items-center rounded-md ${k === 1 ? "bg-accent-soft text-accent-text" : ""}`}><I size={15} aria-hidden /></span>
          ))}
        </div>
        <div className="min-w-0 flex-1 p-3 sm:p-4">
          <div className="mb-3 flex flex-wrap items-center gap-2 text-xs">
            <span className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 font-semibold">CSE-3A <ChevronDown size={12} aria-hidden /></span>
            <span className="hidden rounded-md bg-surface-2 p-0.5 sm:inline-flex">
              {["Section", "Teacher", "Room"].map((v, k) => (
                <span key={v} className={`rounded px-2 py-0.5 ${k === 0 ? "bg-surface font-medium shadow-sm" : "text-muted"}`}>{v}</span>
              ))}
            </span>
            <span className="ml-auto inline-flex items-center gap-1 rounded-full bg-ok-soft px-2 py-0.5 font-medium text-ok">
              <ShieldCheck size={12} aria-hidden /> Published · 0 clashes
            </span>
          </div>
          <div className="relative text-[11px] sm:text-xs" style={{ height: HEAD_H + PERIODS.length * ROW_H }}>
            {WEEK.map((d, c) => (
              <div key={d} className="absolute text-center font-medium text-muted" style={{ ...at(0, c), top: 0, height: HEAD_H }}>{d}</div>
            ))}
            {PERIODS.map((p, r) => (
              <div key={p} className="absolute left-0 w-10 pt-3 text-right font-mono text-[10px] text-muted" style={{ top: HEAD_H + r * ROW_H }}>{p}</div>
            ))}
            {CELLS.flatMap((row, r) => row.map((cell, c) => {
              const key = `${r}-${c}`;
              const tone = picking && SAFE.includes(key) ? "border-ok/60 bg-ok-soft" : picking && OKAY.includes(key) ? "border-warn/60 bg-warn-soft" : "";
              if (r === FROM.r && c === FROM.c) return <div key={key} className={`absolute rounded-md border border-dashed ${moved ? "border-border-strong" : "border-transparent"}`} style={at(r, c)} />;
              if (!cell) return <div key={key} className={`absolute rounded-md border border-dashed transition-colors duration-300 ${tone || "border-transparent"}`} style={at(r, c)} />;
              return (
                <div key={key} style={{ ...at(r, c), ["--h" as string]: HUES[cell] } as CSSProperties}
                  className={`absolute flex items-center justify-center rounded-md font-medium ${cell === "Lunch" ? "border border-dashed border-border-strong text-muted" : "subj border"}`}>
                  {cell}
                </div>
              );
            }))}
            <div style={{ ...at(pos.r, pos.c), ["--h" as string]: HUES.CN } as CSSProperties}
              className={`subj absolute z-10 flex items-center justify-center rounded-md border font-medium transition-all duration-[900ms] ease-[cubic-bezier(0.3,0.7,0.2,1)] ${
                picking ? "scale-105 shadow-xl ring-2 ring-accent/50" : ""}`}>
              CN
              <MousePointer2 size={16} className={`absolute -bottom-3 -right-2 fill-text text-surface transition-opacity duration-300 ${picking ? "opacity-100" : "opacity-0"}`} aria-hidden />
            </div>
          </div>
          <div className="mt-3 flex h-8 items-center justify-end">
            {phase >= 3 && (
              <div className="tt-pop flex items-center gap-2 rounded-lg border border-border bg-surface px-3 py-1.5 text-xs shadow-lg">
                <CheckCircle2 size={14} className="text-ok" aria-hidden />
                {phase === 3 ? "Moved to Wed 1:00 · checked, 0 clashes" : "Undone · back on Mon 12:00"}
                {phase === 3 && <span className="inline-flex items-center gap-1 font-medium text-accent-text"><Undo2 size={12} aria-hidden /> Undo</span>}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
