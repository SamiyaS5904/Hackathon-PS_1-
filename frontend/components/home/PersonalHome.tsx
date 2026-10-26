"use client";

import clsx from "clsx";
import { ArrowRight, CalendarClock } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { DayChangesPanel } from "@/components/changes/DayChangesPanel";
import { MyLeaveCard } from "./MyLeaveCard";
import { TodayView } from "@/components/timetable/TodayView";
import { Badge, Card, ErrorCard, PageHeader, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { greetName } from "@/lib/names";
import { useTimetable } from "@/lib/timetable-context";
import type { WeekOut } from "@/lib/types";
import { usePagePrompts } from "@/lib/chat-context";

const pad = (n: number) => String(n).padStart(2, "0");
const iso = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

/** Home for teachers and students: today first (now / next / done), then the week with changes marked. */
export function PersonalHome() {
  const { college, data, loading, error, reload } = useTimetable();
  const { member, user } = useAuth();
  const [week, setWeek] = useState<WeekOut | null>(null);
  const today = iso(new Date());
  usePagePrompts(member?.role === "teacher"
    ? ["What do I teach next, and where?", "Which classes haven't I marked attendance for?", "When am I free tomorrow?"]
    : ["What's my next class, and where?", "Are any of my classes cancelled this week?", "What's my attendance, and can I miss a class?"]);

  useEffect(() => {
    if (!data?.timetable.sessions.length) return;
    api.week(today).then(setWeek).catch(() => setWeek({ days: [], occurrences: [] }));
  }, [data, today]);

  const byDay = useMemo(() => {
    if (!week) return [];
    return week.days.filter((d) => d.working || d.holiday).map((d) => ({
      ...d,
      items: week.occurrences.filter((o) => o.date === d.date && o.status !== "moved_out")
        .concat(week.occurrences.filter((o) => o.date === d.date && o.status === "moved_out"))
        .sort((a, b) => a.session.start.localeCompare(b.session.start)),
    }));
  }, [week]);

  const subTeacher = (o: { session: { teacher_id: string } }) => o.session.teacher_id;
  const name = (id: string, list?: { id: string; name: string }[]) => list?.find((x) => x.id === id)?.name ?? "";
  const hour = new Date().getHours();
  const hello = `${hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening"}, ${greetName(user?.name)}`;

  if (loading || !college || !member) {
    return (
      <div className="mx-auto max-w-3xl space-y-4">
        {error && !loading && <ErrorCard message={error} onRetry={reload} />}
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }
  if (!data || !data.timetable.sessions.length) {
    return (
      <div className="mx-auto max-w-3xl">
        <PageHeader title={hello} subtitle={college.name} />
        <Card className="p-8 text-center text-sm text-muted">
          <CalendarClock className="mx-auto mb-2 text-muted" size={28} aria-hidden />
          Your timetable isn&rsquo;t published yet. You&rsquo;ll get a notification (the bell, top left) as soon as it is.
        </Card>
      </div>
    );
  }
  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader title={hello} subtitle={college.name} />
      <TodayView college={college} member={member} lunches={data.timetable.lunches} />

      <section className="mt-8">
        <div className="mb-2 flex items-baseline justify-between">
          <h2 className="text-sm font-semibold">This week
            {member.role === "teacher" && <span className="ml-2 text-xs font-normal text-muted">Click a lecture to ask to move it for good</span>}</h2>
          <Link href="/timetable?mode=week" className="inline-flex items-center gap-1 text-xs text-accent-text hover:underline">
            Full timetable <ArrowRight size={12} aria-hidden />
          </Link>
        </div>
        {!week ? <Skeleton className="h-40 w-full" /> : (
          <div className="space-y-2">
            {byDay.map((d) => (
              <Card key={d.date} className={clsx("p-3", d.date === today && "border-accent/50 ring-1 ring-accent/30")}>
                <p className="mb-1.5 flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted">
                  {d.label}{d.date === today && <Badge tone="accent">Today</Badge>}
                </p>
                {d.holiday ? <p className="text-sm text-muted">Holiday: {d.holiday}</p>
                  : d.items.length === 0 ? <p className="text-sm text-muted">No classes</p> : (
                    <ul className="space-y-1">
                      {d.items.map((o) => (
                        <li key={o.occurrence_id + o.status} className={clsx("flex flex-wrap items-center gap-2 text-sm",
                          (o.status === "cancelled" || o.status === "moved_out") && "text-muted line-through")}>
                          <span className="w-12 shrink-0 font-mono text-xs text-muted">{o.session.start}</span>
                          {member.role === "teacher" && o.status === "normal" ? (
                            <Link href={`/timetable?mode=plan&pick=${o.session.id}`} title="Ask to move this lecture for good"
                              className="font-medium text-accent-text hover:underline">{name(o.session.subject_id, college.subjects)}</Link>
                          ) : <span className="font-medium">{name(o.session.subject_id, college.subjects)}</span>}
                          <span className="text-xs text-muted">
                            {name(o.session.venue_id, college.venues)}
                            {member.role === "teacher"
                              ? ` · ${o.session.section_ids.map((id) => name(id, college.sections)).join(" + ")}`
                              : ` · ${name(o.session.teacher_id, college.teachers)}`}
                          </span>
                          {o.substitute_for && o.status === "normal" && (
                            <Badge tone="accent">{o.substitute_for === member.teacher_id
                              ? `Covered by ${name(subTeacher(o), college.teachers)}`
                              : member.role === "teacher" ? "You're covering" : "Substitute"}</Badge>
                          )}
                          {o.status !== "normal" && (
                            <Badge tone={o.status === "cancelled" ? "danger" : "warn"}>
                              {o.status === "cancelled" ? "Cancelled" : o.status === "moved_in" ? "Moved here" : "Moved"}
                            </Badge>
                          )}
                        </li>
                      ))}
                    </ul>
                  )}
              </Card>
            ))}
          </div>
        )}
      </section>

      {member.role === "teacher" && <MyLeaveCard />}
      <div className="mt-8"><DayChangesPanel /></div>
    </div>
  );
}
