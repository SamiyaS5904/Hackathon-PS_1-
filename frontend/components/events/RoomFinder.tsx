"use client";

import clsx from "clsx";
import { CheckCircle2, DoorOpen, Loader2, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { FormError } from "@/components/Field";
import { Button, Card, Skeleton } from "@/components/ui";
import { extraApi } from "@/lib/api";
import type { College, FreeVenue } from "@/lib/types";

const input = "rounded-lg border border-border-strong bg-surface px-2.5 py-1.5 text-sm";

const tomorrow = () => {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

/** Pick a date and a time (in periods), see the rooms that are free then, book one for an event. */
export function RoomFinder({ college, onBooked }: { college: College; onBooked: () => void }) {
  // Period boundaries of every shift, so the times line up with the bell.
  const starts = useMemo(() => [...new Set(college.shifts.flatMap((s) => s.periods.map((p) => p.start)))].sort(), [college]);
  const ends = useMemo(() => [...new Set(college.shifts.flatMap((s) => s.periods.map((p) => p.end)))].sort(), [college]);
  const [date, setDate] = useState(tomorrow);
  const [start, setStart] = useState(starts[0] ?? "09:00");
  const [end, setEnd] = useState(ends[0] ?? "10:00");
  const [seats, setSeats] = useState("");
  const [rooms, setRooms] = useState<FreeVenue[] | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [picked, setPicked] = useState<FreeVenue | null>(null);
  const [title, setTitle] = useState("");
  const [club, setClub] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  useEffect(() => {
    if (end <= start) setEnd(ends.find((e) => e > start) ?? end);
  }, [start, end, ends]);

  useEffect(() => {
    if (!date || end <= start) return;
    let live = true;
    setRooms(null);
    setPicked(null);
    setProblem(null);
    extraApi.freeVenues(date, start, end, Number(seats) || 0)
      .then((r) => live && setRooms(r))
      .catch((e) => { if (live) { setRooms([]); setProblem(e instanceof Error ? e.message : "Couldn't look for rooms"); } });
    return () => { live = false; };
  }, [date, start, end, seats]);

  const book = async () => {
    if (!picked) return;
    setBusy(true);
    setError(null);
    try {
      const r = await extraApi.bookVenue({ venue_id: picked.venue_id, date, start, end, title, club });
      setDone(r.message);
      setTitle("");
      setClub("");
      setRooms((cur) => cur?.filter((x) => x.venue_id !== picked.venue_id) ?? cur);
      setPicked(null);
      onBooked();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't book the room");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="p-5">
      <h2 className="font-semibold">Book a room for an event</h2>
      <p className="mt-1 text-sm text-muted">
        Only rooms with no class, no one-day change and no other event then are shown, so no class is ever moved.
        The room&rsquo;s Department Coordinator approves (the College Admin for shared rooms).
      </p>
      <div className="mt-4 flex flex-wrap items-end gap-2">
        <label className="text-xs text-muted">Date
          <input type="date" aria-label="Date" className={`${input} mt-1 block`} value={date}
            onChange={(e) => { setDate(e.target.value); setDone(null); }} />
        </label>
        <label className="text-xs text-muted">From
          <select aria-label="From" className={`${input} mt-1 block`} value={start} onChange={(e) => { setStart(e.target.value); setDone(null); }}>
            {starts.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </label>
        <label className="text-xs text-muted">To
          <select aria-label="To" className={`${input} mt-1 block`} value={end} onChange={(e) => { setEnd(e.target.value); setDone(null); }}>
            {ends.filter((t) => t > start).map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </label>
        <label className="text-xs text-muted">Seats needed
          <input type="number" min={0} aria-label="Seats needed" placeholder="any" className={`${input} mt-1 block w-24`}
            value={seats} onChange={(e) => setSeats(e.target.value)} />
        </label>
      </div>

      <div className="mt-4">
        {rooms === null ? <Skeleton className="h-20 w-full" /> : problem ? (
          <p className="rounded-lg bg-surface-2 px-3 py-2 text-sm text-muted">{problem}</p>
        ) : rooms.length === 0 ? (
          <p className="rounded-lg bg-surface-2 px-3 py-2 text-sm text-muted">No room is free for the whole time. Try a shorter or another time.</p>
        ) : (
          <>
            <p className="mb-2 flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-muted">
              <Search size={12} aria-hidden /> {rooms.length} free room{rooms.length === 1 ? "" : "s"}, smallest first
            </p>
            <div className="grid gap-2 sm:grid-cols-2">
              {rooms.map((r) => (
                <button key={r.venue_id} onClick={() => { setPicked(r); setDone(null); }} aria-pressed={picked?.venue_id === r.venue_id}
                  className={clsx("flex items-start gap-2 rounded-lg border px-3 py-2 text-left text-sm transition",
                    picked?.venue_id === r.venue_id ? "border-accent bg-accent-soft" : "border-border hover:bg-surface-2")}>
                  <DoorOpen size={16} className="mt-0.5 shrink-0 text-accent-text" aria-hidden />
                  <span className="min-w-0">
                    <span className="block font-medium">{r.name}</span>
                    <span className="text-xs text-muted">{r.capacity} seats · {r.type} · {r.owner} · approved by {r.approver}</span>
                  </span>
                </button>
              ))}
            </div>
          </>
        )}
      </div>

      {picked && (
        <div className="mt-4 flex flex-wrap items-end gap-2 border-t border-border pt-4">
          <label className="min-w-[12rem] flex-1 text-xs text-muted">Event (reason)
            <input aria-label="Event" className={`${input} mt-1 block w-full`} value={title} maxLength={120}
              placeholder="e.g. Coding contest, guest talk" onChange={(e) => setTitle(e.target.value)} />
          </label>
          <label className="min-w-[10rem] flex-1 text-xs text-muted">Club or group (optional)
            <input aria-label="Club" className={`${input} mt-1 block w-full`} value={club} maxLength={80}
              placeholder="e.g. Coding Club" onChange={(e) => setClub(e.target.value)} />
          </label>
          <Button variant="primary" onClick={book} disabled={busy || !title.trim()}>
            {busy && <Loader2 size={16} className="animate-spin" />} Book {picked.name}
          </Button>
        </div>
      )}
      {done && <p className="mt-3 flex items-center gap-1.5 text-sm text-ok"><CheckCircle2 size={15} aria-hidden /> {done}</p>}
      <FormError message={error} />
    </Card>
  );
}
