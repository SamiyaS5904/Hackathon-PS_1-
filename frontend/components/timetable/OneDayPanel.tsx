"use client";

import clsx from "clsx";
import { CalendarClock, CalendarPlus, Loader2, RotateCcw, X, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui";
import { api } from "@/lib/api";
import type { College, DayInfo, MakeupOption, MoveOption, Occurrence, OverrideOut } from "@/lib/types";

/** Change one class on one real date: cancel it, move it (free slots only), find a makeup time, or restore it. */
export function OneDayPanel({
  occurrence: occ,
  days,
  college,
  onDone,
  onClose,
}: {
  occurrence: Occurrence;
  days: DayInfo[];
  college: College;
  onDone: (out: OverrideOut) => void;
  onClose: () => void;
}) {
  const s = occ.session;
  const subject = college.subjects.find((x) => x.id === s.subject_id);
  const teacher = college.teachers.find((x) => x.id === s.teacher_id);
  const venue = college.venues.find((x) => x.id === s.venue_id);
  const sections = s.section_ids.map((id) => college.sections.find((x) => x.id === id)?.name).join(" + ");
  const dayLabel = days.find((d) => d.date === occ.date)?.label ?? occ.date;

  const [mode, setMode] = useState<"menu" | "cancel" | "move" | "makeup">("menu");
  const [makeups, setMakeups] = useState<MakeupOption[] | null>(null);
  const [makeup, setMakeup] = useState<MakeupOption | null>(null);
  const [reason, setReason] = useState("");
  const [toDate, setToDate] = useState(occ.date);
  const [options, setOptions] = useState<MoveOption[] | null>(null);
  const [picked, setPicked] = useState<MoveOption | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  useEffect(() => {
    if (mode !== "move") return;
    setOptions(null);
    setPicked(null);
    api
      .dayOptions(s.id, occ.date, toDate)
      .then(setOptions)
      .catch((e) => setError(e instanceof Error ? e.message : "Couldn't load free times"));
  }, [mode, toDate, s.id, occ.date]);

  useEffect(() => {
    if (mode !== "makeup") return;
    setMakeups(null);
    setMakeup(null);
    api.makeup(s.id, occ.date).then(setMakeups)
      .catch((e) => setError(e instanceof Error ? e.message : "Couldn't look for makeup times"));
  }, [mode, s.id, occ.date]);

  const run = async (fn: () => Promise<OverrideOut>) => {
    setBusy(true);
    setError(null);
    try {
      onDone(await fn());
    } catch (e) {
      setError(e instanceof Error ? e.message : "That change isn't possible");
    } finally {
      setBusy(false);
    }
  };

  const changed = occ.status !== "normal" && mode !== "makeup";
  const byDay = new Map<string, MakeupOption[]>();
  for (const m of makeups ?? []) byDay.set(m.label, [...(byDay.get(m.label) ?? []), m]);

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-black/30" onClick={onClose}>
      <aside
        className="flex h-full w-full max-w-md flex-col border-l border-border bg-surface shadow-xl"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="oneday-title"
      >
        <div className="flex items-start justify-between border-b border-border px-5 py-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-accent-text">{dayLabel} only</p>
            <h2 id="oneday-title" className="mt-0.5 font-semibold">{subject?.name}</h2>
            <p className="text-sm text-muted">
              {sections} · {s.start}–{s.end} · {venue?.name} · {teacher?.name}
            </p>
          </div>
          <button onClick={onClose} aria-label="Close" className="rounded p-1 text-muted hover:bg-surface-2">
            <X size={18} />
          </button>
        </div>

        <div className="flex-1 overflow-auto px-5 py-4">
          {error && <p className="mb-3 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}

          {changed ? (
            <div>
              <p className="rounded-lg bg-surface-2 px-3 py-2 text-sm">{occ.note}</p>
              <div className="mt-4 flex flex-wrap gap-2">
                {occ.status === "cancelled" && (
                  <Button variant="primary" disabled={busy} onClick={() => setMode("makeup")}>
                    <CalendarPlus size={16} aria-hidden /> Find a makeup class
                  </Button>
                )}
                <Button variant={occ.status === "cancelled" ? "secondary" : "primary"} disabled={busy}
                  onClick={() => occ.override_id && run(() => api.removeOverride(occ.override_id!))}>
                  {busy ? <Loader2 size={16} className="animate-spin" /> : <RotateCcw size={16} />} Restore usual time
                </Button>
              </div>
            </div>
          ) : mode === "menu" ? (
            <div className="space-y-2">
              <p className="mb-3 text-sm text-muted">
                Changes here apply to <b className="text-text">{dayLabel}</b> only. The weekly timetable stays the same.
              </p>
              <button onClick={() => setMode("move")}
                className="flex w-full items-center gap-3 rounded-lg border border-border px-4 py-3 text-left hover:bg-surface-2">
                <CalendarClock size={18} className="text-accent-text" aria-hidden />
                <span>
                  <span className="block text-sm font-medium">Reschedule for this day</span>
                  <span className="text-xs text-muted">Pick a free time this week. Nobody else&apos;s classes move.</span>
                </span>
              </button>
              <button onClick={() => setMode("makeup")}
                className="flex w-full items-center gap-3 rounded-lg border border-border px-4 py-3 text-left hover:bg-surface-2">
                <CalendarPlus size={18} className="text-ok" aria-hidden />
                <span>
                  <span className="block text-sm font-medium">Find a makeup time</span>
                  <span className="text-xs text-muted">Every free time in the next 7 days for the teacher, students and a room.</span>
                </span>
              </button>
              <button onClick={() => setMode("cancel")}
                className="flex w-full items-center gap-3 rounded-lg border border-border px-4 py-3 text-left hover:bg-surface-2">
                <XCircle size={18} className="text-danger" aria-hidden />
                <span>
                  <span className="block text-sm font-medium">Cancel on {dayLabel}</span>
                  <span className="text-xs text-muted">Students see it as cancelled; the room becomes free.</span>
                </span>
              </button>
            </div>
          ) : (
            <div className="space-y-4">
              {mode === "makeup" && (
                !makeups ? (
                  <p className="flex items-center gap-2 text-sm text-muted"><Loader2 size={14} className="animate-spin" /> Looking through the next 7 days…</p>
                ) : makeups.length === 0 ? (
                  <p className="rounded-lg bg-surface-2 px-3 py-3 text-sm text-muted">
                    No time in the next 7 days has the teacher, every student and a suitable room free together.
                    Try a one-day reschedule on a specific date instead.
                  </p>
                ) : (
                  <div>
                    <p className="mb-2 text-sm text-muted">
                      Free for <b className="text-text">{teacher?.name}</b>, <b className="text-text">{sections}</b> and a room. Soonest first.
                    </p>
                    {[...byDay.entries()].map(([dayName, list]) => (
                      <div key={dayName} className="mb-3">
                        <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted">{dayName}</p>
                        <div className="grid grid-cols-2 gap-2">
                          {list.map((m) => (
                            <button key={m.date + m.start_period} onClick={() => setMakeup(m)}
                              className={clsx("rounded-lg border border-ok/40 bg-ok-soft px-3 py-2 text-left text-xs text-ok transition hover:ring-2 hover:ring-ok/40",
                                makeup === m && "ring-2 ring-accent")}>
                              <span className="block font-mono font-medium">{m.start}–{m.end}</span>
                              <span className="text-[11px] opacity-80">{m.venue}</span>
                            </button>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )
              )}
              {mode === "move" && (
                <>
                  <label className="block text-sm">
                    <span className="mb-1 block font-medium">Move to</span>
                    <select value={toDate} onChange={(e) => setToDate(e.target.value)}
                      className="w-full rounded-lg border border-border-strong bg-surface px-3 py-2 text-sm">
                      {days.map((d) => (
                        <option key={d.date} value={d.date}>{d.label}{d.date === occ.date ? " (same day)" : ""}</option>
                      ))}
                    </select>
                  </label>
                  {!options ? (
                    <p className="flex items-center gap-2 text-sm text-muted"><Loader2 size={14} className="animate-spin" /> Finding free times…</p>
                  ) : (
                    <div>
                      <p className="mb-2 text-sm font-medium">
                        Free times <span className="font-normal text-muted">({options.filter((o) => o.status === "free").length})</span>
                      </p>
                      <div className="grid grid-cols-3 gap-2">
                        {options.map((o) => (
                          <button key={o.start_period} disabled={o.status !== "free"} onClick={() => setPicked(o)}
                            title={o.status === "free" ? o.reason || "Free" : o.reason}
                            className={clsx(
                              "rounded-lg border px-2 py-2 font-mono text-xs transition",
                              o.status === "free" ? "border-ok/40 bg-ok-soft text-ok hover:ring-2 hover:ring-ok/40" : "cursor-not-allowed border-border bg-surface-2 text-muted line-through",
                              picked?.start_period === o.start_period && "ring-2 ring-accent",
                            )}>
                            {o.start}–{o.end}
                          </button>
                        ))}
                      </div>
                      {picked?.reason && <p className="mt-2 text-xs text-muted">{picked.reason}</p>}
                      {/* Say why each time is taken (hover tooltips don't exist on phones). Both sections, the
                          teacher and a big-enough room must all be free; one-day changes never move other classes. */}
                      {options.some((o) => o.status !== "free") && (
                        <details className="mt-2 text-xs text-muted" open={options.every((o) => o.status !== "free")}>
                          <summary className="cursor-pointer select-none">Why the other times aren&apos;t free</summary>
                          <ul className="mt-1.5 space-y-0.5">
                            {options.filter((o) => o.status !== "free").map((o) => (
                              <li key={o.start_period}>
                                <span className="font-mono">{o.start}</span> · {o.reason.replace(/^Clashes with /, "busy with ")}
                              </li>
                            ))}
                          </ul>
                        </details>
                      )}
                      {options.every((o) => o.status !== "free") && (
                        <p className="mt-2 text-sm text-muted">No free time that day. Try another day.</p>
                      )}
                    </div>
                  )}
                </>
              )}
              <label className="block text-sm">
                <span className="mb-1 block font-medium">Reason <span className="font-normal text-muted">(shown to students)</span></span>
                <input value={reason} onChange={(e) => setReason(e.target.value)} maxLength={120}
                  placeholder={mode === "cancel" ? "e.g. Teacher at a conference" : mode === "makeup" ? "e.g. Makeup for the class missed on Monday" : "e.g. Guest lecture in the usual slot"}
                  className="w-full rounded-lg border border-border-strong bg-surface px-3 py-2 text-sm" />
              </label>
            </div>
          )}
        </div>

        {(mode === "makeup" || (!changed && mode !== "menu")) && (
          <div className="flex justify-between gap-2 border-t border-border px-5 py-4">
            <Button onClick={() => setMode("menu")} disabled={busy}>Back</Button>
            {mode === "makeup" ? (
              <Button variant="primary" disabled={busy || !makeup}
                onClick={() => makeup && run(() => api.addOverride({
                  session_id: s.id, date: occ.date, kind: "move", to_date: makeup.date, start_period: makeup.start_period,
                  reason: reason || "Makeup class",
                }))}>
                {busy && <Loader2 size={16} className="animate-spin" />}
                {makeup ? `Book makeup · ${makeup.label} ${makeup.start}` : "Pick a time"}
              </Button>
            ) : mode === "cancel" ? (
              <Button variant="primary" disabled={busy}
                onClick={() => run(() => api.addOverride({ session_id: s.id, date: occ.date, kind: "cancel", reason }))}>
                {busy && <Loader2 size={16} className="animate-spin" />} Cancel class on {dayLabel}
              </Button>
            ) : (
              <Button variant="primary" disabled={busy || !picked}
                onClick={() => picked && run(() => api.addOverride({
                  session_id: s.id, date: occ.date, kind: "move", to_date: toDate, start_period: picked.start_period, reason,
                }))}>
                {busy && <Loader2 size={16} className="animate-spin" />} Move for this day
              </Button>
            )}
          </div>
        )}
      </aside>
    </div>
  );
}
