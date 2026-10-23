"use client";

import clsx from "clsx";
import { CheckCircle2, ChevronLeft, ChevronRight, Loader2, Move, Printer, Undo2, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { GenerateButton, GenerationProgress } from "@/components/timetable/GenerateButton";
import { PublishButton } from "@/components/timetable/PublishButton";
import { DownloadMenu } from "@/components/timetable/DownloadMenu";
import { HealthStrip } from "@/components/timetable/HealthStrip";
import { OneDayPanel } from "@/components/timetable/OneDayPanel";
import { ProposalDialog } from "@/components/timetable/ProposalDialog";
import { RequestDialog } from "@/components/timetable/RequestDialog";
import { useMoveEditor } from "@/components/timetable/useMoveEditor";
import { type OccurrenceMeta, TimetableGrid } from "@/components/timetable/TimetableGrid";
import { Button, Card, ErrorCard, PageHeader, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { isStaff, useAuth } from "@/lib/auth";
import { useChatPage } from "@/lib/chat-context";
import { useTimetable } from "@/lib/timetable-context";
import type { Occurrence, OverrideOut, Session, TimetableOut, ViewKind, WeekOut } from "@/lib/types";

const isoDate = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const addDays = (iso: string, n: number) => {
  const d = new Date(`${iso}T12:00:00`);
  d.setDate(d.getDate() + n);
  return isoDate(d);
};

const VIEWS: { id: ViewKind; label: string }[] = [
  { id: "section", label: "Section" },
  { id: "teacher", label: "Teacher" },
  { id: "venue", label: "Room" },
];

export default function TimetablePage() {
  const { college, data, loading, error, reload } = useTimetable();
  const { role, member } = useAuth();
  const isStudent = role === "student";
  const isTeacher = role === "teacher";
  // Teachers open on their own timetable, students on their section.
  const [view, setView] = useState<ViewKind>(isTeacher && member?.teacher_id ? "teacher" : "section");
  const [picked, setPicked] = useState<Record<ViewKind, string>>({
    section: member?.section_id ?? "", teacher: member?.teacher_id ?? "", venue: "",
  });
  const editor = useMoveEditor({ requestOnly: isTeacher });
  const { setData } = useTimetable();
  // Students and teachers care about real dates (cancellations, one-day moves) first.
  const [mode, setMode] = useState<"plan" | "week">(isStaff(role) ? "plan" : "week");
  // Staff move classes directly; teachers pick their own lecture and a slot to ask their Coordinator.
  const canDrag = isStaff(role) || (isTeacher && !!member?.teacher_id);
  const [weekStart, setWeekStart] = useState(() => isoDate(new Date()));
  const [week, setWeek] = useState<WeekOut | null>(null);
  const [selected, setSelected] = useState<Occurrence | null>(null);

  const loadWeek = useCallback(async () => {
    try {
      setWeek(await api.week(weekStart));
    } catch (e) {
      editor.setToast({ text: e instanceof Error ? e.message : "Couldn't load this week", tone: "danger" });
    }
  }, [weekStart, editor.setToast]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (mode === "week" && data?.timetable.sessions.length) loadWeek();
  }, [mode, data, loadWeek]);

  // Week mode: occurrences on real dates, shown through the same grid.
  const weekView = useMemo(() => {
    if (mode !== "week" || !week || !data) return null;
    const meta: OccurrenceMeta = new Map();
    const byDisplayId = new Map<string, Occurrence>();
    const sessions: Session[] = week.occurrences.map((o) => {
      const id = `${o.session.id}@${o.date}@${o.status}`;
      meta.set(id, { status: o.status, note: o.note });
      byDisplayId.set(id, o);
      return { ...o.session, id };
    });
    const dayLabels = Object.fromEntries(week.days.map((d) => [d.day, d.label]));
    return { timetable: { ...data.timetable, sessions }, meta, byDisplayId, dayLabels };
  }, [mode, week, data]);

  const onOneDayDone = (out: OverrideOut) => {
    setData(out.timetable);
    setSelected(null);
    editor.setToast({ text: out.message, undo: true, tone: "ok" });
  };

  const isCoordinator = role === "coordinator";
  const options = useMemo(() => {
    if (!college) return [];
    const dept = new Map(college.departments.map((d) => [d.id, d.short]));
    const yearName = (y: number) => `${y}${["th", "st", "nd", "rd"][y % 10 > 3 || Math.floor(y / 10) === 1 ? 0 : y % 10]} year`;
    // A Coordinator works on their own department: its sections (by year) and everyone who teaches them.
    const ownDept = isCoordinator ? member?.department_id : undefined;
    const ownSections = new Set(college.sections.filter((s) => s.department_id === ownDept).map((s) => s.id));
    const teachesOwn = new Set((data?.timetable.sessions ?? [])
      .filter((x) => x.section_ids.some((id) => ownSections.has(id))).map((x) => x.teacher_id));
    const list =
      view === "section"
        ? college.sections.filter((s) => !ownDept || s.department_id === ownDept)
            .sort((a, b) => a.department_id.localeCompare(b.department_id) || a.year - b.year || a.name.localeCompare(b.name))
            .map((s) => ({ id: s.id, label: s.name,
                           group: ownDept ? yearName(s.year) : `${dept.get(s.department_id) ?? ""} · ${yearName(s.year)}` }))
        : view === "teacher"
          ? college.teachers.filter((t) => !ownDept || t.department_id === ownDept || teachesOwn.has(t.id))
              .map((t) => ({ id: t.id, label: t.name,
                             group: ownDept && t.department_id !== ownDept ? `Also teach your sections (${dept.get(t.department_id)})`
                               : dept.get(t.department_id) ?? "" }))
          : college.venues.map((v) => ({
              id: v.id,
              label: `${v.name} (${v.capacity})`,
              group: v.department_id ? (dept.get(v.department_id) ?? "") : "Shared",
            }));
    const groups = new Map<string, typeof list>();
    for (const o of list) groups.set(o.group, [...(groups.get(o.group) ?? []), o]);
    return [...groups.entries()];
  }, [college, data, view, isCoordinator, member]);

  const entityId = picked[view] || options[0]?.[1][0]?.id || "";

  // Tell the assistant what's on screen ("move this class", "is this room free").
  const { setPage } = useChatPage();
  const entityName = useMemo(() => {
    if (!college) return "";
    if (view === "section") return college.sections.find((s) => s.id === entityId)?.name ?? "";
    if (view === "teacher") return college.teachers.find((t) => t.id === entityId)?.name ?? "";
    return college.venues.find((v) => v.id === entityId)?.name ?? "";
  }, [college, view, entityId]);
  useEffect(() => {
    setPage({ view, entity: entityName, mode });
    return () => setPage({});
  }, [view, entityName, mode, setPage]);

  const subtitle = useMemo(() => {
    if (!college || !entityId) return "";
    if (view === "section") {
      const s = college.sections.find((x) => x.id === entityId);
      const shift = college.shifts.find((x) => x.id === s?.shift_id);
      const shiftText = college.shifts.length > 1 ? ` · ${shift?.name} shift` : "";
      return s ? `${s.strength} students${shiftText} · ${s.batches.length} lab batches` : "";
    }
    if (view === "teacher") {
      const t = college.teachers.find((x) => x.id === entityId);
      const n = data?.timetable.sessions.filter((x) => x.teacher_id === entityId).reduce((a, x) => a + x.length, 0);
      const shiftText = college.shifts.length > 1
        ? ` · ${t?.shift_ids.map((id) => college.shifts.find((x) => x.id === id)?.name ?? id).join(" + ")} shift`
        : "";
      return t ? `${n ?? 0} periods a week · max ${t.max_per_day}/day${shiftText}` : "";
    }
    const v = college.venues.find((x) => x.id === entityId);
    const u = data?.quality?.venue_utilisation[entityId];
    return v ? `${v.type} · seats ${v.capacity}${u !== undefined ? ` · used ${(u * 100).toFixed(0)}% of the week` : ""}` : "";
  }, [college, data, view, entityId]);

  return (
    <div className="mx-auto max-w-7xl">
      <PageHeader
        title={isStaff(role) ? "Timetable" : "My timetable"}
        subtitle={college ? `${college.name}${isStudent ? ` · ${studentLabel(college, member)}` : " · weekly timetable"}` : undefined}
        actions={
          <>
            {data && data.timetable.sessions.length > 0 && (
              <DownloadMenu
                view={isStudent ? "section" : view}
                entityId={isStudent ? (member?.section_id ?? "") : entityId}
                entityName={isStudent ? "My timetable" : entityName}
                canAll={isStaff(role)}
              />
            )}
            {data && (
              <Button variant="ghost" onClick={() => window.print()} className="no-print">
                <Printer size={16} aria-hidden /> Print
              </Button>
            )}
            {/* One primary action: Publish while a draft waits, otherwise (re)generate. */}
            {role === "admin" && (
              <GenerateButton primary={!data || data.stale || data.timetable.sessions.length === 0} />
            )}
            {role === "admin" && <PublishButton />}
          </>
        }
      />

      <GenerationProgress />
      {error && <ErrorCard message={error} onRetry={reload} />}

      {loading || !college ? (
        error ? null : <Skeleton className="h-[520px] w-full" />
      ) : !data ? (
        <EmptyState />
      ) : data.timetable.sessions.length === 0 ? (
        <Card className="p-6">
          <h2 className="font-medium">No timetable could be built</h2>
          <ul className="mt-2 list-disc pl-5 text-sm text-muted">
            {data.timetable.messages.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
        </Card>
      ) : (
        <>
          {data.stale && (
            <div className="mb-4 rounded-xl border border-warn/40 bg-warn-soft px-4 py-3 text-sm text-warn" role="status">
              <b>Out of date:</b> college data changed after this timetable was made.
              {role === "admin" ? " Regenerate it (top right) to apply the changes." : " The College Admin will regenerate it."}
              {" "}Editing is paused until then.
            </div>
          )}
          {isStaff(role) && !data.stale && <PublishStatus data={data} />}
          {role === "admin" && !data.stale && <HealthStrip data={data} />}

          <div className="no-print mb-3 flex flex-wrap items-center gap-3">
            {/* Teachers and students see only their own timetable: no switching. */}
            {isStaff(role) && (<>
            <div className="inline-flex rounded-lg border border-border bg-surface p-0.5" role="tablist" aria-label="View by">
              {VIEWS.map((v) => (
                <button
                  key={v.id}
                  role="tab"
                  aria-selected={view === v.id}
                  onClick={() => setView(v.id)}
                  className={clsx(
                    "rounded-md px-3 py-1.5 text-sm transition",
                    view === v.id ? "bg-accent-soft font-medium text-accent-text" : "text-muted hover:text-text",
                  )}
                >
                  {v.label}
                </button>
              ))}
            </div>
            <label className="sr-only" htmlFor="entity">
              Choose
            </label>
            <select
              id="entity"
              value={entityId}
              onChange={(e) => setPicked({ ...picked, [view]: e.target.value })}
              className="min-w-56 rounded-lg border border-border-strong bg-surface px-3 py-2 text-sm"
            >
              {options.map(([group, items]) => (
                <optgroup key={group} label={group}>
                  {items.map((o) => (
                    <option key={o.id} value={o.id}>
                      {o.label}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
            <span className="text-sm text-muted">{subtitle}</span>
            </>)}

            <div className="ml-auto flex items-center gap-2">
              {mode === "week" && week && (
                <div className="flex items-center gap-1 text-sm">
                  <button aria-label="Previous week" onClick={() => setWeekStart(addDays(weekStart, -7))}
                    className="rounded p-1.5 hover:bg-surface-2"><ChevronLeft size={16} /></button>
                  <span className="min-w-36 text-center font-medium">
                    {week.days[0]?.label} – {week.days.at(-1)?.label}
                  </span>
                  <button aria-label="Next week" onClick={() => setWeekStart(addDays(weekStart, 7))}
                    className="rounded p-1.5 hover:bg-surface-2"><ChevronRight size={16} /></button>
                  <button onClick={() => setWeekStart(isoDate(new Date()))}
                    className="rounded px-2 py-1 text-xs text-muted hover:bg-surface-2">Today</button>
                </div>
              )}
              <div className="inline-flex rounded-lg border border-border bg-surface p-0.5" role="tablist" aria-label="Timetable mode">
                {([["plan", "Weekly plan"], ["week", "This week"]] as const).map(([id, label]) => (
                  <button key={id} role="tab" aria-selected={mode === id}
                    onClick={() => { editor.cancel(); setMode(id); }}
                    className={clsx("rounded-md px-3 py-1.5 text-sm transition",
                      mode === id ? "bg-accent-soft font-medium text-accent-text" : "text-muted hover:text-text")}>
                    {label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <EditBar
            editor={editor}
            college={college}
            hint={HINTS[role ?? "student"][mode]}
          />
          {mode === "week" ? (
            weekView ? (
              <TimetableGrid college={college} timetable={weekView.timetable} view={view} entityId={entityId}
                dayLabels={weekView.dayLabels} meta={weekView.meta}
                onSelect={isStudent ? undefined : (s) => {
                  const occ = weekView.byDisplayId.get(s.id) ?? null;
                  // Teachers can change only their own lectures; staff any (the server checks too).
                  if (occ && (isStaff(role) || occ.session.teacher_id === member?.teacher_id)) setSelected(occ);
                  else if (occ) editor.setToast({ text: "You can only change your own lectures.", tone: "danger" });
                }} />
            ) : (
              <Skeleton className="h-[520px] w-full" />
            )
          ) : (
            <TimetableGrid college={college} timetable={data.timetable} view={view} entityId={entityId}
              edit={canDrag && editor.edit ? {
                ...editor.edit,
                onPick: (s) => isTeacher && s.teacher_id !== member?.teacher_id
                  ? editor.setToast({ text: "You can only ask to move your own lectures.", tone: "danger" })
                  : editor.edit!.onPick(s),
              } : undefined} />
          )}
          {selected && week && (
            <OneDayPanel occurrence={selected} days={week.days} college={college} onDone={onOneDayDone}
              onClose={() => setSelected(null)} />
          )}
        </>
      )}
    </div>
  );
}

const HINTS: Record<string, Record<"plan" | "week", string | undefined>> = {
  admin: {
    plan: undefined,
    week: "Real dates. Click a class to cancel or reschedule it for that day only. The weekly plan stays as it is.",
  },
  coordinator: {
    plan: undefined,
    week: "Real dates. Click a class to cancel or reschedule it for that day only. The weekly plan stays as it is.",
  },
  teacher: {
    plan: "Your usual week. Click one of your lectures, then a green or amber slot, to ask your Department Coordinator for a permanent move. For a one-day change, open This week.",
    week: "Click one of your lectures to cancel it or move it for that day. Students see the change straight away.",
  },
  student: {
    plan: "Your usual weekly timetable.",
    week: "Your classes this week, including any one-day changes by your teachers.",
  },
};

function studentLabel(
  college: NonNullable<ReturnType<typeof useTimetable>["college"]>,
  member: ReturnType<typeof useAuth>["member"],
): string {
  const sec = college.sections.find((x) => x.id === member?.section_id);
  const batch = sec?.batches.find((b) => b.id === member?.batch_id);
  return sec ? `${sec.name}${batch ? ` · lab batch ${batch.name}` : ""}` : "";
}

function EditBar({
  editor,
  college,
  hint,
}: {
  editor: ReturnType<typeof useMoveEditor>;
  college: NonNullable<ReturnType<typeof useTimetable>["college"]>;
  hint?: string;
}) {
  const {
    moving, options, busy, proposal, apply, discard, cancel, undo, toast, setToast, moveRequest, sendRequest, closeRequest,
  } = editor;
  const subject = moving ? college.subjects.find((s) => s.id === moving.subject_id)?.name : null;
  const counts = options
    ? [...options.values()].reduce((a, o) => ({ ...a, [o.status]: (a[o.status] ?? 0) + 1 }), {} as Record<string, number>)
    : null;
  return (
    <>
      <div className="no-print mb-3 sm:min-h-[44px]" aria-live="polite">
        {moving ? (
          <div className="flex flex-wrap items-center gap-3 rounded-lg border border-accent/30 bg-accent-soft px-4 py-2.5 text-sm text-accent-text">
            {busy || !options ? <Loader2 size={16} className="animate-spin" aria-hidden /> : <Move size={16} aria-hidden />}
            <span>
              Moving <b>{subject}</b> ({moving.day} {moving.start}).{" "}
              {busy ? "Finding the best way to fit it…" : "Drop it on a highlighted slot, or click one."}
            </span>
            {counts && !busy && (
              <span className="flex gap-3 text-xs">
                <span><i className="mr-1 inline-block h-2.5 w-2.5 rounded-sm bg-ok/70" />{counts.free ?? 0} free</span>
                <span><i className="mr-1 inline-block h-2.5 w-2.5 rounded-sm bg-warn/70" />{counts.repair ?? 0} other classes move</span>
                <span><i className="mr-1 inline-block h-2.5 w-2.5 rounded-sm bg-danger/50" />{counts.blocked ?? 0} blocked</span>
              </span>
            )}
            <button onClick={cancel} className="ml-auto inline-flex items-center gap-1 rounded px-2 py-1 text-xs hover:bg-accent/10">
              <X size={14} aria-hidden /> Cancel (Esc)
            </button>
          </div>
        ) : (
          <p className="hidden px-1 py-3 text-xs text-muted sm:block">
            {hint ?? <>Tip: drag any class to a new slot, or click it and then click a slot. Green = free, amber = other classes
            will move to make room, red = not allowed. You always see the result before it&apos;s applied.</>}
          </p>
        )}
      </div>

      {proposal && <ProposalDialog proposal={proposal} busy={busy} onApply={apply} onDiscard={discard} />}
      {moveRequest && (
        <RequestDialog request={moveRequest} subject={subject ?? ""} busy={busy} onSend={sendRequest}
          onClose={closeRequest} />
      )}

      {toast && (
        <div
          className={clsx(
            "fixed bottom-5 left-1/2 z-50 flex -translate-x-1/2 items-center gap-3 rounded-lg px-4 py-3 text-sm shadow-lg",
            toast.tone === "danger" ? "bg-danger text-white" : "bg-text text-bg",
          )}
          role="status"
        >
          {toast.text}
          {toast.undo && (
            <button onClick={() => { setToast(null); undo(); }} className="inline-flex items-center gap-1 font-semibold underline-offset-2 hover:underline">
              <Undo2 size={14} aria-hidden /> Undo
            </button>
          )}
          <button onClick={() => setToast(null)} aria-label="Dismiss" className="opacity-70 hover:opacity-100">
            <X size={14} />
          </button>
        </div>
      )}
    </>
  );
}

function EmptyState() {
  const { role } = useAuth();
  if (role !== "admin") {
    return (
      <Card className="flex flex-col items-center px-6 py-16 text-center">
        <h2 className="text-lg font-semibold">{isStaff(role) ? "No timetable yet" : "Not published yet"}</h2>
        <p className="mt-2 max-w-md text-sm text-muted">
          {isStaff(role)
            ? "Your College Admin hasn't generated the timetable yet. Check back soon."
            : "Your timetable appears here as soon as the College Admin publishes it. You'll get a notification."}
        </p>
      </Card>
    );
  }
  return (
    <Card className="flex flex-col items-center px-6 py-16 text-center">
      <h2 className="text-lg font-semibold">No timetable yet</h2>
      <p className="mt-2 max-w-md text-sm text-muted">
        Your college data is loaded. Generate a timetable: every class gets a slot, a teacher and a room with no clashes,
        then you can view it by section, teacher or room.
      </p>
      <div className="mt-6">
        <GenerateButton />
      </div>
    </Card>
  );
}

/** Draft or published: staff always know whether teachers and students can see what's on screen. */
function PublishStatus({ data }: { data: TimetableOut }) {
  const { published_at, published_by } = data.timetable;
  if (published_at) {
    const when = new Date(published_at * 1000).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
    return (
      <p className="no-print mb-3 flex items-center gap-2 text-xs text-muted" role="status">
        <CheckCircle2 size={14} className="text-ok" aria-hidden /> Published {when} by {published_by}. Changes reach
        teachers and students straight away.
      </p>
    );
  }
  return (
    <div className="no-print mb-4 rounded-xl border border-accent/30 bg-accent-soft px-4 py-3 text-sm text-accent-text" role="status">
      <b>Draft:</b>{" "}
      {data.ever_published
        ? "teachers and students still see the previously published timetable. Publish this one to replace it."
        : "teachers and students can't see it yet. Review it, then Publish."}
    </div>
  );
}
