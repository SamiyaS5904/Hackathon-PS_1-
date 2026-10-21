"use client";

import clsx from "clsx";
import { FlaskConical, Utensils } from "lucide-react";
import { useMemo } from "react";
import type { College, Session, Timetable, ViewKind } from "@/lib/types";

const toMin = (t: string) => {
  const [h, m] = t.split(":").map(Number);
  return h * 60 + m;
};

/** Stable hue per subject so the same subject has the same colour in every view. */
export function subjectHue(id: string): number {
  let h = 0;
  for (const ch of id) h = (h * 31 + ch.charCodeAt(0)) % 360;
  return (h * 137) % 360;
}

interface Row {
  start: string;
  end: string;
  s: number;
  e: number;
  lunch: boolean;
  breakBefore: string | null;
}

export function TimetableGrid({
  college,
  timetable,
  view,
  entityId,
}: {
  college: College;
  timetable: Timetable;
  view: ViewKind;
  entityId: string;
}) {
  const lookup = useMemo(
    () => ({
      subject: new Map(college.subjects.map((s) => [s.id, s])),
      teacher: new Map(college.teachers.map((t) => [t.id, t])),
      venue: new Map(college.venues.map((v) => [v.id, v])),
      section: new Map(college.sections.map((s) => [s.id, s])),
    }),
    [college],
  );

  const sessions = useMemo(
    () =>
      timetable.sessions.filter((s) =>
        view === "section" ? s.section_ids.includes(entityId) : view === "teacher" ? s.teacher_id === entityId : s.venue_id === entityId,
      ),
    [timetable.sessions, view, entityId],
  );

  const rows = useMemo<Row[]>(() => {
    let shiftIds: string[];
    if (view === "section") shiftIds = [lookup.section.get(entityId)?.shift_id ?? ""];
    else if (view === "teacher") shiftIds = lookup.teacher.get(entityId)?.shift_ids ?? [];
    else shiftIds = college.shifts.map((s) => s.id);

    const seen = new Map<string, Row>();
    for (const sh of college.shifts.filter((s) => shiftIds.includes(s.id))) {
      for (const p of sh.periods) {
        const key = `${p.start}-${p.end}`;
        if (!seen.has(key)) seen.set(key, { ...p, s: toMin(p.start), e: toMin(p.end), lunch: false, breakBefore: null });
      }
    }
    const out = [...seen.values()].sort((a, b) => a.s - b.s || a.e - b.e);

    if (view === "section") {
      const sec = lookup.section.get(entityId);
      const lunch = timetable.lunches.find((l) => l.shift_id === sec?.shift_id && l.year === sec?.year);
      out.forEach((r, i) => {
        r.lunch = !!lunch && lunch.start === r.start;
        if (i > 0 && out[i - 1].e < r.s) r.breakBefore = `${out[i - 1].end}–${r.start}`;
      });
    }
    return out;
  }, [view, entityId, college.shifts, lookup, timetable.lunches]);

  const cell = (day: string, row: Row) =>
    sessions.filter((s) => s.day === day && toMin(s.start) < row.e && row.s < toMin(s.end));

  if (rows.length === 0) {
    return <p className="p-6 text-sm text-muted">Nothing scheduled here.</p>;
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-border bg-surface">
      <table className="w-full min-w-[860px] table-fixed border-collapse text-sm">
        <thead>
          <tr className="border-b border-border bg-surface-2/60">
            <th className="w-28 px-3 py-2.5 text-left text-xs font-medium text-muted">Time</th>
            {college.days.map((d) => (
              <th key={d} className="px-2 py-2.5 text-left text-xs font-medium uppercase tracking-wide text-muted">
                {d}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <RowView key={`${row.start}-${row.end}`} row={row} days={college.days} cell={cell} render={(s) => (
              <SessionCard
                key={s.id}
                session={s}
                view={view}
                startsHere={s.start === row.start}
                lookup={lookup}
              />
            )} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RowView({
  row,
  days,
  cell,
  render,
}: {
  row: Row;
  days: string[];
  cell: (day: string, row: Row) => Session[];
  render: (s: Session) => React.ReactNode;
}) {
  return (
    <>
      {row.breakBefore && (
        <tr className="border-b border-border">
          <td colSpan={days.length + 1} className="bg-surface-2/40 px-3 py-1 text-[11px] text-muted">
            Break · {row.breakBefore}
          </td>
        </tr>
      )}
      <tr className="border-b border-border last:border-0">
        <td className="px-3 py-2 align-top font-mono text-xs text-muted">
          {row.start}
          <br />
          <span className="opacity-70">{row.end}</span>
        </td>
        {row.lunch ? (
          <td colSpan={days.length} className="px-2 py-2">
            <div className="flex items-center justify-center gap-2 rounded-md border border-dashed border-border-strong py-2 text-xs text-muted">
              <Utensils size={13} aria-hidden /> Lunch
            </div>
          </td>
        ) : (
          days.map((d) => (
            <td key={d} className="h-[68px] px-1.5 py-1.5 align-top">
              <div className="flex h-full flex-col gap-1">{cell(d, row).map(render)}</div>
            </td>
          ))
        )}
      </tr>
    </>
  );
}

function SessionCard({
  session: s,
  view,
  startsHere,
  lookup,
}: {
  session: Session;
  view: ViewKind;
  startsHere: boolean;
  lookup: {
    subject: Map<string, { code: string; name: string }>;
    teacher: Map<string, { name: string }>;
    venue: Map<string, { name: string }>;
    section: Map<string, { name: string; batches: { id: string; name: string }[] }>;
  };
}) {
  const subj = lookup.subject.get(s.subject_id);
  const hue = subjectHue(s.subject_id);
  const batch = s.batch_id
    ? lookup.section.get(s.section_ids[0])?.batches.find((b) => b.id === s.batch_id)?.name
    : null;
  const sections = s.section_ids.map((id) => lookup.section.get(id)?.name ?? id).join(" + ");
  // section view: teacher · room | teacher view: sections · room | venue view: teacher · sections
  const who = view === "teacher" ? sections : lookup.teacher.get(s.teacher_id)?.name;
  const where = view === "venue" ? sections : lookup.venue.get(s.venue_id)?.name;
  const title = `${subj?.name} · ${s.start}–${s.end} · ${lookup.teacher.get(s.teacher_id)?.name} · ${lookup.venue.get(s.venue_id)?.name} · ${sections}${batch ? ` (${batch})` : ""}`;

  if (!startsHere) {
    return (
      <div
        className="subj flex flex-1 items-center rounded-md border border-dashed px-2 text-[11px] opacity-70"
        style={{ "--h": hue } as React.CSSProperties}
        title={title}
      >
        ↳ {subj?.code} {s.kind === "lab" ? "lab" : ""} continues
      </div>
    );
  }

  return (
    <div
      className={clsx("subj flex-1 rounded-md border px-2 py-1.5 leading-tight", s.kind === "lab" && "border-l-4")}
      style={{ "--h": hue } as React.CSSProperties}
      title={title}
    >
      <div className="flex items-center gap-1">
        <span className="truncate text-[13px] font-semibold">{subj?.code}</span>
        {s.kind === "lab" && <FlaskConical size={12} aria-label="Lab" className="shrink-0" />}
        {batch && <span className="ml-auto shrink-0 rounded bg-white/60 px-1 text-[10px] font-medium dark:bg-black/30">{batch}</span>}
      </div>
      <div className="truncate text-[11px] opacity-90">{subj?.name}</div>
      <div className="mt-0.5 truncate text-[11px] opacity-75">
        {who}
        {where ? ` · ${where}` : ""}
      </div>
    </div>
  );
}
