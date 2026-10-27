import {
  ArrowRight, CheckCircle2, Mic, MousePointerClick, ShieldCheck, Undo2, Wand2,
} from "lucide-react";
import Link from "next/link";
import type { CSSProperties, ReactNode } from "react";
import { ThemeToggle } from "@/lib/theme";
import { ChatDemo, CountUp, Reveal } from "./motion";

const btn = "inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition";
const primary = `${btn} bg-accent text-white shadow-sm hover:-translate-y-px hover:shadow-md dark:text-bg`;
const secondary = `${btn} border border-border-strong bg-surface hover:bg-surface-2`;

/** The public home page: one idea per screen, little text, calm motion. */
export function Landing() {
  return (
    <div className="min-h-screen overflow-x-hidden bg-bg text-text">
      <Nav />
      <Hero />
      <Stats />
      <Pillars />
      <AssistantShowcase />
      <Everything />
      <Steps />
      <Pricing />
      <FinalCta />
      <Footer />
    </div>
  );
}

function Logo() {
  return (
    <Link href="/welcome" className="flex items-center gap-2">
      <span className="grid h-8 w-8 place-items-center rounded-md bg-accent text-sm font-bold text-white dark:text-bg">T</span>
      <span className="text-lg font-semibold tracking-tight">Timetabl.ai</span>
    </Link>
  );
}

function Nav() {
  return (
    <header className="sticky top-0 z-30 border-b border-border/60 bg-bg/75 backdrop-blur-md">
      <div className="mx-auto flex max-w-6xl items-center gap-4 px-4 py-3">
        <Logo />
        <nav className="ml-6 hidden gap-6 text-sm text-muted md:flex">
          <a href="#features" className="hover:text-text">Product</a>
          <a href="#assistant" className="hover:text-text">Assistant</a>
          <a href="#pricing" className="hover:text-text">Pricing</a>
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <ThemeToggle />
          <Link href="/login" className={`${btn} hidden hover:bg-surface-2 sm:inline-flex`}>Log in</Link>
          <Link href="/demo" className={primary}>Try the demo</Link>
        </div>
      </div>
    </header>
  );
}

function Hero() {
  return (
    <section className="relative">
      <div className="tt-grid-bg pointer-events-none absolute inset-0 -z-0" aria-hidden />
      <div className="tt-glow pointer-events-none absolute left-1/2 top-[-12rem] -z-0 h-[32rem] w-[56rem] -translate-x-1/2 rounded-full bg-accent/20 blur-3xl" aria-hidden />
      <div className="relative mx-auto max-w-6xl px-4 pb-16 pt-16 text-center md:pt-24">
        <p className="tt-fade-up mx-auto inline-flex items-center gap-2 rounded-full border border-border bg-surface/80 px-3 py-1 text-xs text-muted backdrop-blur">
          <span className="relative flex h-2 w-2">
            <span className="tt-ping absolute inline-flex h-full w-full rounded-full bg-ok" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-ok" />
          </span>
          Now with AI cover plans for teacher leave
        </p>
        <h1 className="tt-fade-up mx-auto mt-6 max-w-4xl text-5xl font-semibold leading-[1.05] tracking-tight md:text-7xl" style={{ animationDelay: "80ms" }}>
          Timetables that{" "}
          <span className="bg-gradient-to-r from-accent to-ok bg-clip-text text-transparent">never clash.</span>
        </h1>
        <p className="tt-fade-up mx-auto mt-5 max-w-xl text-lg text-muted md:text-xl" style={{ animationDelay: "160ms" }}>
          Made in minutes. Kept right all semester.
        </p>
        <div className="tt-fade-up mt-8 flex flex-wrap justify-center gap-3" style={{ animationDelay: "240ms" }}>
          <Link href="/demo" className={primary}>Try the demo college <ArrowRight size={16} aria-hidden /></Link>
          <Link href="/signup" className={secondary}>Create your college</Link>
        </div>
        <p className="tt-fade-up mt-4 text-xs text-muted" style={{ animationDelay: "300ms" }}>
          No sign-up. One click to log in as an admin, teacher or student.
        </p>
        <div className="tt-fade-up mx-auto mt-14 max-w-3xl" style={{ animationDelay: "380ms" }}>
          <HeroGrid />
        </div>
      </div>
    </section>
  );
}

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"];
const GRID: (string | null)[][] = [
  ["DBMS", "OS", "Maths", "DBMS", "CN"],
  ["OS", "Lab", "CN", "Maths", "OS"],
  ["Lunch", "Lab", "Lunch", "Lunch", "DBMS"],
  ["CN", "Lunch", "OS", "Lab", "Lunch"],
  ["Maths", "DBMS", null, "Lab", "Maths"],
];
const HUE: Record<string, number> = { DBMS: 228, OS: 160, CN: 32, Maths: 280, Lab: 200 };

function HeroGrid() {
  return (
    <div className="tt-float relative rounded-2xl border border-border bg-surface/90 p-4 text-left shadow-2xl backdrop-blur md:p-5">
      <div className="mb-3 flex items-center gap-2 text-xs">
        <span className="font-semibold">CSE · 3rd year · Section A</span>
        <span className="tt-pop ml-auto inline-flex items-center gap-1.5 rounded-full bg-ok-soft px-2.5 py-0.5 font-medium text-ok" style={{ animationDelay: "1.9s" }}>
          <ShieldCheck size={13} aria-hidden /> 0 clashes
        </span>
      </div>
      <div className="relative grid grid-cols-5 gap-1.5 text-center text-[11px] md:text-xs">
        {DAYS.map((d) => <div key={d} className="pb-1 font-medium text-muted">{d}</div>)}
        {GRID.flatMap((row, r) => row.map((cell, c) => (
          <div key={`${r}-${c}`} style={{ animationDelay: `${500 + (r * 5 + c) * 45}ms`, ...(cell && cell !== "Lunch" ? { "--h": HUE[cell] } : {}) } as CSSProperties}
            className={`tt-pop flex h-9 items-center justify-center rounded-md font-medium md:h-11 ${
              cell === "Lunch" ? "border border-dashed border-border-strong text-muted" : cell ? "subj border" : ""}`}>
            {cell ?? ""}
          </div>
        )))}
        <div className="tt-scan pointer-events-none absolute inset-x-0 h-8 -translate-y-1/2 bg-gradient-to-b from-transparent via-ok/25 to-transparent" aria-hidden />
      </div>
    </div>
  );
}

function Stats() {
  const items: [ReactNode, string][] = [
    [<CountUp key="c" to={570} />, "classes placed for a 1,662-student college"],
    ["0", "clashes, checked on every change"],
    ["1 click", "to cover a teacher's leave"],
    ["~1 s", "answers to everyday questions"],
  ];
  return (
    <section className="border-y border-border/70 bg-surface/50">
      <div className="mx-auto grid max-w-6xl grid-cols-2 gap-6 px-4 py-10 md:grid-cols-4">
        {items.map(([v, l], i) => (
          <Reveal key={l} delay={i * 90} className="text-center">
            <p className="text-3xl font-semibold tracking-tight md:text-4xl">{v}</p>
            <p className="mt-1 text-xs text-muted md:text-sm">{l}</p>
          </Reveal>
        ))}
      </div>
    </section>
  );
}

function Heading({ eyebrow, title, sub }: { eyebrow: string; title: ReactNode; sub?: string }) {
  return (
    <Reveal className="mx-auto max-w-2xl text-center">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-accent-text">{eyebrow}</p>
      <h2 className="mt-3 text-3xl font-semibold tracking-tight md:text-5xl">{title}</h2>
      {sub && <p className="mt-4 text-muted md:text-lg">{sub}</p>}
    </Reveal>
  );
}

function Pillars() {
  const items: [typeof Wand2, string, string][] = [
    [Wand2, "One click. Whole college.", "Every section, teacher and room, scheduled together."],
    [ShieldCheck, "Zero clashes. Proven.", "An independent check on every timetable and every change."],
    [MousePointerClick, "Change without chaos.", "Drag a class, cover a leave, undo anything."],
  ];
  return (
    <section id="features" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-24">
      <Heading eyebrow="Product" title="The hardest part of a semester, solved." />
      <div className="mt-14 grid gap-5 md:grid-cols-3">
        {items.map(([Icon, t, d], i) => (
          <Reveal key={t} delay={i * 110}>
            <div className="group h-full rounded-2xl border border-border bg-surface p-7 transition duration-300 hover:-translate-y-1 hover:border-accent/40 hover:shadow-xl">
              <span className="grid h-11 w-11 place-items-center rounded-xl bg-accent-soft text-accent-text transition group-hover:scale-110">
                <Icon size={20} aria-hidden />
              </span>
              <h3 className="mt-5 text-xl font-semibold tracking-tight">{t}</h3>
              <p className="mt-2 text-muted">{d}</p>
            </div>
          </Reveal>
        ))}
      </div>
    </section>
  );
}

function AssistantShowcase() {
  const points: [typeof Mic, string][] = [
    [CheckCircle2, "Plans cover when a teacher is away"],
    [Mic, "Typed or spoken, in English or Hinglish"],
    [Undo2, "Changes nothing until you click Apply"],
  ];
  return (
    <section id="assistant" className="relative scroll-mt-20 overflow-hidden border-y border-border/70 bg-surface/40">
      <div className="tt-glow pointer-events-none absolute -right-40 top-10 h-96 w-96 rounded-full bg-accent/15 blur-3xl" aria-hidden />
      <div className="relative mx-auto grid max-w-6xl items-center gap-12 px-4 py-24 md:grid-cols-2">
        <Reveal>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-accent-text">AI assistant</p>
          <h2 className="mt-3 text-3xl font-semibold tracking-tight md:text-5xl">Say it. It plans it. You approve.</h2>
          <ul className="mt-8 space-y-4">
            {points.map(([Icon, t]) => (
              <li key={t} className="flex items-center gap-3 text-lg">
                <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-accent-soft text-accent-text"><Icon size={16} aria-hidden /></span>
                {t}
              </li>
            ))}
          </ul>
        </Reveal>
        <Reveal delay={150}>
          <ChatDemo />
        </Reveal>
      </div>
    </section>
  );
}

const EVERYTHING = [
  "Setup wizard", "Excel import", "Two shifts", "Lab batches", "Electives", "Combined classes", "Shared rooms",
  "Drag and drop", "One-day changes", "Makeup finder", "Teacher leave", "Attendance", "Doubt slots", "Room bookings",
  "Notices", "Notifications", "PDF and Excel", "Voice", "Undo", "Light and dark",
];

function Everything() {
  return (
    <section className="py-20">
      <Heading eyebrow="And everything around it" title="Built for how colleges actually run." />
      <div className="tt-mask-x mt-12 overflow-hidden">
        <div className="tt-marquee flex w-max gap-3">
          {[...EVERYTHING, ...EVERYTHING].map((t, i) => (
            <span key={i} className="whitespace-nowrap rounded-full border border-border bg-surface px-4 py-2 text-sm text-muted">{t}</span>
          ))}
        </div>
      </div>
    </section>
  );
}

function Steps() {
  const steps = [
    ["Set up", "Shifts, rooms and departments in a guided wizard."],
    ["Generate", "One click. The whole college, clash-free."],
    ["Run the semester", "Leave, moves and makeups, with undo for everything."],
  ];
  return (
    <section className="mx-auto max-w-5xl px-4 py-20">
      <Heading eyebrow="How it works" title="From sign-up to published in an afternoon." />
      <div className="relative mt-14 grid gap-10 md:grid-cols-3">
        <div className="absolute left-[16%] right-[16%] top-5 hidden h-px bg-gradient-to-r from-transparent via-border-strong to-transparent md:block" aria-hidden />
        {steps.map(([t, d], i) => (
          <Reveal key={t} delay={i * 140} className="relative text-center">
            <span className="relative mx-auto grid h-10 w-10 place-items-center rounded-full bg-accent text-sm font-semibold text-white ring-8 ring-bg dark:text-bg">{i + 1}</span>
            <h3 className="mt-4 text-lg font-semibold">{t}</h3>
            <p className="mt-1 text-sm text-muted">{d}</p>
          </Reveal>
        ))}
      </div>
    </section>
  );
}

function Pricing() {
  const plans = [
    { name: "Starter", price: "Free", unit: "", note: "One department, to try it.", cta: "Create your college", href: "/signup",
      items: ["Up to 300 students", "Generate, views, drag and drop", "Assistant: 100 answers / month"] },
    { name: "College", price: "₹25", unit: "/ student / year", note: "Minimum ₹25,000 a year.", cta: "Try the demo", href: "/demo", featured: true,
      items: ["Unlimited departments and shifts", "Leave cover, bookings, attendance", "Assistant with voice"] },
    { name: "University", price: "Custom", unit: "", note: "Several campuses.", cta: "Talk to us", href: "/signup",
      items: ["Everything in College", "Help importing your timetable", "Priority support"] },
  ];
  return (
    <section id="pricing" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-20">
      <Heading eyebrow="Pricing" title="Simple, per student." sub="Indicative prices." />
      <div className="mt-14 grid gap-5 md:grid-cols-3">
        {plans.map((p, i) => (
          <Reveal key={p.name} delay={i * 110}>
            <div className={`flex h-full flex-col rounded-2xl border bg-surface p-7 transition duration-300 hover:-translate-y-1 hover:shadow-xl ${
              p.featured ? "border-accent shadow-lg ring-1 ring-accent/30" : "border-border"}`}>
              <div className="flex items-center gap-2">
                <h3 className="font-semibold">{p.name}</h3>
                {p.featured && <span className="rounded-full bg-accent-soft px-2 py-0.5 text-[11px] font-medium text-accent-text">Most popular</span>}
              </div>
              <p className="mt-4"><span className="text-4xl font-semibold tracking-tight">{p.price}</span> <span className="text-sm text-muted">{p.unit}</span></p>
              <p className="mt-1 text-sm text-muted">{p.note}</p>
              <ul className="mt-6 flex-1 space-y-2.5 text-sm">
                {p.items.map((it) => <li key={it} className="flex gap-2"><CheckCircle2 size={16} className="mt-0.5 shrink-0 text-ok" aria-hidden />{it}</li>)}
              </ul>
              <Link href={p.href} className={`${p.featured ? primary : secondary} mt-7`}>{p.cta}</Link>
            </div>
          </Reveal>
        ))}
      </div>
    </section>
  );
}

function FinalCta() {
  return (
    <section className="px-4 pb-24">
      <Reveal className="relative mx-auto max-w-5xl overflow-hidden rounded-3xl border border-accent/30 bg-accent-soft/40 px-6 py-16 text-center">
        <div className="tt-grid-bg pointer-events-none absolute inset-0 opacity-60" aria-hidden />
        <div className="relative">
          <h2 className="text-3xl font-semibold tracking-tight md:text-5xl">See it on a real college.</h2>
          <p className="mt-4 text-muted md:text-lg">For admins, coordinators, teachers and students.</p>
          <Link href="/demo" className={`${primary} mt-8 px-6 py-3 text-base`}>Open the demo <ArrowRight size={18} aria-hidden /></Link>
        </div>
      </Reveal>
    </section>
  );
}

function Footer() {
  return (
    <footer className="border-t border-border">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-4 px-4 py-8 text-sm text-muted">
        <Logo />
        <span className="hidden sm:inline">Clash-free timetables for any college.</span>
        <div className="ml-auto flex gap-5">
          <Link href="/demo" className="hover:text-text">Demo</Link>
          <Link href="/login" className="hover:text-text">Log in</Link>
          <Link href="/signup" className="hover:text-text">Create a college</Link>
        </div>
      </div>
    </footer>
  );
}
