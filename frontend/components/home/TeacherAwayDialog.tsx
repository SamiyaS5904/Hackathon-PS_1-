"use client";

import { CalendarX2, Loader2, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useChatPage } from "@/lib/chat-context";
import { useTimetable } from "@/lib/timetable-context";
import { useToast } from "@/lib/toast";
import type { Occurrence } from "@/lib/types";

const pad = (n: number) => String(n).padStart(2, "0");
const iso = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const input = "w-full rounded-lg border border-border-strong bg-surface px-2.5 py-1.5 text-sm";

function mondayOf(d: string): string {
  const x = new Date(`${d}T00:00`);
  x.setDate(x.getDate() - ((x.getDay() + 6) % 7));
  return iso(x);
}
const day = (d: string) => new Date(`${d}T00:00`).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" });

/** A teacher is away for one or more days: see their classes, cancel them in one step and tell everyone.
 *  (Phase 2 adds substitutes and swaps; the assistant can already help.) */
export function TeacherAwayDialog({ onClose, onDone, teacherId: initial }: {
  onClose: () => void;
  onDone: () => void;
  teacherId?: string;
}) {
  const { college, data, setData } = useTimetable();
  const { role, member } = useAuth();
  const { prefill } = useChatPage();
  const showToast = useToast();

  // Next working day (today if it is one).
  const firstDay = useMemo(() => {
    const d = new Date();
    for (let i = 0; i < 14; i++) {
      const x = new Date(d);
      x.setDate(d.getDate() + i);
      if (college?.days.includes(WEEKDAYS[x.getDay()])) return iso(x);
    }
    return iso(d);
  }, [college]);

  const ownSections = useMemo(() => new Set(role === "coordinator"
    ? (college?.sections ?? []).filter((s) => s.department_id === member?.department_id).map((s) => s.id) : []), [college, role, member]);
  const teachers = useMemo(() => {
    const all = [...(college?.teachers ?? [])].sort((a, b) => a.name.localeCompare(b.name));
    if (role !== "coordinator") return all;
    const teachesOwn = new Set((data?.timetable.sessions ?? []).filter((s) => s.section_ids.some((id) => ownSections.has(id)))
      .map((s) => s.teacher_id));
    return all.filter((t) => t.department_id === member?.department_id || teachesOwn.has(t.id));
  }, [college, data, role, member, ownSections]);

  const [teacherId, setTeacherId] = useState(initial ?? "");
  const [from, setFrom] = useState(firstDay);
  const [to, setTo] = useState(firstDay);
  const [reason, setReason] = useState("On leave");
  const [classes, setClasses] = useState<Occurrence[] | null>(null);
  const [skip, setSkip] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  // The teacher's classes on those dates (as they really happen: one-day changes included).
  useEffect(() => {
    if (!teacherId || !from || !to || to < from) {
      setClasses(null);
      return;
    }
    let live = true;
    setClasses(null);
    setError(null);
    const weeks: string[] = [];
    for (let m = mondayOf(from); m <= to && weeks.length < 3; ) {
      weeks.push(m);
      const x = new Date(`${m}T00:00`);
      x.setDate(x.getDate() + 7);
      m = iso(x);
    }
    Promise.all(weeks.map((w) => api.week(w)))
      .then((list) => {
        if (!live) return;
        setClasses(list.flatMap((w) => w.occurrences)
          .filter((o) => o.session.teacher_id === teacherId && o.status === "normal" && o.date >= from && o.date <= to)
          .sort((a, b) => (a.date + a.session.start).localeCompare(b.date + b.session.start)));
        setSkip(new Set());
      })
      .catch((e) => live && setError(e instanceof Error ? e.message : "Couldn't load the classes"));
    return () => { live = false; };
  }, [teacherId, from, to]);

  const canChange = (o: Occurrence) => role !== "coordinator" || o.session.section_ids.every((id) => ownSections.has(id));
  const chosen = (classes ?? []).filter((o) => canChange(o) && !skip.has(o.occurrence_id));
  const teacher = teachers.find((t) => t.id === teacherId)?.name ?? "";
  const subject = (id: string) => college?.subjects.find((s) => s.id === id)?.name ?? "";
  const section = (id: string) => college?.sections.find((s) => s.id === id)?.name ?? "";
  const dates = from === to ? day(from) : `${day(from)} to ${day(to)}`;

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const out = await api.batchOverrides({
        title: `${teacher} away ${dates}: ${chosen.length} class${chosen.length === 1 ? "" : "es"} cancelled`,
        changes: chosen.map((o) => ({ session_id: o.session.id, date: o.date, kind: "cancel", reason })),
      });
      setData(out.timetable);
      showToast({ text: out.message, undoEntryId: out.timetable.last_change?.id, onUndone: (t) => { setData(t); onDone(); } });
      onDone();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't save the changes");
    } finally {
      setBusy(false);
    }
  };

  const askAssistant = () => {
    prefill(`${teacher || "A teacher"} is away ${dates}${reason ? ` (${reason.toLowerCase()})` : ""}. Find who can cover `
      + "each class, or a makeup time, and prepare the changes.");
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4" role="dialog" aria-modal="true" aria-labelledby="away-title">
      <div className="flex max-h-[90vh] w-full max-w-lg flex-col rounded-xl border border-border bg-surface shadow-xl">
        <div className="border-b border-border px-5 py-4">
          <h2 id="away-title" className="font-semibold">A teacher is away</h2>
          <p className="mt-1 text-sm text-muted">Cancel their classes for those days in one step. Students, the teacher and the Coordinator are told.</p>
        </div>
        <div className="space-y-3 overflow-auto px-5 py-4">
          <label className="block text-xs text-muted">Teacher
            <select autoFocus aria-label="Teacher" className={`${input} mt-1`} value={teacherId} onChange={(e) => setTeacherId(e.target.value)}>
              <option value="">Choose a teacher…</option>
              {teachers.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          </label>
          <div className="grid grid-cols-2 gap-2">
            <label className="text-xs text-muted">From
              <input type="date" aria-label="From" className={`${input} mt-1`} value={from}
                onChange={(e) => { setFrom(e.target.value); if (to < e.target.value) setTo(e.target.value); }} />
            </label>
            <label className="text-xs text-muted">To
              <input type="date" aria-label="To" className={`${input} mt-1`} value={to} min={from} onChange={(e) => setTo(e.target.value)} />
            </label>
          </div>
          <label className="block text-xs text-muted">Reason (shown to students)
            <input aria-label="Reason" className={`${input} mt-1`} value={reason} maxLength={120} onChange={(e) => setReason(e.target.value)} />
          </label>

          {teacherId && (
            classes === null ? (
              <p className="flex items-center gap-2 text-sm text-muted"><Loader2 size={14} className="animate-spin" aria-hidden /> Finding their classes…</p>
            ) : classes.length === 0 ? (
              <p className="text-sm text-muted">{teacher} has no classes on {dates}. Nothing to cancel.</p>
            ) : (
              <ul className="divide-y divide-border rounded-lg border border-border">
                {classes.map((o) => {
                  const ok = canChange(o);
                  return (
                    <li key={o.occurrence_id} className="flex items-center gap-3 px-3 py-2 text-sm">
                      <input type="checkbox" aria-label={`Cancel ${subject(o.session.subject_id)} on ${day(o.date)}`} disabled={!ok}
                        checked={ok && !skip.has(o.occurrence_id)}
                        onChange={() => setSkip((s) => { const n = new Set(s); if (n.has(o.occurrence_id)) n.delete(o.occurrence_id); else n.add(o.occurrence_id); return n; })} />
                      <span className="min-w-0 flex-1">
                        <span className="font-medium">{subject(o.session.subject_id)}</span>{" "}
                        <span className="text-muted">{o.session.section_ids.map(section).join(" + ")}</span>
                        <span className="block text-xs text-muted">{day(o.date)} · {o.session.start}-{o.session.end}
                          {!ok && " · another department's class: ask the College Admin"}</span>
                      </span>
                    </li>
                  );
                })}
              </ul>
            )
          )}
          {error && <p role="alert" className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}
        </div>
        <div className="flex flex-wrap items-center gap-2 border-t border-border px-5 py-3">
          <button onClick={askAssistant} className="mr-auto inline-flex items-center gap-1.5 text-sm text-accent-text hover:underline">
            <Sparkles size={14} aria-hidden /> Find substitutes with the assistant
          </button>
          <Button onClick={onClose}>Close</Button>
          <Button variant="primary" onClick={submit} disabled={busy || chosen.length === 0}>
            {busy ? <Loader2 size={16} className="animate-spin" aria-hidden /> : <CalendarX2 size={16} aria-hidden />}
            Cancel {chosen.length || ""} class{chosen.length === 1 ? "" : "es"} and notify
          </Button>
        </div>
      </div>
    </div>
  );
}
