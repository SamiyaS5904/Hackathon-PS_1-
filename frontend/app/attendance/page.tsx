"use client";

import clsx from "clsx";
import { AlertTriangle, CheckCircle2, ClipboardCheck, Loader2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AttendanceSheet } from "@/components/attendance/AttendanceSheet";
import { Badge, Button, Card, ErrorCard, PageHeader, Skeleton } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useTimetable } from "@/lib/timetable-context";
import type { SectionAttendance, StudentAttendance, TeacherClass } from "@/lib/types";
import { usePagePrompts } from "@/lib/chat-context";
import Link from "next/link";

/** Attendance, separate from the timetable: students see where they stand, teachers mark, staff follow up. */
export default function AttendancePage() {
  const { role } = useAuth();
  const { college } = useTimetable();
  usePagePrompts(role === "student"
    ? ["What's my attendance, and can I miss a class?", "Which subject is my attendance lowest in?", "When is my next class?"]
    : role === "teacher"
      ? ["Which classes haven't I marked attendance for?", "Who is often absent in my classes?", "What do I teach next?"]
      : [`Who is below 75% attendance in ${college?.sections[0]?.name ?? "my sections"}?`, "Which sections have the lowest attendance?",
        "Which classes still need attendance marked?"]);
  if (role === "student") return <StudentView />;
  if (role === "teacher") return <TeacherView />;
  return <StaffView />;
}

function Percent({ value, min, size = "lg" }: { value: number | null; min: number; size?: "lg" | "sm" }) {
  const tone = value === null ? "text-muted" : value >= min ? "text-ok" : "text-danger";
  return (
    <span className={clsx("font-semibold tabular-nums", tone, size === "lg" ? "text-4xl" : "text-sm")}>
      {value === null ? "–" : `${Math.round(value)}%`}
    </span>
  );
}

function Bar({ value, min }: { value: number | null; min: number }) {
  return (
    <div className="relative mt-2 h-2 overflow-hidden rounded-full bg-surface-2" aria-hidden>
      <div className={clsx("h-full rounded-full", value !== null && value < min ? "bg-danger" : "bg-ok")}
        style={{ width: `${value ?? 0}%` }} />
      <div className="absolute inset-y-0 w-0.5 bg-text/40" style={{ left: `${min}%` }} title={`${min}% needed`} />
    </div>
  );
}

function StudentView() {
  const [me, setMe] = useState<StudentAttendance | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api.myAttendance().then(setMe).catch((e) => setError(e instanceof ApiError ? e.message : "Couldn't load attendance"));
  }, []);
  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader title="My attendance" subtitle="Your attendance in every subject, against your college's rule." />
      {error && <ErrorCard message={error} />}
      {!me && !error && <Skeleton className="h-56 w-full" />}
      {me && (
        <>
          <Card className="mb-4 p-6">
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-muted">Overall</p>
                <Percent value={me.percent} min={me.min_percent} />
                <p className="mt-1 text-sm text-muted">{me.attended} of {me.held} classes · {me.min_percent}% needed</p>
              </div>
              <p className={clsx("flex max-w-sm items-start gap-2 text-sm",
                me.status === "low" ? "text-danger" : me.status === "ok" ? "text-ok" : "text-muted")}>
                {me.status === "low" ? <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden />
                  : <CheckCircle2 size={16} className="mt-0.5 shrink-0" aria-hidden />}
                {me.advice}
              </p>
            </div>
            <Bar value={me.percent} min={me.min_percent} />
          </Card>

          {me.subjects.length === 0 ? (
            <Card className="p-8 text-center text-sm text-muted">
              Nothing marked yet. Your attendance appears here as soon as your teachers mark their classes.
            </Card>
          ) : (
            <Card className="mb-4 divide-y divide-border">
              {me.subjects.map((s) => (
                <div key={s.subject_id} className="px-5 py-4">
                  <div className="flex items-baseline justify-between gap-3">
                    <p className="text-sm font-medium">{s.name} <span className="font-normal text-muted">{s.code}</span></p>
                    <Percent value={s.percent} min={me.min_percent} size="sm" />
                  </div>
                  <Bar value={s.percent} min={me.min_percent} />
                  <p className={clsx("mt-1.5 text-xs", s.status === "low" ? "text-danger" : "text-muted")}>
                    {s.attended}/{s.held} attended · {s.advice}
                  </p>
                </div>
              ))}
            </Card>
          )}

          {me.recent.length > 0 && (
            <Card className="p-5">
              <h3 className="text-sm font-semibold">Recent classes</h3>
              <ul className="mt-3 space-y-1.5 text-sm">
                {me.recent.map((r, i) => (
                  <li key={i} className="flex items-center justify-between gap-3">
                    <span><span className="font-mono text-xs text-muted">{r.date}</span> · {r.subject}</span>
                    <Badge tone={r.present ? "ok" : "danger"}>{r.present ? "Present" : "Absent"}</Badge>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </>
      )}
    </div>
  );
}

function TeacherView() {
  const [classes, setClasses] = useState<TeacherClass[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<TeacherClass | null>(null);
  const load = useCallback(() => {
    api.myClasses().then(setClasses).catch((e) => setError(e instanceof ApiError ? e.message : "Couldn't load your classes"));
  }, []);
  useEffect(() => { load(); }, [load]);
  const nowMin = new Date().getHours() * 60 + new Date().getMinutes();
  const d = new Date();
  const today = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const started = (c: TeacherClass) => c.date < today || Number(c.start.slice(0, 2)) * 60 + Number(c.start.slice(3)) <= nowMin;
  const list = (classes ?? []).filter(started);
  const unmarked = list.filter((c) => !c.marked).length;
  const groups = useMemo(() => {
    const m = new Map<string, TeacherClass[]>();
    for (const c of list) m.set(c.label, [...(m.get(c.label) ?? []), c]);
    return [...m.entries()];
  }, [list]);

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader title="Attendance" subtitle="Your classes of the last 7 days. Tap one to mark or correct it." />
      {error && <ErrorCard message={error} onRetry={load} />}
      {!classes && !error && <Skeleton className="h-56 w-full" />}
      {classes && (
        <>
          <p className={clsx("mb-4 text-sm", unmarked ? "text-warn" : "text-ok")}>
            {unmarked ? `${unmarked} class${unmarked > 1 ? "es" : ""} not marked yet.` : "Every class is marked."}
          </p>
          {groups.length === 0 && <Card className="p-8 text-center text-sm text-muted">No classes in the last 7 days.</Card>}
          {groups.map(([label, items]) => (
            <div key={label} className="mb-4">
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">{label}</h3>
              <Card className="divide-y divide-border">
                {items.map((c) => (
                  <button key={c.session_id + c.date} onClick={() => setOpen(c)}
                    className="flex w-full items-center gap-3 px-4 py-3 text-left text-sm hover:bg-surface-2">
                    <span className="w-24 shrink-0 font-mono text-xs text-muted">{c.start}–{c.end}</span>
                    <span className="min-w-0 flex-1">
                      <span className="block font-medium">{c.subject}</span>
                      <span className="text-xs text-muted">{c.sections} · {c.venue} · {c.students} students</span>
                    </span>
                    {c.marked ? <Badge tone="ok">Marked · {c.absent} absent</Badge>
                      : <Badge tone="warn"><ClipboardCheck size={12} aria-hidden /> Not marked</Badge>}
                  </button>
                ))}
              </Card>
            </div>
          ))}
        </>
      )}
      {open && <AttendanceSheet sessionId={open.session_id} date={open.date} onClose={() => setOpen(null)} onSaved={load} />}
    </div>
  );
}

function StaffView() {
  const { role, member } = useAuth();
  const { college, reload } = useTimetable();
  const sections = useMemo(() => (college?.sections ?? [])
    .filter((s) => role === "admin" || s.department_id === member?.department_id), [college, role, member]);
  const [sectionId, setSectionId] = useState("");
  const [data, setData] = useState<SectionAttendance | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [rule, setRule] = useState<number | null>(null);
  const [savingRule, setSavingRule] = useState(false);
  const [ruleSaved, setRuleSaved] = useState(false);
  const picked = sectionId || sections[0]?.id || "";

  useEffect(() => {
    if (!picked) return;
    setData(null);
    api.sectionAttendance(picked).then(setData).catch((e) => setError(e instanceof ApiError ? e.message : "Couldn't load"));
  }, [picked]);
  useEffect(() => { if (college) setRule(college.attendance_min_percent); }, [college]);

  const low = data?.students.filter((s) => s.low).length ?? 0;
  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader title="Attendance" subtitle="Each section's attendance; students below the rule come first." />
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <select value={picked} onChange={(e) => setSectionId(e.target.value)} aria-label="Section"
          className="min-w-48 rounded-lg border border-border-strong bg-surface px-3 py-2 text-sm">
          {sections.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
        {data && <span className="text-sm text-muted">{low ? `${low} below ${data.min_percent}%` : `Everyone at ${data.min_percent}% or more`}</span>}
        {role === "admin" && rule !== null && (
          <form className="ml-auto flex items-center gap-2 text-sm" onSubmit={async (e) => {
            e.preventDefault();
            setSavingRule(true);
            try {
              await api.setAttendanceRule(rule);
              await reload();
              setError(null);
              setRuleSaved(true);
              setTimeout(() => setRuleSaved(false), 3000);
            } catch (err) {
              setError(err instanceof Error ? err.message : "Couldn't save the rule");
            } finally { setSavingRule(false); }
          }}>
            <label htmlFor="rule" className="text-muted">Students need</label>
            <input id="rule" type="number" min={1} max={100} value={rule} onChange={(e) => setRule(Number(e.target.value))}
              className="w-16 rounded-lg border border-border-strong bg-surface px-2 py-1.5 text-sm" />
            <span className="text-muted">%</span>
            <Button type="submit" disabled={savingRule}>{savingRule ? <Loader2 size={14} className="animate-spin" /> : "Save"}</Button>
            {ruleSaved && <span className="text-xs text-ok">Saved</span>}
          </form>
        )}
      </div>
      {error && <ErrorCard message={error} />}
      {sections.length === 0 ? (
        <Card className="p-8 text-center text-sm text-muted">
          No sections yet, so there is no attendance to show.
          <span className="mt-3 block"><Link href="/departments"><Button>Add sections</Button></Link></span>
        </Card>
      ) : !data && !error && <Skeleton className="h-64 w-full" />}
      {data && (
        <Card className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted">
                <th className="px-4 py-2 font-medium">Roll</th><th className="px-4 py-2 font-medium">Name</th>
                <th className="px-4 py-2 font-medium">Attended</th><th className="px-4 py-2 font-medium">Attendance</th>
              </tr>
            </thead>
            <tbody>
              {data.students.map((s) => (
                <tr key={s.student_id} className={clsx("border-b border-border last:border-0", s.low && "bg-danger-soft/50")}>
                  <td className="px-4 py-2 font-mono text-xs">{s.roll_no}</td>
                  <td className="px-4 py-2">{s.name}</td>
                  <td className="px-4 py-2 text-muted">{s.held ? `${s.attended}/${s.held}` : "–"}</td>
                  <td className="px-4 py-2"><Percent value={s.percent} min={data.min_percent} size="sm" />
                    {s.low && <span className="ml-2 text-xs text-danger">below {data.min_percent}%</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
