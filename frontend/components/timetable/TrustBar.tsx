"use client";

import clsx from "clsx";
import { AlertTriangle, CheckCircle2, Clock, FileEdit, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { ago } from "@/lib/time";
import type { QualityReport, Role, TimetableOut } from "@/lib/types";

// What each quality item means when it costs points, in words a college uses.
const WEAK: Record<string, string> = {
  gaps: "some free periods between classes",
  student_balance: "a few uneven student days",
  repeats: "the same subject twice a day in places",
  teacher_balance: "some teachers have a heavy day",
  room_fit: "some rooms are bigger than needed",
  home_room: "some sections change rooms often",
};

/** Quality in words: a grade plus the one or two things that cost the most. */
export function qualityInWords(q: QualityReport): string {
  const grade = q.score >= 88 ? "Very good" : q.score >= 78 ? "Good" : q.score >= 65 ? "Fair" : "Needs work";
  const weak = [...q.items].filter((i) => i.penalty >= 3 && WEAK[i.key]).sort((a, b) => b.penalty - a.penalty)
    .slice(0, 2).map((i) => WEAK[i.key]);
  return weak.length ? `${grade}: ${weak.join("; ")}` : `${grade}: few gaps, balanced teacher loads, right-sized rooms`;
}

/** Always-visible trust line on the timetable: published or draft, clashes (checked independently), quality in words,
 *  and who changed it last. Every role sees it; staff see who changed it. */
export function TrustBar({ data, role }: { data: TimetableOut; role: Role }) {
  const [open, setOpen] = useState(false);
  const tt = data.timetable;
  const staff = role === "admin" || role === "coordinator";
  const clashes = data.violations.length;
  const state = data.stale ? "out" : tt.published_at ? "published" : "draft";
  const item = "inline-flex items-center gap-1.5";
  return (
    <div className="no-print mb-3 rounded-lg border border-border bg-surface px-3 py-2 text-xs" role="status">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <span className={clsx(item, "font-medium", state === "published" ? "text-ok" : state === "draft" ? "text-accent-text" : "text-warn")}>
          {state === "published" ? <CheckCircle2 size={14} aria-hidden /> : state === "draft" ? <FileEdit size={14} aria-hidden /> : <AlertTriangle size={14} aria-hidden />}
          {state === "published" ? "Published" : state === "draft" ? "Draft" : "Out of date"}
        </span>
        {!data.stale && (
          <button onClick={() => clashes && setOpen(!open)} aria-expanded={clashes ? open : undefined}
            className={clsx(item, clashes ? "font-medium text-danger hover:underline" : "cursor-default text-text")}>
            {clashes ? <AlertTriangle size={14} aria-hidden /> : <ShieldCheck size={14} className="text-ok" aria-hidden />}
            {clashes ? `${clashes} clash${clashes === 1 ? "" : "es"} found` : "0 clashes, checked by the independent validator"}
          </button>
        )}
        {staff && data.quality && !data.stale && (
          <span className={clsx(item, "text-muted")} title={`Quality score ${data.quality.score}/100`}>
            {qualityInWords(data.quality)}
          </span>
        )}
        <span className={clsx(item, "text-muted sm:ml-auto")}>
          <Clock size={13} aria-hidden />
          {staff && data.last_change
            ? `Last changed by ${data.last_change.actor}, ${ago(data.last_change.at)}`
            : tt.published_at ? `Published ${ago(tt.published_at)}${tt.published_by && staff ? ` by ${tt.published_by}` : ""}` : "Not published yet"}
        </span>
      </div>
      {state === "draft" && staff && (
        <p className="mt-1 text-muted">
          {data.ever_published
            ? "Teachers and students still see the previously published timetable. Publish this one to replace it."
            : "Teachers and students can't see it yet. Review it, then Publish."}
        </p>
      )}
      {open && clashes > 0 && (
        <ul className="mt-2 list-disc space-y-0.5 pl-5 text-danger">
          {data.violations.slice(0, 10).map((v, i) => <li key={i}>{v.message}</li>)}
        </ul>
      )}
    </div>
  );
}
