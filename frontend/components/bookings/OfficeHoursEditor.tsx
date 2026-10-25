"use client";

import { Clock, Loader2, MapPin, Plus, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { FormError } from "@/components/Field";
import { Button, Card } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useTimetable } from "@/lib/timetable-context";
import type { OfficeHour } from "@/lib/types";

const input = "rounded-lg border border-border-strong bg-surface px-2.5 py-1.5 text-sm";

/** A teacher's weekly office hours. Only periods without one of their classes are offered. */
export function OfficeHoursEditor({ hours, onChange }: { hours: OfficeHour[]; onChange: (h: OfficeHour[]) => void }) {
  const { college, data } = useTimetable();
  const { member } = useAuth();
  const [day, setDay] = useState(college?.days[0] ?? "Mon");
  const [slot, setSlot] = useState("");
  const [seats, setSeats] = useState(3);
  const [place, setPlace] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // The teacher's shift periods that are free on the chosen day (no own class, no office hour already).
  const free = useMemo(() => {
    if (!college) return [];
    const me = college.teachers.find((t) => t.id === member?.teacher_id);
    const shifts = college.shifts.filter((s) => !me || me.shift_ids.includes(s.id));
    const seen = new Set<string>();
    const periods = shifts.flatMap((s) => s.periods).filter((p) => {
      const k = `${p.start}-${p.end}`;
      if (seen.has(k)) return false;
      seen.add(k);
      return true;
    }).sort((a, b) => a.start.localeCompare(b.start));
    const overlaps = (a0: string, a1: string, b0: string, b1: string) => a0 < b1 && b0 < a1;
    const classes = (data?.timetable.sessions ?? []).filter((s) => s.day === day && s.teacher_id === member?.teacher_id);
    return periods.filter((p) =>
      !classes.some((s) => overlaps(s.start, s.end, p.start, p.end))
      && !hours.some((h) => h.day === day && overlaps(h.start, h.end, p.start, p.end))
      && !(me?.blocked ?? []).some((b) => b.day === day && overlaps(b.start, b.end, p.start, p.end)));
  }, [college, data, member, day, hours]);

  const chosen = free.find((p) => `${p.start}-${p.end}` === slot) ?? free[0];

  const add = async () => {
    if (!chosen) return;
    setBusy(true);
    setError(null);
    try {
      onChange(await api.addOfficeHour({ day, start: chosen.start, end: chosen.end, seats, place }));
      setSlot("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't save");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: string) => {
    setError(null);
    try {
      onChange(await api.removeOfficeHour(id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't remove");
    }
  };

  return (
    <Card className="p-5">
      <h2 className="font-semibold">My office hours</h2>
      <p className="mt-1 text-sm text-muted">
        Weekly times when students can book a doubt slot with you. Only your free periods are offered; a class
        moved onto an office hour for one day closes that day&rsquo;s slot automatically.
      </p>
      <ul className="mt-4 space-y-2">
        {hours.length === 0 && <li className="text-sm text-muted">No office hours yet. Add one below.</li>}
        {hours.map((h) => (
          <li key={h.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border border-border px-3 py-2 text-sm">
            <span className="flex items-center gap-1.5 font-medium"><Clock size={14} className="text-muted" aria-hidden /> {h.day} {h.start}-{h.end}</span>
            <span className="text-muted">{h.seats} seat{h.seats === 1 ? "" : "s"}</span>
            {h.place && <span className="flex items-center gap-1 text-muted"><MapPin size={13} aria-hidden /> {h.place}</span>}
            <button onClick={() => remove(h.id)} aria-label={`Remove ${h.day} ${h.start} office hour`}
              className="ml-auto rounded p-1.5 text-muted hover:bg-surface-2 hover:text-danger"><Trash2 size={14} /></button>
          </li>
        ))}
      </ul>
      <div className="mt-4 flex flex-wrap items-end gap-2 border-t border-border pt-4">
        <label className="text-xs text-muted">Day
          <select aria-label="Day" className={`${input} mt-1 block`} value={day} onChange={(e) => { setDay(e.target.value); setSlot(""); }}>
            {college?.days.map((d) => <option key={d}>{d}</option>)}
          </select>
        </label>
        <label className="text-xs text-muted">Free period
          <select aria-label="Free period" className={`${input} mt-1 block`} value={chosen ? `${chosen.start}-${chosen.end}` : ""}
            onChange={(e) => setSlot(e.target.value)} disabled={free.length === 0}>
            {free.length === 0 && <option value="">No free period</option>}
            {free.map((p) => <option key={p.start} value={`${p.start}-${p.end}`}>{p.start}-{p.end}</option>)}
          </select>
        </label>
        <label className="text-xs text-muted">Seats
          <input aria-label="Seats" type="number" min={1} max={30} className={`${input} mt-1 block w-20`} value={seats}
            onChange={(e) => setSeats(Math.max(1, Math.min(30, Number(e.target.value) || 1)))} />
        </label>
        <label className="min-w-[10rem] flex-1 text-xs text-muted">Place (optional)
          <input aria-label="Place" className={`${input} mt-1 block w-full`} value={place} maxLength={120} placeholder="e.g. Staff room 2"
            onChange={(e) => setPlace(e.target.value)} />
        </label>
        <Button variant="primary" onClick={add} disabled={busy || !chosen}>
          {busy ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />} Add
        </Button>
      </div>
      <FormError message={error} />
    </Card>
  );
}
