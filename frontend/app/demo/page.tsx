"use client";

import clsx from "clsx";
import { ArrowLeft, Globe2, GraduationCap, Loader2, School, User, UserCog } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { FormError } from "@/components/Field";
import { auth } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { DemoCollege } from "@/lib/types";

const PASSWORD = "demo1234";
const DOMAIN = "demo.timetabl.ai";
const DEPARTMENTS = [
  { id: "cse", name: "Computer Science" },
  { id: "ece", name: "Electronics" },
  { id: "me", name: "Mechanical" },
  { id: "as", name: "Applied Sciences" },
];
const SECTIONS = ["cse-1a", "cse-1b", "cse-2a", "cse-2b", "cse-3a", "cse-3b", "ece-1a", "ece-2a", "ece-3a",
  "me-1a", "me-2a", "me-3a"];
const TEACHERS = [
  ["anita.sharma", "Dr. Anita Sharma"], ["harpreet.kaur", "Dr. Harpreet Kaur"], ["rohit.bansal", "Prof. Rohit Bansal"],
  ["neha.arora", "Dr. Neha Arora"], ["amit.malhotra", "Prof. Amit Malhotra"], ["simran.gill", "Dr. Simran Gill"],
];
const sectionName = (id: string) => id.toUpperCase().replace(/-(\d)/, "-$1");

const select = "w-full rounded-lg border border-border-strong bg-surface px-2.5 py-1.5 text-sm";
const card = "flex w-full items-start gap-3 rounded-lg border border-border px-3 py-3 text-left text-sm transition hover:border-accent/40 hover:bg-accent-soft disabled:opacity-60";
const openBtn = "shrink-0 rounded-lg bg-accent px-3 text-sm font-medium text-white disabled:opacity-60 dark:text-bg";

/** Try the product as any role of a demo college: a click logs in, nothing to type. Two colleges: the built-in
 *  Demo Institute, and GNDEC (re-engineered from GNDEC's public timetables, made-up names). */
export default function DemoPage() {
  const router = useRouter();
  const { signIn } = useAuth();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [college, setCollege] = useState<"demo" | "gndec">("demo");

  const go = async (email: string) => {
    setBusy(email);
    setError(null);
    try {
      const out = await auth.login(email, PASSWORD);
      signIn(out);
      router.replace(out.platform_owner && out.memberships.length === 0 ? "/platform" : "/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't open the demo");
    } finally {
      setBusy(null);
    }
  };
  const icon = (email: string, Icon: typeof School) =>
    busy === email ? <Loader2 size={18} className="mt-0.5 animate-spin" aria-hidden />
      : <Icon size={18} className="mt-0.5 text-accent-text" aria-hidden />;

  return (
    <>
      <Link href="/welcome" className="mb-4 inline-flex items-center gap-1 text-xs text-muted hover:text-text">
        <ArrowLeft size={14} aria-hidden /> About Timetabl.ai
      </Link>
      <h1 className="text-lg font-semibold">Try a demo college</h1>
      <div className="mt-3 grid grid-cols-2 gap-1 rounded-xl bg-surface-2 p-1 text-sm" role="tablist" aria-label="Demo college">
        {([["demo", "Demo Institute", "built-in sample"], ["gndec", "GNDEC (demo)", "4 departments, years 1-4"]] as const).map(([id, name, hint]) => (
          <button key={id} role="tab" aria-selected={college === id} onClick={() => setCollege(id)}
            className={clsx("rounded-lg px-3 py-2 text-left leading-tight", college === id ? "bg-surface font-semibold shadow-sm" : "text-muted hover:text-text")}>
            {name}<span className="block text-[11px] font-normal text-muted">{hint}</span>
          </button>
        ))}
      </div>

      {college === "demo" ? <DemoInstitute go={go} busy={busy} icon={icon} /> : <Gndec go={go} busy={busy} icon={icon} />}

      <p className="pt-4 text-xs font-medium uppercase tracking-wide text-muted">For the Timetabl.ai team</p>
      <button className={`${card} mt-2`} disabled={!!busy} onClick={() => go(`owner@${DOMAIN}`)}>
        {icon(`owner@${DOMAIN}`, Globe2)}
        <span>
          <span className="block font-medium">Platform owner (SaaS)</span>
          <span className="text-xs text-muted">Every college on the platform: plans, progress, health, pause / read-only</span>
        </span>
      </button>
      <div className="mt-3"><FormError message={error} /></div>
      <p className="mt-4 text-xs text-muted">
        Every demo account uses the password <code className="font-mono">{PASSWORD}</code>, so you can also log in by hand.
      </p>
    </>
  );
}

type Props = { go: (email: string) => void; busy: string | null; icon: (email: string, Icon: typeof School) => React.ReactNode };

function Picker({ title, hint, Icon, email, options, value, onChange, go, busy, icon }: Props & {
  title: string; hint: string; Icon: typeof School; email: string;
  options: { value: string; label: string }[]; value: string; onChange: (v: string) => void;
}) {
  return (
    <div className={`${card} hover:bg-transparent`}>
      {icon(email, Icon)}
      <span className="flex-1 space-y-2">
        <span className="block font-medium">{title}</span>
        <span className="block text-xs text-muted">{hint}</span>
        <span className="flex gap-2">
          <select className={select} value={value} onChange={(e) => onChange(e.target.value)} aria-label={title}>
            {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
          <button className={openBtn} disabled={!!busy || !email} onClick={() => go(email)}>Open</button>
        </span>
      </span>
    </div>
  );
}

function DemoInstitute(p: Props) {
  const [dept, setDept] = useState("cse");
  const [section, setSection] = useState("cse-3a");
  const [teacher, setTeacher] = useState("anita.sharma");
  return (
    <div className="mt-4 space-y-2">
      <p className="text-sm text-muted">Demo Institute of Technology: 4 departments, 12 sections, 2 shifts. Pick who you want to be.</p>
      <button className={card} disabled={!!p.busy} onClick={() => p.go(`admin@${DOMAIN}`)}>
        {p.icon(`admin@${DOMAIN}`, School)}
        <span>
          <span className="block font-medium">College Admin</span>
          <span className="text-xs text-muted">Set up the college, generate, publish, change anything</span>
        </span>
      </button>
      <Picker {...p} title="Department Coordinator" hint="Own department's data, leave cover, approvals" Icon={UserCog}
        email={`${dept}.coordinator@${DOMAIN}`} value={dept} onChange={setDept}
        options={DEPARTMENTS.map((d) => ({ value: d.id, label: d.name }))} />
      <Picker {...p} title="Teacher" hint="Own lectures, one-day changes, leave, attendance" Icon={User}
        email={`${teacher}@${DOMAIN}`} value={teacher} onChange={setTeacher}
        options={TEACHERS.map(([id, name]) => ({ value: id, label: name }))} />
      <Picker {...p} title="Student" hint="Own section's week, attendance and the assistant" Icon={GraduationCap}
        email={`${section.replace("-", "")}.01@${DOMAIN}`} value={section} onChange={setSection}
        options={SECTIONS.map((s) => ({ value: s, label: `${sectionName(s)}, roll 01` }))} />
    </div>
  );
}

function Gndec(p: Props) {
  const [data, setData] = useState<DemoCollege | null>(null);
  const [failed, setFailed] = useState(false);
  const [coord, setCoord] = useState("");
  const [teacher, setTeacher] = useState("");
  const [student, setStudent] = useState("");
  useEffect(() => {
    auth.demoLogins("gndec").then((d) => {
      setData(d);
      const first = (role: string) => d.logins.find((l) => l.role === role)?.email ?? "";
      setCoord(first("coordinator"));
      setTeacher(first("teacher"));
      setStudent(d.logins.find((l) => l.section === "JPAL student")?.email ?? first("student"));
    }).catch(() => setFailed(true));
  }, []);
  if (failed) return <p className="mt-4 text-sm text-muted">The GNDEC demo isn&apos;t set up on this server yet. Try the Demo Institute.</p>;
  if (!data) return <p className="mt-4 flex items-center gap-2 text-sm text-muted"><Loader2 size={14} className="animate-spin" aria-hidden /> Loading…</p>;
  const of = (role: string) => data.logins.filter((l) => l.role === role);
  const admin = of("admin")[0]?.email ?? "";
  return (
    <div className="mt-4 space-y-2">
      <p className="text-sm text-muted">
        {data.name}: {data.sections} sections, {data.students.toLocaleString()} students, {data.teachers} teachers,{" "}
        {data.rooms} rooms. Re-engineered from GNDEC&apos;s public timetables; every name is made up.
      </p>
      <button className={card} disabled={!!p.busy} onClick={() => p.go(admin)}>
        {p.icon(admin, School)}
        <span>
          <span className="block font-medium">College Admin</span>
          <span className="text-xs text-muted">The whole college: CSE, IT, Mechanical, Civil, Applied Sciences</span>
        </span>
      </button>
      <Picker {...p} title="Department Coordinator" hint="Leave cover, approvals, notices for the department" Icon={UserCog}
        email={coord} value={coord} onChange={setCoord}
        options={of("coordinator").map((l) => ({ value: l.email, label: l.name }))} />
      <Picker {...p} title="Teacher" hint="Own lectures, leave, attendance, office hours" Icon={User}
        email={teacher} value={teacher} onChange={setTeacher}
        options={of("teacher").map((l) => ({ value: l.email, label: `${l.name}${l.department ? ` (${l.department})` : ""}` }))} />
      <Picker {...p} title="Student" hint="Own section, free rooms, attendance; the JPAL student has the JPAL lab" Icon={GraduationCap}
        email={student} value={student} onChange={setStudent}
        options={of("student").map((l) => ({ value: l.email, label: l.section === "JPAL student" ? `JPAL student (${l.name})` : `${l.section}: ${l.name}` }))} />
    </div>
  );
}
