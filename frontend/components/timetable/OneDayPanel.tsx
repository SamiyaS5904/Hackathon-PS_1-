"use client";

import clsx from "clsx";
import { CalendarClock, CalendarPlus, CheckCircle2, Loader2, Repeat, RotateCcw, Send, X, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui";
import { api, extraApi } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { College, DayInfo, MoveOption, Occurrence, OverrideOut, RescheduleOption } from "@/lib/types";
import { AskAssistant } from "./MoveSuggestions";

/** Change one class on one real date. Opens on the finder: every time in the coming days when the teacher, every
 * student and a room are free. Pick one, then move it for that day only, or (teachers) ask to move it every week.
 * Also: cancel for the day, pick a day yourself, or restore a changed class. */
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

  const { role } = useAuth();
  const [mode, setMode] = useState<"find" | "cancel" | "move">("find");
  const [makeups, setMakeups] = useState<RescheduleOption[] | null>(null);
  const [findNote, setFindNote] = useState("");
  const [makeup, setMakeup] = useState<RescheduleOption | null>(null);
  const [sent, setSent] = useState<string | null>(null);
  // A cancelled class shows its note first; "Find a makeup class" opens the finder.
  const [showFinder, setShowFinder] = useState(occ.status === "normal");
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

  const finding = mode === "find" && showFinder;
  useEffect(() => {
    if (!finding) return;
    setMakeups(null);
    setMakeup(null);
    extraApi.reschedule(s.id, occ.date).then((r) => { setMakeups(r.options); setFindNote(r.note); })
      .catch((e) => setError(e instanceof Error ? e.message : "Couldn't look for free times"));
  }, [finding, s.id, occ.date]);

  // Teachers: ask the Department Coordinator to move it for good (same weekday and period, free every week).
  const askEveryWeek = async (o: RescheduleOption) => {
    setBusy(true);
    setError(null);
    try {
      await api.requestChange({ session_id: s.id, day: o.day, start_period: o.start_period, reason });
      setSent(`Request sent: ${subject?.name} every ${o.day} at ${o.start}. Your Department Coordinator checks it and applies it; you and your students are told.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't send the request");
    } finally {
      setBusy(false);
    }
  };

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

  const changed = occ.status !== "normal" && !showFinder;
  const byDay = new Map<string, RescheduleOption[]>();
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

          {sent ? (
            <p className="flex items-start gap-2 rounded-lg bg-ok-soft px-3 py-3 text-sm text-ok">
              <CheckCircle2 size={16} className="mt-0.5 shrink-0" aria-hidden /> {sent}
            </p>
          ) : changed ? (
            <div>
              <p className="rounded-lg bg-surface-2 px-3 py-2 text-sm">{occ.note}</p>
              <div className="mt-4 flex flex-wrap gap-2">
                {occ.status === "cancelled" && (
                  <Button variant="primary" disabled={busy}
                    onClick={() => { setShowFinder(true); setMode("find"); setReason("Makeup class"); }}>
                    <CalendarPlus size={16} aria-hidden /> Find a makeup class
                  </Button>
                )}
                <Button variant={occ.status === "cancelled" ? "secondary" : "primary"} disabled={busy}
                  onClick={() => occ.override_id && run(() => api.removeOverride(occ.override_id!))}>
                  {busy ? <Loader2 size={16} className="animate-spin" /> : <RotateCcw size={16} />} Restore usual time
                </Button>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              {mode === "find" && (
                !makeups ? (
                  <p className="flex items-center gap-2 text-sm text-muted"><Loader2 size={14} className="animate-spin" /> Looking for times when everyone is free…</p>
                ) : makeups.length === 0 ? (
                  <p className="rounded-lg bg-surface-2 px-3 py-3 text-sm text-muted">{findNote}</p>
                ) : (
                  <div>
                    <p className="mb-2 text-sm text-muted">
                      Free for <b className="text-text">{teacher?.name}</b>, every student of <b className="text-text">{sections}</b> and
                      a room. Soonest first. <Repeat size={12} className="inline text-accent-text" aria-label="free every week" /> = free every week too.
                    </p>
                    {[...byDay.entries()].map(([dayName, list]) => (
                      <div key={dayName} className="mb-3">
                        <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted">{dayName}</p>
                        <div className="grid grid-cols-2 gap-2">
                          {list.map((m) => (
                            <button key={m.date + m.start_period} onClick={() => setMakeup(m)} aria-pressed={makeup === m}
                              className={clsx("rounded-lg border border-ok/40 bg-ok-soft px-3 py-2 text-left text-xs text-ok transition hover:ring-2 hover:ring-ok/40",
                                makeup === m && "ring-2 ring-accent")}>
                              <span className="flex items-center gap-1 font-mono font-medium">
                                {m.start}–{m.end}
                                {m.every_week && <Repeat size={11} className="text-accent-text" aria-label="free every week" />}
                              </span>
                              <span className="text-[11px] opacity-80">{m.venue}</span>
                            </button>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )
              )}
              {mode === "find" && makeups && (
                <AskAssistant before={onClose} label={makeups.length ? "None of these suits? Ask the assistant" : "Ask the assistant to find a way"}
                  text={`Find a time to move ${subject?.name ?? "this class"} (${sections}) from ${dayLabel} ${s.start}. `
                    + "The teacher, every student and a room must be free."} />
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
              {mode === "cancel" && (
                <p className="text-sm text-muted">
                  Students see {subject?.name} as cancelled on <b className="text-text">{dayLabel}</b> and the room becomes
                  free. The weekly timetable stays the same.
                </p>
              )}
              <label className="block text-sm">
                <span className="mb-1 block font-medium">Reason <span className="font-normal text-muted">(shown to students)</span></span>
                <input value={reason} onChange={(e) => setReason(e.target.value)} maxLength={120}
                  placeholder={mode === "cancel" ? "e.g. Teacher at a conference" : "e.g. Guest lecture in the usual slot"}
                  className="w-full rounded-lg border border-border-strong bg-surface px-3 py-2 text-sm" />
              </label>
              {mode === "find" && occ.status === "normal" && (
                <div className="flex flex-wrap gap-x-4 gap-y-1 border-t border-border pt-3 text-xs">
                  <button onClick={() => setMode("move")} className="inline-flex items-center gap-1 text-muted hover:text-text">
                    <CalendarClock size={13} aria-hidden /> Pick a day this week yourself
                  </button>
                  <button onClick={() => setMode("cancel")} className="inline-flex items-center gap-1 text-danger hover:underline">
                    <XCircle size={13} aria-hidden /> Cancel on {dayLabel}
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        {sent ? (
          <div className="flex justify-end border-t border-border px-5 py-4">
            <Button onClick={onClose}>Close</Button>
          </div>
        ) : !changed && (
          <div className="flex flex-wrap justify-between gap-2 border-t border-border px-5 py-4">
            {mode !== "find" ? <Button onClick={() => setMode("find")} disabled={busy}>Back</Button> : <span />}
            {mode === "find" ? (
              <div className="flex flex-wrap justify-end gap-2">
                {role === "teacher" && occ.status === "normal" && makeup?.every_week && (
                  <Button disabled={busy} onClick={() => askEveryWeek(makeup)}
                    title="Your Department Coordinator approves permanent changes">
                    <Send size={15} aria-hidden /> Ask: every {makeup.day}
                  </Button>
                )}
                <Button variant="primary" disabled={busy || !makeup}
                  onClick={() => makeup && run(() => api.addOverride({
                    session_id: s.id, date: occ.date, kind: "move", to_date: makeup.date, start_period: makeup.start_period,
                    reason: reason || (occ.status === "cancelled" ? "Makeup class" : ""),
                  }))}>
                  {busy && <Loader2 size={16} className="animate-spin" />}
                  {makeup ? `Move to ${makeup.label} ${makeup.start} only` : "Pick a time"}
                </Button>
              </div>
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
