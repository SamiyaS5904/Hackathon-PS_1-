"use client";

import clsx from "clsx";
import { ArrowRight, CalendarOff, CalendarX2, Inbox, Loader2, Sparkles, Undo2, UserX } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Badge, Button, Card, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { useChatPage } from "@/lib/chat-context";
import { useTimetable } from "@/lib/timetable-context";
import { ago } from "@/lib/time";
import { useToast } from "@/lib/toast";
import type { TodayReport } from "@/lib/types";
import { TeacherAwayDialog } from "./TeacherAwayDialog";

const STATUS: Record<TodayReport["status"]["state"], { label: string; tone: "ok" | "accent" | "warn" | "neutral" }> = {
  published: { label: "Published", tone: "ok" },
  draft: { label: "Draft, not published", tone: "accent" },
  out_of_date: { label: "Out of date", tone: "warn" },
  none: { label: "No timetable yet", tone: "neutral" },
};

/** Staff home: what needs attention today. A Coordinator sees their own department. */
export function TodayCard() {
  const { data, setData } = useTimetable();
  const { prefill } = useChatPage();
  const showToast = useToast();
  const [report, setReport] = useState<TodayReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [away, setAway] = useState<{ open: boolean; teacherId?: string }>({ open: false });
  const [undoing, setUndoing] = useState(false);

  const load = useCallback(() => {
    api.today().then((r) => { setReport(r); setError(null); })
      .catch((e) => setError(e instanceof Error ? e.message : "Couldn't load today"));
  }, []);
  useEffect(() => {
    load();
  }, [load, data]);

  const handle = (name?: string) => prefill(name
    ? `${name} is away today (${report?.label}). Find who can cover each of their classes, or a makeup time, and prepare the changes.`
    : "Who is away today, and which classes need cover? Prepare the changes.");

  const last = data?.last_change;
  const undo = async () => {
    if (!last) return;
    setUndoing(true);
    try {
      setData(await api.undo(last.id));
      showToast({ text: "Undone. The timetable is back to how it was, and everyone affected is told." });
    } catch (e) {
      showToast({ text: e instanceof Error ? e.message : "Couldn't undo", tone: "danger" });
    } finally {
      setUndoing(false);
    }
  };

  if (error) return <Card className="mb-6 p-5 text-sm text-danger">{error}</Card>;
  if (!report) return <Skeleton className="mb-6 h-40 w-full" />;
  const st = STATUS[report.status.state];
  const live = report.status.state === "published";
  return (
    <Card className="mb-6 p-5">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-lg font-semibold">Today · {report.label}</h2>
        <Badge tone={st.tone}>{st.label}</Badge>
        <div className="ml-auto flex flex-wrap gap-2">
          <Button onClick={() => setAway({ open: true })} disabled={!live} title={live ? undefined : "Publish the timetable first"}>
            <UserX size={16} aria-hidden /> Teacher away
          </Button>
          <Button variant="primary" onClick={() => handle(report.away[0]?.name)}>
            <Sparkles size={16} aria-hidden /> Handle with assistant
          </Button>
        </div>
      </div>

      {!report.working ? (
        <p className="mt-3 flex items-center gap-2 text-sm text-muted">
          <CalendarOff size={16} aria-hidden /> {report.holiday ? `Holiday: ${report.holiday}.` : "Not a working day."} No classes today.
        </p>
      ) : (
        <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-5">
          {([
            ["Classes today", report.classes_today, false, undefined],
            ["Teachers away", report.away.length, report.away.length > 0, undefined],
            ["Not happening", report.cancelled.length, report.cancelled.length > 0, "/changes"],
            ["Moved", report.moved.length, false, "/changes"],
            ["Requests waiting", report.pending_requests, report.pending_requests > 0, "/changes"],
          ] as const).map(([k, v, warn, href]) => {
            const box = (
              <div className={clsx("h-full rounded-lg border px-3 py-2", warn ? "border-warn/40 bg-warn-soft/40" : "border-border")}>
                <p className="text-xs text-muted">{k}</p>
                <p className="text-xl font-semibold">{v}</p>
              </div>
            );
            return href && v > 0 ? <Link key={k} href={href} className="block hover:opacity-90">{box}</Link> : <div key={k}>{box}</div>;
          })}
        </div>
      )}

      {report.away.length > 0 && (
        <div className="mt-4">
          <h3 className="text-xs font-medium uppercase tracking-wide text-muted">Teachers away</h3>
          <ul className="mt-1.5 space-y-1.5">
            {report.away.map((a) => (
              <li key={a.teacher_id} className="flex flex-wrap items-center gap-2 text-sm">
                <UserX size={15} className="text-warn" aria-hidden />
                <span className="font-medium">{a.name}</span>
                <span className="text-muted">{a.classes} class{a.classes === 1 ? "" : "es"} today</span>
                <button onClick={() => handle(a.name)} className="ml-auto inline-flex items-center gap-1 text-xs text-accent-text hover:underline">
                  <Sparkles size={12} aria-hidden /> Find cover
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {report.cancelled.length > 0 && (
        <div className="mt-4">
          <h3 className="text-xs font-medium uppercase tracking-wide text-muted">Not happening today</h3>
          <ul className="mt-1.5 space-y-1 text-sm">
            {report.cancelled.slice(0, 5).map((c) => (
              <li key={c.occurrence_id} className="flex flex-wrap items-center gap-2">
                <CalendarX2 size={14} className="text-danger" aria-hidden />
                <span className="font-medium">{c.start}</span> {c.subject} <span className="text-muted">{c.sections} · {c.teacher}</span>
              </li>
            ))}
          </ul>
          {report.cancelled.length > 5 && (
            <Link href="/changes" className="mt-1 inline-flex items-center gap-1 text-xs text-accent-text hover:underline">
              All {report.cancelled.length} in Changes <ArrowRight size={12} aria-hidden />
            </Link>
          )}
        </div>
      )}

      {report.recent.length > 0 && (
        <div className="mt-4">
          <div className="flex items-baseline justify-between">
            <h3 className="text-xs font-medium uppercase tracking-wide text-muted">Latest changes</h3>
            <Link href="/changes" className="text-xs text-accent-text hover:underline">All changes</Link>
          </div>
          <ul className="mt-1.5 space-y-1.5 text-sm">
            {report.recent.slice(0, 3).map((r, i) => (
              <li key={r.id} className={clsx("flex flex-wrap items-center gap-2", r.undone && "text-muted line-through")}>
                <span className="min-w-0 flex-1 truncate">{r.action}</span>
                <span className="text-xs text-muted">{r.actor} · {ago(r.at)}</span>
                {i === 0 && last?.can_undo && last.id === r.id && (
                  <button onClick={undo} disabled={undoing} className="inline-flex items-center gap-1 text-xs text-accent-text hover:underline">
                    {undoing ? <Loader2 size={12} className="animate-spin" aria-hidden /> : <Undo2 size={12} aria-hidden />} Undo
                  </button>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {report.pending_requests > 0 && (
        <Link href="/changes" className="mt-4 flex items-center gap-3 rounded-lg border border-accent/30 bg-accent-soft px-3 py-2 text-sm text-accent-text hover:bg-accent/15">
          <Inbox size={16} aria-hidden />
          <span className="flex-1">{report.pending_requests} request{report.pending_requests > 1 ? "s" : ""} from teachers waiting for you</span>
          <ArrowRight size={16} aria-hidden />
        </Link>
      )}

      {away.open && <TeacherAwayDialog teacherId={away.teacherId} onClose={() => setAway({ open: false })} onDone={load} />}
    </Card>
  );
}
