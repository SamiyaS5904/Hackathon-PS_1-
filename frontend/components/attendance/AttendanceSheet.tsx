"use client";

import clsx from "clsx";
import { Check, Loader2, Search, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import type { ClassAttendance } from "@/lib/types";

/** Take attendance for one class on one date. Everyone starts present: tap the ones who aren't there. */
export function AttendanceSheet({ sessionId, date, onClose, onSaved }: {
  sessionId: string; date: string; onClose: () => void; onSaved?: (c: ClassAttendance) => void;
}) {
  const [sheet, setSheet] = useState<ClassAttendance | null>(null);
  const [absent, setAbsent] = useState<Set<string>>(new Set());
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api.classAttendance(sessionId, date)
      .then((c) => { setSheet(c); setAbsent(new Set(c.absent)); })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Couldn't open the class"));
  }, [sessionId, date]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (sheet?.roster ?? []).filter((s) => !q || s.roll_no.toLowerCase().includes(q) || s.name.toLowerCase().includes(q));
  }, [sheet, query]);

  const toggle = (id: string) => {
    if (!sheet?.can_edit) return;
    setSaved(false);
    setAbsent((cur) => {
      const next = new Set(cur);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const save = async () => {
    if (!sheet) return;
    setBusy(true);
    setError(null);
    try {
      const out = await api.saveAttendance(sheet.session_id, sheet.date, [...absent]);
      setSheet(out);
      setSaved(true);
      onSaved?.(out);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't save attendance");
    } finally {
      setBusy(false);
    }
  };

  const total = sheet?.roster.length ?? 0;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 sm:items-center sm:p-4" role="dialog"
      aria-modal="true" aria-labelledby="att-title">
      <div className="flex max-h-[92vh] w-full max-w-lg flex-col rounded-t-2xl border border-border bg-surface shadow-xl sm:rounded-xl">
        <div className="flex items-start justify-between gap-3 border-b border-border px-5 py-4">
          <div>
            <h2 id="att-title" className="font-semibold">{sheet ? `Attendance · ${sheet.subject}` : "Attendance"}</h2>
            {sheet && (
              <p className="mt-0.5 text-sm text-muted">
                {sheet.sections} · {new Date(sheet.date).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" })}
                {" "}· {sheet.start}–{sheet.end}{sheet.venue ? ` · ${sheet.venue}` : ""}
              </p>
            )}
          </div>
          <button onClick={onClose} aria-label="Close" className="rounded p-1.5 text-muted hover:bg-surface-2"><X size={18} /></button>
        </div>

        {!sheet && !error && (
          <p className="flex items-center gap-2 px-5 py-8 text-sm text-muted"><Loader2 size={16} className="animate-spin" /> Opening the class…</p>
        )}

        {sheet && (
          <>
            <div className="flex flex-wrap items-center gap-3 px-5 pt-4 text-sm">
              <span><b className="text-ok">{total - absent.size}</b> present</span>
              <span><b className={absent.size ? "text-danger" : ""}>{absent.size}</b> absent</span>
              <span className="text-muted">of {total}</span>
              {sheet.can_edit && absent.size > 0 && (
                <button className="ml-auto text-xs text-accent-text hover:underline" onClick={() => { setAbsent(new Set()); setSaved(false); }}>
                  Mark everyone present
                </button>
              )}
            </div>
            {!sheet.can_edit && <p className="mx-5 mt-3 rounded-lg bg-surface-2 px-3 py-2 text-xs text-muted">{sheet.note}</p>}
            <label className="mx-5 mt-3 flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm">
              <Search size={15} className="text-muted" aria-hidden />
              <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Find a roll number or name"
                aria-label="Find a student" className="w-full bg-transparent outline-none" />
            </label>
            <p className="px-5 pt-2 text-xs text-muted">Everyone is present by default. Tap a student to mark them absent.</p>
            <ul className="mt-2 flex-1 overflow-y-auto px-3 pb-3">
              {shown.map((s) => {
                const away = absent.has(s.student_id);
                return (
                  <li key={s.student_id}>
                    <button onClick={() => toggle(s.student_id)} disabled={!sheet.can_edit} aria-pressed={away}
                      className={clsx("flex w-full items-center gap-3 rounded-lg px-2 py-2 text-left text-sm transition",
                        sheet.can_edit && "hover:bg-surface-2", away && "bg-danger-soft")}>
                      <span className="w-12 shrink-0 font-mono text-xs text-muted">{s.roll_no}</span>
                      <span className={clsx("flex-1 truncate", away && "text-danger")}>{s.name}</span>
                      <span className={clsx("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
                        away ? "bg-danger text-white" : "bg-ok-soft text-ok")}>
                        {away ? <><X size={12} aria-hidden /> Absent</> : <><Check size={12} aria-hidden /> Present</>}
                      </span>
                    </button>
                  </li>
                );
              })}
              {shown.length === 0 && <li className="px-2 py-6 text-center text-sm text-muted">No student matches “{query}”.</li>}
            </ul>
          </>
        )}

        <div className="flex items-center justify-between gap-3 border-t border-border px-5 py-3">
          <span className="text-xs text-muted" role="status">
            {error ? <span className="text-danger">{error}</span>
              : saved ? "Saved. Students see it in My attendance."
                : sheet?.marked ? `Last saved by ${sheet.marked_by}` : "Not saved yet"}
          </span>
          {sheet?.can_edit && (
            <Button variant="primary" onClick={save} disabled={busy}>
              {busy && <Loader2 size={16} className="animate-spin" aria-hidden />} {sheet.marked ? "Save changes" : "Save attendance"}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
