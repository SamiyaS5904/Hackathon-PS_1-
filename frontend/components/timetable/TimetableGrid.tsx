"use client";

import clsx from "clsx";
import { FlaskConical, Utensils } from "lucide-react";
import { useMemo } from "react";
import type { College, MoveOption, OccurrenceStatus, Session, Timetable, ViewKind } from "@/lib/types";

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

/** Week mode: what happened to a class on its real date. Keyed by display session id. */
export type OccurrenceMeta = Map<string, { status: OccurrenceStatus; note: string }>;

export interface EditState {
  movingId: string | null;
  options: Map<string, MoveOption> | null; // key: `${day}|${start}`
  busy: boolean;
  changedIds: Set<string>;
  onPick: (s: Session) => void;
  onDrop: (day: string, start: string) => void;
}

export function TimetableGrid({
  college,
  timetable,
  view,
  entityId,
  edit,
  dayLabels,
  meta,
  onSelect,
}: {
  college: College;
  timetable: Timetable;
  view: ViewKind;
  entityId: string;
  edit?: EditState;
  dayLabels?: Record<string, string>;
  meta?: OccurrenceMeta;
  onSelect?: (s: Session) => void;
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

  if (rows.length === 0) {
    return <p className="p-6 text-sm text-muted">Nothing scheduled here.</p>;
  }

  const moving = edit?.movingId ? timetable.sessions.find((s) => s.id === edit.movingId) : undefined;

  return (
    <div className="overflow-x-auto rounded-xl border border-border bg-surface">
      <table className="w-full min-w-[860px] table-fixed border-collapse text-sm">
        <thead>
          <tr className="border-b border-border bg-surface-2/60">
            <th className="w-28 px-3 py-2.5 text-left text-xs font-medium text-muted">Time</th>
            {college.days.map((d) => (
              <th key={d} className="px-2 py-2.5 text-left text-xs font-medium uppercase tracking-wide text-muted">
                {dayLabels?.[d] ?? d}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <GridRow key={`${row.start}-${row.end}`} row={row} days={college.days}>
              {(day) => {
                const items = sessions.filter((s) => s.day === day && toMin(s.start) < row.e && row.s < toMin(s.end));
                const opt = moving ? edit?.options?.get(`${day}|${row.start}`) : undefined;
                const isOrigin = moving && moving.day === day && moving.start === row.start;
                return (
                  <TargetCell option={opt} origin={!!isOrigin} edit={edit} day={day} start={row.start}>
                    {items.map((s) => (
                      <SessionCard
                        key={s.id}
                        session={s}
                        view={view}
                        startsHere={s.start === row.start}
                        lookup={lookup}
                        edit={edit}
                        meta={meta?.get(s.id)}
                        onSelect={onSelect}
                      />
                    ))}
                  </TargetCell>
                );
              }}
            </GridRow>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function GridRow({ row, days, children }: { row: Row; days: string[]; children: (day: string) => React.ReactNode }) {
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
            <td key={d} className="h-[68px] p-1 align-top">
              {children(d)}
            </td>
          ))
        )}
      </tr>
    </>
  );
}

function TargetCell({
  option,
  origin,
  edit,
  day,
  start,
  children,
}: {
  option?: MoveOption;
  origin: boolean;
  edit?: EditState;
  day: string;
  start: string;
  children: React.ReactNode;
}) {
  const active = !!edit?.movingId;
  const droppable = active && option && option.status !== "blocked";
  const label = option
    ? option.status === "free"
      ? `Free slot${option.reason ? `: ${option.reason}` : ""}`
      : option.reason
    : undefined;
  return (
    <div
      className={clsx(
        "relative flex h-full flex-col gap-1 rounded-md p-0.5 transition",
        active && option?.status === "free" && "bg-ok-soft ring-2 ring-ok/60",
        active && option?.status === "repair" && "bg-warn-soft ring-2 ring-warn/50",
        active && option?.status === "blocked" && "bg-danger-soft/60",
        active && origin && "ring-2 ring-accent",
        droppable && "cursor-pointer",
      )}
      title={active ? label : undefined}
      onDragOver={(e) => droppable && e.preventDefault()}
      onDrop={(e) => {
        e.preventDefault();
        if (droppable) edit?.onDrop(day, start);
      }}
      onClick={() => droppable && edit?.onDrop(day, start)}
      role={droppable ? "button" : undefined}
      aria-label={droppable ? `Move here: ${day} ${start}. ${label ?? ""}` : undefined}
      tabIndex={droppable ? 0 : undefined}
      onKeyDown={(e) => droppable && (e.key === "Enter" || e.key === " ") && edit?.onDrop(day, start)}
    >
      {children}
      {active && option && option.status !== "free" && (
        <span
          className={clsx(
            "pointer-events-none absolute bottom-0.5 right-1 text-[10px] font-medium",
            option.status === "repair" ? "text-warn" : "text-danger",
          )}
        >
          {option.status === "repair" ? "other classes move" : "blocked"}
        </span>
      )}
    </div>
  );
}

function SessionCard({
  session: s,
  view,
  startsHere,
  lookup,
  edit,
  meta,
  onSelect,
}: {
  session: Session;
  view: ViewKind;
  startsHere: boolean;
  meta?: { status: OccurrenceStatus; note: string };
  onSelect?: (s: Session) => void;
  lookup: {
    subject: Map<string, { code: string; name: string }>;
    teacher: Map<string, { name: string }>;
    venue: Map<string, { name: string }>;
    section: Map<string, { name: string; batches: { id: string; name: string }[] }>;
  };
  edit?: EditState;
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
  const isMoving = edit?.movingId === s.id;
  const changed = edit?.changedIds.has(s.id);
  const status = meta?.status ?? "normal";
  const interactive = !!edit || !!onSelect;

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
      draggable={!!edit && !edit.busy}
      onDragStart={(e) => {
        e.dataTransfer.effectAllowed = "move";
        e.dataTransfer.setData("text/plain", s.id);
        edit?.onPick(s);
      }}
      onClick={(e) => {
        if (onSelect) return onSelect(s);
        if (!edit || edit.busy) return;
        // While moving another class, let the click reach the cell (drop target).
        if (edit.movingId && edit.movingId !== s.id) return;
        e.stopPropagation();
        edit.onPick(s); // pick, or cancel when it's the class being moved
      }}
      role={interactive ? "button" : undefined}
      tabIndex={interactive ? 0 : undefined}
      aria-pressed={edit ? isMoving : undefined}
      aria-label={
        onSelect
          ? `${subj?.name}, ${s.start}${status !== "normal" ? `, ${meta?.note}` : ""}. Press for options.`
          : edit ? `${subj?.name}, ${s.day} ${s.start}. Press to move.` : undefined
      }
      onKeyDown={(e) => {
        if (e.key !== "Enter" && e.key !== " ") return;
        e.preventDefault();
        if (onSelect) onSelect(s);
        else edit?.onPick(s);
      }}
      className={clsx(
        "subj flex-1 rounded-md border px-2 py-1.5 leading-tight",
        s.kind === "lab" && "border-l-4",
        edit && "cursor-grab active:cursor-grabbing hover:shadow-sm",
        onSelect && "cursor-pointer hover:shadow-sm",
        isMoving && "opacity-50 ring-2 ring-accent",
        changed && "ring-2 ring-accent/70",
        status === "cancelled" && "opacity-55 [&_.code]:line-through",
        status === "moved_out" && "border-dashed opacity-55",
        status === "moved_in" && "ring-2 ring-accent",
      )}
      style={{ "--h": hue } as React.CSSProperties}
      title={meta && status !== "normal" ? `${meta.note} · ${title}` : title}
    >
      <div className="flex items-center gap-1">
        <span className="code truncate text-[13px] font-semibold">{subj?.code}</span>
        {status === "cancelled" && <span className="rounded bg-danger-soft px-1 text-[9px] font-semibold uppercase text-danger">cancelled</span>}
        {status === "moved_out" && <span className="rounded bg-surface-2 px-1 text-[9px] font-semibold uppercase text-muted">moved</span>}
        {status === "moved_in" && <span className="rounded bg-accent px-1 text-[9px] font-semibold uppercase text-white dark:text-bg">this day</span>}
        {s.kind === "lab" && <FlaskConical size={12} aria-label="Lab" className="shrink-0" />}
        {s.elective_slot_id && <span className="rounded bg-white/60 px-1 text-[9px] font-semibold uppercase dark:bg-black/30">elective</span>}
        {changed && <span className="rounded bg-accent px-1 text-[9px] font-semibold uppercase text-white dark:text-bg">new</span>}
        {batch && <span className="ml-auto shrink-0 rounded bg-white/60 px-1 text-[10px] font-medium dark:bg-black/30">{batch}</span>}
      </div>
      <div className="truncate text-[11px] opacity-90">{subj?.name}</div>
      <div className="mt-0.5 truncate text-[11px] opacity-75">
        {status !== "normal" && meta ? meta.note : `${who ?? ""}${where ? ` · ${where}` : ""}`}
      </div>
    </div>
  );
}
