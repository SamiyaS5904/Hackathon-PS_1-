"use client";

import clsx from "clsx";
import { CheckCircle2, Loader2, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { FormError } from "@/components/Field";
import { Button, Card } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useTimetable } from "@/lib/timetable-context";
import type { BookingSlot } from "@/lib/types";

const input = "rounded-lg border border-border-strong bg-surface px-2.5 py-1.5 text-sm";

/** Coordinator / Admin: choose teachers, find times when all of them are free, book a meeting. */
export function MeetingPlanner({ onBooked, preset }: { onBooked: () => void; preset?: string[] }) {
  const { college } = useTimetable();
  const { member, role } = useAuth();
  const [chosen, setChosen] = useState<string[]>(preset ?? []);
  const [query, setQuery] = useState("");
  const [days, setDays] = useState(7);
  const [periods, setPeriods] = useState(1);
  const [slots, setSlots] = useState<BookingSlot[] | null>(null);
  const [picked, setPicked] = useState<BookingSlot | null>(null);
  const [title, setTitle] = useState("");
  const [place, setPlace] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  useEffect(() => {
    if (preset?.length) {
      setChosen(preset);
      setSlots(null);
    }
  }, [preset]);

  const depts = useMemo(() => Object.fromEntries((college?.departments ?? []).map((d) => [d.id, d.short])), [college]);
  // A Coordinator plans with their own department's teachers; the Admin with anyone.
  const teachers = useMemo(() => (college?.teachers ?? [])
    .filter((t) => role !== "coordinator" || t.department_id === member?.department_id)
    .filter((t) => !query || `${t.name} ${depts[t.department_id] ?? ""}`.toLowerCase().includes(query.toLowerCase()))
    .sort((a, b) => a.name.localeCompare(b.name)), [college, role, member, query, depts]);
  const names = useMemo(() => Object.fromEntries((college?.teachers ?? []).map((t) => [t.id, t.name])), [college]);

  const toggle = (id: string) => {
    setChosen((c) => (c.includes(id) ? c.filter((x) => x !== id) : [...c, id]));
    setSlots(null);
    setPicked(null);
    setDone(null);
  };

  const find = async () => {
    setBusy(true);
    setError(null);
    setPicked(null);
    setDone(null);
    try {
      setSlots(await api.meetingTimes({ teacher_ids: chosen, days, periods }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't find times");
    } finally {
      setBusy(false);
    }
  };

  const book = async () => {
    if (!picked) return;
    setBusy(true);
    setError(null);
    try {
      const r = await api.bookMeeting({ teacher_ids: chosen, date: picked.date, start: picked.start, end: picked.end, title, place });
      setDone(r.message);
      setSlots(null);
      setPicked(null);
      setTitle("");
      onBooked();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't book");
    } finally {
      setBusy(false);
    }
  };

  const byDate = (slots ?? []).reduce<Record<string, BookingSlot[]>>((acc, s) => {
    (acc[s.label] ??= []).push(s);
    return acc;
  }, {});

  return (
    <Card className="p-5">
      <h2 className="font-semibold">Plan a meeting</h2>
      <p className="mt-1 text-sm text-muted">
        Pick the teachers. You get the times when every one of them is free (no class, no blocked time, no other
        booking) inside their working hours. They are notified when you book.
      </p>

      <div className="mt-4">
        <div className="flex items-center gap-2 rounded-lg border border-border-strong px-2.5 py-1.5">
          <Search size={14} className="text-muted" aria-hidden />
          <input className="w-full bg-transparent text-sm outline-none" placeholder="Search teachers" value={query}
            onChange={(e) => setQuery(e.target.value)} aria-label="Search teachers" />
        </div>
        <div className="mt-2 max-h-48 overflow-y-auto rounded-lg border border-border p-1">
          {teachers.length === 0 && <p className="p-2 text-sm text-muted">No teachers match.</p>}
          {teachers.map((t) => (
            <label key={t.id} className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-surface-2">
              <input type="checkbox" checked={chosen.includes(t.id)} onChange={() => toggle(t.id)} />
              <span className="flex-1">{t.name}</span>
              <span className="text-xs text-muted">{depts[t.department_id]}</span>
            </label>
          ))}
        </div>
        {chosen.length > 0 && (
          <p className="mt-2 text-xs text-muted">Chosen: {chosen.map((id) => names[id] ?? id).join(", ")}</p>
        )}
      </div>

      <div className="mt-4 flex flex-wrap items-end gap-2">
        <label className="text-xs text-muted">Within
          <select aria-label="Within" className={`${input} mt-1 block`} value={days} onChange={(e) => { setDays(Number(e.target.value)); setSlots(null); }}>
            <option value={7}>Next 7 days</option>
            <option value={14}>Next 14 days</option>
          </select>
        </label>
        <label className="text-xs text-muted">Length
          <select aria-label="Length" className={`${input} mt-1 block`} value={periods} onChange={(e) => { setPeriods(Number(e.target.value)); setSlots(null); }}>
            <option value={1}>1 period</option>
            <option value={2}>2 periods</option>
            <option value={3}>3 periods</option>
          </select>
        </label>
        <Button variant="primary" onClick={find} disabled={busy || chosen.length === 0}>
          {busy && !picked ? <Loader2 size={16} className="animate-spin" /> : <Search size={16} />} Find free times
        </Button>
      </div>

      {slots && (
        <div className="mt-4 space-y-3 border-t border-border pt-4">
          {slots.length === 0 ? (
            <p className="text-sm text-muted">No common free time. Try 14 days, a shorter meeting or fewer teachers.</p>
          ) : Object.entries(byDate).map(([day, list]) => (
            <div key={day}>
              <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-muted">{day}</p>
              <div className="flex flex-wrap gap-2">
                {list.map((s) => {
                  const on = picked?.date === s.date && picked.start === s.start;
                  return (
                    <button key={`${s.date}-${s.start}`} onClick={() => setPicked(s)} aria-pressed={on}
                      className={clsx("rounded-lg border px-3 py-1.5 text-sm transition",
                        on ? "border-accent bg-accent-soft text-accent-text" : "border-border hover:bg-surface-2")}>
                      {s.start}-{s.end}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}

      {picked && (
        <div className="mt-4 flex flex-wrap items-end gap-2 border-t border-border pt-4">
          <label className="min-w-[12rem] flex-1 text-xs text-muted">Title
            <input aria-label="Title" className={`${input} mt-1 block w-full`} value={title} maxLength={200} placeholder="e.g. Syllabus review"
              onChange={(e) => setTitle(e.target.value)} />
          </label>
          <label className="min-w-[9rem] text-xs text-muted">Place (optional)
            <input aria-label="Place" className={`${input} mt-1 block w-full`} value={place} maxLength={120} placeholder="e.g. Board room"
              onChange={(e) => setPlace(e.target.value)} />
          </label>
          <Button variant="primary" onClick={book} disabled={busy}>
            {busy && <Loader2 size={16} className="animate-spin" />} Book {picked.label} {picked.start}
          </Button>
        </div>
      )}
      {done && <p className="mt-3 flex items-center gap-1.5 text-sm text-ok"><CheckCircle2 size={15} aria-hidden /> {done}</p>}
      <FormError message={error} />
    </Card>
  );
}
