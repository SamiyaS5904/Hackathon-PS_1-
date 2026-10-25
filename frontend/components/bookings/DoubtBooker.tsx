"use client";

import clsx from "clsx";
import { CheckCircle2, Loader2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { FormError } from "@/components/Field";
import { Button, Card, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import type { BookingSlot, TeacherHours } from "@/lib/types";

const input = "rounded-lg border border-border-strong bg-surface px-2.5 py-1.5 text-sm";

/** Student: pick a teacher, pick an open slot (next two weeks), add a topic, book. */
export function DoubtBooker({ onBooked, teacherId: initialTeacher }: { onBooked: () => void; teacherId?: string }) {
  const [teachers, setTeachers] = useState<TeacherHours[] | null>(null);
  const [teacherId, setTeacherId] = useState(initialTeacher ?? "");
  const [slots, setSlots] = useState<BookingSlot[] | null>(null);
  const [picked, setPicked] = useState<BookingSlot | null>(null);
  const [topic, setTopic] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  useEffect(() => {
    api.bookingTeachers().then((t) => {
      setTeachers(t);
      setTeacherId((cur) => cur || t[0]?.teacher_id || "");
    }).catch((e) => setError(e instanceof Error ? e.message : "Couldn't load teachers"));
  }, []);
  useEffect(() => {
    if (initialTeacher) setTeacherId(initialTeacher);
  }, [initialTeacher]);

  const loadSlots = useCallback(() => {
    if (!teacherId) return;
    setSlots(null);
    setPicked(null);
    api.doubtSlots(teacherId).then(setSlots).catch((e) => setError(e instanceof Error ? e.message : "Couldn't load slots"));
  }, [teacherId]);
  useEffect(loadSlots, [loadSlots]);

  const book = async () => {
    if (!picked?.office_hour_id) return;
    setBusy(true);
    setError(null);
    try {
      const r = await api.bookDoubt({ office_hour_id: picked.office_hour_id, date: picked.date, topic });
      setDone(r.message);
      setTopic("");
      loadSlots();
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
      <h2 className="font-semibold">Book a doubt slot</h2>
      <p className="mt-1 text-sm text-muted">
        Times in your teachers&rsquo; office hours over the next two weeks when you have no class.
      </p>
      {teachers === null ? (
        error ? <FormError message={error} /> : <Skeleton className="mt-4 h-24 w-full" />
      ) : teachers.length === 0 ? (
        <p className="mt-4 text-sm text-muted">No teacher has set office hours yet. Ask your teacher to add them under Bookings.</p>
      ) : (
        <>
          <label className="mt-4 block text-xs text-muted">Teacher
            <select aria-label="Teacher" className={`${input} mt-1 block w-full sm:w-auto`} value={teacherId}
              onChange={(e) => { setTeacherId(e.target.value); setDone(null); }}>
              {teachers.map((t) => (
                <option key={t.teacher_id} value={t.teacher_id}>
                  {t.name}{t.department ? ` (${t.department})` : ""}{t.teaches_you ? " · teaches you" : ""}
                </option>
              ))}
            </select>
          </label>
          <div className="mt-4 space-y-3">
            {slots === null ? <Skeleton className="h-16 w-full" /> : slots.length === 0 ? (
              <p className="text-sm text-muted">No open slot in the next two weeks (full, or you have a class then).</p>
            ) : Object.entries(byDate).map(([day, list]) => (
              <div key={day}>
                <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-muted">{day}</p>
                <div className="flex flex-wrap gap-2">
                  {list.map((s) => {
                    const on = picked?.date === s.date && picked.office_hour_id === s.office_hour_id;
                    return (
                      <button key={`${s.date}-${s.office_hour_id}`} onClick={() => { setPicked(s); setDone(null); }}
                        aria-pressed={on}
                        className={clsx("rounded-lg border px-3 py-1.5 text-sm transition",
                          on ? "border-accent bg-accent-soft text-accent-text" : "border-border hover:bg-surface-2")}>
                        {s.start}-{s.end}
                        <span className="ml-1.5 text-xs text-muted">{s.seats_left} left{s.place ? ` · ${s.place}` : ""}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
          {picked && (
            <div className="mt-4 flex flex-wrap items-end gap-2 border-t border-border pt-4">
              <label className="min-w-[12rem] flex-1 text-xs text-muted">What do you want to ask? (optional)
                <input aria-label="Topic" className={`${input} mt-1 block w-full`} value={topic} maxLength={200}
                  placeholder="e.g. Recursion questions from Unit 2" onChange={(e) => setTopic(e.target.value)} />
              </label>
              <Button variant="primary" onClick={book} disabled={busy}>
                {busy && <Loader2 size={16} className="animate-spin" />} Book {picked.label} {picked.start}
              </Button>
            </div>
          )}
          {done && <p className="mt-3 flex items-center gap-1.5 text-sm text-ok"><CheckCircle2 size={15} aria-hidden /> {done}</p>}
          <FormError message={error} />
        </>
      )}
    </Card>
  );
}
