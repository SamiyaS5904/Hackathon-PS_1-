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
const HUES: Record<string, number> = { DBMS: 228, OS: 160, CN: 32, Maths: 280, Lab: 200 };
const LUNCH = new Set(["2-0", "2-2", "2-3", "3-1", "3-4"]);
const BUSY = new Set(["4-4"]); // the teacher has another class then: shows that every move is checked
type Klass = { id: number; s: string; r: number; c: number; off?: boolean };
const START: Klass[] = [
  ["DBMS", 0, 0], ["OS", 0, 1], ["Maths", 0, 2], ["DBMS", 0, 3], ["CN", 0, 4],
  ["OS", 1, 0], ["Lab", 1, 1], ["CN", 1, 2], ["Maths", 1, 3], ["OS", 1, 4],
  ["Lab", 2, 1], ["DBMS", 2, 4],
  ["CN", 3, 0], ["OS", 3, 2], ["Lab", 3, 3],
  ["Maths", 4, 0], ["Lab", 4, 3],
].map(([s, r, c], id) => ({ id, s: s as string, r: r as number, c: c as number }));
const ROW_H = 46;
const HEAD_H = 24;
const at = (r: number, c: number): CSSProperties => ({
  top: HEAD_H + r * ROW_H,
  left: `calc(44px + ${c} * ((100% - 44px) / 5))`,
  width: "calc((100% - 44px) / 5 - 6px)",
  height: ROW_H - 6,
});
const when = (r: number, c: number) => `${WEEK[c]} ${PERIODS[r]}`;
type Toast = { ok: boolean; text: string; undo?: Klass[] };

/** The product in the hero, and it works: drag a class (or tap it, then tap a slot) to move it, cancel it for a day,
 *  undo. Green slots are safe; red ones say why not. Runs only in the browser, nothing is saved. */
export function HeroApp() {
  const [classes, setClasses] = useState<Klass[]>(START);
  const [sel, setSel] = useState<number | null>(null);
  const [toast, setToast] = useState<Toast | null>(null);
  const [touched, setTouched] = useState(false);
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 5000);
    return () => clearTimeout(t);
  }, [toast]);

  const picked = classes.find((k) => k.id === sel) ?? null;
  const occupant = (r: number, c: number) => classes.find((k) => k.r === r && k.c === c);
  const why = (r: number, c: number): string | null => {
    const key = `${r}-${c}`;
    if (LUNCH.has(key)) return "that's the section's lunch break";
    const other = occupant(r, c);
    if (other) return `CSE-3A already has ${other.s} then`;
    if (BUSY.has(key)) return "the teacher has another class then";
    return null;
  };
  const choose = (id: number) => { setTouched(true); setSel((s) => (s === id ? null : id)); };
  const moveTo = (r: number, c: number) => {
    if (!picked) return;
    const reason = why(r, c);
    if (reason) { setToast({ ok: false, text: `Can't move to ${when(r, c)}: ${reason}.` }); return; }
    setToast({ ok: true, text: `${picked.s} moved to ${when(r, c)} · checked, 0 clashes`, undo: classes });
    setClasses(classes.map((k) => (k.id === picked.id ? { ...k, r, c } : k)));
    setSel(null);
  };
  const cancel = () => {
    if (!picked) return;
    const off = !picked.off;
    setToast({ ok: true, text: off ? `${picked.s} on ${when(picked.r, picked.c)} cancelled for one day · students notified` : `${picked.s} restored`, undo: classes });
    setClasses(classes.map((k) => (k.id === picked.id ? { ...k, off } : k)));
    setSel(null);
  };
  const undo = () => { if (toast?.undo) { setClasses(toast.undo); setToast({ ok: true, text: "Undone" }); } };
  const reset = () => { setClasses(START); setSel(null); setToast(null); };

  return (
    <div className="overflow-hidden rounded-2xl border border-border-strong/70 bg-surface text-left shadow-[0_30px_80px_-20px_rgb(0_0_0/0.35)]">
      <div className="flex items-center gap-2 border-b border-border bg-surface-2/70 px-4 py-2.5">
        <span className="h-2.5 w-2.5 rounded-full bg-border-strong" /><span className="h-2.5 w-2.5 rounded-full bg-border-strong" /><span className="h-2.5 w-2.5 rounded-full bg-border-strong" />
        <span className="mx-auto rounded-md bg-surface px-3 py-0.5 font-mono text-[11px] text-muted">timetabl.ai/timetable</span>
        <button onClick={reset} className="rounded px-1.5 text-[11px] text-muted hover:text-text">Reset</button>
      </div>
      <div className="flex">
        <div className="hidden w-12 shrink-0 flex-col items-center gap-3 border-r border-border py-4 text-muted sm:flex">
          <span className="grid h-7 w-7 place-items-center rounded-md bg-accent text-[11px] font-bold text-white dark:text-bg">T</span>
          {[House, CalendarDays, Users, Bell].map((I, k) => (
            <span key={k} className={`grid h-7 w-7 place-items-center rounded-md ${k === 1 ? "bg-accent-soft text-accent-text" : ""}`}><I size={15} aria-hidden /></span>
          ))}
        </div>
        <div className="min-w-0 flex-1 p-3 sm:p-4">
          <div className="mb-3 flex min-h-[28px] flex-wrap items-center gap-2 text-xs">
            <span className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 font-semibold">CSE-3A <ChevronDown size={12} aria-hidden /></span>
            {picked ? (
              <>
                <span className="text-muted"><b className="text-text">{picked.s}</b> · {picked.off ? "cancelled for the day" : "drop it on a green slot"}</span>
                <button onClick={cancel} className="rounded-md border border-border px-2 py-1 font-medium hover:bg-surface-2">
                  {picked.off ? "Restore" : "Cancel for one day"}
                </button>
              </>
            ) : (
              <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-medium ${touched ? "text-muted" : "bg-accent-soft text-accent-text"}`}>
                <MousePointer2 size={12} aria-hidden /> Try it: drag a class, or tap one
              </span>
            )}
            <span className="ml-auto inline-flex items-center gap-1 rounded-full bg-ok-soft px-2 py-0.5 font-medium text-ok">
              <ShieldCheck size={12} aria-hidden /> 0 clashes
            </span>
          </div>
          <div className="relative select-none text-[11px] sm:text-xs" style={{ height: HEAD_H + PERIODS.length * ROW_H }}>
            {WEEK.map((d, c) => (
              <div key={d} className="absolute text-center font-medium text-muted" style={{ ...at(0, c), top: 0, height: HEAD_H }}>{d}</div>
            ))}
            {PERIODS.map((p, r) => (
              <div key={p} className="absolute left-0 w-10 pt-3 text-right font-mono text-[10px] text-muted" style={{ top: HEAD_H + r * ROW_H }}>{p}</div>
            ))}
            {PERIODS.flatMap((_, r) => WEEK.map((__, c) => {
              const key = `${r}-${c}`;
              const bad = picked ? why(r, c) : null;
              const lunch = LUNCH.has(key);
              if (!lunch && occupant(r, c)) return null;
              const tone = !picked ? (lunch ? "border-border-strong text-muted" : "border-transparent")
                : bad ? "border-danger/50 bg-danger-soft/60 text-danger" : "border-ok/60 bg-ok-soft text-ok";
              return (
                <button key={key} type="button" aria-label={lunch ? `Lunch, ${when(r, c)}` : `Empty slot, ${when(r, c)}`}
                  onClick={() => moveTo(r, c)} onDragOver={(e) => { if (picked && !bad) e.preventDefault(); }}
                  onDrop={(e) => { e.preventDefault(); moveTo(r, c); }}
                  className={`absolute flex items-center justify-center rounded-md border border-dashed text-[10px] transition-colors duration-200 ${tone} ${picked ? "cursor-pointer" : "cursor-default"}`}
                  style={at(r, c)}>
                  {lunch ? "Lunch" : picked && !bad ? "Move here" : ""}
                </button>
              );
            }))}
            {classes.map((k) => (
              <button key={k.id} type="button" draggable onDragStart={() => { setTouched(true); setSel(k.id); }}
                onClick={() => (picked && picked.id !== k.id ? moveTo(k.r, k.c) : choose(k.id))}
                style={{ ...at(k.r, k.c), ["--h" as string]: HUES[k.s] } as CSSProperties}
                aria-label={`${k.s}, ${when(k.r, k.c)}${k.off ? ", cancelled" : ""}`}
                className={`subj absolute z-10 flex cursor-grab items-center justify-center rounded-md border font-medium transition-all duration-500 ease-[cubic-bezier(0.3,0.7,0.2,1)] active:cursor-grabbing ${
                  sel === k.id ? "scale-105 shadow-xl ring-2 ring-accent" : "hover:-translate-y-px hover:shadow-md"} ${
                  k.off ? "line-through opacity-45" : ""} ${!touched && k.id === 12 ? "ring-2 ring-accent/40 ring-offset-1 ring-offset-surface" : ""}`}>
                {k.s}
              </button>
            ))}
          </div>
          <div className="mt-3 flex min-h-8 items-center justify-end" aria-live="polite">
            {toast && (
              <div key={toast.text} className={`tt-pop flex items-center gap-2 rounded-lg border px-3 py-1.5 text-xs shadow-lg ${
                toast.ok ? "border-border bg-surface" : "border-danger/40 bg-danger-soft text-danger"}`}>
                {toast.ok ? <CheckCircle2 size={14} className="shrink-0 text-ok" aria-hidden /> : <ShieldCheck size={14} className="shrink-0" aria-hidden />}
                {toast.text}
                {toast.undo && (
                  <button onClick={undo} className="inline-flex items-center gap-1 font-medium text-accent-text hover:underline">
                    <Undo2 size={12} aria-hidden /> Undo
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
