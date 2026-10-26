"use client";

import { Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui";
import { LeavePlanView } from "@/components/leave/LeavePlanView";
import { useAuth } from "@/lib/auth";
import { useChatPage } from "@/lib/chat-context";
import { useTimetable } from "@/lib/timetable-context";
import type { Leave } from "@/lib/types";

const pad = (n: number) => String(n).padStart(2, "0");
const iso = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const input = "w-full rounded-lg border border-border-strong bg-surface px-2.5 py-1.5 text-sm";

const day = (d: string) => new Date(`${d}T00:00`).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" });

/** A teacher is away (leave): pick the teacher and dates, then the cover plan shows every class with a
 *  ranked substitute (or cancel, per year). Apply goes validator -> apply -> activity log -> notifications. */
export function TeacherAwayDialog({ onClose, onDone, teacherId: initial, leave }: {
  onClose: () => void;
  onDone: () => void;
  teacherId?: string;
  leave?: Leave; // an asked-for leave being planned
}) {
  const { college, data } = useTimetable();
  const { role, member } = useAuth();
  const { prefill } = useChatPage();

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

  const teachers = useMemo(() => {
    const all = [...(college?.teachers ?? [])].sort((a, b) => a.name.localeCompare(b.name));
    return role === "coordinator" ? all.filter((t) => t.department_id === member?.department_id) : all;
  }, [college, role, member]);

  const [teacherId, setTeacherId] = useState(leave?.teacher_id ?? initial ?? "");
  const [from, setFrom] = useState(leave?.start_date ?? firstDay);
  const [to, setTo] = useState(leave?.end_date ?? firstDay);
  const [reason, setReason] = useState(leave?.reason || "On leave");

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const teacher = teachers.find((t) => t.id === teacherId)?.name ?? leave?.teacher_name ?? "";
  const dates = from === to ? day(from) : `${day(from)} to ${day(to)}`;

  const askAssistant = () => {
    prefill(`${teacher || "A teacher"} is away ${dates}${reason ? ` (${reason.toLowerCase()})` : ""}. Plan cover for `
      + "their classes: substitutes where possible.");
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4" role="dialog" aria-modal="true" aria-labelledby="away-title">
      <div className="flex max-h-[90vh] w-full max-w-2xl flex-col rounded-xl border border-border bg-surface shadow-xl">
        <div className="border-b border-border px-5 py-4">
          <h2 id="away-title" className="font-semibold">{leave ? `Plan cover: ${leave.teacher_name}` : "A teacher is away"}</h2>
          <p className="mt-1 text-sm text-muted">Each class gets a free teacher who teaches the subject (or a colleague), or is cancelled. Choose per year; change any class. Nothing changes until you apply.</p>
        </div>
        <div className="space-y-3 overflow-auto px-5 py-4">
          {!leave && (
            <>
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
            </>
          )}
          {leave && <p className="text-sm text-muted">{dates}{leave.reason ? ` · ${leave.reason}` : ""}</p>}
          {teacherId && data && <LeavePlanView key={`${teacherId}${from}${to}`} teacherId={teacherId} from={from} to={to}
            reason={reason} leaveId={leave?.id} onApplied={() => onDone()} />}
        </div>
        <div className="flex flex-wrap items-center gap-2 border-t border-border px-5 py-3">
          <button onClick={askAssistant} className="mr-auto inline-flex items-center gap-1.5 text-sm text-accent-text hover:underline">
            <Sparkles size={14} aria-hidden /> Plan it with the assistant
          </button>
          <Button onClick={onClose}>Close</Button>
        </div>
      </div>
    </div>
  );
}
