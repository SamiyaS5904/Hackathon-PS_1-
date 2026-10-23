"use client";

import clsx from "clsx";
import { CalendarOff, CheckCircle2, ClipboardCheck, Clock, Loader2, MapPin, User, Utensils } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AttendanceSheet } from "@/components/attendance/AttendanceSheet";
import { Button, Card, ErrorCard } from "@/components/ui";
import { api } from "@/lib/api";
import type { College, Lunch, Member, Occurrence, TeacherClass, WeekOut } from "@/lib/types";

const pad = (n: number) => String(n).padStart(2, "0");
const isoDate = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const toMin = (t: string) => Number(t.slice(0, 2)) * 60 + Number(t.slice(3, 5));
const inWords = (min: number) => (min < 60 ? `${min} min` : `${Math.floor(min / 60)} h ${min % 60 ? `${min % 60} min` : ""}`.trim());

type Item =
  | { kind: "class"; occ: Occurrence; start: number; end: number }
  | { kind: "lunch"; start: number; end: number; label: string };

/** Today, for a student or teacher: what's on now, what's next, what's done. Teachers take attendance here. */
export function TodayView({ college, member, lunches }: { college: College; member: Member; lunches: Lunch[] }) {
  const [now, setNow] = useState(() => new Date());
  const [week, setWeek] = useState<WeekOut | null>(null);
  const [marks, setMarks] = useState<Map<string, TeacherClass>>(new Map());
  const [error, setError] = useState<string | null>(null);
  const [sheet, setSheet] = useState<{ sessionId: string; date: string } | null>(null);
  const isTeacher = member.role === "teacher";
  const today = isoDate(now);

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 30_000);
    return () => clearInterval(id);
  }, []);

  const loadMarks = useCallback(() => {
    if (!isTeacher) return;
    api.myClasses()
      .then((list) => setMarks(new Map(list.filter((c) => c.date === today).map((c) => [c.session_id, c]))))
      .catch(() => {});
  }, [isTeacher, today]);

  useEffect(() => {
    api.week(today).then(setWeek).catch((e) => setError(e instanceof Error ? e.message : "Couldn't load today"));
    loadMarks();
  }, [today, loadMarks]);

  const info = week?.days.find((d) => d.date === today);
  const items = useMemo<Item[]>(() => {
    if (!week) return [];
    const list: Item[] = week.occurrences
      .filter((o) => o.date === today)
      .map((o) => ({ kind: "class" as const, occ: o, start: toMin(o.session.start), end: toMin(o.session.end) }));
    const sec = college.sections.find((s) => s.id === member.section_id);
    const lunch = sec && info && lunches.find((l) => l.section_id === sec.id && l.day === info.day);
    if (lunch) list.push({ kind: "lunch", start: toMin(lunch.start), end: toMin(lunch.end), label: `${lunch.start}–${lunch.end}` });
    return list.sort((a, b) => a.start - b.start);
  }, [week, today, college.sections, member.section_id, info, lunches]);

  const minutes = now.getHours() * 60 + now.getMinutes();
  const live = items.filter((i) => i.kind === "class" && ["normal", "moved_in"].includes(i.occ.status)) as Extract<Item, { kind: "class" }>[];
  const current = live.find((i) => i.start <= minutes && minutes < i.end);
  const next = live.find((i) => i.start > minutes);
  // One main button: the class on now, else the latest one that started and isn't marked yet.
  const focus = current?.occ.session.id
    ?? [...live].reverse().find((i) => i.start <= minutes && !marks.get(i.occ.session.id)?.marked)?.occ.session.id;
  const lookup = (id: string, list: { id: string; name: string }[]) => list.find((x) => x.id === id)?.name ?? "";

  if (error) return <ErrorCard message={error} />;
  if (!week) return <Card className="flex items-center gap-2 p-6 text-sm text-muted"><Loader2 size={16} className="animate-spin" /> Loading today…</Card>;

  const describe = (o: Occurrence) => ({
    subject: college.subjects.find((s) => s.id === o.session.subject_id)?.name ?? "",
    room: lookup(o.session.venue_id, college.venues),
    teacher: lookup(o.session.teacher_id, college.teachers),
    sections: o.session.section_ids.map((id) => lookup(id, college.sections)).join(" + "),
  });

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-4 flex items-baseline justify-between">
        <h2 className="text-lg font-semibold">{now.toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" })}</h2>
        <span className="flex items-center gap-1.5 font-mono text-sm text-muted"><Clock size={14} aria-hidden />
          {now.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}</span>
      </div>

      {/* The one thing to know right now. */}
      <Card className="mb-5 p-5">
        {info?.holiday ? (
          <p className="flex items-center gap-2 font-medium"><CalendarOff size={18} className="text-muted" /> Holiday: {info.holiday}. No classes today.</p>
        ) : !info?.working && !live.length ? (
          <p className="flex items-center gap-2 font-medium"><CalendarOff size={18} className="text-muted" /> No classes today.</p>
        ) : current ? (
          <NowNext label="Now" tone="accent" occ={current.occ} d={describe(current.occ)} isTeacher={isTeacher}
            when={`until ${current.occ.session.end} · ${inWords(current.end - minutes)} left`}
            progress={(minutes - current.start) / (current.end - current.start)} />
        ) : next ? (
          <NowNext label="Next" tone="ok" occ={next.occ} d={describe(next.occ)} isTeacher={isTeacher}
            when={`${next.occ.session.start} · in ${inWords(next.start - minutes)}`} />
        ) : live.length ? (
          <p className="flex items-center gap-2 font-medium"><CheckCircle2 size={18} className="text-ok" /> That&apos;s all for today.</p>
        ) : (
          <p className="flex items-center gap-2 font-medium"><CalendarOff size={18} className="text-muted" /> No classes today.</p>
        )}
      </Card>

      {items.length > 0 && (
        <ol className="space-y-2" aria-label="Today's classes">
          {items.map((it, i) => {
            if (it.kind === "lunch") {
              return (
                <li key={`lunch-${i}`} className={clsx("flex items-center gap-3 rounded-xl border border-dashed border-border px-4 py-2.5 text-sm text-muted",
                  it.end <= minutes && "opacity-60")}>
                  <span className="w-24 shrink-0 font-mono text-xs">{it.label}</span><Utensils size={14} aria-hidden /> Lunch
                </li>
              );
            }
            const o = it.occ;
            const d = describe(o);
            const gone = o.status === "cancelled" || o.status === "moved_out";
            const done = !gone && it.end <= minutes;
            const isNow = current?.occ === o;
            const mark = marks.get(o.session.id);
            const started = !gone && it.start <= minutes;
            return (
              <li key={o.occurrence_id + o.status}
                className={clsx("rounded-xl border px-4 py-3 text-sm transition",
                  isNow ? "border-accent/50 bg-accent-soft" : "border-border bg-surface",
                  done && "opacity-60")}>
                <div className="flex flex-wrap items-start gap-3">
                  <span className="w-24 shrink-0 font-mono text-xs text-muted">{o.session.start}–{o.session.end}</span>
                  <div className="min-w-0 flex-1">
                    <p className={clsx("font-medium", gone && "line-through")}>
                      {d.subject}
                      {done && <CheckCircle2 size={14} className="ml-1.5 inline text-ok" aria-label="Done" />}
                      {isNow && <span className="ml-2 rounded-full bg-accent px-2 py-0.5 text-[10px] font-semibold uppercase text-white dark:text-bg">Now</span>}
                    </p>
                    <p className="mt-0.5 text-xs text-muted">
                      {isTeacher ? d.sections : d.teacher}{d.room ? ` · ${d.room}` : ""}
                    </p>
                    {o.note && <p className={clsx("mt-1 text-xs", gone ? "text-danger" : "text-warn")}>{o.note}</p>}
                  </div>
                  {isTeacher && !gone && (
                    started ? (
                      <Button variant={!mark?.marked && focus === o.session.id ? "primary" : "secondary"} onClick={() => setSheet({ sessionId: o.session.id, date: today })}>
                        <ClipboardCheck size={15} aria-hidden />
                        {mark?.marked ? `Marked · ${mark.absent} absent` : "Take attendance"}
                      </Button>
                    ) : <span className="text-xs text-muted">Attendance opens at {o.session.start}</span>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
      )}

      {sheet && (
        <AttendanceSheet sessionId={sheet.sessionId} date={sheet.date} onClose={() => setSheet(null)} onSaved={loadMarks} />
      )}
    </div>
  );
}

function NowNext({ label, tone, occ, d, when, progress, isTeacher }: {
  label: string; tone: "accent" | "ok"; occ: Occurrence; when: string; progress?: number; isTeacher: boolean;
  d: { subject: string; room: string; teacher: string; sections: string };
}) {
  return (
    <div>
      <p className={clsx("text-xs font-semibold uppercase tracking-wide", tone === "accent" ? "text-accent-text" : "text-ok")}>{label}</p>
      <p className="mt-1 text-xl font-semibold">{d.subject}</p>
      <p className="mt-1 text-sm text-muted">{when}</p>
      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-sm">
        {d.room && <span className="flex items-center gap-1.5"><MapPin size={14} className="text-muted" aria-hidden /> {d.room}</span>}
        <span className="flex items-center gap-1.5"><User size={14} className="text-muted" aria-hidden /> {isTeacher ? d.sections : d.teacher}</span>
      </div>
      {occ.note && <p className="mt-2 text-xs text-warn">{occ.note}</p>}
      {progress !== undefined && (
        <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-accent/15" aria-hidden>
          <div className="h-full rounded-full bg-accent" style={{ width: `${Math.min(100, Math.max(0, progress * 100))}%` }} />
        </div>
      )}
    </div>
  );
}
