import { ArrowRight, CheckCircle2, FileSpreadsheet, Mic, ShieldCheck, Undo2 } from "lucide-react";
import { Instrument_Serif } from "next/font/google";
import Link from "next/link";
import type { ReactNode } from "react";
import { ThemeToggle } from "@/lib/theme";
import { ChatDemo, HeroApp, Reveal } from "./motion";

const serif = Instrument_Serif({ weight: "400", style: "italic", subsets: ["latin"], variable: "--font-serif", display: "swap" });

const btn = "inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition";
const primary = `${btn} bg-accent text-white shadow-sm hover:-translate-y-px hover:shadow-md dark:text-bg`;
const secondary = `${btn} border border-border-strong bg-surface hover:bg-surface-2`;

/** One accented phrase per heading, in an editorial serif. */
const Em = ({ children }: { children: ReactNode }) => <span className="tt-serif text-[1.08em] text-accent-text">{children}</span>;

/** The public home page: one idea per screen, little text, the product itself as the picture. */
export function Landing() {
  return (
    <div className={`${serif.variable} min-h-screen overflow-x-hidden bg-bg text-text`}>
      <Nav />
      <Hero />
      <Bento />
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
      <div className="tt-grid-bg pointer-events-none absolute inset-0" aria-hidden />
      <div className="pointer-events-none absolute inset-x-0 top-0 h-[38rem] bg-[radial-gradient(60%_50%_at_50%_0%,rgb(var(--accent)/0.10),transparent)]" aria-hidden />
      <div className="relative mx-auto max-w-6xl px-4 pb-20 pt-16 text-center md:pt-24">
        <a href="#assistant" className="tt-fade-up group mx-auto inline-flex items-center gap-2 rounded-full border border-border bg-surface/80 py-1 pl-1 pr-3 text-xs text-muted backdrop-blur transition hover:border-border-strong">
          <span className="rounded-full bg-accent-soft px-2 py-0.5 font-medium text-accent-text">New</span>
          Cover plans for teacher leave
          <ArrowRight size={12} className="transition group-hover:translate-x-0.5" aria-hidden />
        </a>
        <h1 className="tt-fade-up mx-auto mt-7 max-w-4xl text-[2.9rem] font-semibold leading-[1.02] tracking-[-0.035em] md:text-[5.2rem]" style={{ animationDelay: "80ms" }}>
          Timetables that <span className="whitespace-nowrap"><Em>never clash.</Em></span>
        </h1>
        <p className="tt-fade-up mx-auto mt-6 max-w-lg text-lg text-muted md:text-xl" style={{ animationDelay: "160ms" }}>
          Made in minutes. Kept right all semester.
        </p>
        <div className="tt-fade-up mt-9 flex flex-wrap justify-center gap-3" style={{ animationDelay: "240ms" }}>
          <Link href="/demo" className={primary}>Try the demo college <ArrowRight size={16} aria-hidden /></Link>
          <Link href="/signup" className={secondary}>Create your college</Link>
        </div>
        <p className="tt-fade-up mt-4 text-xs text-muted" style={{ animationDelay: "300ms" }}>
          No sign-up. One click to log in as an admin, teacher or student.
        </p>
        <div className="tt-fade-up mx-auto mt-16 max-w-4xl" style={{ animationDelay: "380ms" }}>
          <HeroApp />
        </div>
        <p className="tt-fade-up mt-8 text-xs text-muted" style={{ animationDelay: "500ms" }}>
          Tested on two colleges · Demo Institute of Technology · GNDEC (demo) · 570 classes, 0 clashes
        </p>
      </div>
    </section>
  );
}

function Heading({ eyebrow, title, sub }: { eyebrow: string; title: ReactNode; sub?: string }) {
  return (
    <Reveal className="mx-auto max-w-2xl text-center">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-accent-text">{eyebrow}</p>
      <h2 className="mt-3 text-3xl font-semibold tracking-[-0.03em] md:text-5xl">{title}</h2>
      {sub && <p className="mt-4 text-muted md:text-lg">{sub}</p>}
    </Reveal>
  );
}

function Tile({ title, children, className = "", delay = 0 }: { title: ReactNode; children: ReactNode; className?: string; delay?: number }) {
  return (
    <Reveal delay={delay} className={className}>
      <div className="flex h-full flex-col overflow-hidden rounded-2xl border border-border bg-surface p-6 transition duration-300 hover:border-border-strong hover:shadow-lg">
        <h3 className="text-xl font-semibold tracking-tight">{title}</h3>
        <div className="mt-5 flex-1">{children}</div>
      </div>
    </Reveal>
  );
}

/** A line that appears when its tile scrolls into view. */
const Row = ({ children, i, className = "" }: { children: ReactNode; i: number; className?: string }) => (
  <li className={`tt-stagger ${className}`} style={{ animationDelay: `${220 + i * 150}ms` }}>{children}</li>
);

const Tick = ({ children, i }: { children: ReactNode; i: number }) => (
  <Row i={i} className="flex items-center gap-2"><CheckCircle2 size={15} className="shrink-0 text-ok" aria-hidden /> {children}</Row>
);

const COVER = [["Mon 9:00", "DBMS · 3A", "Dr. Mehta"], ["Mon 11:00", "DBMS · 3B", "Dr. Arora"], ["Tue 10:00", "Lab · 3A", "Ms. Bedi"], ["Tue 2:00", "DBMS · 2A", "Cancelled"]];
const VIEWS = [
  ["Student · CSE-3A", "DBMS", "G-12 · until 10:30", "OS · Software Lab-2 · 10:30"],
  ["Teacher · Dr. Kaur", "Data Structures", "G-14 · until 11:30", "Free, then CSE-2B at 12:30"],
];
const RULES = [["No first-year class after 4 pm", "Must"], ["At most 4 lectures a day per teacher", "Try"], ["Lunch split across two hours", "Try"]];

function Bento() {
  return (
    <section id="features" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-24">
      <Heading eyebrow="Product" title={<>The hardest part of a semester, <Em>solved.</Em></>} />
      <div className="mt-14 grid gap-4 md:grid-cols-3">
        <Tile className="md:col-span-2" title={<>One click. <Em>The whole college.</Em></>}>
          <ul className="space-y-2.5 text-sm text-muted">
            <Tick i={0}>Reads 28 sections, 96 teachers and 51 rooms</Tick>
            <Tick i={1}>Places labs as blocks and electives side by side</Tick>
            <Tick i={2}>Gives every section a lunch gap, every day</Tick>
          </ul>
          <div className="mt-6 h-1.5 overflow-hidden rounded-full bg-surface-2"><div className="tt-bar h-full rounded-full bg-accent" /></div>
          <p className="tt-stagger mt-3 flex flex-wrap gap-x-4 gap-y-1 text-sm" style={{ animationDelay: "2600ms" }}>
            <span className="font-semibold">570 classes</span><span className="text-ok">0 clashes</span><span className="text-muted">quality 79/100</span>
          </p>
        </Tile>
        <Tile delay={100} title={<>Checked <Em>twice.</Em></>}>
          <ul className="space-y-2.5 text-sm">
            <Tick i={0}>No teacher in two places</Tick>
            <Tick i={1}>No room booked twice</Tick>
            <Tick i={2}>Every room big enough</Tick>
            <Tick i={3}>Labs kept in one block</Tick>
          </ul>
          <p className="mt-5 text-xs text-muted">A separate validator checks every timetable and every change.</p>
        </Tile>

        <Tile title={<>Teacher away? <Em>Covered.</Em></>}>
          <ul className="space-y-2 text-xs">
            {COVER.map(([w, c, s], i) => (
              <Row key={w} i={i} className="flex items-center gap-2 rounded-lg border border-border px-2.5 py-2">
                <span className="w-16 font-mono text-[10px] text-muted">{w}</span>
                <span className="flex-1">{c}</span>
                <span className={s === "Cancelled" ? "text-muted line-through" : "font-medium text-accent-text"}>{s}</span>
              </Row>
            ))}
          </ul>
        </Tile>
        <Tile className="md:col-span-2" delay={100} title={<>Everyone sees <Em>their own</Em> day.</>}>
          <ul className="grid gap-3 sm:grid-cols-2">
            {VIEWS.map(([who, now, where, next], i) => (
              <Row key={who} i={i} className="rounded-xl border border-border bg-surface-2/50 p-4">
                <p className="text-[11px] font-medium uppercase tracking-wide text-muted">{who}</p>
                <p className="mt-3 flex items-center gap-2 text-xs text-ok"><span className="h-1.5 w-1.5 rounded-full bg-ok" /> Now</p>
                <p className="mt-1 text-lg font-semibold">{now}</p>
                <p className="text-sm text-muted">{where}</p>
                <p className="mt-3 border-t border-border pt-3 text-xs text-muted">Next: {next}</p>
              </Row>
            ))}
          </ul>
        </Tile>

        <Tile title={<>Undo <Em>anything.</Em></>}>
          <ul className="space-y-2 text-xs">
            {["Moved CN to Wed 1:00", "Cover plan for Dr. Kaur", "Cancelled Lab on 28 Oct"].map((c, i) => (
              <Row key={c} i={i} className="flex items-center gap-2">
                <span className="flex-1 truncate">{c}</span>
                <span className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-muted"><Undo2 size={11} aria-hidden /> Undo</span>
              </Row>
            ))}
          </ul>
        </Tile>
        <Tile delay={80} title={<>Excel in. <Em>PDF out.</Em></>}>
          <ul className="flex flex-wrap items-center gap-3 text-xs">
            <Row i={0} className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2">
              <FileSpreadsheet size={16} className="text-ok" aria-hidden /> cse.xlsx
            </Row>
            <Row i={1} className="text-muted"><ArrowRight size={14} aria-hidden /></Row>
            <Row i={2} className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2">
              <ShieldCheck size={16} className="text-accent-text" aria-hidden /> Notice-board PDF
            </Row>
          </ul>
          <p className="mt-5 text-xs text-muted">One sheet per department, with row-level errors.</p>
        </Tile>
        <Tile delay={160} title={<>Your rules, <Em>your way.</Em></>}>
          <ul className="space-y-2 text-xs">
            {RULES.map(([r, k], i) => (
              <Row key={r} i={i} className="flex items-center gap-2">
                <span className="flex-1">{r}</span>
                <span className={`rounded-full px-2 py-0.5 font-medium ${k === "Must" ? "bg-accent-soft text-accent-text" : "bg-surface-2 text-muted"}`}>{k}</span>
              </Row>
            ))}
          </ul>
        </Tile>
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
    <section id="assistant" className="relative scroll-mt-20 border-y border-border/70 bg-surface/40">
      <div className="mx-auto grid max-w-6xl items-center gap-12 px-4 py-24 md:grid-cols-2">
        <Reveal>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-accent-text">AI assistant</p>
          <h2 className="mt-3 text-3xl font-semibold tracking-[-0.03em] md:text-5xl">Say it. It plans it. <Em>You approve.</Em></h2>
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
      <Heading eyebrow="And everything around it" title={<>Built for how colleges <Em>actually</Em> run.</>} />
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
      <Heading eyebrow="How it works" title={<>From sign-up to published <Em>in an afternoon.</Em></>} />
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
      <Heading eyebrow="Pricing" title={<>Simple, <Em>per student.</Em></>} sub="Indicative prices." />
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
      <Reveal className="relative mx-auto max-w-5xl overflow-hidden rounded-3xl border border-border bg-surface px-6 py-16 text-center">
        <div className="tt-grid-bg pointer-events-none absolute inset-0 opacity-70" aria-hidden />
        <div className="relative">
          <h2 className="text-3xl font-semibold tracking-[-0.03em] md:text-5xl">See it on a <Em>real</Em> college.</h2>
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
