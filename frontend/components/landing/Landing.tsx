import {
  ArrowRight, Bell, CalendarCheck2, CalendarClock, CheckCircle2, ClipboardCheck, DoorOpen, FileSpreadsheet, GraduationCap,
  Headphones, LayoutGrid, Layers, MousePointerClick, ShieldCheck, Sparkles, UserCheck, Users, Wand2, Zap,
} from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { ThemeToggle } from "@/lib/theme";

const btn = "inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition";
const primary = `${btn} bg-accent text-white shadow-sm hover:bg-accent/90 dark:text-bg`;
const secondary = `${btn} border border-border-strong bg-surface hover:bg-surface-2`;

/** The public home page: what Timetabl.ai does, for whom, and what it costs. */
export function Landing() {
  return (
    <div className="min-h-screen bg-bg text-text">
      <Nav />
      <Hero />
      <Problems />
      <Features />
      <Assistant />
      <HowItWorks />
      <Roles />
      <Pricing />
      <Footer />
    </div>
  );
}

function Nav() {
  return (
    <header className="sticky top-0 z-30 border-b border-border bg-bg/85 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center gap-4 px-4 py-3">
        <Link href="/welcome" className="flex items-center gap-2">
          <span className="grid h-8 w-8 place-items-center rounded-md bg-accent text-sm font-bold text-white dark:text-bg">T</span>
          <span className="text-lg font-semibold tracking-tight">Timetabl.ai</span>
        </Link>
        <nav className="ml-6 hidden gap-5 text-sm text-muted md:flex">
          <a href="#features" className="hover:text-text">Features</a>
          <a href="#assistant" className="hover:text-text">AI assistant</a>
          <a href="#how" className="hover:text-text">How it works</a>
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
    <section className="mx-auto grid max-w-6xl items-center gap-10 px-4 py-14 md:grid-cols-[1.05fr_1fr] md:pb-36 md:pt-20">
      <div>
        <p className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-1 text-xs text-muted">
          <ShieldCheck size={14} className="text-ok" aria-hidden /> 0 clashes, checked by an independent validator
        </p>
        <h1 className="mt-4 text-4xl font-semibold leading-tight tracking-tight md:text-5xl">
          Clash-free college timetables, made in minutes and kept right all semester.
        </h1>
        <p className="mt-4 max-w-xl text-lg text-muted">
          Your departments fill in their data, you click Generate, and every section, teacher and room gets a
          timetable with no clashes and fewer gaps. When a teacher is away or a class moves, an AI assistant plans
          the fix and you apply it with one click.
        </p>
        <div className="mt-7 flex flex-wrap gap-3">
          <Link href="/demo" className={primary}>Try the demo college <ArrowRight size={16} aria-hidden /></Link>
          <Link href="/signup" className={secondary}>Create your college</Link>
        </div>
        <p className="mt-4 text-xs text-muted">One-click logins for Admin, Coordinator, teacher and student. No sign-up needed.</p>
      </div>
      <HeroVisual />
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
const TONE: Record<string, string> = {
  DBMS: "bg-accent-soft text-accent-text", OS: "bg-ok-soft text-ok", CN: "bg-warn-soft text-warn",
  Maths: "bg-surface-2 text-text", Lab: "bg-accent/15 text-accent-text", Lunch: "border border-dashed border-border-strong text-muted",
};

function HeroVisual() {
  return (
    <div className="relative">
      <div className="rounded-2xl border border-border bg-surface p-4 shadow-xl">
        <div className="mb-3 flex items-center gap-2 text-xs">
          <span className="font-semibold">CSE-3A</span>
          <span className="rounded-full bg-ok-soft px-2 py-0.5 font-medium text-ok">Published · 0 clashes</span>
          <span className="ml-auto text-muted">Quality 86/100</span>
        </div>
        <div className="grid grid-cols-5 gap-1.5 text-center text-[11px]">
          {DAYS.map((d) => <div key={d} className="pb-1 font-medium text-muted">{d}</div>)}
          {GRID.flatMap((row, r) => row.map((cell, c) => (
            <div key={`${r}-${c}`} className={`flex h-9 items-center justify-center rounded-md font-medium ${cell ? TONE[cell] : ""}`}>
              {cell ?? ""}
            </div>
          )))}
        </div>
        <p className="mt-3 text-[11px] text-muted">Every section gets a lunch gap inside the mess timings, chosen per day.</p>
      </div>
      <div className="relative mx-auto -mt-6 w-72 rounded-xl border border-border bg-surface p-3 text-xs shadow-xl md:absolute md:-bottom-28 md:-left-10 md:mt-0">
        <p className="ml-6 rounded-xl rounded-br-sm bg-accent-soft px-3 py-1.5">Dr. Kaur is away tomorrow. Plan cover.</p>
        <p className="mt-2 flex items-center gap-1.5 text-muted"><CheckCircle2 size={12} className="text-ok" aria-hidden /> Found 4 classes, checked who is free</p>
        <div className="mt-2 rounded-lg border border-accent/30 bg-accent-soft/40 p-2">
          <p className="font-semibold text-accent-text">Cover plan · not applied yet</p>
          <p className="mt-1">4 classes: 3 substitutes, 1 cancelled</p>
          <span className="mt-2 inline-block rounded-md bg-accent px-2 py-1 font-medium text-white dark:text-bg">Apply</span>
        </div>
      </div>
    </div>
  );
}

function Section({ id, eyebrow, title, intro, children }: { id?: string; eyebrow: string; title: string; intro?: string; children: ReactNode }) {
  return (
    <section id={id} className="mx-auto max-w-6xl scroll-mt-20 px-4 py-14">
      <p className="text-xs font-semibold uppercase tracking-wide text-accent-text">{eyebrow}</p>
      <h2 className="mt-2 max-w-3xl text-3xl font-semibold tracking-tight">{title}</h2>
      {intro && <p className="mt-3 max-w-3xl text-muted">{intro}</p>}
      <div className="mt-8">{children}</div>
    </section>
  );
}

const PROBLEMS = [
  ["Hand-made timetables clash", "Two classes in one room, a teacher in two places. Found on Monday morning.", "Built by a scheduling algorithm and checked by a separate validator: a clash can't be published."],
  ["Gaps all day, no idea where to sit", "Free periods scattered across the day, and nobody knows which room is empty.", "Fewer gaps by design, and \"which rooms are free now?\" is answered in a second."],
  ["A teacher is away, classes just vanish", "Students wait, nobody covers, the class is lost.", "The cover plan finds a free teacher of the same subject for every class, or cancels and finds a makeup."],
  ["Every change is a phone call", "Moving one lecture means checking ten people's timetables by hand.", "Drag a class: green slots are safe. Teachers and students are notified when you apply."],
];

function Problems() {
  return (
    <Section eyebrow="Why" title="Timetables are the daily headache of every college." intro="We built Timetabl.ai after facing these as students.">
      <div className="grid gap-4 md:grid-cols-2">
        {PROBLEMS.map(([p, pain, fix]) => (
          <div key={p} className="rounded-xl border border-border bg-surface p-5">
            <h3 className="font-semibold">{p}</h3>
            <p className="mt-1 text-sm text-muted">{pain}</p>
            <p className="mt-3 flex gap-2 text-sm"><CheckCircle2 size={16} className="mt-0.5 shrink-0 text-ok" aria-hidden /> {fix}</p>
          </div>
        ))}
      </div>
    </Section>
  );
}

const FEATURES: [typeof LayoutGrid, string, string][] = [
  [Wand2, "One-click generation", "College-wide timetable for every section, teacher and room: labs as blocks with parallel batches, combined classes, electives, 1 or 2 shifts, shared rooms."],
  [ShieldCheck, "No clash, ever", "An independent validator checks every timetable and every change before anyone sees it."],
  [Layers, "Setup without help", "A step-by-step wizard and one Excel sheet per department, with row-level errors. Or load a sample college."],
  [LayoutGrid, "Every view", "Section, teacher and room timetables, colour-coded, light and dark, on any phone. Today and This week with real dates."],
  [MousePointerClick, "Safe drag and drop", "Green, amber and red slots while you drag. Only the classes that must move do, and every change can be undone."],
  [CalendarClock, "One-day changes", "Cancel or move a class for a single day, with a makeup finder for when the teacher, the students and a room are all free."],
  [UserCheck, "Teacher leave, covered", "A teacher asks for leave, the Coordinator approves, and the cover plan ranks substitutes fairly."],
  [ClipboardCheck, "Attendance", "Teachers mark in seconds. Students see how many classes they can still miss."],
  [CalendarCheck2, "Bookings", "Doubt slots in teachers' office hours, meetings when everyone is free, rooms for club events with approval."],
  [Bell, "Notices and notifications", "Only the people affected are told: the students, the teacher and the Coordinator of that class."],
  [FileSpreadsheet, "Excel and PDF", "Print-ready timetables for notice boards, per section, teacher or room."],
  [Users, "Built for many colleges", "Each college's data is kept apart, with roles from College Admin down to student."],
];

function Features() {
  return (
    <Section id="features" eyebrow="Features" title="Everything a college needs, around one clash-free timetable.">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {FEATURES.map(([Icon, t, d]) => (
          <div key={t} className="rounded-xl border border-border bg-surface p-5">
            <Icon size={20} className="text-accent-text" aria-hidden />
            <h3 className="mt-3 font-semibold">{t}</h3>
            <p className="mt-1 text-sm text-muted">{d}</p>
          </div>
        ))}
      </div>
    </Section>
  );
}

function Assistant() {
  const points: [typeof Zap, string, string][] = [
    [Headphones, "Talk to it", "Hands-free Talk mode: speak, it answers aloud, and you can interrupt it. Or type, with suggestions as you go."],
    [Sparkles, "It does the work", "\"Dr. Kaur is away Thursday\" becomes a full cover plan. \"Move CSE-3A's lecture to Friday\" becomes a checked change."],
    [MousePointerClick, "It drives the screen", "It opens the timetable, teacher or week it is talking about, beside the chat."],
    [ShieldCheck, "You stay in control", "It never changes anything by itself: you see the change and click Apply. It can only do what you can do."],
    [Zap, "Instant answers", "\"My next class\", \"free rooms now\", \"where is Dr. Arora\" are answered in under a second, without AI cost."],
    [GraduationCap, "For every role", "Students ask about their week and attendance; teachers plan makeups; Coordinators handle leave; Admins see everything."],
  ];
  return (
    <Section id="assistant" eyebrow="AI assistant" title="An assistant that plans the fix, not just answers."
      intro="The timetable itself is always made by the algorithm. The assistant uses it: it finds the facts, prepares the change, and shows you the plan.">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {points.map(([Icon, t, d]) => (
          <div key={t} className="rounded-xl border border-accent/25 bg-accent-soft/30 p-5">
            <Icon size={20} className="text-accent-text" aria-hidden />
            <h3 className="mt-3 font-semibold">{t}</h3>
            <p className="mt-1 text-sm text-muted">{d}</p>
          </div>
        ))}
      </div>
    </Section>
  );
}

function HowItWorks() {
  const steps = [
    ["Set up the college", "Shifts, periods, mess timings, rooms and departments, in a guided wizard."],
    ["Departments add their data", "Each Coordinator uploads one Excel sheet: sections, subjects, teachers, students. Teacher suggestions included."],
    ["Generate and publish", "One click builds the whole college's timetable in under a minute. Review it, then publish to everyone."],
    ["Run the semester", "Leave, moves, makeups, bookings and attendance, with the assistant and an undo for every change."],
  ];
  return (
    <Section id="how" eyebrow="How it works" title="From sign-up to a published timetable in an afternoon.">
      <ol className="grid gap-4 md:grid-cols-4">
        {steps.map(([t, d], i) => (
          <li key={t} className="rounded-xl border border-border bg-surface p-5">
            <span className="grid h-7 w-7 place-items-center rounded-full bg-accent text-sm font-semibold text-white dark:text-bg">{i + 1}</span>
            <h3 className="mt-3 font-semibold">{t}</h3>
            <p className="mt-1 text-sm text-muted">{d}</p>
          </li>
        ))}
      </ol>
    </Section>
  );
}

function Roles() {
  const roles = [
    ["College Admin", "Sets up the college, generates and publishes, sees every department, the assistant's cost and the readiness checklist."],
    ["Department Coordinator", "Fills the department's data, approves teacher requests and leave, plans cover, posts notices."],
    ["Teacher", "Sees their own lectures, changes a class for one day, asks for leave, marks attendance, sets office hours."],
    ["Student", "Today and this week on the phone, free rooms, attendance, doubt slots with teachers."],
  ];
  return (
    <Section eyebrow="For everyone" title="One app, the right view for each person.">
      <div className="grid gap-4 md:grid-cols-4">
        {roles.map(([r, d]) => (
          <div key={r} className="rounded-xl border border-border bg-surface p-5">
            <h3 className="font-semibold">{r}</h3>
            <p className="mt-1 text-sm text-muted">{d}</p>
          </div>
        ))}
      </div>
    </Section>
  );
}

function Pricing() {
  const plans = [
    { name: "Starter", price: "Free", unit: "", note: "To try it with one department.", cta: "Create your college", href: "/signup",
      items: ["1 department, up to 300 students", "Generate, all views, drag and drop", "Excel import and export", "Assistant: 100 answers a month"] },
    { name: "College", price: "₹25", unit: "per student / year", note: "Most colleges. Minimum ₹25,000 a year.", cta: "Try the demo", href: "/demo", featured: true,
      items: ["Unlimited departments, 1 or 2 shifts", "Teacher leave cover, makeups, bookings, events", "Attendance, notices, notifications", "Assistant with voice (fair use)", "Email support"] },
    { name: "University", price: "Custom", unit: "", note: "Several campuses or very large colleges.", cta: "Talk to us", href: "/signup",
      items: ["Everything in College", "Several campuses in one account", "Help importing your current timetable", "Priority support"] },
  ];
  return (
    <Section id="pricing" eyebrow="Pricing" title="Simple pricing per student."
      intro="Indicative prices for the demo. Making and changing the timetable never uses AI, so it costs nothing extra; the assistant costs us about ₹0.10 to ₹2 per answer and is included in fair use.">
      <div className="grid gap-4 md:grid-cols-3">
        {plans.map((p) => (
          <div key={p.name} className={`flex flex-col rounded-xl border bg-surface p-6 ${p.featured ? "border-accent shadow-lg" : "border-border"}`}>
            <div className="flex items-center gap-2">
              <h3 className="font-semibold">{p.name}</h3>
              {p.featured && <span className="rounded-full bg-accent-soft px-2 py-0.5 text-[11px] font-medium text-accent-text">Most popular</span>}
            </div>
            <p className="mt-3"><span className="text-3xl font-semibold">{p.price}</span> <span className="text-sm text-muted">{p.unit}</span></p>
            <p className="mt-1 text-sm text-muted">{p.note}</p>
            <ul className="mt-4 flex-1 space-y-2 text-sm">
              {p.items.map((i) => <li key={i} className="flex gap-2"><CheckCircle2 size={16} className="mt-0.5 shrink-0 text-ok" aria-hidden />{i}</li>)}
            </ul>
            <Link href={p.href} className={`${p.featured ? primary : secondary} mt-6`}>{p.cta}</Link>
          </div>
        ))}
      </div>
    </Section>
  );
}

function Footer() {
  return (
    <footer className="border-t border-border">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-4 px-4 py-8 text-sm text-muted">
        <span className="flex items-center gap-2"><DoorOpen size={16} aria-hidden /> Timetabl.ai: clash-free timetables for any college.</span>
        <div className="ml-auto flex gap-4">
          <Link href="/demo" className="hover:text-text">Demo</Link>
          <Link href="/login" className="hover:text-text">Log in</Link>
          <Link href="/signup" className="hover:text-text">Create a college</Link>
        </div>
      </div>
    </footer>
  );
}
