"use client";

import { Plus, Trash2 } from "lucide-react";
import type { Period, ShiftFull } from "@/lib/types";

/** How an admin describes a shift; the period list is built from it. */
export interface ShiftPlan {
  id: string;
  name: string;
  start: string;
  minutes: number; // lecture length
  count: number; // periods
  breaks: { after: number; minutes: number; label: string }[];
  lunch: boolean;
  lunchFrom: string;
  lunchTo: string;
}

const toMin = (t: string) => {
  const [h, m] = t.split(":").map(Number);
  return h * 60 + m;
};
const toTime = (m: number) => `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;

export function buildPeriods(p: ShiftPlan): Period[] {
  const out: Period[] = [];
  let t = toMin(p.start || "09:00");
  for (let i = 1; i <= p.count; i++) {
    out.push({ start: toTime(t), end: toTime(t + p.minutes) });
    t += p.minutes;
    for (const b of p.breaks) if (b.after === i) t += b.minutes;
  }
  return out;
}

export function planToShift(p: ShiftPlan): ShiftFull {
  return {
    id: p.id, name: p.name, periods: buildPeriods(p), year_breaks: [],
    lunch: p.lunch ? { window_start: p.lunchFrom, window_end: p.lunchTo } : null,
  };
}

/** Read an existing shift back into a plan (gaps between periods become breaks). */
export function shiftToPlan(s: ShiftFull): ShiftPlan {
  const ps = s.periods;
  const minutes = ps.length ? toMin(ps[0].end) - toMin(ps[0].start) : 50;
  const breaks = ps.slice(1).flatMap((p, i) => {
    const gap = toMin(p.start) - toMin(ps[i].end);
    return gap > 0 ? [{ after: i + 1, minutes: gap, label: "Break" }] : [];
  });
  return {
    id: s.id, name: s.name, start: ps[0]?.start ?? "09:00", minutes, count: ps.length || 7, breaks,
    lunch: !!s.lunch, lunchFrom: s.lunch?.window_start ?? "12:30", lunchTo: s.lunch?.window_end ?? "14:00",
  };
}

const input = "rounded-lg border border-border-strong bg-surface px-2.5 py-1.5 text-sm";

/** ``single``: the college has one timing for everyone, so no shift name and no shift wording. */
export function ShiftEditor({ plan, single = false, onChange }: {
  plan: ShiftPlan; single?: boolean; onChange: (p: ShiftPlan) => void;
}) {
  const set = (patch: Partial<ShiftPlan>) => onChange({ ...plan, ...patch });
  const periods = buildPeriods(plan);
  return (
    <div className="rounded-xl border border-border p-4">
      <div className={`grid gap-3 ${single ? "sm:grid-cols-3" : "sm:grid-cols-4"}`}>
        {!single && (
          <label className="text-sm">
            <span className="mb-1 block font-medium">Shift name</span>
            <input className={`${input} w-full`} value={plan.name} onChange={(e) => set({ name: e.target.value })} />
          </label>
        )}
        <label className="text-sm">
          <span className="mb-1 block font-medium">First period starts</span>
          <input type="time" className={`${input} w-full`} value={plan.start} onChange={(e) => set({ start: e.target.value })} />
        </label>
        <label className="text-sm">
          <span className="mb-1 block font-medium">Lecture length (min)</span>
          <input type="number" min={20} max={120} className={`${input} w-full`} value={plan.minutes}
            onChange={(e) => set({ minutes: Math.max(1, Number(e.target.value) || 0) })} />
        </label>
        <label className="text-sm">
          <span className="mb-1 block font-medium">Periods a day</span>
          <input type="number" min={1} max={14} className={`${input} w-full`} value={plan.count}
            onChange={(e) => set({ count: Math.min(14, Math.max(1, Number(e.target.value) || 1)) })} />
        </label>
      </div>

      <div className="mt-4">
        <p className="text-sm font-medium">Fixed breaks <span className="font-normal text-muted">({single ? "same for everyone" : "same for everyone in this shift"})</span></p>
        <div className="mt-2 space-y-2">
          {plan.breaks.map((b, i) => (
            <div key={i} className="flex flex-wrap items-center gap-2 text-sm">
              <span className="text-muted">After period</span>
              <input type="number" min={1} max={plan.count - 1} className={`${input} w-16`} value={b.after}
                onChange={(e) => set({ breaks: plan.breaks.map((x, j) => (j === i ? { ...x, after: Number(e.target.value) } : x)) })} />
              <span className="text-muted">for</span>
              <input type="number" min={5} max={120} className={`${input} w-20`} value={b.minutes}
                onChange={(e) => set({ breaks: plan.breaks.map((x, j) => (j === i ? { ...x, minutes: Number(e.target.value) } : x)) })} />
              <span className="text-muted">min</span>
              <button aria-label="Remove break" onClick={() => set({ breaks: plan.breaks.filter((_, j) => j !== i) })}
                className="rounded p-1 text-muted hover:bg-surface-2"><Trash2 size={14} /></button>
            </div>
          ))}
          <button onClick={() => set({ breaks: [...plan.breaks, { after: Math.min(3, plan.count - 1), minutes: 20, label: "Break" }] })}
            className="inline-flex items-center gap-1 text-sm text-accent-text hover:underline"><Plus size={14} /> Add a break</button>
        </div>
      </div>

      <div className="mt-4 rounded-lg bg-surface-2 p-3">
        <label className="flex items-center gap-2 text-sm font-medium">
          <input type="checkbox" checked={plan.lunch} onChange={(e) => set({ lunch: e.target.checked })} />
          Lunch inside the mess timings
        </label>
        <p className="mt-1 text-xs text-muted">
          The timetable picks each year&apos;s lunch period inside this window (same time every day), whichever gives the
          best timetable and room use.
        </p>
        {plan.lunch && (
          <div className="mt-2 flex items-center gap-2 text-sm">
            <span className="text-muted">Mess open</span>
            <input type="time" className={input} value={plan.lunchFrom} onChange={(e) => set({ lunchFrom: e.target.value })} />
            <span className="text-muted">to</span>
            <input type="time" className={input} value={plan.lunchTo} onChange={(e) => set({ lunchTo: e.target.value })} />
          </div>
        )}
      </div>

      <div className="mt-4">
        <p className="text-xs font-medium uppercase tracking-wide text-muted">Preview</p>
        <div className="mt-1 flex flex-wrap gap-1.5">
          {periods.map((p, i) => (
            <span key={i} className="rounded-md border border-border bg-surface px-2 py-1 font-mono text-xs">
              P{i + 1} {p.start}–{p.end}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
